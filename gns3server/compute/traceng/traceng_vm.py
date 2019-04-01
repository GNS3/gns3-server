# -*- coding: utf-8 -*-
#
# Copyright (C) 2018 GNS3 Technologies Inc.
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

"""
TraceNG VM management  in order to run a TraceNG VM.
"""

import sys
import os
import socket
import subprocess
import asyncio
import shutil
import ipaddress

from gns3server.utils.asyncio import wait_for_process_termination
from gns3server.utils.asyncio import monitor_process

from .traceng_error import TraceNGError
from ..adapters.ethernet_adapter import EthernetAdapter
from ..nios.nio_udp import NIOUDP
from ..base_node import BaseNode


import logging
log = logging.getLogger(__name__)


class TraceNGVM(BaseNode):
    module_name = 'traceng'

    """
    TraceNG VM implementation.

    :param name: TraceNG VM name
    :param node_id: Node identifier
    :param project: Project instance
    :param manager: Manager instance
    :param console: TCP console port
    """

    def __init__(self, name, node_id, project, manager, console=None, console_type="none"):

        super().__init__(name, node_id, project, manager, console=console, console_type=console_type)
        self._process = None
        self._started = False
        self._ip_address = None
        self._default_destination = None
        self._destination = None
        self._local_udp_tunnel = None
        self._ethernet_adapter = EthernetAdapter()  # one adapter with 1 Ethernet interface

    @property
    def ethernet_adapter(self):
        return self._ethernet_adapter

    async def close(self):
        """
        Closes this TraceNG VM.
        """

        if not (await super().close()):
            return False

        nio = self._ethernet_adapter.get_nio(0)
        if isinstance(nio, NIOUDP):
            self.manager.port_manager.release_udp_port(nio.lport, self._project)

        if self._local_udp_tunnel:
            self.manager.port_manager.release_udp_port(self._local_udp_tunnel[0].lport, self._project)
            self.manager.port_manager.release_udp_port(self._local_udp_tunnel[1].lport, self._project)
            self._local_udp_tunnel = None

        await self._stop_ubridge()

        if self.is_running():
            self._terminate_process()

        return True

    async def _check_requirements(self):
        """
        Check if TraceNG is available.
        """

        path = self._traceng_path()
        if not path:
            raise TraceNGError("No path to a TraceNG executable has been set")

        # This raise an error if ubridge is not available
        self.ubridge_path

        if not os.path.isfile(path):
            raise TraceNGError("TraceNG program '{}' is not accessible".format(path))

        if not os.access(path, os.X_OK):
            raise TraceNGError("TraceNG program '{}' is not executable".format(path))

    def __json__(self):

        return {"name": self.name,
                "ip_address": self.ip_address,
                "default_destination": self._default_destination,
                "node_id": self.id,
                "node_directory": self.working_path,
                "status": self.status,
                "console": self._console,
                "console_type": "none",
                "project_id": self.project.id,
                "command_line": self.command_line}

    def _traceng_path(self):
        """
        Returns the TraceNG executable path.

        :returns: path to TraceNG
        """

        search_path = self._manager.config.get_section_config("TraceNG").get("traceng_path", "traceng")
        path = shutil.which(search_path)
        # shutil.which return None if the path doesn't exists
        if not path:
            return search_path
        return path

    @property
    def ip_address(self):
        """
        Returns the IP address for this node.

        :returns: IP address
        """

        return self._ip_address

    @ip_address.setter
    def ip_address(self, ip_address):
        """
        Sets the IP address of this node.

        :param ip_address: IP address
        """

        try:
            if ip_address:
                ipaddress.IPv4Address(ip_address)
        except ipaddress.AddressValueError:
            raise TraceNGError("Invalid IP address: {}\n".format(ip_address))

        self._ip_address = ip_address
        log.info("{module}: {name} [{id}] set IP address to {ip_address}".format(module=self.manager.module_name,
                                                                                name=self.name,
                                                                                id=self.id,
                                                                                ip_address=ip_address))

    @property
    def default_destination(self):
        """
        Returns the default destination IP/host for this node.

        :returns: destination IP/host
        """

        return self._default_destination

    @default_destination.setter
    def default_destination(self, destination):
        """
        Sets the destination IP/host for this node.

        :param destination: destination IP/host
        """

        self._default_destination = destination
        log.info("{module}: {name} [{id}] set default destination to {destination}".format(module=self.manager.module_name,
                                                                                           name=self.name,
                                                                                           id=self.id,
                                                                                           destination=destination))

    async def start(self, destination=None):
        """
        Starts the TraceNG process.
        """

        if not sys.platform.startswith("win"):
            raise TraceNGError("Sorry, TraceNG can only run on Windows")
        await self._check_requirements()
        if not self.is_running():
            nio = self._ethernet_adapter.get_nio(0)
            command = self._build_command(destination)
            await self._stop_ubridge()  # make use we start with a fresh uBridge instance
            try:
                log.info("Starting TraceNG: {}".format(command))
                flags = 0
                if hasattr(subprocess, "CREATE_NEW_CONSOLE"):
                    flags = subprocess.CREATE_NEW_CONSOLE
                self.command_line = ' '.join(command)
                self._process = await asyncio.create_subprocess_exec(*command,
                                                                          cwd=self.working_dir,
                                                                          creationflags=flags)
                monitor_process(self._process, self._termination_callback)

                await self._start_ubridge()
                if nio:
                    await self.add_ubridge_udp_connection("TraceNG-{}".format(self._id), self._local_udp_tunnel[1], nio)

                log.info("TraceNG instance {} started PID={}".format(self.name, self._process.pid))
                self._started = True
                self.status = "started"
            except (OSError, subprocess.SubprocessError) as e:
                log.error("Could not start TraceNG {}: {}\n".format(self._traceng_path(), e))
                raise TraceNGError("Could not start TraceNG {}: {}\n".format(self._traceng_path(), e))

    def _termination_callback(self, returncode):
        """
        Called when the process has stopped.

        :param returncode: Process returncode
        """

        if self._started:
            log.info("TraceNG process has stopped, return code: %d", returncode)
            self._started = False
            self.status = "stopped"
            self._process = None
            if returncode != 0:
                self.project.emit("log.error", {"message": "TraceNG process has stopped, return code: {}\n".format(returncode)})

    async def stop(self):
        """
        Stops the TraceNG process.
        """

        await self._stop_ubridge()
        if self.is_running():
            self._terminate_process()
            if self._process.returncode is None:
                try:
                    await wait_for_process_termination(self._process, timeout=3)
                except asyncio.TimeoutError:
                    if self._process.returncode is None:
                        try:
                            self._process.kill()
                        except OSError as e:
                            log.error("Cannot stop the TraceNG process: {}".format(e))
                        if self._process.returncode is None:
                            log.warning('TraceNG VM "{}" with PID={} is still running'.format(self._name, self._process.pid))

        self._process = None
        self._started = False
        await super().stop()

    async def reload(self):
        """
        Reloads the TraceNG process (stop & start).
        """

        await self.stop()
        await self.start(self._destination)

    def _terminate_process(self):
        """
        Terminate the process if running
        """

        log.info("Stopping TraceNG instance {} PID={}".format(self.name, self._process.pid))
        #if sys.platform.startswith("win32"):
        #    self._process.send_signal(signal.CTRL_BREAK_EVENT)
        #else:
        try:
            self._process.terminate()
        # Sometime the process may already be dead when we garbage collect
        except ProcessLookupError:
            pass

    def is_running(self):
        """
        Checks if the TraceNG process is running

        :returns: True or False
        """

        if self._process and self._process.returncode is None:
            return True
        return False

    async def port_add_nio_binding(self, port_number, nio):
        """
        Adds a port NIO binding.

        :param port_number: port number
        :param nio: NIO instance to add to the slot/port
        """

        if not self._ethernet_adapter.port_exists(port_number):
            raise TraceNGError("Port {port_number} doesn't exist in adapter {adapter}".format(adapter=self._ethernet_adapter,
                                                                                           port_number=port_number))

        if self.is_running():
            await self.add_ubridge_udp_connection("TraceNG-{}".format(self._id), self._local_udp_tunnel[1], nio)

        self._ethernet_adapter.add_nio(port_number, nio)
        log.info('TraceNG "{name}" [{id}]: {nio} added to port {port_number}'.format(name=self._name,
                                                                                     id=self.id,
                                                                                     nio=nio,
                                                                                     port_number=port_number))

        return nio

    async def port_update_nio_binding(self, port_number, nio):
        """
        Updates a port NIO binding.

        :param port_number: port number
        :param nio: NIO instance to update on the slot/port
        """

        if not self._ethernet_adapter.port_exists(port_number):
            raise TraceNGError("Port {port_number} doesn't exist on adapter {adapter}".format(adapter=self._ethernet_adapter,
                                                                                              port_number=port_number))
        if self.is_running():
            await self.update_ubridge_udp_connection("TraceNG-{}".format(self._id), self._local_udp_tunnel[1], nio)

    async def port_remove_nio_binding(self, port_number):
        """
        Removes a port NIO binding.

        :param port_number: port number

        :returns: NIO instance
        """

        if not self._ethernet_adapter.port_exists(port_number):
            raise TraceNGError("Port {port_number} doesn't exist in adapter {adapter}".format(adapter=self._ethernet_adapter,
                                                                                              port_number=port_number))

        await self.stop_capture(port_number)
        if self.is_running():
            await self._ubridge_send("bridge delete {name}".format(name="TraceNG-{}".format(self._id)))

        nio = self._ethernet_adapter.get_nio(port_number)
        if isinstance(nio, NIOUDP):
            self.manager.port_manager.release_udp_port(nio.lport, self._project)
        self._ethernet_adapter.remove_nio(port_number)

        log.info('TraceNG "{name}" [{id}]: {nio} removed from port {port_number}'.format(name=self._name,
                                                                                         id=self.id,
                                                                                         nio=nio,
                                                                                         port_number=port_number))
        return nio

    def get_nio(self, port_number):
        """
        Gets a port NIO binding.

        :param port_number: port number

        :returns: NIO instance
        """

        if not self._ethernet_adapter.port_exists(port_number):
            raise TraceNGError("Port {port_number} doesn't exist on adapter {adapter}".format(adapter=self._ethernet_adapter,
                                                                                              port_number=port_number))
        nio = self._ethernet_adapter.get_nio(port_number)
        if not nio:
            raise TraceNGError("Port {} is not connected".format(port_number))
        return nio

    async def start_capture(self, port_number, output_file):
        """
        Starts a packet capture.

        :param port_number: port number
        :param output_file: PCAP destination file for the capture
        """

        nio = self.get_nio(port_number)
        if nio.capturing:
            raise TraceNGError("Packet capture is already activated on port {port_number}".format(port_number=port_number))

        nio.start_packet_capture(output_file)
        if self.ubridge:
            await self._ubridge_send('bridge start_capture {name} "{output_file}"'.format(name="TraceNG-{}".format(self._id),
                                                                                               output_file=output_file))

        log.info("TraceNG '{name}' [{id}]: starting packet capture on port {port_number}".format(name=self.name,
                                                                                                 id=self.id,
                                                                                                 port_number=port_number))

    async def stop_capture(self, port_number):
        """
        Stops a packet capture.

        :param port_number: port number
        """

        nio = self.get_nio(port_number)
        if not nio.capturing:
            return

        nio.stop_packet_capture()
        if self.ubridge:
            await self._ubridge_send('bridge stop_capture {name}'.format(name="TraceNG-{}".format(self._id)))

        log.info("TraceNG '{name}' [{id}]: stopping packet capture on port {port_number}".format(name=self.name,
                                                                                                 id=self.id,
                                                                                                 port_number=port_number))

    def _build_command(self, destination):
        """
        Command to start the TraceNG process.
        (to be passed to subprocess.Popen())
        """

        if not destination:
            # use the default destination if no specific destination provided
            destination = self.default_destination
        if not destination:
            raise TraceNGError("Please provide a host or IP address to trace")
        if not self.ip_address:
            raise TraceNGError("Please configure an IP address for this TraceNG node")
        if self.ip_address == destination:
            raise TraceNGError("Destination cannot be the same as the IP address")

        self._destination = destination
        command = [self._traceng_path()]
        # use the local UDP tunnel to uBridge instead
        if not self._local_udp_tunnel:
            self._local_udp_tunnel = self._create_local_udp_tunnel()
        nio = self._local_udp_tunnel[0]
        if nio and isinstance(nio, NIOUDP):
            # UDP tunnel
            command.extend(["-u"])  # enable UDP tunnel
            command.extend(["-c", str(nio.lport)])  # source UDP port
            command.extend(["-v", str(nio.rport)])  # destination UDP port
            try:
                command.extend(["-b", socket.gethostbyname(nio.rhost)])  # destination host, we need to resolve the hostname because TraceNG doesn't support it
            except socket.gaierror as e:
                raise TraceNGError("Can't resolve hostname {}: {}".format(nio.rhost, e))

        command.extend(["-s", "ICMP"])  # Use ICMP probe type by default
        command.extend(["-f", self._ip_address])  # source IP address to trace from
        command.extend([destination])  # host or IP to trace
        return command
