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
import stat
import shutil
import asyncio
import tempfile
import psutil
import platform
import re

from fastapi import WebSocketDisconnect
from gns3server.utils.interfaces import interfaces
from gns3server.compute.compute_error import ComputeError
from ..compute.port_manager import PortManager
from ..utils.asyncio import wait_run_in_executor, locking
from ..utils.asyncio.telnet_server import AsyncioTelnetServer
from gns3server.compute.ubridge.hypervisor import Hypervisor
from gns3server.compute.ubridge.ubridge_error import UbridgeError
from .nios.nio_udp import NIOUDP
from .error import NodeError

import logging

log = logging.getLogger(__name__)


class BaseNode:

    """
    Base node implementation.

    :param name: name of this node
    :param node_id: Node instance identifier
    :param project: Project instance
    :param manager: parent node manager
    :param console: console TCP port
    :param console_type: console type
    :param aux: auxiliary console TCP port
    :param aux_type: auxiliary console type
    :param linked_clone: The node base image is duplicate/overlay (Each node data are independent)
    :param wrap_console: The console is wrapped using AsyncioTelnetServer
    :param wrap_aux: The auxiliary console is wrapped using AsyncioTelnetServer
    """

    def __init__(
        self,
        name,
        node_id,
        project,
        manager,
        console=None,
        console_type="telnet",
        aux=None,
        aux_type="none",
        linked_clone=True,
        wrap_console=False,
        wrap_aux=False,
    ):

        self._name = name
        self._usage = ""
        self._id = node_id
        self._linked_clone = linked_clone
        self._project = project
        self._manager = manager
        self._console = console
        self._aux = aux
        self._console_type = console_type
        self._aux_type = aux_type
        self._temporary_directory = None
        self._hw_virtualization = False
        self._ubridge_hypervisor = None
        self._closed = False
        self._node_status = "stopped"
        self._command_line = ""
        self._wrap_console = wrap_console
        self._wrap_aux = wrap_aux
        self._wrapper_telnet_servers = []
        self._wrap_console_reader = None
        self._wrap_console_writer = None
        self._internal_console_port = None
        self._internal_aux_port = None
        self._custom_adapters = []
        self._ubridge_require_privileged_access = False

        if self._console is not None:
            # use a previously allocated console port
            if console_type == "vnc":
                vnc_console_start_port_range, vnc_console_end_port_range = self._get_vnc_console_port_range()
                self._console = self._manager.port_manager.reserve_tcp_port(
                    self._console,
                    self._project,
                    port_range_start=vnc_console_start_port_range,
                    port_range_end=vnc_console_end_port_range,
                )
            elif console_type == "none":
                self._console = None
            else:
                self._console = self._manager.port_manager.reserve_tcp_port(self._console, self._project)

        if self._aux is not None:
            # use a previously allocated auxiliary console port
            if aux_type == "vnc":
                # VNC is a special case and the range must be 5900-6000
                self._aux = self._manager.port_manager.reserve_tcp_port(
                    self._aux, self._project, port_range_start=5900, port_range_end=6000
                )
            elif aux_type == "none":
                self._aux = None
            else:
                self._aux = self._manager.port_manager.reserve_tcp_port(self._aux, self._project)

        if self._console is None:
            # allocate a new console
            if console_type == "vnc":
                vnc_console_start_port_range, vnc_console_end_port_range = self._get_vnc_console_port_range()
                self._console = self._manager.port_manager.get_free_tcp_port(
                    self._project,
                    port_range_start=vnc_console_start_port_range,
                    port_range_end=vnc_console_end_port_range,
                )
            elif console_type != "none":
                self._console = self._manager.port_manager.get_free_tcp_port(self._project)

        if self._aux is None:
            # allocate a new auxiliary console
            if aux_type == "vnc":
                # VNC is a special case and the range must be 5900-6000
                self._aux = self._manager.port_manager.get_free_tcp_port(
                    self._project, port_range_start=5900, port_range_end=6000
                )
            elif aux_type != "none":
                self._aux = self._manager.port_manager.get_free_tcp_port(self._project)

        if self._wrap_console:
            self._internal_console_port = self._manager.port_manager.get_free_tcp_port(self._project)

        if self._wrap_aux:
            self._internal_aux_port = self._manager.port_manager.get_free_tcp_port(self._project)

        log.debug(
            "{module}: {name} [{id}] initialized. Console port {console}".format(
                module=self.manager.module_name, name=self.name, id=self.id, console=self._console
            )
        )

    def __del__(self):

        if hasattr(self, "_temporary_directory") and self._temporary_directory is not None:
            if os.path.exists(self._temporary_directory):
                shutil.rmtree(self._temporary_directory, ignore_errors=True)

    @property
    def linked_clone(self):
        return self._linked_clone

    @linked_clone.setter
    def linked_clone(self, val):
        self._linked_clone = val

    @property
    def custom_adapters(self):
        return self._custom_adapters

    @custom_adapters.setter
    def custom_adapters(self, val):
        self._custom_adapters = val

    @property
    def status(self):
        """
        Returns current node status
        """

        return self._node_status

    @status.setter
    def status(self, status):

        self._node_status = status
        self.updated()

    def updated(self):
        """
        Sends an updated event
        """
        self.project.emit("node.updated", self)

    @property
    def command_line(self):
        """
        Returns command used to start the node
        """

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

        log.info(
            "{module}: {name} [{id}] renamed to {new_name}".format(
                module=self.manager.module_name, name=self.name, id=self.id, new_name=new_name
            )
        )
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
    def working_path(self):
        """
        Return the node working path. Doesn't create structure of directories when not present.
        """

        return self._project.node_working_path(self)

    @property
    def temporary_directory(self):
        if self._temporary_directory is None:
            try:
                self._temporary_directory = tempfile.mkdtemp()
            except OSError as e:
                raise NodeError(f"Can't create temporary directory: {e}")
        return self._temporary_directory

    def create(self):
        """
        Creates the node.
        """

        log.info("{module}: {name} [{id}] created".format(module=self.manager.module_name, name=self.name, id=self.id))

    async def delete(self):
        """
        Delete the node (including all its files).
        """

        def set_rw(operation, name, exc):
            os.chmod(name, stat.S_IWRITE)

        directory = self.project.node_working_directory(self)
        if os.path.exists(directory):
            try:
                await wait_run_in_executor(shutil.rmtree, directory, onerror=set_rw)
            except OSError as e:
                raise ComputeError(f"Could not delete the node working directory: {e}")

    def start(self):
        """
        Starts the node process.
        """

        raise NotImplementedError

    async def stop(self):
        """
        Stop the node process.
        """

        await self.stop_wrap_console()
        self.status = "stopped"

    def suspend(self):
        """
        Suspends the node process.
        """

        raise NotImplementedError

    async def close(self):
        """
        Close the node process.
        """

        if self._closed:
            return False

        log.info(
            "{module}: '{name}' [{id}]: is closing".format(module=self.manager.module_name, name=self.name, id=self.id)
        )

        if self._console:
            self._manager.port_manager.release_tcp_port(self._console, self._project)
            self._console = None
        if self._wrap_console:
            self._manager.port_manager.release_tcp_port(self._internal_console_port, self._project)
            self._internal_console_port = None
        if self._aux:
            self._manager.port_manager.release_tcp_port(self._aux, self._project)
            self._aux = None
        if self._wrap_aux:
            self._manager.port_manager.release_tcp_port(self._internal_aux_port, self._project)
            self._internal_aux_port = None

        self._closed = True
        return True

    def _get_vnc_console_port_range(self):
        """
        Returns the VNC console port range.
        """

        vnc_console_start_port_range = self._manager.config.settings.Server.vnc_console_start_port_range
        vnc_console_end_port_range = self._manager.config.settings.Server.vnc_console_end_port_range

        if not 5900 <= vnc_console_start_port_range <= 65535:
            raise NodeError("The VNC console start port range must be between 5900 and 65535")
        if not 5900 <= vnc_console_end_port_range <= 65535:
            raise NodeError("The VNC console start port range must be between 5900 and 65535")
        if vnc_console_start_port_range >= vnc_console_end_port_range:
            raise NodeError(
                f"The VNC console start port range value ({vnc_console_start_port_range}) "
                f"cannot be above or equal to the end value ({vnc_console_end_port_range})"
            )

        return vnc_console_start_port_range, vnc_console_end_port_range

    async def _wrap_telnet_proxy(self, internal_port, external_port):
        """
        Start a telnet proxy for the console allowing multiple telnet clients
        to be connected at the same time
        """

        remaining_trial = 60
        while True:
            try:
                (self._wrap_console_reader, self._wrap_console_writer) = await asyncio.open_connection(
                    host="127.0.0.1",
                    port=self._internal_console_port
                )
                break
            except (OSError, ConnectionRefusedError) as e:
                if remaining_trial <= 0:
                    raise e
            await asyncio.sleep(0.1)
            remaining_trial -= 1
        await AsyncioTelnetServer.write_client_intro(self._wrap_console_writer, echo=True)
        server = AsyncioTelnetServer(
            reader=self._wrap_console_reader,
            writer=self._wrap_console_writer,
            binary=True,
            echo=True
        )
        # warning: this will raise OSError exception if there is a problem...
        telnet_server = await asyncio.start_server(server.run, self._manager.port_manager.console_host, external_port)
        self._wrapper_telnet_servers.append(telnet_server)

    async def start_wrap_console(self):
        """
        Start a Telnet proxy servers for the console and auxiliary console allowing multiple telnet clients
        to be connected at the same time
        """

        if self._wrap_console and self._console_type == "telnet":
            await self._wrap_telnet_proxy(self._internal_console_port, self.console)
            log.info(
                f"New Telnet proxy server for console started "
                f"(internal port = {self._internal_console_port}, external port = {self.console})"
            )

        if self._wrap_aux and self._aux_type == "telnet":
            await self._wrap_telnet_proxy(self._internal_aux_port, self.aux)
            log.info(
                f"New Telnet proxy server for auxiliary console started "
                f"(internal port = {self._internal_aux_port}, external port = {self.aux})"
            )

    async def stop_wrap_console(self):
        """
        Stops the telnet proxy servers.
        """

        if self._wrap_console_writer:
            self._wrap_console_writer.close()
            await self._wrap_console_writer.wait_closed()
        for telnet_proxy_server in self._wrapper_telnet_servers:
            telnet_proxy_server.close()
            await telnet_proxy_server.wait_closed()
        self._wrapper_telnet_servers = []

    async def reset_wrap_console(self):
        """
        Reset the wrap console (restarts the Telnet proxy)
        """

        await self.stop_wrap_console()
        await self.start_wrap_console()

    async def start_websocket_console(self, websocket):
        """
        Connect to console using Websocket.

        :param ws: Websocket object
        """

        log.info(
            f"New client {websocket.client.host}:{websocket.client.port}  has connected to compute"
            f" console WebSocket"
        )

        if self.status != "started":
            raise NodeError(f"Node {self.name} is not started")

        if self._console_type != "telnet":
            raise NodeError(f"Node {self.name} console type is not telnet")

        try:
            host = self._manager.port_manager.console_host
            port = self.console
            (telnet_reader, telnet_writer) = await asyncio.open_connection(host, port)
            log.info(f"Connected to local Telnet server {host}:{port}")
        except ConnectionError as e:
            raise NodeError(f"Cannot connect to node {self.name} telnet server: {e}")

        async def ws_forward(telnet_writer):

            try:
                while True:
                    data = await websocket.receive_text()
                    if data:
                        telnet_writer.write(data.encode())
                        await telnet_writer.drain()
            except WebSocketDisconnect:
                log.info(
                    f"Client {websocket.client.host}:{websocket.client.port} has disconnected from compute"
                    f" console WebSocket"
                )

        async def telnet_forward(telnet_reader):

            while not telnet_reader.at_eof():
                data = await telnet_reader.read(1024)
                if data:
                    await websocket.send_bytes(data)

        # keep forwarding websocket data in both direction
        if sys.version_info >= (3, 11, 0):
            # Starting with Python 3.11, passing coroutine objects to wait() directly is forbidden.
            aws = [asyncio.create_task(ws_forward(telnet_writer)), asyncio.create_task(telnet_forward(telnet_reader))]
        else:
            aws = [ws_forward(telnet_writer), telnet_forward(telnet_reader)]

        done, pending = await asyncio.wait(aws, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            if task.exception():
                log.warning(f"Exception while forwarding WebSocket data to Telnet server {task.exception()}")
        for task in pending:
            task.cancel()

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

        if aux == self._aux or self._aux_type == "none":
            return

        if self._aux_type == "vnc" and aux is not None and aux < 5900:
            raise NodeError(f"VNC auxiliary console require a port superior or equal to 5900, current port is {aux}")

        if self._aux:
            self._manager.port_manager.release_tcp_port(self._aux, self._project)
            self._aux = None
        if aux is not None:
            if self.aux_type == "vnc":
                self._aux = self._manager.port_manager.reserve_tcp_port(
                    aux, self._project, port_range_start=5900, port_range_end=6000
                )
            else:
                self._aux = self._manager.port_manager.reserve_tcp_port(aux, self._project)

            log.info(
                "{module}: '{name}' [{id}]: auxiliary console port set to {port}".format(
                    module=self.manager.module_name, name=self.name, id=self.id, port=aux
                )
            )

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

        if console == self._console or self._console_type == "none":
            return

        if self._console_type == "vnc" and console is not None and console < 5900:
            raise NodeError(f"VNC console require a port superior or equal to 5900, current port is {console}")

        if self._console:
            self._manager.port_manager.release_tcp_port(self._console, self._project)
            self._console = None
        if console is not None:
            if self.console_type == "vnc":
                vnc_console_start_port_range, vnc_console_end_port_range = self._get_vnc_console_port_range()
                self._console = self._manager.port_manager.reserve_tcp_port(
                    console,
                    self._project,
                    port_range_start=vnc_console_start_port_range,
                    port_range_end=vnc_console_end_port_range,
                )
            else:
                self._console = self._manager.port_manager.reserve_tcp_port(console, self._project)

            log.info(
                "{module}: '{name}' [{id}]: console port set to {port}".format(
                    module=self.manager.module_name, name=self.name, id=self.id, port=console
                )
            )

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
            if self._console:
                self._manager.port_manager.release_tcp_port(self._console, self._project)
            if console_type == "none":
                # no need to allocate a port when the console type is none
                self._console = None
            elif console_type == "vnc":
                vnc_console_start_port_range, vnc_console_end_port_range = self._get_vnc_console_port_range()
                self._console = self._manager.port_manager.get_free_tcp_port(
                    self._project,
                    vnc_console_start_port_range,
                    vnc_console_end_port_range
                )
            else:
                self._console = self._manager.port_manager.get_free_tcp_port(self._project)

        self._console_type = console_type
        log.info(
            "{module}: '{name}' [{id}]: console type set to {console_type} (console port is {console})".format(
                module=self.manager.module_name,
                name=self.name,
                id=self.id,
                console_type=console_type,
                console=self.console,
            )
        )

    @property
    def aux_type(self):
        """
        Returns the auxiliary console type for this node.

        :returns: aux type (string)
        """

        return self._aux_type

    @aux_type.setter
    def aux_type(self, aux_type):
        """
        Sets the auxiliary console type for this node.

        :param aux_type: console type (string)
        """

        if aux_type != self._aux_type:
            # get a new port if the aux type change
            if self._aux:
                self._manager.port_manager.release_tcp_port(self._aux, self._project)
            if aux_type == "none":
                # no need to allocate a port when the auxiliary console type is none
                self._aux = None
            elif aux_type == "vnc":
                # VNC is a special case and the range must be 5900-6000
                self._aux = self._manager.port_manager.get_free_tcp_port(self._project, 5900, 6000)
            else:
                self._aux = self._manager.port_manager.get_free_tcp_port(self._project)

        self._aux_type = aux_type
        log.info(
            "{module}: '{name}' [{id}]: console type set to {aux_type} (auxiliary console port is {aux})".format(
                module=self.manager.module_name, name=self.name, id=self.id, aux_type=aux_type, aux=self.aux
            )
        )

    @property
    def ubridge(self):
        """
        Returns the uBridge hypervisor.

        :returns: instance of uBridge
        """

        if self._ubridge_hypervisor and not self._ubridge_hypervisor.is_running():
            self._ubridge_hypervisor = None
        return self._ubridge_hypervisor

    @ubridge.setter
    def ubridge(self, ubride_hypervisor):
        """
        Set an uBridge hypervisor.

        :param ubride_hypervisor: uBridge hypervisor
        """

        self._ubridge_hypervisor = ubride_hypervisor

    @property
    def ubridge_path(self):
        """
        Returns the uBridge executable path.

        :returns: path to uBridge
        """

        path = shutil.which(self._manager.config.settings.Server.ubridge_path)
        return path

    async def _ubridge_send(self, command):
        """
        Sends a command to uBridge hypervisor.

        :param command: command to send
        """

        if not self._ubridge_hypervisor or not self._ubridge_hypervisor.is_running():
            await self._start_ubridge(self._ubridge_require_privileged_access)
        if not self._ubridge_hypervisor or not self._ubridge_hypervisor.is_running():
            raise NodeError(f"Cannot send command '{command}': uBridge is not running")
        try:
            await self._ubridge_hypervisor.send(command)
        except UbridgeError as e:
            raise UbridgeError(
                f"Error while sending command '{command}': {e}: {self._ubridge_hypervisor.read_stdout()}"
            )

    @locking
    async def _start_ubridge(self, require_privileged_access=False):
        """
        Starts uBridge (handles connections to and from this node).
        """

        # Prevent us to start multiple ubridge
        if self._ubridge_hypervisor and self._ubridge_hypervisor.is_running():
            return

        if self.ubridge_path is None:
            raise NodeError(
                "uBridge is not available, path doesn't exist, or you just installed GNS3 and need to restart your user session to refresh user permissions."
            )

        if require_privileged_access and not self._manager.has_privileged_access(self.ubridge_path):
            raise NodeError("uBridge requires root access or the capability to interact with network adapters")

        server_host = self._manager.config.settings.Server.host
        if not self.ubridge:
            self._ubridge_hypervisor = Hypervisor(self._project, self.ubridge_path, self.working_dir, server_host)
        log.info(f"Starting new uBridge hypervisor {self._ubridge_hypervisor.host}:{self._ubridge_hypervisor.port}")
        await self._ubridge_hypervisor.start()
        if self._ubridge_hypervisor:
            log.info(
                f"Hypervisor {self._ubridge_hypervisor.host}:{self._ubridge_hypervisor.port} has successfully started"
            )
            await self._ubridge_hypervisor.connect()
        # save if privileged are required in case uBridge needs to be restarted in self._ubridge_send()
        self._ubridge_require_privileged_access = require_privileged_access

    async def _stop_ubridge(self):
        """
        Stops uBridge.
        """

        if self._ubridge_hypervisor and self._ubridge_hypervisor.is_running():
            log.info(f"Stopping uBridge hypervisor {self._ubridge_hypervisor.host}:{self._ubridge_hypervisor.port}")
            await self._ubridge_hypervisor.stop()
        self._ubridge_hypervisor = None

    async def add_ubridge_udp_connection(self, bridge_name, source_nio, destination_nio):
        """
        Creates an UDP connection in uBridge.

        :param bridge_name: bridge name in uBridge
        :param source_nio: source NIO instance
        :param destination_nio: destination NIO instance
        """

        await self._ubridge_send(f"bridge create {bridge_name}")

        if not isinstance(destination_nio, NIOUDP):
            raise NodeError("Destination NIO is not UDP")

        await self._ubridge_send(
            "bridge add_nio_udp {name} {lport} {rhost} {rport}".format(
                name=bridge_name, lport=source_nio.lport, rhost=source_nio.rhost, rport=source_nio.rport
            )
        )

        await self._ubridge_send(
            "bridge add_nio_udp {name} {lport} {rhost} {rport}".format(
                name=bridge_name, lport=destination_nio.lport, rhost=destination_nio.rhost, rport=destination_nio.rport
            )
        )

        if destination_nio.capturing:
            await self._ubridge_send(
                'bridge start_capture {name} "{pcap_file}"'.format(
                    name=bridge_name, pcap_file=destination_nio.pcap_output_file
                )
            )

        await self._ubridge_send(f"bridge start {bridge_name}")
        await self._ubridge_apply_filters(bridge_name, destination_nio.filters)

    async def update_ubridge_udp_connection(self, bridge_name, source_nio, destination_nio):
        if destination_nio:
            await self._ubridge_apply_filters(bridge_name, destination_nio.filters)

    async def ubridge_delete_bridge(self, name):
        """
        :params name: Delete the bridge with this name
        """

        if self.ubridge:
            await self._ubridge_send(f"bridge delete {name}")

    async def _ubridge_apply_filters(self, bridge_name, filters):
        """
        Apply packet filters

        :param bridge_name: bridge name in uBridge
        :param filters: Array of filter dictionary
        """

        await self._ubridge_send("bridge reset_packet_filters " + bridge_name)
        for packet_filter in self._build_filter_list(filters):
            cmd = f"bridge add_packet_filter {bridge_name} {packet_filter}"
            try:
                await self._ubridge_send(cmd)
            except UbridgeError as e:
                match = re.search(r"Cannot compile filter '(.*)': syntax error", str(e))
                if match:
                    message = f"Warning: ignoring BPF packet filter '{self.name}' due to syntax error: {match.group(1)}"
                    log.warning(message)
                    self.project.emit("log.warning", {"message": message})
                else:
                    raise

    def _build_filter_list(self, filters):
        """
        :returns: Iterator building a list of filter
        """

        i = 0
        for (filter_type, values) in filters.items():
            if isinstance(values[0], str):
                for line in values[0].split("\n"):
                    line = line.strip()
                    yield "{filter_name} {filter_type} {filter_value}".format(
                        filter_name="filter" + str(i),
                        filter_type=filter_type,
                        filter_value='"{}" {}'.format(line, " ".join([str(v) for v in values[1:]])),
                    ).strip()
                    i += 1
            else:
                yield "{filter_name} {filter_type} {filter_value}".format(
                    filter_name="filter" + str(i),
                    filter_type=filter_type,
                    filter_value=" ".join([str(v) for v in values]),
                )
                i += 1

    async def _add_ubridge_ethernet_connection(self, bridge_name, ethernet_interface, block_host_traffic=False):
        """
        Creates a connection with an Ethernet interface in uBridge.

        :param bridge_name: bridge name in uBridge
        :param ethernet_interface: Ethernet interface name
        :param block_host_traffic: block network traffic originating from the host OS (Windows only)
        """

        if sys.platform.startswith("linux") and block_host_traffic is False:
            # on Linux we use RAW sockets by default excepting if host traffic must be blocked
            await self._ubridge_send(
                'bridge add_nio_linux_raw {name} "{interface}"'.format(name=bridge_name, interface=ethernet_interface)
            )
        else:
            # on other platforms we just rely on the pcap library
            await self._ubridge_send(
                'bridge add_nio_ethernet {name} "{interface}"'.format(name=bridge_name, interface=ethernet_interface)
            )
            source_mac = None
            for interface in interfaces():
                if interface["name"] == ethernet_interface:
                    source_mac = interface["mac_address"]
            if source_mac:
                await self._ubridge_send(
                    'bridge set_pcap_filter {name} "not ether src {mac}"'.format(name=bridge_name, mac=source_mac)
                )
                log.info(f"PCAP filter applied on '{ethernet_interface}' for source MAC {source_mac}")

    def _create_local_udp_tunnel(self):
        """
        Creates a local UDP tunnel (pair of 2 NIOs, one for each direction)

        :returns: source NIO and destination NIO.
        """

        m = PortManager.instance()
        lport = m.get_free_udp_port(self.project)
        rport = m.get_free_udp_port(self.project)
        source_nio_settings = {"lport": lport, "rhost": "127.0.0.1", "rport": rport, "type": "nio_udp"}
        destination_nio_settings = {"lport": rport, "rhost": "127.0.0.1", "rport": lport, "type": "nio_udp"}
        source_nio = self.manager.create_nio(source_nio_settings)
        destination_nio = self.manager.create_nio(destination_nio_settings)
        log.info(
            "{module}: '{name}' [{id}]:local UDP tunnel created between port {port1} and {port2}".format(
                module=self.manager.module_name, name=self.name, id=self.id, port1=lport, port2=rport
            )
        )
        return source_nio, destination_nio

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
        percentage_left = 100 - psutil.virtual_memory().percent
        if requested_ram > available_ram:
            message = '"{}" requires {}MB of RAM to run but there is only {}MB - {}% of RAM left on "{}"'.format(
                self.name, requested_ram, available_ram, percentage_left, platform.node()
            )
            self.project.emit("log.warning", {"message": message})

    def _get_custom_adapter_settings(self, adapter_number):

        for custom_adapter in self.custom_adapters:
            if custom_adapter["adapter_number"] == adapter_number:
                return custom_adapter
        return {}
