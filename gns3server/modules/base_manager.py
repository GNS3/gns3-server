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

from uuid import UUID, uuid4
from ..config import Config
from .project_manager import ProjectManager


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

    @classmethod
    @asyncio.coroutine  # FIXME: why coroutine?
    def destroy(cls):

        cls._instance = None

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
        future = vm.create()
        if isinstance(future, asyncio.Future):
            yield from future
        self._vms[vm.uuid] = vm
        return vm

    @asyncio.coroutine
    def start_vm(self, uuid):

        vm = self.get_vm(uuid)
        yield from vm.start()

    @asyncio.coroutine
    def stop_vm(self, uuid):

        vm = self.get_vm(uuid)
        yield from vm.stop()
