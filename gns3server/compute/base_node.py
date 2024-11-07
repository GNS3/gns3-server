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
import stat
import logging
import aiohttp
import shutil
import asyncio
import tempfile
import psutil
import platform
import re

from aiohttp.web import WebSocketResponse
from gns3server.utils.interfaces import interfaces
from ..compute.port_manager import PortManager
from ..utils.asyncio import wait_run_in_executor, locking
from ..utils.asyncio.telnet_server import AsyncioTelnetServer
from ..ubridge.hypervisor import Hypervisor
from ..ubridge.ubridge_error import UbridgeError
from .nios.nio_udp import NIOUDP
from .error import NodeError


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
    :param linked_clone: The node base image is duplicate/overlay (Each node data are independent)
    :param wrap_console: The console is wrapped using AsyncioTelnetServer
    """

    def __init__(self, name, node_id, project, manager, console=None, console_type="telnet", aux=None, allocate_aux=False, linked_clone=True, wrap_console=False):

        self._name = name
        self._usage = ""
        self._id = node_id
        self._linked_clone = linked_clone
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
        self._wrap_console = wrap_console
        self._wrapper_telnet_server = None
        self._wrap_console_reader = None
        self._wrap_console_writer = None
        self._internal_console_port = None
        self._custom_adapters = []
        self._ubridge_require_privileged_access = False

        if self._console is not None:
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

        # We need to allocate aux before giving a random console port
        if self._aux is not None:
            self._aux = self._manager.port_manager.reserve_tcp_port(self._aux, self._project)

        if self._console is None:
            if console_type == "vnc":
                vnc_console_start_port_range, vnc_console_end_port_range = self._get_vnc_console_port_range()
                self._console = self._manager.port_manager.get_free_tcp_port(
                    self._project,
                    port_range_start=vnc_console_start_port_range,
                    port_range_end=vnc_console_end_port_range)
            elif console_type != "none":
                self._console = self._manager.port_manager.get_free_tcp_port(self._project)

        if self._wrap_console:
            self._internal_console_port = self._manager.port_manager.get_free_tcp_port(self._project)

        if self._aux is None and allocate_aux:
            self._aux = self._manager.port_manager.get_free_tcp_port(self._project)

        log.debug("{module}: {name} [{id}] initialized. Console port {console}".format(module=self.manager.module_name,
                                                                                       name=self.name,
                                                                                       id=self.id,
                                                                                       console=self._console))

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
                raise NodeError("Can't create temporary directory: {}".format(e))
        return self._temporary_directory

    def create(self):
        """
        Creates the node.
        """

        log.info("{module}: {name} [{id}] created".format(module=self.manager.module_name,
                                                          name=self.name,
                                                          id=self.id))

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
                raise aiohttp.web.HTTPInternalServerError(text="Could not delete the node working directory: {}".format(e))

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

        log.info("{module}: '{name}' [{id}]: is closing".format(module=self.manager.module_name,
                                                                name=self.name,
                                                                id=self.id))

        if self._console:
            self._manager.port_manager.release_tcp_port(self._console, self._project)
            self._console = None
        if self._wrap_console:
            self._manager.port_manager.release_tcp_port(self._internal_console_port, self._project)
            self._internal_console_port = None
        if self._aux:
            self._manager.port_manager.release_tcp_port(self._aux, self._project)
            self._aux = None

        self._closed = True
        return True

    def _get_vnc_console_port_range(self):
        """
        Returns the VNC console port range.
        """

        server_config = self._manager.config.get_section_config("Server")
        vnc_console_start_port_range = server_config.getint("vnc_console_start_port_range", 5900)
        vnc_console_end_port_range = server_config.getint("vnc_console_end_port_range", 10000)

        if not 5900 <= vnc_console_start_port_range <= 65535:
            raise NodeError("The VNC console start port range must be between 5900 and 65535")
        if not 5900 <= vnc_console_end_port_range <= 65535:
            raise NodeError("The VNC console start port range must be between 5900 and 65535")
        if vnc_console_start_port_range >= vnc_console_end_port_range:
            raise NodeError(f"The VNC console start port range value ({vnc_console_start_port_range}) "
                            f"cannot be above or equal to the end value ({vnc_console_end_port_range})")

        return vnc_console_start_port_range, vnc_console_end_port_range

    async def start_wrap_console(self):
        """
        Start a telnet proxy for the console allowing multiple telnet clients
        to be connected at the same time
        """

        if not self._wrap_console or self._console_type != "telnet":
            return
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
        self._wrapper_telnet_server = await asyncio.start_server(
            server.run,
            self._manager.port_manager.console_host,
            self.console
        )

    async def stop_wrap_console(self):
        """
        Stops the telnet proxy.
        """

        if self._wrap_console_writer:
            self._wrap_console_writer.close()
            await self._wrap_console_writer.wait_closed()
            self._wrap_console_writer = None
        if self._wrapper_telnet_server:
            self._wrapper_telnet_server.close()
            await self._wrapper_telnet_server.wait_closed()
            self._wrapper_telnet_server = None

    async def reset_wrap_console(self):
        """
        Reset the wrap console (restarts the Telnet proxy)
        """

        await self.stop_wrap_console()
        await self.start_wrap_console()

    async def start_websocket_console(self, request):
        """
        Connect to console using Websocket.

        :param ws: Websocket object
        """

        if self.status != "started":
            raise NodeError("Node {} is not started".format(self.name))

        if self._console_type != "telnet":
            raise NodeError("Node {} console type is not telnet".format(self.name))

        try:
            (telnet_reader, telnet_writer) = await asyncio.open_connection(self._manager.port_manager.console_host, self.console)
        except ConnectionError as e:
            raise NodeError("Cannot connect to node {} telnet server: {}".format(self.name, e))

        log.info("Connected to Telnet server")

        ws = WebSocketResponse()
        await ws.prepare(request)
        request.app['websockets'].add(ws)

        log.info("New client has connected to console WebSocket")

        async def ws_forward(telnet_writer):

            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    telnet_writer.write(msg.data.encode())
                    await telnet_writer.drain()
                elif msg.type == aiohttp.WSMsgType.BINARY:
                    telnet_writer.write(msg.data)
                    await telnet_writer.drain()
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    log.debug("Websocket connection closed with exception {}".format(ws.exception()))

        async def telnet_forward(telnet_reader):

            while not ws.closed and not telnet_reader.at_eof():
                data = await telnet_reader.read(1024)
                if data:
                    await ws.send_bytes(data)

        try:
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
        finally:
            log.info("Client has disconnected from console WebSocket")
            if not ws.closed:
                await ws.close()
            request.app['websockets'].discard(ws)

        return ws

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

        if console == self._console or self._console_type == "none":
            return

        if self._console_type == "vnc" and console is not None and console < 5900:
            raise NodeError("VNC console require a port superior or equal to 5900, current port is {}".format(console))

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
                    port_range_end=vnc_console_end_port_range
                )
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
        log.info("{module}: '{name}' [{id}]: console type set to {console_type} (console port is {console})".format(module=self.manager.module_name,
                                                                                                                    name=self.name,
                                                                                                                    id=self.id,
                                                                                                                    console_type=console_type,
                                                                                                                    console=self.console))

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

        path = self._manager.config.get_section_config("Server").get("ubridge_path", "ubridge")
        if sys.platform.startswith("win") and hasattr(sys, "frozen"):
            ubridge_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "ubridge"))
            os.environ["PATH"] = os.pathsep.join(ubridge_dir) + os.pathsep + os.environ.get("PATH", "")
        path = shutil.which(path)
        return path

    @locking
    async def _ubridge_send(self, command):
        """
        Sends a command to uBridge hypervisor.

        :param command: command to send
        """

        if not self._ubridge_hypervisor or not self._ubridge_hypervisor.is_running():
            await self._start_ubridge(self._ubridge_require_privileged_access)
        if not self._ubridge_hypervisor or not self._ubridge_hypervisor.is_running():
            raise NodeError("Cannot send command '{}': uBridge is not running".format(command))
        try:
            await self._ubridge_hypervisor.send(command)
        except UbridgeError as e:
            raise UbridgeError("Error while sending command '{}': {}: {}".format(command, e, self._ubridge_hypervisor.read_stdout()))

    @locking
    async def _start_ubridge(self, require_privileged_access=False):
        """
        Starts uBridge (handles connections to and from this node).
        """

        # Prevent us to start multiple ubridge
        if self._ubridge_hypervisor and self._ubridge_hypervisor.is_running():
            return

        if self.ubridge_path is None:
            raise NodeError("uBridge is not available, path doesn't exist, or you just installed GNS3 and need to restart your user session to refresh user permissions.")

        if require_privileged_access and not self._manager.has_privileged_access(self.ubridge_path):
            raise NodeError("uBridge requires root access or the capability to interact with network adapters")

        server_config = self._manager.config.get_section_config("Server")
        server_host = server_config.get("host")
        if not self.ubridge:
            self._ubridge_hypervisor = Hypervisor(self._project, self.ubridge_path, self.working_dir, server_host)
        log.info("Starting new uBridge hypervisor {}:{}".format(self._ubridge_hypervisor.host, self._ubridge_hypervisor.port))
        await self._ubridge_hypervisor.start()
        if self._ubridge_hypervisor:
            log.info("Hypervisor {}:{} has successfully started".format(self._ubridge_hypervisor.host, self._ubridge_hypervisor.port))
            await self._ubridge_hypervisor.connect()
        # save if privileged are required in case uBridge needs to be restarted in self._ubridge_send()
        self._ubridge_require_privileged_access = require_privileged_access

    async def _stop_ubridge(self):
        """
        Stops uBridge.
        """

        if self._ubridge_hypervisor and self._ubridge_hypervisor.is_running():
            log.info("Stopping uBridge hypervisor {}:{}".format(self._ubridge_hypervisor.host, self._ubridge_hypervisor.port))
            await self._ubridge_hypervisor.stop()
        self._ubridge_hypervisor = None

    async def add_ubridge_udp_connection(self, bridge_name, source_nio, destination_nio):
        """
        Creates an UDP connection in uBridge.

        :param bridge_name: bridge name in uBridge
        :param source_nio: source NIO instance
        :param destination_nio: destination NIO instance
        """

        await self._ubridge_send("bridge create {name}".format(name=bridge_name))

        if not isinstance(destination_nio, NIOUDP):
            raise NodeError("Destination NIO is not UDP")

        await self._ubridge_send('bridge add_nio_udp {name} {lport} {rhost} {rport}'.format(name=bridge_name,
                                                                                                 lport=source_nio.lport,
                                                                                                 rhost=source_nio.rhost,
                                                                                                 rport=source_nio.rport))

        await self._ubridge_send('bridge add_nio_udp {name} {lport} {rhost} {rport}'.format(name=bridge_name,
                                                                                                 lport=destination_nio.lport,
                                                                                                 rhost=destination_nio.rhost,
                                                                                                 rport=destination_nio.rport))

        if destination_nio.capturing:
            await self._ubridge_send('bridge start_capture {name} "{pcap_file}"'.format(name=bridge_name,
                                                                                             pcap_file=destination_nio.pcap_output_file))

        await self._ubridge_send('bridge start {name}'.format(name=bridge_name))
        await self._ubridge_apply_filters(bridge_name, destination_nio.filters)

    async def update_ubridge_udp_connection(self, bridge_name, source_nio, destination_nio):
        if destination_nio:
            await self._ubridge_apply_filters(bridge_name, destination_nio.filters)

    async def ubridge_delete_bridge(self, name):
        """
        :params name: Delete the bridge with this name
        """

        if self.ubridge:
            await self._ubridge_send("bridge delete {name}".format(name=name))

    async def _ubridge_apply_filters(self, bridge_name, filters):
        """
        Apply packet filters

        :param bridge_name: bridge name in uBridge
        :param filters: Array of filter dictionary
        """

        await self._ubridge_send('bridge reset_packet_filters ' + bridge_name)
        for packet_filter in self._build_filter_list(filters):
            cmd = 'bridge add_packet_filter {} {}'.format(bridge_name, packet_filter)
            try:
                await self._ubridge_send(cmd)
            except UbridgeError as e:
                match = re.search(r"Cannot compile filter '(.*)': syntax error", str(e))
                if match:
                    message = "Warning: ignoring BPF packet filter '{}' due to syntax error".format(self.name, match.group(1))
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
                for line in values[0].split('\n'):
                    line = line.strip()
                    yield "{filter_name} {filter_type} {filter_value}".format(
                        filter_name="filter" + str(i),
                        filter_type=filter_type,
                        filter_value='"{}" {}'.format(line, " ".join([str(v) for v in values[1:]]))).strip()
                    i += 1
            else:
                yield "{filter_name} {filter_type} {filter_value}".format(
                    filter_name="filter" + str(i),
                    filter_type=filter_type,
                    filter_value=" ".join([str(v) for v in values]))
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
            await self._ubridge_send('bridge add_nio_linux_raw {name} "{interface}"'.format(name=bridge_name, interface=ethernet_interface))
        elif sys.platform.startswith("win"):
            npf_id, source_mac = self._find_windows_interface(ethernet_interface)

            if npf_id:
                await self._ubridge_send('bridge add_nio_ethernet {name} "{interface}"'.format(name=bridge_name,
                                                                                                    interface=npf_id))
            else:
                raise NodeError("Could not find NPF id for interface {}".format(ethernet_interface))

            if block_host_traffic:
                if source_mac:
                    await self._ubridge_send('bridge set_pcap_filter {name} "not ether src {mac}"'.format(name=bridge_name, mac=source_mac))
                    log.info('PCAP filter applied on "{interface}" for source MAC {mac}'.format(interface=ethernet_interface, mac=source_mac))
                else:
                    log.warning("Could not block host network traffic on {} (no MAC address found)".format(ethernet_interface))
        else:
            # on other platforms we just rely on the pcap library
            await self._ubridge_send('bridge add_nio_ethernet {name} "{interface}"'.format(name=bridge_name, interface=ethernet_interface))
            source_mac = None
            for interface in interfaces():
                if interface["name"] == ethernet_interface:
                    source_mac = interface["mac_address"]
            if source_mac:
                await self._ubridge_send('bridge set_pcap_filter {name} "not ether src {mac}"'.format(name=bridge_name, mac=source_mac))
                log.info('PCAP filter applied on "{interface}" for source MAC {mac}'.format(interface=ethernet_interface, mac=source_mac))

    @staticmethod
    def _find_windows_interface(ethernet_interface):
        """
        Get NPF ID and MAC address by input ethernet interface name.
        Return None, None when not match any interface

        :returns: NPF ID and MAC address
        """
        # on Windows we use Winpcap/Npcap
        windows_interfaces = interfaces()
        for interface in windows_interfaces:
            if str.strip(ethernet_interface) == str.strip(interface["name"]):
                return interface["id"], interface["mac_address"]

        for interface in windows_interfaces:
            if "netcard" in interface and ethernet_interface in interface["netcard"]:
                return interface["id"], interface["mac_address"]
        return None, None

    def _create_local_udp_tunnel(self):
        """
        Creates a local UDP tunnel (pair of 2 NIOs, one for each direction)

        :returns: source NIO and destination NIO.
        """

        m = PortManager.instance()
        lport = m.get_free_udp_port(self.project)
        rport = m.get_free_udp_port(self.project)
        source_nio_settings = {'lport': lport, 'rhost': '127.0.0.1', 'rport': rport, 'type': 'nio_udp'}
        destination_nio_settings = {'lport': rport, 'rhost': '127.0.0.1', 'rport': lport, 'type': 'nio_udp'}
        source_nio = self.manager.create_nio(source_nio_settings)
        destination_nio = self.manager.create_nio(destination_nio_settings)
        log.info("{module}: '{name}' [{id}]:local UDP tunnel created between port {port1} and {port2}".format(module=self.manager.module_name,
                                                                                                              name=self.name,
                                                                                                              id=self.id,
                                                                                                              port1=lport,
                                                                                                              port2=rport))
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
            message = '"{}" requires {}MB of RAM to run but there is only {}MB - {}% of RAM left on "{}"'.format(self.name,
                                                                                                                 requested_ram,
                                                                                                                 available_ram,
                                                                                                                 percentage_left,
                                                                                                                 platform.node())
            self.project.emit("log.warning", {"message": message})

    def _get_custom_adapter_settings(self, adapter_number):

        for custom_adapter in self.custom_adapters:
            if custom_adapter["adapter_number"] == adapter_number:
                return custom_adapter
        return {}
