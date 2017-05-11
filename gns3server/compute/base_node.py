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

from gns3server.utils.interfaces import interfaces
from ..compute.port_manager import PortManager
from ..utils.asyncio import wait_run_in_executor, locked_coroutine
from ..utils.asyncio.telnet_server import AsyncioTelnetServer
from ..ubridge.hypervisor import Hypervisor
from ..ubridge.ubridge_error import UbridgeError
from .nios.nio_udp import NIOUDP
from .error import NodeError
from ..config import Config


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

        # check if the node will use uBridge or not
        server_config = Config.instance().get_section_config("Server")
        self._use_ubridge = server_config.getboolean("use_ubridge")

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
        def set_rw(operation, name, exc):
            os.chmod(name, stat.S_IWRITE)

        directory = self.project.node_working_directory(self)
        if os.path.exists(directory):
            try:
                yield from wait_run_in_executor(shutil.rmtree, directory, onerror=set_rw)
            except OSError as e:
                raise aiohttp.web.HTTPInternalServerError(text="Could not delete the node working directory: {}".format(e))

    def start(self):
        """
        Starts the node process.
        """

        raise NotImplementedError

    @asyncio.coroutine
    def stop(self):
        """
        Stop the node process.
        """
        if self._wrapper_telnet_server:
            self._wrapper_telnet_server.close()
            yield from self._wrapper_telnet_server.wait_closed()
        self.status = "stopped"

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

    @asyncio.coroutine
    def start_wrap_console(self):
        """
        Start a telnet proxy for the console allowing multiple client
        connected at the same time
        """
        if not self._wrap_console or self._console_type != "telnet":
            return
        remaining_trial = 60
        while True:
            try:
                (reader, writer) = yield from asyncio.open_connection(host="127.0.0.1", port=self._internal_console_port)
                break
            except (OSError, ConnectionRefusedError) as e:
                if remaining_trial <= 0:
                    raise e
            yield from asyncio.sleep(0.1)
            remaining_trial -= 1
        yield from AsyncioTelnetServer.write_client_intro(writer, echo=True)
        server = AsyncioTelnetServer(reader=reader, writer=writer, binary=True, echo=True)
        self._wrapper_telnet_server = yield from asyncio.start_server(server.run, self._manager.port_manager.console_host, self.console)

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
    def use_ubridge(self):
        """
        Returns if uBridge is used for this node or not

        :returns: boolean
        """

        return self._use_ubridge

    @property
    def ubridge(self):
        """
        Returns the uBridge hypervisor.

        :returns: path to uBridge
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
        path = shutil.which(path)
        return path

    @asyncio.coroutine
    def _ubridge_send(self, command):
        """
        Sends a command to uBridge hypervisor.

        :param command: command to send
        """

        if not self._ubridge_hypervisor or not self._ubridge_hypervisor.is_running():
            raise NodeError("Cannot send command '{}': uBridge is not running".format(command))
        try:
            yield from self._ubridge_hypervisor.send(command)
        except UbridgeError as e:
            raise UbridgeError("{}: {}".format(e, self._ubridge_hypervisor.read_stdout()))

    @locked_coroutine
    def _start_ubridge(self):
        """
        Starts uBridge (handles connections to and from this node).
        """

        # Prevent us to start multiple ubridge
        if self._ubridge_hypervisor and self._ubridge_hypervisor.is_running():
            return

        if self.ubridge_path is None:
            raise NodeError("uBridge is not available, path doesn't exist, or you just installed GNS3 and need to restart your user session to refresh user permissions.")

        if not self._manager.has_privileged_access(self.ubridge_path):
            raise NodeError("uBridge requires root access or the capability to interact with network adapters")

        server_config = self._manager.config.get_section_config("Server")
        server_host = server_config.get("host")
        if not self.ubridge:
            self._ubridge_hypervisor = Hypervisor(self._project, self.ubridge_path, self.working_dir, server_host)
        log.info("Starting new uBridge hypervisor {}:{}".format(self._ubridge_hypervisor.host, self._ubridge_hypervisor.port))
        yield from self._ubridge_hypervisor.start()
        if self._ubridge_hypervisor:
            log.info("Hypervisor {}:{} has successfully started".format(self._ubridge_hypervisor.host, self._ubridge_hypervisor.port))
            yield from self._ubridge_hypervisor.connect()

    @asyncio.coroutine
    def _stop_ubridge(self):
        """
        Stops uBridge.
        """

        if self._ubridge_hypervisor and self._ubridge_hypervisor.is_running():
            log.info("Stopping uBridge hypervisor {}:{}".format(self._ubridge_hypervisor.host, self._ubridge_hypervisor.port))
            yield from self._ubridge_hypervisor.stop()
        self._ubridge_hypervisor = None

    @asyncio.coroutine
    def _add_ubridge_udp_connection(self, bridge_name, source_nio, destination_nio):
        """
        Creates an UDP connection in uBridge.

        :param bridge_name: bridge name in uBridge
        :param source_nio: source NIO instance
        :param destination_nio: destination NIO instance
        """

        yield from self._ubridge_send("bridge create {name}".format(name=bridge_name))

        if not isinstance(destination_nio, NIOUDP):
            raise NodeError("Destination NIO is not UDP")

        yield from self._ubridge_send('bridge add_nio_udp {name} {lport} {rhost} {rport}'.format(name=bridge_name,
                                                                                                 lport=source_nio.lport,
                                                                                                 rhost=source_nio.rhost,
                                                                                                 rport=source_nio.rport))

        yield from self._ubridge_send('bridge add_nio_udp {name} {lport} {rhost} {rport}'.format(name=bridge_name,
                                                                                                 lport=destination_nio.lport,
                                                                                                 rhost=destination_nio.rhost,
                                                                                                 rport=destination_nio.rport))

        if destination_nio.capturing:
            yield from self._ubridge_send('bridge start_capture {name} "{pcap_file}"'.format(name=bridge_name,
                                                                                             pcap_file=destination_nio.pcap_output_file))

        yield from self._ubridge_send('bridge start {name}'.format(name=bridge_name))

    @asyncio.coroutine
    def _add_ubridge_ethernet_connection(self, bridge_name, ethernet_interface, block_host_traffic=True):
        """
        Creates a connection with an Ethernet interface in uBridge.

        :param bridge_name: bridge name in uBridge
        :param ethernet_interface: Ethernet interface name
        :param block_host_traffic: block network traffic originating from the host OS (Windows only)
        """

        if sys.platform.startswith("linux"):
            # on Linux we use RAW sockets
            yield from self._ubridge_send('bridge add_nio_linux_raw {name} "{interface}"'.format(name=bridge_name, interface=ethernet_interface))
        elif sys.platform.startswith("win"):
            # on Windows we use Winpcap/Npcap
            windows_interfaces = interfaces()
            npf_id = None
            source_mac = None
            for interface in windows_interfaces:
                # Winpcap/Npcap uses a NPF ID to identify an interface on Windows
                if "netcard" in interface and ethernet_interface in interface["netcard"]:
                    npf_id = interface["id"]
                    source_mac = interface["mac_address"]
                elif ethernet_interface in interface["name"]:
                    npf_id = interface["id"]
                    source_mac = interface["mac_address"]
            if npf_id:
                yield from self._ubridge_send('bridge add_nio_ethernet {name} "{interface}"'.format(name=bridge_name,
                                                                                                    interface=npf_id))
            else:
                raise NodeError("Could not find NPF id for interface {}".format(ethernet_interface))

            if block_host_traffic:
                if source_mac:
                    yield from self._ubridge_send('bridge set_pcap_filter {name} "not ether src {mac}"'.format(name=bridge_name, mac=source_mac))
                else:
                    log.warn("Could not block host network traffic on {} (no MAC address found)".format(ethernet_interface))
        else:
            # on other platforms we just rely on the pcap library
            yield from self._ubridge_send('bridge add_nio_ethernet {name} "{interface}"'.format(name=bridge_name, interface=ethernet_interface))

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
        percentage_left = psutil.virtual_memory().percent
        if requested_ram > available_ram:
            message = '"{}" requires {}MB of RAM to run but there is only {}MB - {}% of RAM left on "{}"'.format(self.name,
                                                                                                                 requested_ram,
                                                                                                                 available_ram,
                                                                                                                 percentage_left,
                                                                                                                 platform.node())
            self.project.emit("log.warning", {"message": message})
