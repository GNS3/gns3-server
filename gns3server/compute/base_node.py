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

from ..utils.asyncio import wait_run_in_executor
from ..ubridge.hypervisor import Hypervisor
from .node_error import NodeError


log = logging.getLogger(__name__)


class BaseNode:

    """
    Base node implementation.

    :param name: name of this node
    :param node_id: Node instance identifier
    :param project: Project instance
    :param manager: parent node manager
    :param console: TCP console port
    :param aux: TCP aux console port
    :param allocate_aux: Boolean if true will allocate an aux console port
    """

    def __init__(self, name, node_id, project, manager, console=None, console_type="telnet", aux=None, allocate_aux=False):

        self._name = name
        self._usage = ""
        self._id = node_id
        self._project = project
        self._manager = manager
        self._console = console
        self._aux = aux
        self._console_type = console_type
        self._temporary_directory = None
        self._hw_virtualization = False
        self._ubridge_hypervisor = None
        self._closed = False
        self._node_status = "stopped"
        self._command_line = ""
        self._allocate_aux = allocate_aux

        if self._console is not None:
            if console_type == "vnc":
                self._console = self._manager.port_manager.reserve_tcp_port(self._console, self._project, port_range_start=5900, port_range_end=6000)
            else:
                self._console = self._manager.port_manager.reserve_tcp_port(self._console, self._project)

        # We need to allocate aux before giving a random console port
        if self._aux is not None:
            self._aux = self._manager.port_manager.reserve_tcp_port(self._aux, self._project)

        if self._console is None:
            if console_type == "vnc":
                # VNC is a special case and the range must be 5900-6000
                self._console = self._manager.port_manager.get_free_tcp_port(self._project, port_range_start=5900, port_range_end=6000)
            else:
                self._console = self._manager.port_manager.get_free_tcp_port(self._project)

        if self._aux is None and allocate_aux:
            self._aux = self._manager.port_manager.get_free_tcp_port(self._project)

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
        """Return current node status"""

        return self._node_status

    @status.setter
    def status(self, status):

        self._node_status = status
        self.updated()

    def updated(self):
        """
        Send a updated event
        """
        self.project.emit("node.updated", self)

    @property
    def command_line(self):
        """Return command used to start the node"""

        return self._command_line

    @command_line.setter
    def command_line(self, command_line):

        self._command_line = command_line

    @property
    def project(self):
        """
        Returns the node current project.

        :returns: Project instance.
        """

        return self._project

    @property
    def name(self):
        """
        Returns the name for this node.

        :returns: name
        """

        return self._name

    @name.setter
    def name(self, new_name):
        """
        Sets the name of this node.

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
        Returns the usage for this node.

        :returns: usage
        """

        return self._usage

    @usage.setter
    def usage(self, new_usage):
        """
        Sets the usage of this node.

        :param new_usage: usage
        """

        self._usage = new_usage

    @property
    def id(self):
        """
        Returns the ID for this node.

        :returns: Node identifier (string)
        """

        return self._id

    @property
    def manager(self):
        """
        Returns the manager for this node.

        :returns: instance of manager
        """

        return self._manager

    @property
    def working_dir(self):
        """
        Return the node working directory
        """

        return self._project.node_working_directory(self)

    @property
    def temporary_directory(self):
        if self._temporary_directory is None:
            try:
                self._temporary_directory = tempfile.mkdtemp()
            except OSError as e:
                raise NodeError("Can't create temporary directory: {}".format(e))
        return self._temporary_directory

    def create(self):
        """
        Creates the node.
        """

        log.info("{module}: {name} [{id}] created".format(module=self.manager.module_name,
                                                          name=self.name,
                                                          id=self.id))

    @asyncio.coroutine
    def delete(self):
        """
        Delete the node (including all its files).
        """

        directory = self.project.node_working_directory(self)
        if os.path.exists(directory):
            try:
                yield from wait_run_in_executor(shutil.rmtree, directory)
            except OSError as e:
                raise aiohttp.web.HTTPInternalServerError(text="Could not delete the node working directory: {}".format(e))

    def start(self):
        """
        Starts the node process.
        """

        raise NotImplementedError

    def stop(self):
        """
        Starts the node process.
        """

        raise NotImplementedError

    def suspend(self):
        """
        Suspends the node process.
        """

        raise NotImplementedError

    @asyncio.coroutine
    def close(self):
        """
        Close the node process.
        """

        if self._closed:
            return False

        log.info("{module}: '{name}' [{id}]: is closing".format(
            module=self.manager.module_name,
            name=self.name,
            id=self.id))

        if self._console:
            self._manager.port_manager.release_tcp_port(self._console, self._project)
            self._console = None

        if self._aux:
            self._manager.port_manager.release_tcp_port(self._aux, self._project)
            self._aux = None

        self._closed = True
        return True

    @property
    def allocate_aux(self):
        """
        :returns: Boolean allocate or not an aux console
        """
        return self._allocate_aux

    @allocate_aux.setter
    def allocate_aux(self, allocate_aux):
        """
        :returns: Boolean allocate or not an aux console
        """
        self._allocate_aux = allocate_aux

    @property
    def aux(self):
        """
        Returns the aux console port of this node.

        :returns: aux console port
        """

        return self._aux

    @aux.setter
    def aux(self, aux):
        """
        Changes the aux port

        :params aux: Console port (integer) or None to free the port
        """

        if aux == self._aux:
            return

        if self._aux:
            self._manager.port_manager.release_tcp_port(self._aux, self._project)
            self._aux = None
        if aux is not None:
            self._aux = self._manager.port_manager.reserve_tcp_port(aux, self._project)
            log.info("{module}: '{name}' [{id}]: aux port set to {port}".format(module=self.manager.module_name,
                                                                                name=self.name,
                                                                                id=self.id,
                                                                                port=aux))

    @property
    def console(self):
        """
        Returns the console port of this node.

        :returns: console port
        """

        return self._console

    @console.setter
    def console(self, console):
        """
        Changes the console port

        :params console: Console port (integer) or None to free the port
        """

        if console == self._console:
            return

        if self._console_type == "vnc" and console is not None and console < 5900:
            raise NodeError("VNC console require a port superior or equal to 5900 currently it's {}".format(console))

        if self._console:
            self._manager.port_manager.release_tcp_port(self._console, self._project)
            self._console = None
        if console is not None:
            if self.console_type == "vnc":
                self._console = self._manager.port_manager.reserve_tcp_port(console, self._project, port_range_start=5900, port_range_end=6000)
            else:
                self._console = self._manager.port_manager.reserve_tcp_port(console, self._project)

            log.info("{module}: '{name}' [{id}]: console port set to {port}".format(module=self.manager.module_name,
                                                                                    name=self.name,
                                                                                    id=self.id,
                                                                                    port=console))

    @property
    def console_type(self):
        """
        Returns the console type for this node.

        :returns: console type (string)
        """

        return self._console_type

    @console_type.setter
    def console_type(self, console_type):
        """
        Sets the console type for this node.

        :param console_type: console type (string)
        """

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

        if path is None or len(path) == 0:
            raise NodeError("uBridge is not installed")
        return path

    @asyncio.coroutine
    def _ubridge_send(self, command):
        """
        Sends a command to uBridge hypervisor.

        :param command: command to send
        """

        if not self._ubridge_hypervisor or not self._ubridge_hypervisor.is_running():
            raise NodeError("Cannot send command '{}': uBridge is not running".format(command))
        yield from self._ubridge_hypervisor.send(command)

    @asyncio.coroutine
    def _start_ubridge(self):
        """
        Starts uBridge (handles connections to and from this node).
        """

        if not self._manager.has_privileged_access(self.ubridge_path):
            raise NodeError("uBridge requires root access or capability to interact with network adapters")

        server_config = self._manager.config.get_section_config("Server")
        server_host = server_config.get("host")
        self._ubridge_hypervisor = Hypervisor(self._project, self.ubridge_path, self.working_dir, server_host)

        log.info("Starting new uBridge hypervisor {}:{}".format(self._ubridge_hypervisor.host, self._ubridge_hypervisor.port))
        yield from self._ubridge_hypervisor.start()
        log.info("Hypervisor {}:{} has successfully started".format(self._ubridge_hypervisor.host, self._ubridge_hypervisor.port))
        yield from self._ubridge_hypervisor.connect()

    @asyncio.coroutine
    def _stop_ubridge(self):
        """
        Stops uBridge.
        """

        if self._ubridge_hypervisor and self._ubridge_hypervisor.is_running():
            yield from self._ubridge_hypervisor.stop()

    @property
    def hw_virtualization(self):
        """
        Returns either the node is using hardware virtualization or not.

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
