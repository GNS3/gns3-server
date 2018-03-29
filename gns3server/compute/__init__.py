# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 GNS3 Technologies Inc.
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

from .builtin import Builtin
from .vpcs import VPCS
from .virtualbox import VirtualBox
from .dynamips import Dynamips
from .qemu import Qemu
from .vmware import VMware
from .traceng import TraceNG

MODULES = [Builtin, VPCS, VirtualBox, Dynamips, Qemu, VMware, TraceNG]

if sys.platform.startswith("linux") or hasattr(sys, "_called_from_test") or os.environ.get("PYTEST_BUILD_DOCUMENTATION") == "1":
    # IOU & Docker only runs on Linux but test suite works on UNIX platform
    if not sys.platform.startswith("win"):
        from .docker import Docker
        MODULES.append(Docker)
        from .iou import IOU
        MODULES.append(IOU)
