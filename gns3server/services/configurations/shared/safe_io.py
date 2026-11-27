"""Safe bounded file I/O, atomic private state and cancellation-safe disk replacement."""

import asyncio
import json
import os
import shutil
import stat
import tempfile
from pathlib import Path

from .errors import ConfigurationError

MAX_JSON_BYTES = 34 * 1024 * 1024  # The largest saved state file (the sets store is the biggest).


PROJECT_FILES = "project-files"


def linked(path) -> bool:
    """True when ``path`` goes through a symbolic link that must not be followed.

    Links on the way into a project (the projects folder, ``project-files`` itself) are the administrator's
    layout. Below ``project-files`` the files can come from an imported project or from a guest, so none of
    them may be a link. Outside a project the file and its folder are checked.
    """
    path = Path(path).absolute()
    parts = path.parts
    if PROJECT_FILES in parts:
        first = parts.index(PROJECT_FILES) + 1
        return any(Path(*parts[: end + 1]).is_symlink() for end in range(first, len(parts)))
    return path.is_symlink() or path.parent.is_symlink()


def stable_read(root: str, path: Path, limit: int) -> bytes:
    """Bounded regular-file snapshot; reject static links and concurrent writes."""
    given = Path(root).absolute()
    root_path = given.resolve(strict=True)
    path = Path(path).absolute()
    if not path.is_relative_to(root_path):
        # A root reached through a link: the same file, named below the resolved root.
        if linked(path) or not path.is_relative_to(given):
            raise ConfigurationError("unsafe_configuration_path")
        path = root_path / path.relative_to(given)
    for component in (path, *path.parents):
        if component == root_path:
            break
        if component.is_symlink():
            raise ConfigurationError("unsafe_configuration_path")
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
        with os.fdopen(descriptor, "rb") as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
                raise ConfigurationError("unsafe_configuration_file")
            if before.st_size > limit:
                raise ConfigurationError("configuration_too_large")
            data = stream.read(limit + 1)
            after = os.fstat(stream.fileno())
        current = path.stat(follow_symlinks=False)

        def identity(info):
            return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)

        if identity(before) != identity(after) or identity(after) != identity(current):
            raise ConfigurationError("configuration_changed_during_capture")
        if len(data) > limit:
            raise ConfigurationError("configuration_too_large")
        return data
    except FileNotFoundError:
        raise ConfigurationError("configuration_not_found") from None
    except OSError:
        raise ConfigurationError("configuration_read_failed") from None


def atomic_write(root, filename, content):
    """Replace a fixed configuration file without following file/directory links."""
    from gns3server.schemas.configurations import MAX_FILE_BYTES, ExportFile

    filename = ExportFile.safe_filename(filename)
    root = Path(root).resolve(strict=True)
    target = root / filename
    if target.exists() or target.is_symlink():
        stable_read(str(root), target, MAX_FILE_BYTES)
    payload = content.encode("utf-8")
    if len(payload) > MAX_FILE_BYTES:
        raise ConfigurationError("configuration_too_large")
    parts = target.relative_to(root).parts
    # os.replace shares rename's implementation, and only os.rename is listed as taking directory descriptors.
    if os.rename in os.supports_dir_fd and os.mkdir in os.supports_dir_fd and hasattr(os, "O_DIRECTORY"):
        _atomic_write_at(root, parts, payload)
        return
    directory = root
    for part in parts[:-1]:
        directory /= part
        if directory.is_symlink() or (directory.exists() and not directory.is_dir()):
            raise ConfigurationError("unsafe_configuration_path")
        directory.mkdir(exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{target.name}-", dir=directory)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _atomic_write_at(root, parts, payload):
    """Directory-fd based replace: a directory swapped for a symlink mid-way is refused.

    Every component is opened with O_NOFOLLOW relative to its parent's descriptor
    and the temporary file is created and renamed through the final directory's
    descriptor, so no path is re-resolved between the checks and the writes.
    """
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    descriptors = [os.open(root, flags)]
    try:
        for part in parts[:-1]:
            try:
                os.mkdir(part, dir_fd=descriptors[-1])
            except FileExistsError:
                pass
            try:
                descriptors.append(os.open(part, flags, dir_fd=descriptors[-1]))
            except OSError:
                # Symlink (ELOOP), regular file (ENOTDIR) or anything else unexpected.
                raise ConfigurationError("unsafe_configuration_path") from None
        directory = descriptors[-1]
        name = parts[-1]
        temporary = f".{name}-{os.urandom(8).hex()}"
        handle = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
        try:
            with os.fdopen(handle, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, name, src_dir_fd=directory, dst_dir_fd=directory)
        finally:
            try:
                os.unlink(temporary, dir_fd=directory)
            except FileNotFoundError:
                pass
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def validate_owned_paths(root, paths):
    # Validate every candidate before erasing anything. Never follow links or
    # accept directories/devices in place of generated files.
    for path in paths:
        if not path.is_relative_to(root) or ".." in path.relative_to(root).parts:
            raise ConfigurationError("unsafe_configuration_path")
        for component in (path, *path.parents):
            if component == root:
                break
            if component.is_symlink():
                raise ConfigurationError("unsafe_configuration_path")
        if path.exists() and not stat.S_ISREG(path.stat().st_mode):
            raise ConfigurationError("unsafe_configuration_file")


def safe_directory(path):
    path = Path(path).absolute()
    if linked(path):
        raise ConfigurationError("unsafe_configuration_path")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


def read_json(path, default=None):
    path = Path(path).absolute()
    if linked(path):
        raise ConfigurationError("unsafe_configuration_path")
    if not path.exists():
        return default
    try:
        return json.loads(stable_read(str(path.parent), path, MAX_JSON_BYTES))
    except (ValueError, UnicodeError):
        raise ConfigurationError("invalid_startup_configurations") from None


def atomic_bytes(path, payload):
    if len(payload) > MAX_JSON_BYTES:
        raise ConfigurationError("configuration_too_large")
    path = Path(path).absolute()
    safe_directory(path.parent)
    if path.exists() or path.is_symlink():
        stable_read(str(path.parent), path, MAX_JSON_BYTES)
    descriptor, temporary = tempfile.mkstemp(prefix=".startup-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        # Persist the rename as well as the bytes before crossing a reset boundary.
        fsync_directory(path.parent)
    finally:
        Path(temporary).unlink(missing_ok=True)


def write_json(path, value):
    atomic_bytes(path, json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def fsync_directory(path):
    if os.name == "posix":
        directory = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory)
        finally:
            os.close(directory)


async def run_file_io(function, *args):
    # The caller must retain ownership of files and locks until the thread exits.
    task = asyncio.create_task(asyncio.to_thread(function, *args))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                continue
        task.result()
        raise


async def copy_private_disk(source, destination):
    """Copy large overlays atomically with private permissions and no links."""
    safe_directory(destination.parent)
    validate_owned_paths(destination.parent, [destination])

    def copy():
        descriptor, temporary = tempfile.mkstemp(prefix=".disk-copy-", dir=destination.parent)
        try:
            with os.fdopen(descriptor, "wb") as target:
                source_fd = os.open(source, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
                with os.fdopen(source_fd, "rb") as origin:
                    before = os.fstat(origin.fileno())
                    if not stat.S_ISREG(before.st_mode):
                        raise ConfigurationError("unsafe_configuration_file")
                    shutil.copyfileobj(origin, target, length=1024 * 1024)
                    after = os.fstat(origin.fileno())
                    if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                        after.st_size,
                        after.st_mtime_ns,
                        after.st_ctime_ns,
                    ):
                        raise ConfigurationError("configuration_image_changed")
                    target.flush()
                    os.fsync(target.fileno())
            os.replace(temporary, destination)
        finally:
            Path(temporary).unlink(missing_ok=True)

    await run_file_io(copy)
