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
import asyncio
import aiohttp
from uuid import UUID, uuid4
from contextlib import contextmanager

from .vm import VM
from .udp_link import UDPLink
from ..notification_queue import NotificationQueue
from ..config import Config


class Project:
    """
    A project inside controller

    :param project_id: force project identifier (None by default auto generate an UUID)
    :param path: path of the project. (None use the standard directory)
    :param temporary: boolean to tell if the project is a temporary project (destroy when closed)
    """

    def __init__(self, name=None, project_id=None, path=None, temporary=False):

        self._name = name
        if project_id is None:
            self._id = str(uuid4())
        else:
            try:
                UUID(project_id, version=4)
            except ValueError:
                raise aiohttp.web.HTTPBadRequest(text="{} is not a valid UUID".format(project_id))
            self._id = project_id

        #TODO: Security check if not locale
        if path is None:
            location = self._config().get("project_directory", self._get_default_project_directory())
            path = os.path.join(location, self._id)
        self.path = path

        self._temporary = temporary
        self._computes = set()
        self._vms = {}
        self._links = {}
        self._listeners = set()

    @property
    def name(self):
        return self._name

    @property
    def id(self):
        return self._id

    @property
    def temporary(self):
        return self._temporary

    @property
    def path(self):
        return self._path

    @path.setter
    def path(self, path):
        try:
            os.makedirs(path, exist_ok=True)
        except OSError as e:
            raise aiohttp.web.HTTPInternalServerError(text="Could not create project directory: {}".format(e))

        if '"' in path:
            raise aiohttp.web.HTTPForbidden(text="You are not allowed to use \" in the project directory path. It's not supported by Dynamips.")

        self._path = path

    def _config(self):
        return Config.instance().get_section_config("Server")

    @property
    def captures_directory(self):
        """
        Location of the captures file
        """
        path = os.path.join(self._path, "project-files", "captures")
        os.makedirs(path, exist_ok=True)
        return path

    @asyncio.coroutine
    def addCompute(self, compute):
        self._computes.add(compute)
        yield from compute.post("/projects", self)

    @asyncio.coroutine
    def addVM(self, compute, vm_id, **kwargs):
        """
        Create a vm or return an existing vm

        :param kwargs: See the documentation of VM
        """
        if vm_id not in self._vms:
            vm = VM(self, compute, vm_id=vm_id, **kwargs)
            yield from vm.create()
            self._vms[vm.id] = vm
            return vm
        return self._vms[vm_id]

    def getVM(self, vm_id):
        """
        Return the VM or raise a 404 if the VM is unknown
        """
        try:
            return self._vms[vm_id]
        except KeyError:
            raise aiohttp.web.HTTPNotFound(text="VM ID {} doesn't exist".format(vm_id))

    @property
    def vms(self):
        """
        :returns: Dictionnary of the VMS
        """
        return self._vms

    @asyncio.coroutine
    def addLink(self):
        """
        Create a link. By default the link is empty
        """
        link = UDPLink(self)
        self._links[link.id] = link
        return link

    def getLink(self, link_id):
        """
        Return the Link or raise a 404 if the VM is unknown
        """
        try:
            return self._links[link_id]
        except KeyError:
            raise aiohttp.web.HTTPNotFound(text="Link ID {} doesn't exist".format(link_id))

    @property
    def links(self):
        """
        :returns: Dictionnary of the Links
        """
        return self._links

    @asyncio.coroutine
    def close(self):
        for compute in self._computes:
            yield from compute.post("/projects/{}/close".format(self._id))

    @asyncio.coroutine
    def commit(self):
        for compute in self._computes:
            yield from compute.post("/projects/{}/commit".format(self._id))

    @asyncio.coroutine
    def delete(self):
        for compute in self._computes:
            yield from compute.delete("/projects/{}".format(self._id))
        shutil.rmtree(self.path)

    @contextmanager
    def queue(self):
        """
        Get a queue of notifications

        Use it with Python with
        """
        queue = NotificationQueue()
        self._listeners.add(queue)
        yield queue
        self._listeners.remove(queue)

    def emit(self, action, event, **kwargs):
        """
        Send an event to all the client listening for notifications

        :param action: Action name
        :param event: Event to send
        :param kwargs: Add this meta to the notif (project_id for example)
        """
        for listener in self._listeners:
            listener.put_nowait((action, event, kwargs))

    @classmethod
    def _get_default_project_directory(cls):
        """
        Return the default location for the project directory
        depending of the operating system
        """

        server_config = Config.instance().get_section_config("Server")
        path = os.path.expanduser(server_config.get("projects_path", "~/GNS3/projects"))
        path = os.path.normpath(path)
        try:
            os.makedirs(path, exist_ok=True)
        except OSError as e:
            raise aiohttp.web.HTTPInternalServerError(text="Could not create project directory: {}".format(e))
        return path

    def __json__(self):

        return {
            "name": self._name,
            "project_id": self._id,
            "temporary": self._temporary,
            "path": self._path
        }
