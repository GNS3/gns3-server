#!/usr/bin/env python3
#
# Copyright (C) 2020 GNS3 Technologies Inc.
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
import time
import shutil
import zipfile


def pack_zip(filename, root_dir=None, base_dir=None):
    """Create a zip archive"""

    if filename[-4:].lower() == ".zip":
        filename = filename[:-4]
    shutil.make_archive(filename, "zip", root_dir, base_dir)


def unpack_zip(filename, extract_dir=None):
    """Unpack a zip archive"""

    dirs = []
    if not extract_dir:
        extract_dir = os.getcwd()

    try:
        with zipfile.ZipFile(filename, "r") as zfile:
            for zinfo in zfile.infolist():
                fname = os.path.join(extract_dir, zinfo.filename)
                date_time = time.mktime(zinfo.date_time + (0, 0, -1))
                zfile.extract(zinfo, extract_dir)

                # update timestamp
                if zinfo.is_dir():
                    dirs.append((fname, date_time))
                else:
                    os.utime(fname, (date_time, date_time))
        # update timestamp of directories
        for fname, date_time in reversed(dirs):
            os.utime(fname, (date_time, date_time))
    except zipfile.BadZipFile:
        raise shutil.ReadError("%s is not a zip file" % filename)
