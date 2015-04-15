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
VPCS server module.
"""

import os
import asyncio

from ..base_manager import BaseManager
from .vpcs_error import VPCSError
from .vpcs_vm import VPCSVM


class VPCS(BaseManager):

    _VM_CLASS = VPCSVM

    def __init__(self):

        super().__init__()
        self._free_mac_ids = {}
        self._used_mac_ids = {}

    @asyncio.coroutine
    def create_vm(self, *args, **kwargs):
        """
        Creates a new VPCS VM.

        :returns: VPCSVM instance
        """

        vm = yield from super().create_vm(*args, **kwargs)
        self._free_mac_ids.setdefault(vm.project.id, list(range(0, 255)))
        try:
            self._used_mac_ids[vm.id] = self._free_mac_ids[vm.project.id].pop(0)
        except IndexError:
            raise VPCSError("Cannot create a new VPCS VM (limit of 255 VMs reached on this host)")
        return vm

    @asyncio.coroutine
    def close_vm(self, vm_id, *args, **kwargs):
        """
        Closes a VPCS VM.

        :returns: VPCSVM instance
        """

        vm = self.get_vm(vm_id)
        if vm_id in self._used_mac_ids:
            i = self._used_mac_ids[vm_id]
            self._free_mac_ids[vm.project.id].insert(0, i)
            del self._used_mac_ids[vm_id]
        yield from super().close_vm(vm_id, *args, **kwargs)
        return vm

    def get_mac_id(self, vm_id):
        """
        Get an unique VPCS MAC id (offset)

        :param vm_id: VPCS VM identifier

        :returns: VPCS MAC identifier
        """

        return self._used_mac_ids.get(vm_id, 1)

    @staticmethod
    def get_legacy_vm_workdir(legacy_vm_id, name):
        """
        Returns the name of the legacy working directory name for a VM.

        :param legacy_vm_id: legacy VM identifier (integer)
        :param name: VM name (not used)

        :returns: working directory name
        """

        return os.path.join("vpcs", "pc-{}".format(legacy_vm_id))
