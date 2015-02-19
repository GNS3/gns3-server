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

"""
Qemu server module.
"""

import asyncio

from ..base_manager import BaseManager
from .qemu_error import QemuError
from .qemu_vm import QemuVM


class Qemu(BaseManager):
    _VM_CLASS = QemuVM

    @staticmethod
    def get_legacy_vm_workdir_name(legacy_vm_id):
        """
        Returns the name of the legacy working directory name for a VM.

        :param legacy_vm_id: legacy VM identifier (integer)
        :returns: working directory name
        """

        return "pc-{}".format(legacy_vm_id)
