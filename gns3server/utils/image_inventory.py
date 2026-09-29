"""Filesystem primitives shared by image writers and inventory reconciliation."""

import asyncio
import hashlib
import os
import stat

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
