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

import os
import logging
import aiohttp
import shutil
import asyncio
import tempfile
import psutil
import platform

from pkg_resources import parse_version
from ..utils.asyncio import wait_run_in_executor
from ..ubridge.hypervisor import Hypervisor
from .vm_error import VMError


log = logging.getLogger(__name__)


class BaseVM:

    """
    Base vm implementation.

    :param name: name of this IOU vm
    :param vm_id: IOU instance identifier
    :param project: Project instance
    :param manager: parent VM Manager
    :param console: TCP console port
    """

    def __init__(self, name, vm_id, project, manager, console=None, console_type="telnet"):

        self._name = name
        self._usage = ""
        self._id = vm_id
        self._project = project
        self._manager = manager
        self._console = console
        self._console_type = console_type
        self._temporary_directory = None
        self._hw_virtualization = False
        self._ubridge_hypervisor = None
        self._vm_status = "stopped"

        if self._console is not None:
            if console_type == "vnc":
                self._console = self._manager.port_manager.reserve_tcp_port(self._console, self._project, port_range_start=5900, port_range_end=6000)
            else:
                self._console = self._manager.port_manager.reserve_tcp_port(self._console, self._project)
        else:
            if console_type == "vnc":
                # VNC is a special case and the range must be 5900-6000
                self._console = self._manager.port_manager.get_free_tcp_port(self._project, port_range_start=5900, port_range_end=6000)
            else:
                self._console = self._manager.port_manager.get_free_tcp_port(self._project)

        log.debug("{module}: {name} [{id}] initialized. Console port {console}".format(module=self.manager.module_name,
                                                                                       name=self.name,
                                                                                       id=self.id,
                                                                                       console=self._console))

    def __del__(self):

        if self._temporary_directory is not None:
            if os.path.exists(self._temporary_directory):
                shutil.rmtree(self._temporary_directory, ignore_errors=True)

    @property
    def status(self):
        """Return current VM status"""

        return self._vm_status

    @status.setter
    def status(self, status):

        self._vm_status = status
        self._project.emit("vm.{}".format(status), self)

    @property
    def project(self):
        """
        Returns the VM current project.

        :returns: Project instance.
        """

        return self._project

    @property
    def name(self):
        """
        Returns the name for this VM.

        :returns: name
        """

        return self._name

    @name.setter
    def name(self, new_name):
        """
        Sets the name of this VM.

        :param new_name: name
        """

        log.info("{module}: {name} [{id}] renamed to {new_name}".format(module=self.manager.module_name,
                                                                        name=self.name,
                                                                        id=self.id,
                                                                        new_name=new_name))
        self._name = new_name

    @property
    def usage(self):
        """
        Returns the usage for this VM.

        :returns: usage
        """

        return self._usage

    @usage.setter
    def usage(self, new_usage):
        """
        Sets the usage of this VM.

        :param new_usage: usage
        """

        self._usage = new_usage

    @property
    def id(self):
        """
        Returns the ID for this VM.

        :returns: VM identifier (string)
        """

        return self._id

    @property
    def manager(self):
        """
        Returns the manager for this VM.

        :returns: instance of manager
        """

        return self._manager

    @property
    def working_dir(self):
        """
        Return VM working directory
        """

        return self._project.vm_working_directory(self)

    @property
    def temporary_directory(self):
        if self._temporary_directory is None:
            try:
                self._temporary_directory = tempfile.mkdtemp()
            except OSError as e:
                raise VMError("Can't create temporary directory: {}".format(e))
        return self._temporary_directory

    def create(self):
        """
        Creates the VM.
        """

        log.info("{module}: {name} [{id}] created".format(module=self.manager.module_name,
                                                          name=self.name,
                                                          id=self.id))

    @asyncio.coroutine
    def delete(self):
        """
        Delete the VM (including all its files).
        """

        directory = self.project.vm_working_directory(self)
        if os.path.exists(directory):
            try:
                yield from wait_run_in_executor(shutil.rmtree, directory)
            except OSError as e:
                raise aiohttp.web.HTTPInternalServerError(text="Could not delete the VM working directory: {}".format(e))

    def start(self):
        """
        Starts the VM process.
        """

        raise NotImplementedError

    def stop(self):
        """
        Starts the VM process.
        """

        raise NotImplementedError

    def close(self):
        """
        Close the VM process.
        """

        raise NotImplementedError

    @property
    def console(self):
        """
        Returns the console port of this VM.

        :returns: console port
        """

        return self._console

    @console.setter
    def console(self, console):
        """
        Changes the console port

        :params console: Console port (integer)
        """

        if console == self._console:
            return

        if self._console_type == "vnc" and console < 5900:
            raise VMError("VNC console require a port superior or equal to 5900")

        if self._console:
            self._manager.port_manager.release_tcp_port(self._console, self._project)
        self._console = self._manager.port_manager.reserve_tcp_port(console, self._project)
        log.info("{module}: '{name}' [{id}]: console port set to {port}".format(module=self.manager.module_name,
                                                                                name=self.name,
                                                                                id=self.id,
                                                                                port=console))

    @property
    def console_type(self):
        """
        Returns the console type for this VM.

        :returns: console type (string)
        """

        return self._console_type

    @console_type.setter
    def console_type(self, console_type):
        """
        Sets the console type for this VM.

        :param console_type: console type (string)
        """

        log.info('QEMU VM "{name}" [{id}] has set the console type to {console_type}'.format(name=self._name,
                                                                                             id=self._id,
                                                                                             console_type=console_type))

        if console_type != self._console_type:
            # get a new port if the console type change
            self._manager.port_manager.release_tcp_port(self._console, self._project)
            if console_type == "vnc":
                # VNC is a special case and the range must be 5900-6000
                self._console = self._manager.port_manager.get_free_tcp_port(self._project, 5900, 6000)
            else:
                self._console = self._manager.port_manager.get_free_tcp_port(self._project)

        self._console_type = console_type
        log.info("{module}: '{name}' [{id}]: console type set to {console_type}".format(module=self.manager.module_name,
                                                                                        name=self.name,
                                                                                        id=self.id,
                                                                                        console_type=console_type))

    @property
    def ubridge_path(self):
        """
        Returns the uBridge executable path.

        :returns: path to uBridge
        """

        path = self._manager.config.get_section_config("Server").get("ubridge_path", "ubridge")
        if path == "ubridge":
            path = shutil.which("ubridge")
        return path

    @asyncio.coroutine
    def _start_ubridge(self):
        """
        Starts uBridge (handles connections to and from this VMware VM).
        """

        if not self._manager.has_privileged_access(self.ubridge_path):
            raise VMError("uBridge requires root access or capability to interact with network adapters")

        server_config = self._manager.config.get_section_config("Server")
        server_host = server_config.get("host")
        self._ubridge_hypervisor = Hypervisor(self._project, self.ubridge_path, self.working_dir, server_host)

        log.info("Starting new uBridge hypervisor {}:{}".format(self._ubridge_hypervisor.host, self._ubridge_hypervisor.port))
        yield from self._ubridge_hypervisor.start()
        log.info("Hypervisor {}:{} has successfully started".format(self._ubridge_hypervisor.host, self._ubridge_hypervisor.port))
        yield from self._ubridge_hypervisor.connect()
        if parse_version(self._ubridge_hypervisor.version) < parse_version('0.9.2'):
            raise VMError("uBridge version must be >= 0.9.2, detected version is {}".format(self._ubridge_hypervisor.version))

    @property
    def hw_virtualization(self):
        """
        Returns either the VM is using hardware virtualization or not.

        :return: boolean
        """

        return self._hw_virtualization

    def check_available_ram(self, requested_ram):
        """
        Sends a warning notification if there is not enough RAM on the system to allocate requested RAM.

        :param requested_ram: requested amount of RAM in MB
        """

        available_ram = int(psutil.virtual_memory().available / (1024 * 1024))
        percentage_left = psutil.virtual_memory().percent
        if requested_ram > available_ram:
            message = '"{}" requires {}MB of RAM to run but there is only {}MB - {}% of RAM left on "{}"'.format(self.name,
                                                                                                                 requested_ram,
                                                                                                                 available_ram,
                                                                                                                 percentage_left,
                                                                                                                 platform.node())
            self.project.emit("log.warning", {"message": message})
