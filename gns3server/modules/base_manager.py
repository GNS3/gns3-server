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


import asyncio
import aiohttp

from .vm_error import VMError


class BaseManager:
    """
    Base class for all Manager.
    Responsible of management of a VM pool
    """

    def __init__(self):

        self._vms = {}
        self._port_manager = None

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
    def port_manager(self):
        """
        Returns the port_manager for this VMs

        :returns: Port manager
        """

        return self._port_manager

    @port_manager.setter
    def port_manager(self, new_port_manager):

        self._port_manager = new_port_manager

    @classmethod
    @asyncio.coroutine  # FIXME: why coroutine?
    def destroy(cls):
        cls._instance = None

    def get_vm(self, vm_id):
        """
        Returns a VM instance.

        :param vm_id: VM identifier

        :returns: VM instance
        """

        if vm_id not in self._vms:
            raise aiohttp.web.HTTPNotFound(text="ID {} doesn't exist".format(vm_id))
        return self._vms[vm_id]

    @asyncio.coroutine
    def create_vm(self, vmname, identifier=None):
        if not identifier:
            for i in range(1, 1024):
                if i not in self._vms:
                    identifier = i
                    break
            if identifier == 0:
                raise VMError("Maximum number of VM instances reached")
        else:
            if identifier in self._vms:
                raise VMError("VM identifier {} is already used by another VM instance".format(identifier))
        vm = self._VM_CLASS(vmname, identifier, self)
        yield from vm.wait_for_creation()
        self._vms[vm.id] = vm
        return vm

    @asyncio.coroutine
    def start_vm(self, vm_id):
        vm = self.get_vm(vm_id)
        yield from vm.start()

    @asyncio.coroutine
    def stop_vm(self, vm_id):
        vm = self.get_vm(vm_id)
        yield from vm.stop()
