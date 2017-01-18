#!/usr/bin/env python
#
# Copyright (C) 2016 GNS3 Technologies Inc.
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

import asyncio

from .base_gns3_vm import BaseGNS3VM
from .gns3_vm_error import GNS3VMError


import logging
log = logging.getLogger(__name__)


class RemoteGNS3VM(BaseGNS3VM):

    def __init__(self, controller):

        self._engine = "remote"
        super().__init__(controller)

    @asyncio.coroutine
    def list(self):
        """
        List all VMs
        """

        res = []

        for compute in self._controller.computes.values():
            if compute.id not in ["local", "vm"]:
                res.append({"vmname": compute.name})
        return res

    @asyncio.coroutine
    def start(self):
        """
        Starts the GNS3 VM.
        """

        if not self.vmname:
            return
        vm_compute = None
        for compute in self._controller.computes.values():
            if compute.name == self.vmname:
                self.running = True
                self.protocol = compute.protocol
                self.ip_address = compute.host
                self.port = compute.port
                self.user = compute.user
                self.password = compute.password
                return
        raise GNS3VMError("Can't start the GNS3 VM remote VM {} not found".format(self.vmname))

    @asyncio.coroutine
    def suspend(self):
        """
        Suspend do nothing for remote server
        """
        self.running = False

    @asyncio.coroutine
    def stop(self):
        """
        Stops the GNS3 VM.
        """
        self.running = False
