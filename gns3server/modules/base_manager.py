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
    Base class for all Manager classes.
    Responsible of management of a VM pool of the same type.
    """

    _convert_lock = None

    def __init__(self):

        BaseManager._convert_lock = asyncio.Lock()
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
    def convert_old_project(self, project, legacy_id, name):
        """
        Convert projects made before version 1.3

        :param project: Project instance
        :param legacy_id: old identifier
        :param name: node name

        :returns: new identifier
        """

        new_id = str(uuid4())
        legacy_project_files_path = os.path.join(project.path, "{}-files".format(project.name))
        new_project_files_path = os.path.join(project.path, "project-files")
        if os.path.exists(legacy_project_files_path) and not os.path.exists(new_project_files_path):
            # move the project files
            log.info("Converting old project...")
            try:
                log.info('Moving "{}" to "{}"'.format(legacy_project_files_path, new_project_files_path))
                yield from wait_run_in_executor(shutil.move, legacy_project_files_path, new_project_files_path)
            except OSError as e:
                raise aiohttp.web.HTTPInternalServerError(text="Could not move project files directory: {} to {} {}".format(legacy_project_files_path,
                                                                                                                            new_project_files_path, e))

        if project.is_local() is False:
            legacy_remote_project_path = os.path.join(project.location, project.name, self.module_name.lower())
            new_remote_project_path = os.path.join(project.path, "project-files", self.module_name.lower())
            if os.path.exists(legacy_remote_project_path) and not os.path.exists(new_remote_project_path):
                # move the legacy remote project (remote servers only)
                log.info("Converting old remote project...")
                try:
                    log.info('Moving "{}" to "{}"'.format(legacy_remote_project_path, new_remote_project_path))
                    yield from wait_run_in_executor(shutil.move, legacy_remote_project_path, new_remote_project_path)
                except OSError as e:
                    raise aiohttp.web.HTTPInternalServerError(text="Could not move directory: {} to {} {}".format(legacy_remote_project_path,
                                                                                                                  new_remote_project_path, e))

        if hasattr(self, "get_legacy_vm_workdir"):
            # rename old project VM working dir
            log.info("Converting old VM working directory...")
            legacy_vm_dir = self.get_legacy_vm_workdir(legacy_id, name)
            legacy_vm_working_path = os.path.join(new_project_files_path, legacy_vm_dir)
            new_vm_working_path = os.path.join(new_project_files_path, self.module_name.lower(), new_id)
            if os.path.exists(legacy_vm_working_path) and not os.path.exists(new_vm_working_path):
                try:
                    log.info('Moving "{}" to "{}"'.format(legacy_vm_working_path, new_vm_working_path))
                    yield from wait_run_in_executor(shutil.move, legacy_vm_working_path, new_vm_working_path)
                except OSError as e:
                    raise aiohttp.web.HTTPInternalServerError(text="Could not move VM working directory: {} to {} {}".format(legacy_vm_working_path,
                                                                                                                             new_vm_working_path, e))

        return new_id

    @asyncio.coroutine
    def create_vm(self, name, project_id, vm_id, *args, **kwargs):
        """
        Create a new VM

        :param name: VM name
        :param project_id: Project identifier
        :param vm_id: restore a VM identifier
        """

        if vm_id in self._vms:
            return self._vms[vm_id]

        project = ProjectManager.instance().get_project(project_id)
        if vm_id and isinstance(vm_id, int):
            with (yield from BaseManager._convert_lock):
                vm_id = yield from self.convert_old_project(project, vm_id, name)

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
    def project_closing(self, project):
        """
        Called when a project is about to be closed.

        :param project: Project instance
        """

        pass

    @asyncio.coroutine
    def project_closed(self, project):
        """
        Called when a project is closed.

        :param project: Project instance
        """

        for vm in project.vms:
            if vm.id in self._vms:
                del self._vms[vm.id]

    @asyncio.coroutine
    def project_moved(self, project):
        """
        Called when a project is moved

        :param project: project instance
        """

        pass

    @asyncio.coroutine
    def project_committed(self, project):
        """
        Called when a project is committed.

        :param project: Project instance
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
            # FIXME: check for permissions on tap device
            # if not self._has_privileged_access(executable):
            #    raise aiohttp.web.HTTPForbidden(text="{} has no privileged access to {}.".format(executable, tap_device))
            nio = NIOTAP(tap_device)
        elif nio_settings["type"] == "nio_generic_ethernet":
            nio = NIOGenericEthernet(nio_settings["ethernet_device"])
        assert nio is not None
        return nio

    def get_abs_image_path(self, path):
        """
        Get the absolute path of an image

        :param path: file path
        :return: file path
        """

        if not path:
            return ""
        img_directory = self.get_images_directory()
        if not os.path.isabs(path):
            s = os.path.split(path)
            return os.path.normpath(os.path.join(img_directory, *s))
        return path

    def get_relative_image_path(self, path):
        """
        Get a path relative to images directory path
        or an abspath if the path is not located inside
        image directory

        :param path: file path
        :return: file path
        """

        if not path:
            return ""
        img_directory = self.get_images_directory()
        path = self.get_abs_image_path(path)
        if os.path.dirname(path) == img_directory:
            return os.path.basename(path)
        return path

    @asyncio.coroutine
    def list_images(self):
        """
        Return the list of available images for this VM type

        :returns: Array of hash
        """

        try:
            files = os.listdir(self.get_images_directory())
        except FileNotFoundError:
            return []
        files.sort()
        images = []
        for filename in files:
            if filename[0] != ".":
                images.append({"filename": filename})
        return images

    def get_images_directory(self):
        """
        Get the image directory on disk
        """

        raise NotImplementedError

    @asyncio.coroutine
    def write_image(self, filename, stream):
        directory = self.get_images_directory()
        path = os.path.join(directory, os.path.basename(filename))
        log.info("Writting image file %s", path)
        try:
            os.makedirs(directory, exist_ok=True)
            with open(path, 'wb+') as f:
                while True:
                    packet = yield from stream.read(512)
                    if not packet:
                        break
                    f.write(packet)
            os.chmod(path, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
        except OSError as e:
            raise aiohttp.web.HTTPConflict(text="Could not write image: {} to {}".format(filename, e))
