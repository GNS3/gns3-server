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
IOU server module.
"""

import os
import asyncio

from ..base_manager import BaseManager
from .iou_error import IOUError
from .iou_vm import IOUVM

import logging
log = logging.getLogger(__name__)


class IOU(BaseManager):

    _NODE_CLASS = IOUVM
    _NODE_TYPE = "iou"

    def __init__(self):

        super().__init__()
        self._iou_id_lock = asyncio.Lock()

    async def create_node(self, *args, **kwargs):
        """
        Creates a new IOU VM.

        :returns: IOUVM instance
        """

        node = await super().create_node(*args, **kwargs)
        return node

    @staticmethod
    def get_legacy_vm_workdir(legacy_vm_id, name):
        """
        Returns the name of the legacy working directory (pre 1.3) name for a node.

        :param legacy_vm_id: legacy node identifier (integer)
        :param name: Node name (not used)

        :returns: working directory name
        """

        return os.path.join("iou", "device-{}".format(legacy_vm_id))
