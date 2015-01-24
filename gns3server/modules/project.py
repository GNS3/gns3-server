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
import tempfile
import shutil
from uuid import UUID, uuid4
from ..config import Config


import logging
log = logging.getLogger(__name__)


class Project:
    """
    A project contains a list of VM.
    In theory VM are isolated project/project.

    :param uuid: Force project uuid (None by default auto generate an UUID)
    :param location: Parent path of the project. (None should create a tmp directory)
    :param temporary: Boolean the project is a temporary project (destroy when closed)
    """

    def __init__(self, uuid=None, location=None, temporary=False):

        if uuid is None:
            self._uuid = str(uuid4())
        else:
            try:
                UUID(uuid, version=4)
            except ValueError:
                raise aiohttp.web.HTTPBadRequest(text="{} is not a valid UUID".format(uuid))
            self._uuid = uuid

        config = Config.instance().get_section_config("Server")
        self._location = location
        if location is None:
            self._location = config.get("project_directory", self._get_default_project_directory())
        else:
            if config.get("local", False) is False:
                raise aiohttp.web.HTTPForbidden(text="You are not allowed to modifiy the project directory location")

        self._temporary = temporary
        self._vms = set()
        self._vms_to_destroy = set()
        self._path = os.path.join(self._location, self._uuid)
        try:
            os.makedirs(os.path.join(self._path, "vms"), exist_ok=True)
        except OSError as e:
            raise aiohttp.web.HTTPInternalServerError(text="Could not create project directory: {}".format(e))
        log.debug("Create project {uuid} in directory {path}".format(path=self._path, uuid=self._uuid))

    def _get_default_project_directory(self):
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
    def uuid(self):

        return self._uuid

    @property
    def location(self):

        return self._location

    @property
    def path(self):

        return self._path

    @property
    def vms(self):

        return self._vms

    @property
    def temporary(self):

        return self._temporary

    @temporary.setter
    def temporary(self, temporary):

        self._temporary = temporary

    def vm_working_directory(self, vm):
        """
        Return a working directory for a specific VM.
        If the directory doesn't exist, the directory is created.

        :param vm: An instance of VM
        :returns: A string with a VM working directory
        """

        workdir = os.path.join(self._path, vm.manager.module_name.lower(), vm.uuid)
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
            "uuid": self._uuid,
            "location": self._location,
            "temporary": self._temporary
        }

    def add_vm(self, vm):
        """
        Add a VM to the project.
        In theory this should be called by the VM manager.

        :param vm: A VM instance
        """

        self._vms.add(vm)

    def remove_vm(self, vm):
        """
        Remove a VM from the project.
        In theory this should be called by the VM manager.

        :param vm: A VM instance
        """

        if vm in self._vms:
            self._vms.remove(vm)

    def close(self):
        """Close the project, but keep informations on disk"""

        self._close_and_clean(self._temporary)

    def _close_and_clean(self, cleanup):
        """
        Close the project, and cleanup the disk if cleanup is True

        :param cleanup: If True drop the project directory
        """

        for vm in self._vms:
            vm.close()
        if cleanup and os.path.exists(self.path):
            shutil.rmtree(self.path)

    def commit(self):
        """Write project changes on disk"""

        while self._vms_to_destroy:
            vm = self._vms_to_destroy.pop()
            directory = self.vm_working_directory(vm)
            if os.path.exists(directory):
                shutil.rmtree(directory)
            self.remove_vm(vm)

    def delete(self):
        """Remove project from disk"""

        self._close_and_clean(True)
