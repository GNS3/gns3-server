# -*- coding: utf-8 -*-
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

from ..config import Config
from . import force_unix_path
from io import DEFAULT_BUFFER_SIZE

import logging
log = logging.getLogger(__name__)


def list_images(emulator_type):
    """
    Scan directories for available image for a given emulator type

    :param emulator_type: emulator type (dynamips, qemu, iou)
    """
    files = set()
    images = []

    server_config = Config.instance().get_section_config("Server")
    general_images_directory = os.path.expanduser(server_config.get("images_path", "~/GNS3/images"))

    # Subfolder of the general_images_directory specific to this emulator type
    default_directory = default_images_directory(emulator_type)

    for directory in images_directories(emulator_type):

        # We limit recursion to path outside the default images directory
        # the reason is in the default directory manage file organization and
        # it should be flat to keep things simple
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

                filesize = os.stat(os.path.join(root, filename)).st_size
                if filesize < 7:
                    log.debug("File {} is too small to be an image, skipping...".format(filename))
                    continue

                try:
                    with open(os.path.join(root, filename), "rb") as f:
                        # read the first 7 bytes of the file.
                        elf_header_start = f.read(7)
                    if emulator_type == "dynamips" and elf_header_start != b'\x7fELF\x01\x02\x01':
                        # IOS images must start with the ELF magic number, be 32-bit, big endian and have an ELF version of 1
                        log.warning("IOS image {} does not start with a valid ELF magic number, skipping...".format(filename))
                        continue
                    elif emulator_type == "iou" and elf_header_start != b'\x7fELF\x02\x01\x01' and elf_header_start != b'\x7fELF\x01\x01\x01':
                        # IOU images must start with the ELF magic number, be 32-bit or 64-bit, little endian and have an ELF version of 1
                        log.warning("IOU image {} does not start with a valid ELF magic number, skipping...".format(filename))
                        continue
                    elif emulator_type == "qemu" and elf_header_start[:4] == b'\x7fELF':
                        # QEMU images should not start with an ELF magic number
                        log.warning("QEMU image {} starts with an ELF magic number, skipping...".format(filename))
                        continue

                    # It the image is located in the standard directory the path is relative
                    if os.path.commonprefix([root, default_directory]) != default_directory:
                        path = os.path.join(root, filename)
                    else:
                        path = os.path.relpath(os.path.join(root, filename), default_directory)

                    images.append(
                        {
                            "filename": filename,
                            "path": force_unix_path(path),
                            "md5sum": md5sum(os.path.join(root, filename)),
                            "filesize": filesize
                         }
                    )

                except OSError as e:
                    log.warning("Can't add image {}: {}".format(path, str(e)))
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


def default_images_directory(emulator_type):
    """
    :returns: Return the default directory for a node type
    """
    server_config = Config.instance().get_section_config("Server")
    img_dir = os.path.expanduser(server_config.get("images_path", "~/GNS3/images"))
    if emulator_type == "qemu":
        return os.path.join(img_dir, "QEMU")
    elif emulator_type == "iou":
        return os.path.join(img_dir, "IOU")
    elif emulator_type == "dynamips":
        return os.path.join(img_dir, "IOS")
    else:
        raise NotImplementedError("%s node type is not supported", emulator_type)


def images_directories(emulator_type):
    """
    Return all directories where we will look for images
    by priority

    :param emulator_type: Type of emulator
    """
    server_config = Config.instance().get_section_config("Server")

    paths = []
    img_dir = os.path.expanduser(server_config.get("images_path", "~/GNS3/images"))
    type_img_directory = default_images_directory(emulator_type)
    try:
        os.makedirs(type_img_directory, exist_ok=True)
        paths.append(type_img_directory)
    except (OSError, PermissionError):
        pass
    for directory in server_config.get("additional_images_path", "").split(";"):
        paths.append(directory)
    # Compatibility with old topologies we look in parent directory
    paths.append(img_dir)
    # Return only the existing paths
    return [force_unix_path(p) for p in paths if os.path.exists(p)]


def md5sum(path, stopped_event=None):
    """
    Return the md5sum of an image and cache it on disk

    :param path: Path to the image
    :param stopped_event: In case you execute this function on thread and would like to have possibility
                          to cancel operation pass the `threading.Event`
    :returns: Digest of the image
    """

    if path is None or len(path) == 0 or not os.path.exists(path):
        return None

    try:
        with open(path + '.md5sum') as f:
            md5 = f.read().strip()
            if len(md5) == 32:
                return md5
    # Unicode error is when user rename an image to .md5sum ....
    except (OSError, UnicodeDecodeError):
        pass

    try:
        m = hashlib.md5()
        log.debug("Calculating MD5 sum of `{}`".format(path))
        with open(path, 'rb') as f:
            while True:
                if stopped_event is not None and stopped_event.is_set():
                    log.error("MD5 sum calculation of `{}` has stopped due to cancellation".format(path))
                    return
                buf = f.read(DEFAULT_BUFFER_SIZE)
                if not buf:
                    break
                m.update(buf)
        digest = m.hexdigest()
    except OSError as e:
        log.error("Can't create digest of %s: %s", path, str(e))
        return None

    try:
        with open('{}.md5sum'.format(path), 'w+') as f:
            f.write(digest)
    except OSError as e:
        log.error("Can't write digest of %s: %s", path, str(e))

    return digest


def remove_checksum(path):
    """
    Remove the checksum of an image from cache if exists
    """

    path = '{}.md5sum'.format(path)
    if os.path.exists(path):
        os.remove(path)
