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

    _NODE_CLASS = VPCSVM

    def __init__(self):

        super().__init__()
        self._free_mac_ids = {}
        self._used_mac_ids = {}

    async def create_node(self, *args, **kwargs):
        """
        Creates a new VPCS VM.

        :returns: VPCSVM instance
        """

        node = await super().create_node(*args, **kwargs)
        self._free_mac_ids.setdefault(node.project.id, list(range(0, 255)))
        try:
            self._used_mac_ids[node.id] = self._free_mac_ids[node.project.id].pop(0)
        except IndexError:
            raise VPCSError("Cannot create a new VPCS VM (limit of 255 VMs reached on this host)")
        return node

    async def close_node(self, node_id, *args, **kwargs):
        """
        Closes a VPCS VM.

        :returns: VPCSVM instance
        """

        node = self.get_node(node_id)
        if node_id in self._used_mac_ids:
            i = self._used_mac_ids[node_id]
            self._free_mac_ids[node.project.id].insert(0, i)
            del self._used_mac_ids[node_id]
        await super().close_node(node_id, *args, **kwargs)
        return node

    def get_mac_id(self, node_id):
        """
        Get an unique VPCS MAC id (offset)

        :param node_id: VPCS node identifier

        :returns: VPCS MAC identifier
        """

        return self._used_mac_ids.get(node_id, 1)

    @staticmethod
    def get_legacy_vm_workdir(legacy_vm_id, name):
        """
        Returns the name of the legacy working directory name for a node.

        :param legacy_vm_id: legacy node identifier (integer)
        :param name: node name (not used)

        :returns: working directory name
        """

        return os.path.join("vpcs", f"pc-{legacy_vm_id}")
