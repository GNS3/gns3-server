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

from pkg_resources import parse_version
from .vmware_error import VMwareError
from ..nios.nio_udp import NIOUDP
from ..base_vm import BaseVM

import logging
log = logging.getLogger(__name__)


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

    def __json__(self):

        return {"name": self.name,
                "vm_id": self.id,
                "console": self.console,
                "project_id": self.project.id,
                "vmx_path": self.vmx_path,
                "headless": self.headless}

    @asyncio.coroutine
    def _control_vm(self, subcommand, *additional_args):

        args = [self._vmx_path]
        args.extend(additional_args)
        result = yield from self.manager.execute(subcommand, args)
        log.debug("Control VM '{}' result: {}".format(subcommand, result))
        return result

    @asyncio.coroutine
    def start(self):
        """
        Starts this VMware VM.
        """

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

        yield from self._control_vm("pause")
        log.info("VMware VM '{name}' [{id}] paused".format(name=self.name, id=self.id))

    @asyncio.coroutine
    def resume(self):
        """
        Resumes this VMware VM.
        """

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
