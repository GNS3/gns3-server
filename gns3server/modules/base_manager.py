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
import shutil

import logging
log = logging.getLogger(__name__)

from uuid import UUID, uuid4
from ..config import Config
from ..utils.asyncio import wait_run_in_executor
from .project_manager import ProjectManager

from .nios.nio_udp import NIOUDP
from .nios.nio_tap import NIOTAP
from .nios.nio_generic_ethernet import NIOGenericEthernet


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

        tasks = []
        for vm_id in self._vms.keys():
            tasks.append(asyncio.async(self.close_vm(vm_id)))

        if tasks:
            done, _ = yield from asyncio.wait(tasks)
            for future in done:
                try:
                    future.result()
                except Exception as e:
                    log.error("Could not close VM {}".format(e), exc_info=1)
                    continue

        if hasattr(BaseManager, "_instance"):
            BaseManager._instance = None
        log.debug("Module {} unloaded".format(self.module_name))

    def get_vm(self, vm_id, project_id=None):
        """
        Returns a VM instance.

        :param vm_id: VM identifier
        :param project_id: Project identifier

        :returns: VM instance
        """

        if project_id:
            # check the project_id exists
            project = ProjectManager.instance().get_project(project_id)

        try:
            UUID(vm_id, version=4)
        except ValueError:
            raise aiohttp.web.HTTPBadRequest(text="VM ID {} is not a valid UUID".format(vm_id))

        if vm_id not in self._vms:
            raise aiohttp.web.HTTPNotFound(text="VM ID {} doesn't exist".format(vm_id))

        vm = self._vms[vm_id]
        if project_id:
            if vm.project.id != project.id:
                raise aiohttp.web.HTTPNotFound(text="Project ID {} doesn't belong to VM {}".format(project_id, vm.name))

        return vm

    @asyncio.coroutine
    def create_vm(self, name, project_id, vm_id, *args, **kwargs):
        """
        Create a new VM

        :param name: VM name
        :param project_id: Project identifier
        :param vm_id: restore a VM identifier
        """

        project = ProjectManager.instance().get_project(project_id)

        # If it's not an UUID, old topology
        if vm_id and (isinstance(vm_id, int) or len(vm_id) != 36):
            legacy_id = int(vm_id)
            vm_id = str(uuid4())
            if hasattr(self, "get_legacy_vm_workdir_name"):
                # move old project VM files to a new location

                project_name = os.path.basename(project.path)
                project_files_dir = os.path.join(project.path, "{}-files".format(project_name))
                module_path = os.path.join(project_files_dir, self.module_name.lower())
                vm_working_dir = os.path.join(module_path, self.get_legacy_vm_workdir_name(legacy_id))
                new_vm_working_dir = os.path.join(project.path, "project-files", self.module_name.lower(), vm_id)
                try:
                    yield from wait_run_in_executor(shutil.move, vm_working_dir, new_vm_working_dir)
                except OSError as e:
                    raise aiohttp.web.HTTPInternalServerError(text="Could not move VM working directory: {} to {} {}".format(vm_working_dir, new_vm_working_dir, e))

                if os.listdir(module_path) == []:
                    try:
                        os.rmdir(module_path)
                    except OSError as e:
                        raise aiohttp.web.HTTPInternalServerError(text="Could not delete {}: {}".format(module_path, e))

                if os.listdir(project_files_dir) == []:
                    try:
                        os.rmdir(project_files_dir)
                    except OSError as e:
                        raise aiohttp.web.HTTPInternalServerError(text="Could not delete {}: {}".format(project_files_dir, e))

        if not vm_id:
            vm_id = str(uuid4())

        vm = self._VM_CLASS(name, vm_id, project, self, *args, **kwargs)
        if asyncio.iscoroutinefunction(vm.create):
            yield from vm.create()
        else:
            vm.create()
        self._vms[vm.id] = vm
        project.add_vm(vm)
        return vm

    @asyncio.coroutine
    def close_vm(self, vm_id):
        """
        Delete a VM

        :param vm_id: VM identifier

        :returns: VM instance
        """

        vm = self.get_vm(vm_id)
        if asyncio.iscoroutinefunction(vm.close):
            yield from vm.close()
        else:
            vm.close()
        return vm

    @asyncio.coroutine
    def project_closed(self, project_dir):
        """
        Called when a project is closed.

        :param project_dir: project directory
        """

        pass

    @asyncio.coroutine
    def delete_vm(self, vm_id):
        """
        Delete a VM. VM working directory will be destroy when
        we receive a commit.

        :param vm_id: VM identifier
        :returns: VM instance
        """

        vm = yield from self.close_vm(vm_id)
        vm.project.mark_vm_for_destruction(vm)
        del self._vms[vm.id]
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
            nio = NIOUDP(lport, rhost, rport)
        elif nio_settings["type"] == "nio_tap":
            tap_device = nio_settings["tap_device"]
            if not self._has_privileged_access(executable):
                raise aiohttp.web.HTTPForbidden(text="{} has no privileged access to {}.".format(executable, tap_device))
            nio = NIOTAP(tap_device)
        elif nio_settings["type"] == "nio_generic_ethernet":
            nio = NIOGenericEthernet(nio_settings["ethernet_device"])
        assert nio is not None
        return nio
