#
# Copyright (C) 2014 GNS3 Technologies Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import asyncio
import hashlib
import os
import stat

import aiofiles

from gns3server.utils.image_inventory import (
    ImageUploadDirectory,
    contained_path,
    fingerprint,
    image_lock,
    stat_fingerprint,
    validate_image_subdirectory,
    validate_image_upload_name,
)

try:
    import importlib_resources
except ImportError:
    from importlib import resources as importlib_resources

import logging
from io import DEFAULT_BUFFER_SIZE
from typing import AsyncGenerator, List

import gns3server.db.models as models
from gns3server.db.repositories.images import ImagesRepository
from gns3server.utils.asyncio import wait_run_in_executor

from ..config import Config
from . import force_unix_path

log = logging.getLogger(__name__)


async def list_images(image_type):
    """
    Scan directories for available image for a given type.

    :param image_type: image type (dynamips, qemu, iou)
    """
    files = set()
    images = []

    server_config = Config.instance().settings.Server
    general_images_directory = os.path.expanduser(server_config.images_path)

    # Subfolder of the general_images_directory specific to this VM type
    default_directory = default_images_directory(image_type)

    for directory in images_directories(image_type):
        # We limit recursion to path outside the default images directory
        # the reason is in the default directory manage file organization and
        # it should be flatten to keep things simple
        recurse = True
        if os.path.commonprefix([directory, general_images_directory]) == general_images_directory:
            recurse = False

        directory = os.path.normpath(directory)
        for root, _, filenames in _os_walk(directory, recurse=recurse):
            for filename in filenames:
                if filename in files:
                    log.debug("File {} has already been found, skipping...".format(filename))
                    continue
                if filename.endswith(".md5sum") or filename.startswith("."):
                    continue

                files.add(filename)

                # It the image is located in the standard directory the path is relative
                if os.path.commonprefix([root, default_directory]) != default_directory:
                    path = os.path.join(root, filename)
                else:
                    path = os.path.relpath(os.path.join(root, filename), default_directory)

                filesize = os.stat(os.path.join(root, filename)).st_size
                if filesize < 7:
                    log.debug(f"File {filename} is too small to be an image, skipping...")
                    continue

                try:
                    with open(os.path.join(root, filename), "rb") as f:
                        # read the first 7 bytes of the file.
                        elf_header_start = f.read(7)
                    if image_type == "dynamips" and elf_header_start != b"\x7fELF\x01\x02\x01":
                        # IOS images must start with the ELF magic number, be 32-bit, big endian and have an ELF version of 1
                        log.warning(f"IOS image {filename} does not start with a valid ELF magic number, skipping...")
                        continue
                    elif (
                        image_type == "iou"
                        and elf_header_start != b"\x7fELF\x02\x01\x01"
                        and elf_header_start != b"\x7fELF\x01\x01\x01"
                    ):
                        # IOU images must start with the ELF magic number, be 32-bit or 64-bit, little endian and have an ELF version of 1
                        log.warning(f"IOU image {filename} does not start with a valid ELF magic number, skipping...")
                        continue
                    elif image_type == "qemu" and elf_header_start[:4] == b"\x7fELF":
                        # QEMU images should not start with an ELF magic number
                        log.warning(f"QEMU image {filename} starts with an ELF magic number, skipping...")
                        continue

                    images.append(
                        {
                            "filename": filename,
                            "path": force_unix_path(path),
                            "md5sum": await wait_run_in_executor(md5sum, os.path.join(root, filename)),
                            "filesize": filesize,
                        }
                    )
                except OSError as e:
                    log.warning(f"Can't add image {path}: {e!s}")
    return images


def get_builtin_disks() -> List[str]:
    builtin_disks = []
    for entry in importlib_resources.files("gns3server").joinpath("disks").iterdir():
        if entry.is_file():
            builtin_disks.append(entry.name)
    return builtin_disks


def inspect_image_file(path, expected_image_type=None, allow_raw_image=False, stopped_event=None):
    """Read a stable regular file once, never trusting checksum sidecars."""
    before = fingerprint(path)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    with os.fdopen(os.open(path, flags), "rb") as f:
        info = os.fstat(f.fileno())
        if not stat.S_ISREG(info.st_mode) or stat_fingerprint(info) != before:
            raise ImageChangedError(f"Image changed while opening: {path}")
        header = f.read(7)
        if len(header) < 7:
            raise InvalidImageError(f"Image '{path}' is too small to be valid")
        image_type = check_valid_image_header(path, header, allow_raw_image)
        if expected_image_type and image_type != expected_image_type:
            raise InvalidImageError(f"Detected image type for '{path}' is {image_type}, expected {expected_image_type}")
        digest = hashlib.md5(header)
        while True:
            if stopped_event is not None and stopped_event.is_set():
                raise InterruptedError("Image inspection cancelled")
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
        if stat_fingerprint(os.fstat(f.fileno())) != before or fingerprint(path) != before:
            raise ImageChangedError(f"Image changed while reading: {path}")
    return dict(
        image_name=os.path.basename(path),
        image_type=image_type,
        image_size=info.st_size,
        path=path,
        checksum=digest.hexdigest(),
        checksum_algorithm="md5",
        file_fingerprint=before,
    )


async def read_image_info(path: str, expected_image_type: str | None = None, allow_raw_image=False) -> dict:
    try:
        return await asyncio.to_thread(inspect_image_file, path, expected_image_type, allow_raw_image)
    except OSError as e:
        raise InvalidImageError(f"Cannot read image '{path}': {e}") from e


async def discover_images(image_type: str, skip_image_paths: list | None = None) -> List[dict]:
    """
    Scan directories for available images
    """

    files = set()
    images = []

    for directory in images_directories(image_type, include_parent_directory=False):
        log.info(f"Discovering images in '{directory}'")
        for root, _, filenames in os.walk(os.path.normpath(directory)):
            for filename in filenames:
                if filename.endswith(".tmp") or filename.endswith(".md5sum") or filename.startswith("."):
                    continue
                path = os.path.join(root, filename)
                if not os.path.isfile(path) or (skip_image_paths and path in skip_image_paths) or path in files:
                    continue
                if "/lib/" in path or "/lib64/" in path:
                    # ignore custom IOU libraries
                    continue
                files.add(path)

                try:
                    images.append(await read_image_info(path, image_type))
                except InvalidImageError as e:
                    log.debug(str(e))
                    continue
    return images


def _os_walk(directory, recurse=True, **kwargs):
    """
    Work like os.walk but if recurse is False just list current directory
    """
    if recurse:
        for root, dirs, files in os.walk(directory, **kwargs):
            yield root, dirs, files
    else:
        files = []
        for filename in os.listdir(directory):
            if os.path.isfile(os.path.join(directory, filename)):
                files.append(filename)
        yield directory, [], files


def default_images_directory(image_type):
    """
    :returns: Return the default directory for an image type.
    """

    server_config = Config.instance().settings.Server
    img_dir = os.path.expanduser(server_config.images_path)
    if image_type == "qemu":
        return os.path.join(img_dir, "QEMU")
    elif image_type == "iou":
        return os.path.join(img_dir, "IOU")
    elif image_type == "dynamips" or image_type == "ios":
        return os.path.join(img_dir, "IOS")
    else:
        raise NotImplementedError("%s node type is not supported", image_type)


def images_directories(image_type, include_parent_directory=True):
    """
    Return all directories where we will look for images
    by priority

    :param image_type: Type of emulator
    """

    server_config = Config.instance().settings.Server
    paths = []

    type_img_directory = default_images_directory(image_type)
    try:
        os.makedirs(type_img_directory, exist_ok=True)
        paths.append(type_img_directory)
    except (OSError, PermissionError):
        pass
    for directory in server_config.additional_images_paths:
        paths.append(directory)
    if include_parent_directory:
        # Compatibility with old topologies we look in parent directory
        img_dir = os.path.expanduser(server_config.images_path)
        paths.append(img_dir)
    # Return only the existing paths
    return [force_unix_path(p) for p in paths if os.path.exists(p)]


def md5sum(path, working_dir=None, stopped_event=None, cache_to_md5file=True, use_cache=True):
    """
    Return the md5sum of an image and cache it on disk

    :param path: Path to the image
    :param workdir_dir: where to store .md5sum files
    :param stopped_event: In case you execute this function on thread and would like to have possibility
                          to cancel operation pass the `threading.Event`
    :returns: Digest of the image
    """

    if path is None or len(path) == 0 or not os.path.exists(path):
        return None

    if working_dir:
        md5sum_file = os.path.join(working_dir, os.path.basename(path) + ".md5sum")
    else:
        md5sum_file = path + ".md5sum"

    if use_cache and os.path.exists(md5sum_file):
        try:
            with open(md5sum_file) as f:
                md5 = f.read().strip()
                if len(md5) == 32:
                    return md5
        # Unicode error is when user rename an image to .md5sum ....
        except (OSError, UnicodeDecodeError):
            pass

    try:
        m = hashlib.md5()
        log.debug(f"Calculating MD5 sum of `{path}`")
        with open(path, "rb") as f:
            while True:
                if stopped_event is not None and stopped_event.is_set():
                    log.error(f"MD5 sum calculation of `{path}` has stopped due to cancellation")
                    return None
                buf = f.read(DEFAULT_BUFFER_SIZE)
                if not buf:
                    break
                m.update(buf)
        digest = m.hexdigest()
    except OSError as e:
        log.error("Can't create digest of %s: %s", path, str(e))
        return None

    if cache_to_md5file:
        try:
            with open(md5sum_file, "w+") as f:
                f.write(digest)
        except OSError as e:
            log.warning("Can't write digest of %s: %s", path, str(e))

    return digest


def remove_checksum(path):
    """
    Remove the checksum of an image from cache if exists
    """

    path = f"{path}.md5sum"
    if os.path.exists(path):
        os.remove(path)


class InvalidImageError(Exception):
    def __init__(self, message: str):
        super().__init__()
        self._message = message

    def __str__(self):
        return self._message


class ImageChangedError(InvalidImageError):
    """An observation must be retried because the file is still changing."""


def check_valid_image_header(path: str, data: bytes, allow_raw_image: bool = False) -> str:

    if data[:7] == b"\x7fELF\x01\x02\x01":
        # for IOS images: file must start with the ELF magic number, be 32-bit, big endian and have an ELF version of 1
        return "ios"
    elif data[:7] == b"\x7fELF\x01\x01\x01" or data[:7] == b"\x7fELF\x02\x01\x01":
        # for IOU images: file must start with the ELF magic number, be 32-bit or 64-bit, little endian and
        # have an ELF version of 1 (normal IOS images are big endian!)
        return "iou"
    elif data[:4] == b"QFI\xfb" or data[:4] == b"KDMV":
        # for Qemy images: file must be QCOW2 or VMDK
        return "qemu"
    else:
        if allow_raw_image is True:
            return "qemu"
        raise InvalidImageError(f"{path}: could not detect image type, please make sure it is a valid image")


async def write_image(
    image_filename: str,
    image_path: str,
    stream: AsyncGenerator[bytes, None],
    images_repo: ImagesRepository,
    check_image_header=True,
    allow_raw_image=False,
    subdirectory=None,
) -> models.Image:

    image_dir, image_name = os.path.split(image_filename)
    subfolders = []
    if subdirectory is not None:
        validate_image_upload_name(image_filename)
        subfolders = validate_image_subdirectory(subdirectory)
    # HTTP chunk boundaries need not align with the seven-byte image header.
    iterator = stream.__aiter__()
    prefix = bytearray()
    async for chunk in iterator:
        prefix.extend(chunk)
        if len(prefix) >= 7:
            break
    if len(prefix) < 7:
        raise InvalidImageError("The image content is empty or too small to be valid")
    image_type = check_valid_image_header(image_path, bytes(prefix), allow_raw_image or not check_image_header)
    if not image_dir:
        image_path = os.path.abspath(os.path.join(default_images_directory(image_type), *subfolders, image_name))
        root = os.path.realpath(os.path.expanduser(Config.instance().settings.Server.images_path))
        if not contained_path(os.path.realpath(image_path), root):
            raise InvalidImageError(f"Image destination is outside the configured image directory: {image_path}")
    root = Config.instance().settings.Server.images_path
    with ImageUploadDirectory(root, os.path.dirname(image_path)) as directory:
        descriptor, temporary = directory.temporary()
        checksum = hashlib.md5()
        try:
            # Own the descriptor explicitly so cancellation cannot leak it.
            async with aiofiles.open(descriptor, "wb", closefd=False) as f:
                await f.write(prefix)
                checksum.update(prefix)
                async for chunk in iterator:
                    await f.write(chunk)
                    checksum.update(chunk)
            image_size = os.fstat(descriptor).st_size
            # Preserve executable IOU permissions even under a restrictive umask.
            permissions = stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC
            if hasattr(os, "fchmod"):
                os.fchmod(descriptor, permissions)
            else:
                directory.verify()
                os.chmod(os.path.join(directory.path, temporary), permissions)
            os.close(descriptor)
            descriptor = None
            async with image_lock(image_path):
                directory.verify()
                if os.path.lexists(image_path):
                    raise InvalidImageError(
                        f"File '{image_path}' already exists, "
                        f"please choose a different name or remove the existing image"
                    )
                checksum_str = checksum.hexdigest()
                duplicate_image = await images_repo.get_image_by_checksum(checksum_str, os.path.dirname(image_path))
                if duplicate_image:
                    raise InvalidImageError(
                        f"Image '{duplicate_image.filename}' with the same checksum "
                        f"already exists in '{os.path.dirname(image_path)}'"
                    )
                file_fingerprint = directory.publish(temporary, image_name)
                # Complete files survive a database failure for reconciliation.
                image = await images_repo.save_verified_image(
                    dict(
                        image_name=image_name,
                        image_type=image_type,
                        image_size=image_size,
                        path=image_path,
                        checksum=checksum_str,
                        checksum_algorithm="md5",
                        file_fingerprint=file_fingerprint,
                    )
                )
                if image is None:
                    raise InvalidImageError(f"Failed to save image '{image_name}' to database")
                return image
        finally:
            if descriptor is not None:
                os.close(descriptor)
            try:
                directory.remove(temporary)
            except FileNotFoundError:
                pass
            except OSError:
                log.warning("Could not remove temporary image '%s'", temporary)
