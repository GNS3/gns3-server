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

import os
import hashlib
import stat
import aiofiles
import shutil

from typing import List, AsyncGenerator
from ..config import Config
from . import force_unix_path
from io import DEFAULT_BUFFER_SIZE

import gns3server.db.models as models
from gns3server.db.repositories.images import ImagesRepository
from gns3server.utils.asyncio import wait_run_in_executor


import logging

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
                if filename not in files:
                    if filename.endswith(".md5sum") or filename.startswith("."):
                        continue
                    elif (
                        ((filename.endswith(".image") or filename.endswith(".bin")) and image_type == "dynamips")
                        or ((filename.endswith(".bin") or filename.startswith("i86bi")) and image_type == "iou")
                        or (not filename.endswith(".bin") and not filename.endswith(".image") and image_type == "qemu")
                    ):
                        files.add(filename)

                        # It the image is located in the standard directory the path is relative
                        if os.path.commonprefix([root, default_directory]) != default_directory:
                            path = os.path.join(root, filename)
                        else:
                            path = os.path.relpath(os.path.join(root, filename), default_directory)

                        try:
                            if image_type in ["dynamips", "iou"]:
                                with open(os.path.join(root, filename), "rb") as f:
                                    # read the first 7 bytes of the file.
                                    elf_header_start = f.read(7)
                                # valid IOU or IOS images must start with the ELF magic number, be 32-bit or 64-bit,
                                # little endian and have an ELF version of 1
                                if elf_header_start != b'\x7fELF\x02\x01\x01' and elf_header_start != b'\x7fELF\x01\x01\x01':
                                    continue

                            images.append(
                                {
                                    "filename": filename,
                                    "path": force_unix_path(path),
                                    "md5sum": await wait_run_in_executor(md5sum, os.path.join(root, filename)),
                                    "filesize": os.stat(os.path.join(root, filename)).st_size,
                                }
                            )
                        except OSError as e:
                            log.warning(f"Can't add image {path}: {str(e)}")
    return images


async def read_image_info(path: str, expected_image_type: str = None) -> dict:

    header_magic_len = 7
    try:
        async with aiofiles.open(path, "rb") as f:
            image_header = await f.read(header_magic_len)  # read the first 7 bytes of the file
            if len(image_header) >= header_magic_len:
                detected_image_type = check_valid_image_header(image_header)
                if expected_image_type and detected_image_type != expected_image_type:
                    raise InvalidImageError(f"Detected image type for '{path}' is {detected_image_type}, "
                                            f"expected type is {expected_image_type}")
            else:
                raise InvalidImageError(f"Image '{path}' is too small to be valid")
    except OSError as e:
        raise InvalidImageError(f"Cannot read image '{path}': {e}")

    image_info = {
        "image_name": os.path.basename(path),
        "image_type": detected_image_type,
        "image_size": os.stat(path).st_size,
        "path": path,
        "checksum": await wait_run_in_executor(md5sum, path, cache_to_md5file=False),
        "checksum_algorithm": "md5",
    }
    return image_info


async def discover_images(image_type: str, skip_image_paths: list = None) -> List[dict]:
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
                if not os.path.isfile(path) or skip_image_paths and path in skip_image_paths or path in files:
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
        raise NotImplementedError(f"%s node type is not supported", image_type)


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


def md5sum(path, working_dir=None, stopped_event=None, cache_to_md5file=True):
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
                    return
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
            log.error("Can't write digest of %s: %s", path, str(e))

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


def check_valid_image_header(data: bytes, allow_raw_image: bool = False) -> str:

    if data[:7] == b'\x7fELF\x01\x02\x01':
        # for IOS images: file must start with the ELF magic number, be 32-bit, big endian and have an ELF version of 1
        return "ios"
    elif data[:7] == b'\x7fELF\x01\x01\x01' or data[:7] == b'\x7fELF\x02\x01\x01':
        # for IOU images: file must start with the ELF magic number, be 32-bit or 64-bit, little endian and
        # have an ELF version of 1 (normal IOS images are big endian!)
        return "iou"
    elif data[:4] == b'QFI\xfb' or data[:4] == b'KDMV':
        # for Qemy images: file must be QCOW2 or VMDK
        return "qemu"
    else:
        if allow_raw_image is True:
            return "qemu"
        raise InvalidImageError("Could not detect image type, please make sure it is a valid image")


async def write_image(
        image_filename: str,
        image_path: str,
        stream: AsyncGenerator[bytes, None],
        images_repo: ImagesRepository,
        check_image_header=True,
        allow_raw_image=False
) -> models.Image:

    image_dir, image_name = os.path.split(image_filename)
    log.info(f"Writing image file to '{image_path}'")
    # Store the file under its final name only when the upload is completed
    tmp_path = image_path + ".tmp"
    os.makedirs(os.path.dirname(image_path), exist_ok=True)
    checksum = hashlib.md5()
    header_magic_len = 7
    image_type = None
    try:
        async with aiofiles.open(tmp_path, "wb") as f:
            async for chunk in stream:
                if check_image_header and len(chunk) >= header_magic_len:
                    check_image_header = False
                    image_type = check_valid_image_header(chunk, allow_raw_image)
                await f.write(chunk)
                checksum.update(chunk)

        image_size = os.path.getsize(tmp_path)
        if not image_size or image_size < header_magic_len:
            raise InvalidImageError("The image content is empty or too small to be valid")

        checksum = checksum.hexdigest()
        duplicate_image = await images_repo.get_image_by_checksum(checksum)
        if duplicate_image and os.path.dirname(duplicate_image.path) == os.path.dirname(image_path):
            raise InvalidImageError(f"Image {duplicate_image.filename} with "
                                    f"same checksum already exists in the same directory")
        if not image_dir:
            directory = default_images_directory(image_type)
            os.makedirs(directory, exist_ok=True)
            image_path = os.path.abspath(os.path.join(directory, image_filename))
        shutil.move(tmp_path, image_path)
        os.chmod(image_path, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            log.warning(f"Could not remove '{tmp_path}'")

    return await images_repo.add_image(
        image_name,
        image_type,
        image_size,
        image_path,
        checksum,
        checksum_algorithm="md5"
    )
