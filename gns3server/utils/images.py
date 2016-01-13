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

import logging
log = logging.getLogger(__name__)


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
