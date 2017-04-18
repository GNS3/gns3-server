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


import logging
log = logging.getLogger(__name__)


def list_images(type):
    """
    Scan directories for available image for a type

    :param type: emulator type (dynamips, qemu, iou)
    """
    files = set()
    images = []

    server_config = Config.instance().get_section_config("Server")
    general_images_directory = os.path.expanduser(server_config.get("images_path", "~/GNS3/images"))

    # Subfolder of the general_images_directory specific to this VM type
    default_directory = default_images_directory(type)

    for directory in images_directories(type):

        # We limit recursion to path outside the default images directory
        # the reason is in the default directory manage file organization and
        # it should be flatten to keep things simple
        recurse = True
        if os.path.commonprefix([directory, general_images_directory]) == general_images_directory:
            recurse = False

        directory = os.path.normpath(directory)
        for root, _, filenames in _os_walk(directory, recurse=recurse):
            for filename in filenames:
                path = os.path.join(root, filename)
                if filename not in files:
                    if filename.endswith(".md5sum") or filename.startswith("."):
                        continue
                    elif ((filename.endswith(".image") or filename.endswith(".bin")) and type == "dynamips") \
                            or ((filename.endswith(".bin") or filename.startswith("i86bi")) and type == "iou") \
                            or (not filename.endswith(".bin") and not filename.endswith(".image") and type == "qemu"):
                        files.add(filename)

                        # It the image is located in the standard directory the path is relative
                        if os.path.commonprefix([root, default_directory]) != default_directory:
                            path = os.path.join(root, filename)
                        else:
                            path = os.path.relpath(os.path.join(root, filename), default_directory)

                        try:
                            if type in ["dynamips", "iou"]:
                                with open(os.path.join(root, filename), "rb") as f:
                                    # read the first 7 bytes of the file.
                                    elf_header_start = f.read(7)
                                # valid IOS images must start with the ELF magic number, be 32-bit, big endian and have an ELF version of 1
                                if not elf_header_start == b'\x7fELF\x01\x02\x01' and not elf_header_start == b'\x7fELF\x01\x01\x01':
                                    continue

                            images.append({
                                "filename": filename,
                                "path": force_unix_path(path),
                                "md5sum": md5sum(os.path.join(root, filename)),
                                "filesize": os.stat(os.path.join(root, filename)).st_size})
                        except OSError as e:
                            log.warn("Can't add image {}: {}".format(path, str(e)))
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


def default_images_directory(type):
    """
    :returns: Return the default directory for a node type
    """
    server_config = Config.instance().get_section_config("Server")
    img_dir = os.path.expanduser(server_config.get("images_path", "~/GNS3/images"))
    if type == "qemu":
        return os.path.join(img_dir, "QEMU")
    elif type == "iou":
        return os.path.join(img_dir, "IOU")
    elif type == "dynamips":
        return os.path.join(img_dir, "IOS")
    else:
        raise NotImplementedError("%s node type is not supported", type)


def images_directories(type):
    """
    Return all directory where we will look for images
    by priority

    :param type: Type of emulator
    """
    server_config = Config.instance().get_section_config("Server")

    paths = []
    img_dir = os.path.expanduser(server_config.get("images_path", "~/GNS3/images"))
    type_img_directory = default_images_directory(type)
    try:
        os.makedirs(type_img_directory, exist_ok=True)
        paths.append(type_img_directory)
    except (OSError, PermissionError):
        pass
    for directory in server_config.get("additional_images_path", "").split(";"):
        paths.append(directory)
    # Compatibility with old topologies we look in parent directory
    paths.append(img_dir)
    # Return only the existings paths
    return [force_unix_path(p) for p in paths if os.path.exists(p)]


def md5sum(path):
    """
    Return the md5sum of an image and cache it on disk

    :param path: Path to the image
    :returns: Digest of the image
    """

    if path is None or len(path) == 0 or not os.path.exists(path):
        return None

    try:
        with open(path + '.md5sum') as f:
            md5 = f.read()
            if len(md5) == 32:
                return md5
    # Unicode error is when user rename an image to .md5sum ....
    except (OSError, UnicodeDecodeError):
        pass

    try:
        m = hashlib.md5()
        with open(path, 'rb') as f:
            while True:
                buf = f.read(128)
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
