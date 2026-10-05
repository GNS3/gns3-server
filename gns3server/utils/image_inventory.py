"""Filesystem primitives shared by image writers and inventory reconciliation."""

import asyncio
import hashlib
import os
import re
import stat
import uuid

from gns3server.config import Config


def normalized_path(path):
    return os.path.normcase(os.path.abspath(os.path.expanduser(path)))


def contained_path(path, root):
    try:
        return os.path.commonpath((normalized_path(path), normalized_path(root))) == normalized_path(root)
    except ValueError:
        return False


def fingerprint(path):
    info = os.stat(path, follow_symlinks=True)
    if not stat.S_ISREG(info.st_mode):
        raise OSError(f"Not a regular image file: {path}")
    return stat_fingerprint(info)


def stat_fingerprint(info):
    # Store as text: inode/device numbers need not fit a signed SQL BIGINT.
    return ":".join(
        str(value) for value in (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
    )


class ImageLockBusy(Exception):
    pass


class ImageLock:
    """Advisory lock shared by controller processes using the same config directory.

    Lock files are deliberately retained: unlinking them permits two processes to
    lock different inodes for the same name. OS locks are released on process exit.
    """

    def __init__(self, key, wait=True):
        self.key = key
        self.wait = wait
        self._file = None

    async def __aenter__(self):
        directory = os.path.join(Config.instance().config_dir, ".image-locks")
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, hashlib.sha256(self.key.encode()).hexdigest() + ".lock")
        self._file = open(path, "a+b")
        if os.name == "nt" and os.fstat(self._file.fileno()).st_size == 0:
            self._file.write(b"\0")
            self._file.flush()
        try:
            while True:
                try:
                    if os.name == "nt":
                        import msvcrt

                        self._file.seek(0)
                        msvcrt.locking(self._file.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl

                        fcntl.flock(self._file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    return self
                except (BlockingIOError, PermissionError):
                    if not self.wait:
                        raise ImageLockBusy(self.key)
                    await asyncio.sleep(0.05)
        except BaseException:
            self._file.close()
            self._file = None
            raise

    async def __aexit__(self, *args):
        if self._file is not None:
            self._file.close()
            self._file = None


def image_lock(path):
    return ImageLock("image:" + normalized_path(os.path.realpath(path)))


def publish_image(temporary, destination):
    """Atomically publish a complete file without replacing an existing image.

    Both paths must be on the same filesystem. Hard linking provides the atomic
    no-overwrite operation that os.replace()/shutil.move() cannot provide.
    """
    os.link(temporary, destination)
    os.unlink(temporary)


def validate_image_subdirectory(value):
    """A portable relative folder below the server-selected image type root."""
    if not value:
        return []
    parts = value.split("/")
    if len(value) > 512 or len(parts) > 8:
        raise ValueError("Image subfolder is too long or has more than eight levels")
    for part in parts:
        if (
            not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 ._-]{0,63}", part)
            or part.endswith((".", " ", ".tmp", ".md5sum"))
            or part.lower() in ("lib", "lib64")
            or re.fullmatch(r"(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?", part)
        ):
            raise ValueError(
                "Use relative subfolders with letters, numbers, spaces, dots, hyphens or underscores; "
                "hidden, reserved and traversal names are not allowed"
            )
    return parts


class ImageUploadDirectory:
    """Keep upload operations anchored to the authorized directory.

    POSIX operations use directory descriptors and never follow descendant
    symlinks. The portable fallback rejects symlinks/junctions and rechecks the
    directory before each operation. The configured root is administrator-owned.
    """

    def __init__(self, root, path):
        self.root = os.path.realpath(os.path.expanduser(root))
        self.path = os.path.abspath(path)
        if contained_path(self.path, normalized_path(root)):
            self.path = os.path.join(self.root, os.path.relpath(self.path, normalized_path(root)))
        self.fd = None
        self.identity = None
        self.anchored = (
            all(operation in os.supports_dir_fd for operation in (os.open, os.mkdir, os.link, os.unlink))
            and hasattr(os, "O_NOFOLLOW")
            and hasattr(os, "O_DIRECTORY")
        )

    def __enter__(self):
        if not contained_path(self.path, self.root):
            raise OSError("Image destination is outside the configured image directory")
        os.makedirs(self.root, exist_ok=True)
        parts = os.path.relpath(self.path, self.root).split(os.sep)
        if parts == ["."]:
            parts = []
        try:
            current = self.root
            if self.anchored:
                self.fd = os.open(current, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            for part in parts:
                if self.anchored:
                    try:
                        os.mkdir(part, mode=0o755, dir_fd=self.fd)
                    except FileExistsError:
                        pass
                    child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=self.fd)
                    os.close(self.fd)
                    self.fd = child
                else:
                    self._check_components(current)
                    current = os.path.join(current, part)
                    try:
                        os.mkdir(current, mode=0o755)
                    except FileExistsError:
                        pass
                    self._check_components(current)
            info = os.fstat(self.fd) if self.anchored else os.stat(self.path, follow_symlinks=False)
            self.identity = (info.st_dev, info.st_ino)
            self.verify()
            return self
        except BaseException:
            self.__exit__()
            raise

    def _check_components(self, path):
        current = self.root
        relative = os.path.relpath(path, self.root)
        for part in [] if relative == "." else relative.split(os.sep):
            current = os.path.join(current, part)
            info = os.lstat(current)
            reparse = getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
            if stat.S_ISLNK(info.st_mode) or reparse:
                raise OSError("Image upload folders must not be symlinks or junctions")

    def verify(self):
        self._check_components(self.path)
        info = os.stat(self.path, follow_symlinks=False)
        if (info.st_dev, info.st_ino) != self.identity or not contained_path(os.path.realpath(self.path), self.root):
            raise OSError("Image upload directory changed during upload")

    def temporary(self):
        self.verify()
        name = f".gns3-upload-{uuid.uuid4().hex}.tmp"
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        if self.anchored:
            fd = os.open(name, flags | os.O_NOFOLLOW, 0o700, dir_fd=self.fd)
        else:
            fd = os.open(os.path.join(self.path, name), flags, 0o700)
        return fd, name

    def publish(self, temporary, filename):
        self.verify()
        if self.anchored:
            os.link(temporary, filename, src_dir_fd=self.fd, dst_dir_fd=self.fd, follow_symlinks=False)
        else:
            os.link(os.path.join(self.path, temporary), os.path.join(self.path, filename))
        self.remove(temporary)
        self.verify()
        return fingerprint(os.path.join(self.path, filename))

    def remove(self, name):
        if self.anchored:
            os.unlink(name, dir_fd=self.fd)
        else:
            self.verify()
            os.unlink(os.path.join(self.path, name))

    def __exit__(self, *args):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None


def validate_image_upload_name(name):
    if (
        not name
        or len(name) > 255
        or name.startswith(".")
        or name.endswith((".", " ", ".tmp", ".md5sum"))
        or any(ord(c) < 32 or ord(c) == 127 or c in '/\\:%<>"|?*' for c in name)
        or re.fullmatch(r"(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?", name)
    ):
        raise ValueError(
            "Subfolder uploads require a plain, non-hidden image filename without path separators or reserved characters"
        )
