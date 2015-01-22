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

        vm = yield from super().create_vm(*args, **kwargs)
        self._free_mac_ids.setdefault(vm.project.uuid, list(range(0, 255)))
        try:
            self._used_mac_ids[vm.uuid] = self._free_mac_ids[vm.project.uuid].pop(0)
        except IndexError:
            raise VPCSError("No mac address available")
        return vm

    @asyncio.coroutine
    def delete_vm(self, uuid, *args, **kwargs):

        vm = self.get_vm(uuid)
        i = self._used_mac_ids[uuid]
        self._free_mac_ids[vm.project.uuid].insert(0, i)
        del self._used_mac_ids[uuid]
        yield from super().delete_vm(uuid, *args, **kwargs)

    def get_mac_id(self, vm_uuid):
        """
        Get an unique VPCS mac id

        :param vm_uuid: UUID of the VPCS vm
        :returns: VPCS Mac id
        """

        return self._used_mac_ids.get(vm_uuid, 1)
