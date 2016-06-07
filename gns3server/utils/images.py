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


def images_directories(type):
    """
    Return all directory where we will look for images
    by priority

    :param type: Type of emulator
    """
    server_config = Config.instance().get_section_config("Server")

    paths = []
    img_dir = os.path.expanduser(server_config.get("images_path", "~/GNS3/images"))
    if type == "qemu":
        type_img_directory = os.path.join(img_dir, "QEMU")
    elif type == "iou":
        type_img_directory = os.path.join(img_dir, "IOU")
    elif type == "dynamips":
        type_img_directory = os.path.join(img_dir, "IOS")
    else:
        raise NotImplementedError("%s is not supported", type)
    os.makedirs(type_img_directory, exist_ok=True)
    paths.append(type_img_directory)
    for directory in server_config.get("additional_images_path", "").split(":"):
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
            return f.read()
    except OSError:
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
