# -*- coding: utf-8 -*-
#
# Copyright (C) 2014 GNS3 Technologies Inc.
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
VMware VM instance.
"""

import sys
import shlex
import re
import os
import tempfile
import json
import socket
import asyncio

from gns3server.utils.interfaces import interfaces
from pkg_resources import parse_version
from .vmware_error import VMwareError
from ..nios.nio_udp import NIOUDP
from ..adapters.ethernet_adapter import EthernetAdapter
from ..base_vm import BaseVM

import logging
log = logging.getLogger(__name__)

VMX_ETHERNET_TEMPLATE = """
ethernet{number}.present = "TRUE"
ethernet{number}.connectionType = "hostonly"
ethernet{number}.addressType = "generated"
ethernet{number}.generatedAddressOffset = "0"
ethernet{number}.autoDetect = "TRUE"
"""

class VMwareVM(BaseVM):

    """
    VMware VM implementation.
    """

    def __init__(self, name, vm_id, project, manager, vmx_path, linked_clone, console=None):

        super().__init__(name, vm_id, project, manager, console=console)

        self._linked_clone = linked_clone
        self._closed = False

        # VMware VM settings
        self._headless = False
        self._vmx_path = vmx_path
        self._enable_remote_console = False
        self._adapters = 0
        self._ethernet_adapters = {}
        self._adapter_type = "e1000"

        if not os.path.exists(vmx_path):
            raise VMwareError('VMware VM "{name}" [{id}]: could not find VMX file "{}"'.format(name, vmx_path))

    def __json__(self):

        return {"name": self.name,
                "vm_id": self.id,
                "console": self.console,
                "project_id": self.project.id,
                "vmx_path": self.vmx_path,
                "headless": self.headless,
                "enable_remote_console": self.enable_remote_console,
                "adapters": self._adapters,
                "adapter_type": self.adapter_type}

    @asyncio.coroutine
    def _control_vm(self, subcommand, *additional_args):

        args = [self._vmx_path]
        args.extend(additional_args)
        result = yield from self.manager.execute(subcommand, args)
        log.debug("Control VM '{}' result: {}".format(subcommand, result))
        return result

    def _set_network_options(self):

        try:
            self._vmx_pairs = self.manager.parse_vmware_file(self._vmx_path)
        except OSError as e:
            raise VMwareError('Could not read VMware VMX file "{}": {}'.format(self._vmx_path, e))

        vmnet_interfaces = interfaces()
        print(vmnet_interfaces)

        for adapter_number in range(0, self._adapters):
            nio = self._ethernet_adapters[adapter_number].get_nio(0)
            if nio and isinstance(nio, NIOUDP):
                connection_type = "ethernet{}.connectionType".format(adapter_number)
                if connection_type in self._vmx_pairs and self._vmx_pairs[connection_type] not in ("hostonly", "custom"):
                    raise VMwareError("Attachment ({}) already configured on adapter {}. "
                                      "Please set it to 'hostonly' or 'custom to allow GNS3 to use it.".format(self._vmx_pairs[connection_type],
                                                                                                               adapter_number))

                vnet = "ethernet{}.vnet".format(adapter_number)
                if vnet in self._vmx_pairs:
                    pass
                #if "ethernet{}.present".format(adapter_number) in self._vmx_pairs:
                #    print("ETHERNET {} FOUND".format(adapter_number))
                #ethernet0.vnet

    @asyncio.coroutine
    def start(self):
        """
        Starts this VMware VM.
        """

        self._set_network_options()
        if self._headless:
            yield from self._control_vm("start", "nogui")
        else:
            yield from self._control_vm("start")
        log.info("VMware VM '{name}' [{id}] started".format(name=self.name, id=self.id))

    @asyncio.coroutine
    def stop(self):
        """
        Stops this VMware VM.
        """

        yield from self._control_vm("stop")
        log.info("VMware VM '{name}' [{id}] stopped".format(name=self.name, id=self.id))

    @asyncio.coroutine
    def suspend(self):
        """
        Suspends this VMware VM.
        """

        if self.manager.host_type != "ws":
            raise VMwareError("Pausing a VM is only supported by VMware Workstation")
        yield from self._control_vm("pause")
        log.info("VMware VM '{name}' [{id}] paused".format(name=self.name, id=self.id))

    @asyncio.coroutine
    def resume(self):
        """
        Resumes this VMware VM.
        """

        if self.manager.host_type != "ws":
            raise VMwareError("Unpausing a VM is only supported by VMware Workstation")
        yield from self._control_vm("unpause")
        log.info("VMware VM '{name}' [{id}] resumed".format(name=self.name, id=self.id))

    @asyncio.coroutine
    def reload(self):
        """
        Reloads this VMware VM.
        """

        yield from self._control_vm("reset")
        log.info("VMware VM '{name}' [{id}] reloaded".format(name=self.name, id=self.id))

    @asyncio.coroutine
    def close(self):
        """
        Closes this VirtualBox VM.
        """

        if self._closed:
            # VM is already closed
            return

        log.debug("VMware VM '{name}' [{id}] is closing".format(name=self.name, id=self.id))
        if self._console:
            self._manager.port_manager.release_tcp_port(self._console, self._project)
            self._console = None

        #for adapter in self._ethernet_adapters.values():
        #    if adapter is not None:
        #        for nio in adapter.ports.values():
        #            if nio and isinstance(nio, NIOUDP):
        #                self.manager.port_manager.release_udp_port(nio.lport, self._project)

        try:
            yield from self.stop()
        except VMwareError:
            pass

        log.info("VirtualBox VM '{name}' [{id}] closed".format(name=self.name, id=self.id))
        self._closed = True

    @property
    def headless(self):
        """
        Returns either the VM will start in headless mode

        :returns: boolean
        """

        return self._headless

    @headless.setter
    def headless(self, headless):
        """
        Sets either the VM will start in headless mode

        :param headless: boolean
        """

        if headless:
            log.info("VMware VM '{name}' [{id}] has enabled the headless mode".format(name=self.name, id=self.id))
        else:
            log.info("VMware VM '{name}' [{id}] has disabled the headless mode".format(name=self.name, id=self.id))
        self._headless = headless

    @property
    def vmx_path(self):
        """
        Returns the path to the vmx file.

        :returns: VMware vmx file
        """

        return self._vmx_path

    @vmx_path.setter
    def vmx_path(self, vmx_path):
        """
        Sets the path to the vmx file.

        :param vmx_path: VMware vmx file
        """

        log.info("VMware VM '{name}' [{id}] has set the vmx file path to '{vmx}'".format(name=self.name, id=self.id, vmx=vmx_path))
        self._vmx_path = vmx_path

    @property
    def enable_remote_console(self):
        """
        Returns either the remote console is enabled or not

        :returns: boolean
        """

        return self._enable_remote_console

    @enable_remote_console.setter
    def enable_remote_console(self, enable_remote_console):
        """
        Sets either the console is enabled or not

        :param enable_remote_console: boolean
        """

        if enable_remote_console:
            log.info("VMware VM '{name}' [{id}] has enabled the console".format(name=self.name, id=self.id))
            #self._start_remote_console()
        else:
            log.info("VMware VM '{name}' [{id}] has disabled the console".format(name=self.name, id=self.id))
            #self._stop_remote_console()
        self._enable_remote_console = enable_remote_console

    @property
    def adapters(self):
        """
        Returns the number of adapters configured for this VMware VM.

        :returns: number of adapters
        """

        return self._adapters

    @adapters.setter
    def adapters(self, adapters):
        """
        Sets the number of Ethernet adapters for this VMware VM instance.

        :param adapters: number of adapters
        """

        # VMware VMs are limit to 10 adapters
        if adapters > 10:
            raise VMwareError("Number of adapters above the maximum supported of 10")

        self._ethernet_adapters.clear()
        for adapter_number in range(0, adapters):
            self._ethernet_adapters[adapter_number] = EthernetAdapter()

        self._adapters = len(self._ethernet_adapters)
        log.info("VMware VM '{name}' [{id}] has changed the number of Ethernet adapters to {adapters}".format(name=self.name,
                                                                                                              id=self.id,
                                                                                                              adapters=adapters))

    @property
    def adapter_type(self):
        """
        Returns the adapter type for this VMware VM instance.

        :returns: adapter type (string)
        """

        return self._adapter_type

    @adapter_type.setter
    def adapter_type(self, adapter_type):
        """
        Sets the adapter type for this VMware VM instance.

        :param adapter_type: adapter type (string)
        """

        self._adapter_type = adapter_type
        log.info("VMware VM '{name}' [{id}]: adapter type changed to {adapter_type}".format(name=self.name,
                                                                                            id=self.id,
                                                                                            adapter_type=adapter_type))

    def adapter_add_nio_binding(self, adapter_number, nio):
        """
        Adds an adapter NIO binding.

        :param adapter_number: adapter number
        :param nio: NIO instance to add to the slot/port
        """

        try:
            adapter = self._ethernet_adapters[adapter_number]
        except IndexError:
            raise VMwareError("Adapter {adapter_number} doesn't exist on VMware VM '{name}'".format(name=self.name,
                                                                                                    adapter_number=adapter_number))

        adapter.add_nio(0, nio)
        log.info("VMware VM '{name}' [{id}]: {nio} added to adapter {adapter_number}".format(name=self.name,
                                                                                             id=self.id,
                                                                                             nio=nio,
                                                                                             adapter_number=adapter_number))

    def adapter_remove_nio_binding(self, adapter_number):
        """
        Removes an adapter NIO binding.

        :param adapter_number: adapter number

        :returns: NIO instance
        """

        try:
            adapter = self._ethernet_adapters[adapter_number]
        except IndexError:
            raise VMwareError("Adapter {adapter_number} doesn't exist on VMware VM '{name}'".format(name=self.name,
                                                                                                    adapter_number=adapter_number))

        nio = adapter.get_nio(0)
        if isinstance(nio, NIOUDP):
            self.manager.port_manager.release_udp_port(nio.lport, self._project)
        adapter.remove_nio(0)

        log.info("VMware VM '{name}' [{id}]: {nio} removed from adapter {adapter_number}".format(name=self.name,
                                                                                                 id=self.id,
                                                                                                 nio=nio,
                                                                                                 adapter_number=adapter_number))
        return nio
