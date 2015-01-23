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
import struct
import stat
import asyncio
import aiohttp
import socket

import logging
log = logging.getLogger(__name__)

from uuid import UUID, uuid4
from ..config import Config
from .project_manager import ProjectManager

from .nios.nio_udp import NIO_UDP
from .nios.nio_tap import NIO_TAP


class BaseManager:

    """
    Base class for all Manager.
    Responsible of management of a VM pool
    """

    def __init__(self):

        self._vms = {}
        self._port_manager = None
        self._config = Config.instance()

    @classmethod
    def instance(cls):
        """
        Singleton to return only one instance of BaseManager.

        :returns: instance of BaseManager
        """

        if not hasattr(cls, "_instance") or cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def module_name(self):
        """
        Returns the module name.

        :returns: module name
        """

        return self.__class__.__name__

    @property
    def port_manager(self):
        """
        Returns the port manager.

        :returns: Port manager
        """

        return self._port_manager

    @port_manager.setter
    def port_manager(self, new_port_manager):

        self._port_manager = new_port_manager

    @property
    def config(self):
        """
        Returns the server config.

        :returns: Config
        """

        return self._config

    @asyncio.coroutine
    def unload(self):

        for uuid in self._vms.keys():
            try:
                self.delete_vm(uuid)
            except Exception as e:
                log.warn("Could not delete VM {}: {}".format(uuid, e))

        if hasattr(BaseManager, "_instance"):
            BaseManager._instance = None

    def get_vm(self, uuid):
        """
        Returns a VM instance.

        :param uuid: VM UUID

        :returns: VM instance
        """

        try:
            UUID(uuid, version=4)
        except ValueError:
            raise aiohttp.web.HTTPBadRequest(text="{} is not a valid UUID".format(uuid))

        if uuid not in self._vms:
            raise aiohttp.web.HTTPNotFound(text="UUID {} doesn't exist".format(uuid))
        return self._vms[uuid]

    @asyncio.coroutine
    def create_vm(self, name, project_uuid, uuid, *args, **kwargs):
        """
        Create a new VM

        :param name: VM name
        :param project_uuid: UUID of Project
        :param uuid: restore a VM UUID
        """

        project = ProjectManager.instance().get_project(project_uuid)

        # TODO: support for old projects VM with normal IDs.

        if not uuid:
            uuid = str(uuid4())

        vm = self._VM_CLASS(name, uuid, project, self, *args, **kwargs)
        project.add_vm(vm)
        if asyncio.iscoroutinefunction(vm.create):
            yield from vm.create()
        else:
            vm.create()
        self._vms[vm.uuid] = vm
        return vm

    @asyncio.coroutine
    def close_vm(self, uuid):
        """
        Delete a VM

        :param uuid: VM UUID
        :returns: VM instance
        """

        vm = self.get_vm(uuid)
        if asyncio.iscoroutinefunction(vm.close):
            yield from vm.close()
        else:
            vm.close()
        return vm

    @asyncio.coroutine
    def delete_vm(self, uuid):
        """
        Delete a VM. VM working directory will be destroy when
        we receive a commit.

        :param uuid: VM UUID
        :returns: VM instance
        """

        vm = yield from self.close_vm(uuid)
        vm.project.mark_vm_for_destruction(vm)
        del self._vms[vm.uuid]
        return vm

    @staticmethod
    def _has_privileged_access(executable):
        """
        Check if an executable can access Ethernet and TAP devices in
        RAW mode.

        :param executable: executable path

        :returns: True or False
        """

        if sys.platform.startswith("win"):
            # do not check anything on Windows
            return True

        if os.geteuid() == 0:
            # we are root, so we should have privileged access.
            return True
        if os.stat(executable).st_mode & stat.S_ISUID or os.stat(executable).st_mode & stat.S_ISGID:
            # the executable has set UID bit.
            return True

        # test if the executable has the CAP_NET_RAW capability (Linux only)
        if sys.platform.startswith("linux") and "security.capability" in os.listxattr(executable):
            try:
                caps = os.getxattr(executable, "security.capability")
                # test the 2nd byte and check if the 13th bit (CAP_NET_RAW) is set
                if struct.unpack("<IIIII", caps)[1] & 1 << 13:
                    return True
            except Exception as e:
                log.error("could not determine if CAP_NET_RAW capability is set for {}: {}".format(executable, e))

        return False

    def create_nio(self, executable, nio_settings):
        """
        Creates a new NIO.

        :param nio_settings: information to create the NIO

        :returns: a NIO object
        """

        nio = None
        if nio_settings["type"] == "nio_udp":
            lport = nio_settings["lport"]
            rhost = nio_settings["rhost"]
            rport = nio_settings["rport"]
            try:
                # TODO: handle IPv6
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                    sock.connect((rhost, rport))
            except OSError as e:
                raise aiohttp.web.HTTPInternalServerError(text="Could not create an UDP connection to {}:{}: {}".format(rhost, rport, e))
            nio = NIO_UDP(lport, rhost, rport)
        elif nio_settings["type"] == "nio_tap":
            tap_device = nio_settings["tap_device"]
            if not self._has_privileged_access(executable):
                raise aiohttp.web.HTTPForbidden(text="{} has no privileged access to {}.".format(executable, tap_device))
            nio = NIO_TAP(tap_device)
        assert nio is not None
        return nio
