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

import os
import logging
import asyncio

from gns3server.compute.vmware import (
    VMware,
    VMwareError
)

from .base_gns3_vm import BaseGNS3VM
from .gns3_vm_error import GNS3VMError
log = logging.getLogger(__name__)


class VMwareGNS3VM(BaseGNS3VM):

    def __init__(self):

        self._engine = "vmware"
        super().__init__()
        self._vmware_manager = VMware()
        self._vmx_path = None

    @asyncio.coroutine
    def _execute(self, subcommand, args, timeout=60):

        try:
            result = yield from self._vmware_manager.execute(subcommand, args, timeout)
            return (''.join(result))
        except VMwareError as e:
            raise GNS3VMError("Error while executing VMware command: {}".format(e))

    @asyncio.coroutine
    def _set_vcpus_ram(self, vcpus, ram):
        """
        Set the number of vCPU cores and amount of RAM for the GNS3 VM.

        :param vcpus: number of vCPU cores
        :param ram: amount of RAM
        """

        try:
            pairs = VMware.parse_vmware_file(self._vmx_path)
            pairs["numvcpus"] = str(vcpus)
            pairs["memsize"] = str(ram)
            VMware.write_vmx_file(self._vmx_path, pairs)
            log.info("GNS3 VM vCPU count set to {} and RAM amount set to {}".format(vcpus, ram))
        except OSError as e:
            raise GNS3VMError('Could not read/write VMware VMX file "{}": {}'.format(self._vmx_path, e))

    @asyncio.coroutine
    def list(self):
        """
        List all VMware VMs
        """

        return (yield from self._vmware_manager.list_vms())

    @asyncio.coroutine
    def start(self):
        """
        Starts the GNS3 VM.
        """

        vms = yield from self.list()
        for vm in vms:
            if vm["vmname"] == self.vmname:
                self._vmx_path = vm["vmx_path"]
                break

        # check we have a valid VMX file path
        if not self._vmx_path:
            raise GNS3VMError("GNS3 VM is not configured")
        if not os.path.exists(self._vmx_path):
            raise GNS3VMError("VMware VMX file {} doesn't exist".format(self._vmx_path))

        # set the number of vCPUs and amount of RAM  # FIXME
        # yield from self._set_vcpus_ram(self.vcpus, self.ram)

        # start the VM
        args = [self._vmx_path]
        if self._headless:
            args.extend(["nogui"])
        yield from self._execute("start", args)
        log.info("GNS3 VM has been started")
        self.running = True

        # check if the VMware guest tools are installed
        vmware_tools_state = yield from self._execute("checkToolsState", [self._vmx_path])
        print(vmware_tools_state)
        if vmware_tools_state not in ("installed", "running"):
            raise GNS3VMError("VMware tools are not installed in {}".format(self.vmname))

        # get the guest IP address (first adapter only)
        guest_ip_address = yield from self._execute("getGuestIPAddress", [self._vmx_path, "-wait"], timeout=120)
        self.ip_address = guest_ip_address
        log.info("GNS3 VM IP address set to {}".format(guest_ip_address))

    @asyncio.coroutine
    def stop(self):
        """
        Stops the GNS3 VM.
        """

        if self._vmx_path is None:
            raise GNS3VMError("No VMX path configured, can't stop the VM")
        yield from self._execute("stop", [self._vmx_path, "soft"])
        log.info("GNS3 VM has been stopped")
        self.running = False
