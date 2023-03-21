# -*- coding: utf-8 -*-
#
# Copyright (C) 2013 GNS3 Technologies Inc.
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

import sys
import os
import shutil
import subprocess

from setuptools import setup

BUSYBOX_PATH = "gns3server/compute/docker/resources/bin/busybox"


def copy_busybox():
    if not sys.platform.startswith("linux"):
        return
    if os.path.isfile(BUSYBOX_PATH):
        return
    for bb_cmd in ("busybox-static", "busybox.static", "busybox"):
        bb_path = shutil.which(bb_cmd)
        if bb_path:
            if subprocess.call(["ldd", bb_path],
                               stdin=subprocess.DEVNULL,
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL):
                shutil.copy2(bb_path, BUSYBOX_PATH, follow_symlinks=True)
                break
    else:
        raise SystemExit("No static busybox found")


copy_busybox()  # TODO: this should probably be done when the first time the server is started
setup()  # required with setuptools below version 64.0.0
