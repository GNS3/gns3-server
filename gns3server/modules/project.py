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

import aiohttp
import os
import shutil
import asyncio
from uuid import UUID, uuid4

from ..config import Config
from ..utils.asyncio import wait_run_in_executor

import logging
log = logging.getLogger(__name__)


class Project:

    """
    A project contains a list of VM.
    In theory VM are isolated project/project.

    :param project_id: Force project identifier (None by default auto generate an UUID)
    :param path: Path of the project. (None use the standard directory)
    :param location: Parent path of the project. (None should create a tmp directory)
    :param temporary: Boolean the project is a temporary project (destroy when closed)
    """

    def __init__(self, project_id=None, path=None, location=None, temporary=False):

        if project_id is None:
            self._id = str(uuid4())
        else:
            try:
                UUID(project_id, version=4)
            except ValueError:
                raise aiohttp.web.HTTPBadRequest(text="{} is not a valid UUID".format(project_id))
            self._id = project_id

        self._location = None
        if location is None:
            self._location = self._config().get("project_directory", self._get_default_project_directory())
        else:
            self.location = location

        self._vms = set()
        self._vms_to_destroy = set()
        self._devices = set()

        self.temporary = temporary

        if path is None:
            path = os.path.join(self._location, self._id)
        try:
            os.makedirs(path, exist_ok=True)
        except OSError as e:
            raise aiohttp.web.HTTPInternalServerError(text="Could not create project directory: {}".format(e))
        self.path = path

        log.debug("Create project {id} in directory {path}".format(path=self._path, id=self._id))

    def _config(self):

        return Config.instance().get_section_config("Server")

    @classmethod
    def _get_default_project_directory(cls):
        """
        Return the default location for the project directory
        depending of the operating system
        """

        path = os.path.normpath(os.path.expanduser("~/GNS3/projects"))
        try:
            os.makedirs(path, exist_ok=True)
        except OSError as e:
            raise aiohttp.web.HTTPInternalServerError(text="Could not create project directory: {}".format(e))
        return path

    @property
    def id(self):

        return self._id

    @property
    def location(self):

        return self._location

    @location.setter
    def location(self, location):

        if location != self._location and self._config().get("local", False) is False:
            raise aiohttp.web.HTTPForbidden(text="You are not allowed to modify the project directory location")

        self._location = location

    @property
    def path(self):

        return self._path

    @path.setter
    def path(self, path):

        if hasattr(self, "_path"):
            if path != self._path and self._config().get("local", False) is False:
                raise aiohttp.web.HTTPForbidden(text="You are not allowed to modify the project directory location")

        self._path = path
        self._update_temporary_file()

    @property
    def vms(self):

        return self._vms

    @property
    def devices(self):

        return self._devices

    @property
    def temporary(self):

        return self._temporary

    @temporary.setter
    def temporary(self, temporary):

        if hasattr(self, 'temporary') and temporary == self._temporary:
            return

        self._temporary = temporary
        self._update_temporary_file()

    def _update_temporary_file(self):
        """
        Update the .gns3_temporary file in order to reflect current
        project status.
        """

        if not hasattr(self, "_path"):
            return

        if self._temporary:
            try:
                with open(os.path.join(self._path, ".gns3_temporary"), 'w+') as f:
                    f.write("1")
            except OSError as e:
                raise aiohttp.web.HTTPInternalServerError(text="Could not create temporary project: {}".format(e))
        else:
            if os.path.exists(os.path.join(self._path, ".gns3_temporary")):
                os.remove(os.path.join(self._path, ".gns3_temporary"))

    def vm_working_directory(self, vm):
        """
        Return a working directory for a specific VM.
        If the directory doesn't exist, the directory is created.

        :param vm: An instance of VM
        :returns: A string with a VM working directory
        """

        workdir = os.path.join(self._path, 'project-files', vm.manager.module_name.lower(), vm.id)
        try:
            os.makedirs(workdir, exist_ok=True)
        except OSError as e:
            raise aiohttp.web.HTTPInternalServerError(text="Could not create the VM working directory: {}".format(e))
        return workdir

    def capture_working_directory(self):
        """
        Return a working directory where to store packet capture files.

        :returns: path to the directory
        """

        workdir = os.path.join(self._path, "captures")
        try:
            os.makedirs(workdir, exist_ok=True)
        except OSError as e:
            raise aiohttp.web.HTTPInternalServerError(text="Could not create the capture working directory: {}".format(e))
        return workdir

    def mark_vm_for_destruction(self, vm):
        """
        :param vm: An instance of VM
        """

        self.remove_vm(vm)
        self._vms_to_destroy.add(vm)

    def __json__(self):

        return {
            "project_id": self._id,
            "location": self._location,
            "temporary": self._temporary,
            "path": self._path,
        }

    def add_vm(self, vm):
        """
        Add a VM to the project.
        In theory this should be called by the VM manager.

        :param vm: VM instance
        """

        self._vms.add(vm)

    def remove_vm(self, vm):
        """
        Remove a VM from the project.
        In theory this should be called by the VM manager.

        :param vm: VM instance
        """

        if vm in self._vms:
            self._vms.remove(vm)

    def add_device(self, device):
        """
        Add a device to the project.
        In theory this should be called by the VM manager.

        :param device: Device instance
        """

        self._devices.add(device)

    def remove_device(self, device):
        """
        Remove a device from the project.
        In theory this should be called by the VM manager.

        :param device: Device instance
        """

        if device in self._devices:
            self._devices.remove(device)

    @asyncio.coroutine
    def close(self):
        """Close the project, but keep information on disk"""

        yield from self._close_and_clean(self._temporary)

    @asyncio.coroutine
    def _close_and_clean(self, cleanup):
        """
        Close the project, and cleanup the disk if cleanup is True

        :param cleanup: If True drop the project directory
        """

        tasks = []
        for vm in self._vms:
            if asyncio.iscoroutinefunction(vm.close):
                tasks.append(asyncio.async(vm.close()))
            else:
                vm.close()

        for device in self._devices:
            tasks.append(asyncio.async(device.delete()))

        if tasks:
            done, _ = yield from asyncio.wait(tasks)
            for future in done:
                try:
                    future.result()
                except Exception as e:
                    log.error("Could not close VM or device {}".format(e), exc_info=1)

        if cleanup and os.path.exists(self.path):
            try:
                yield from wait_run_in_executor(shutil.rmtree, self.path)
            except OSError as e:
                raise aiohttp.web.HTTPInternalServerError(text="Could not delete the project directory: {}".format(e))

    @asyncio.coroutine
    def commit(self):
        """Write project changes on disk"""

        while self._vms_to_destroy:
            vm = self._vms_to_destroy.pop()
            directory = self.vm_working_directory(vm)
            if os.path.exists(directory):
                try:
                    yield from wait_run_in_executor(shutil.rmtree, directory)
                except OSError as e:
                    raise aiohttp.web.HTTPInternalServerError(text="Could not delete the project directory: {}".format(e))
            self.remove_vm(vm)

    @asyncio.coroutine
    def delete(self):
        """Remove project from disk"""

        yield from self._close_and_clean(True)

    @classmethod
    def clean_project_directory(cls):
        """At startup drop old temporary project. After a crash for example"""

        config = Config.instance().get_section_config("Server")
        directory = config.get("project_directory", cls._get_default_project_directory())
        if os.path.exists(directory):
            for project in os.listdir(directory):
                path = os.path.join(directory, project)
                if os.path.exists(os.path.join(path, ".gns3_temporary")):
                    log.warning("Purge old temporary project {}".format(project))
                    shutil.rmtree(path)
