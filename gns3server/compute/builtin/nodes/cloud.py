# -*- coding: utf-8 -*-
#
# Copyright (C) 2016 GNS3 Technologies Inc.
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
import subprocess

from ...error import NodeError
from ...base_node import BaseNode
from ...nios.nio_udp import NIOUDP
from ....ubridge.ubridge_error import UbridgeError

import gns3server.utils.interfaces
import gns3server.utils.asyncio

import logging
log = logging.getLogger(__name__)


class Cloud(BaseNode):

    """
    Cloud.

    :param name: name for this cloud
    :param node_id: Node identifier
    :param project: Project instance
    :param manager: Parent VM Manager
    """

    def __init__(self, name, node_id, project, manager, ports=None):

        super().__init__(name, node_id, project, manager)
        self._nios = {}
        self._remote_console_host = ""
        self._remote_console_port = 23
        self._remote_console_type = "none"
        self._remote_console_http_path = "/"

        # Populate the cloud with host interfaces if it is not configured
        if not ports or len(ports) == 0:
            self._ports_mapping = []
            for interface in self._interfaces():
                if not interface["special"]:
                    self._ports_mapping.append({
                        "interface": interface["name"],
                        "type": interface["type"],
                        "port_number": len(self._ports_mapping),
                        "name": interface["name"]
                    })
        else:
            port_number = 0
            for port in ports:
                port["port_number"] = port_number
                port_number += 1
            self._ports_mapping = ports

    @property
    def nios(self):
        return self._nios

    def _interfaces(self):
        return gns3server.utils.interfaces.interfaces()

    def __json__(self):

        host_interfaces = []
        network_interfaces = gns3server.utils.interfaces.interfaces()
        for interface in network_interfaces:
            host_interfaces.append({"name": interface["name"],
                                    "type": interface["type"],
                                    "special": interface["special"]})

        return {"name": self.name,
                "node_id": self.id,
                "project_id": self.project.id,
                "remote_console_host": self.remote_console_host,
                "remote_console_port": self.remote_console_port,
                "remote_console_type": self.remote_console_type,
                "remote_console_http_path": self.remote_console_http_path,
                "ports_mapping": self._ports_mapping,
                "interfaces": host_interfaces,
                "status": self.status,
                "node_directory": self.working_path
                }

    @property
    def remote_console_host(self):
        """
        Returns the remote console host for this cloud.

        :returns: remote console host
        """

        return self._remote_console_host

    @remote_console_host.setter
    def remote_console_host(self, remote_console_host):
        """
        Sets the remote console host for this cloud.

        :param remote_console_host: remote console host
        """

        self._remote_console_host = remote_console_host

    @property
    def remote_console_port(self):
        """
        Returns the remote console port for this cloud.

        :returns: remote console port
        """

        return self._remote_console_port

    @remote_console_port.setter
    def remote_console_port(self, remote_console_port):
        """
        Sets the remote console port for this cloud.

        :param remote_console_port: remote console port
        """

        self._remote_console_port = remote_console_port

    @property
    def remote_console_type(self):
        """
        Returns the remote console type for this cloud.

        :returns: remote console host
        """

        return self._remote_console_type

    @remote_console_type.setter
    def remote_console_type(self, remote_console_type):
        """
        Sets the remote console type for this cloud.

        :param remote_console_type: remote console type
        """

        self._remote_console_type = remote_console_type

    @property
    def remote_console_http_path(self):
        """
        Returns the remote console HTTP path for this cloud.

        :returns: remote console HTTP path
        """

        return self._remote_console_http_path

    @remote_console_http_path.setter
    def remote_console_http_path(self, remote_console_http_path):
        """
        Sets the remote console HTTP path for this cloud.

        :param remote_console_http_path: remote console HTTP path
        """

        self._remote_console_http_path = remote_console_http_path

    @property
    def ports_mapping(self):
        """
        Ports on this cloud.

        :returns: ports info
        """

        return self._ports_mapping

    @ports_mapping.setter
    def ports_mapping(self, ports):
        """
        Set the ports on this cloud.

        :param ports: ports info
        """

        if ports != self._ports_mapping:
            if len(self._nios) > 0:
                raise NodeError("Cannot modify a cloud that is already connected.")

            port_number = 0
            for port in ports:
                port["port_number"] = port_number
                port_number += 1

            self._ports_mapping = ports

    async def create(self):
        """
        Creates this cloud.
        """

        await self.start()
        log.info('Cloud "{name}" [{id}] has been created'.format(name=self._name, id=self._id))

    async def start(self):
        """
        Starts this cloud.
        """

        if self.status != "started":
            if self._ubridge_hypervisor and self._ubridge_hypervisor.is_running():
                await self._stop_ubridge()
            await self._start_ubridge()
            for port_number in self._nios:
                if self._nios[port_number]:
                    try:
                        await self._add_ubridge_connection(self._nios[port_number], port_number)
                    except (UbridgeError, NodeError) as e:
                        self.status = "stopped"
                        raise e
            self.status = "started"

    async def close(self):
        """
        Closes this cloud.
        """

        if not (await super().close()):
            return False

        for nio in self._nios.values():
            if nio and isinstance(nio, NIOUDP):
                self.manager.port_manager.release_udp_port(nio.lport, self._project)

        await self._stop_ubridge()
        log.info('Cloud "{name}" [{id}] has been closed'.format(name=self._name, id=self._id))

    async def _is_wifi_adapter_osx(self, adapter_name):
        """
        Detects a Wifi adapter on Mac.
        """

        try:
            output = await gns3server.utils.asyncio.subprocess_check_output("networksetup", "-listallhardwareports")
        except (OSError, subprocess.SubprocessError) as e:
            log.warning("Could not execute networksetup: {}".format(e))
            return False

        is_wifi = False
        for line in output.splitlines():
            if is_wifi:
                if adapter_name == line.replace("Device: ", ""):
                    return True
                is_wifi = False
            else:
                if 'Wi-Fi' in line:
                    is_wifi = True
        return False

    async def _add_ubridge_connection(self, nio, port_number):
        """
        Creates a connection in uBridge.

        :param nio: NIO instance
        :param port_number: port number
        """

        port_info = None
        for port in self._ports_mapping:
            if port["port_number"] == port_number:
                port_info = port
                break

        if not port_info:
            raise NodeError("Port {port_number} doesn't exist on cloud '{name}'".format(name=self.name,
                                                                                        port_number=port_number))

        bridge_name = "{}-{}".format(self._id, port_number)
        await self._ubridge_send("bridge create {name}".format(name=bridge_name))
        if not isinstance(nio, NIOUDP):
            raise NodeError("Source NIO is not UDP")
        await self._ubridge_send('bridge add_nio_udp {name} {lport} {rhost} {rport}'.format(name=bridge_name,
                                                                                            lport=nio.lport,
                                                                                            rhost=nio.rhost,
                                                                                            rport=nio.rport))

        await self._ubridge_apply_filters(bridge_name, nio.filters)
        if port_info["type"] in ("ethernet", "tap"):

            if not self.manager.has_privileged_access(self.ubridge_path):
                raise NodeError("uBridge requires root access or the capability to interact with Ethernet and TAP adapters")

            if sys.platform.startswith("win"):
                await self._add_ubridge_ethernet_connection(bridge_name, port_info["interface"])

            else:
                if port_info["type"] == "ethernet":
                    network_interfaces = [interface["name"] for interface in self._interfaces()]
                    if not port_info["interface"] in network_interfaces:
                        raise NodeError("Interface '{}' could not be found on this system, please update '{}'".format(port_info["interface"], self.name))

                    if sys.platform.startswith("linux"):
                        await self._add_linux_ethernet(port_info, bridge_name)
                    elif sys.platform.startswith("darwin"):
                        await self._add_osx_ethernet(port_info, bridge_name)
                    else:
                        await self._add_windows_ethernet(port_info, bridge_name)

                elif port_info["type"] == "tap":
                    await self._ubridge_send('bridge add_nio_tap {name} "{interface}"'.format(name=bridge_name, interface=port_info["interface"]))

        elif port_info["type"] == "udp":
            await self._ubridge_send('bridge add_nio_udp {name} {lport} {rhost} {rport}'.format(name=bridge_name,
                                                                                                     lport=port_info["lport"],
                                                                                                     rhost=port_info["rhost"],
                                                                                                     rport=port_info["rport"]))

        if nio.capturing:
            await self._ubridge_send('bridge start_capture {name} "{pcap_file}"'.format(name=bridge_name,
                                                                                             pcap_file=nio.pcap_output_file))

        await self._ubridge_send('bridge start {name}'.format(name=bridge_name))

    async def _add_linux_ethernet(self, port_info, bridge_name):
        """
        Connects an Ethernet interface on Linux using raw sockets.

        A TAP is used if the interface is a bridge
        """

        interface = port_info["interface"]
        if gns3server.utils.interfaces.is_interface_bridge(interface):

            network_interfaces = [interface["name"] for interface in self._interfaces()]
            i = 0
            while True:
                tap = "gns3tap{}-{}".format(i, port_info["port_number"])
                if tap not in network_interfaces:
                    break
                i += 1

            await self._ubridge_send('bridge add_nio_tap "{name}" "{interface}"'.format(name=bridge_name, interface=tap))
            await self._ubridge_send('brctl addif "{interface}" "{tap}"'.format(tap=tap, interface=interface))
        else:
            await self._ubridge_send('bridge add_nio_linux_raw {name} "{interface}"'.format(name=bridge_name, interface=interface))

    async def _add_osx_ethernet(self, port_info, bridge_name):
        """
        Connects an Ethernet interface on OSX using libpcap.
        """

        # Wireless adapters are not well supported by the libpcap on OSX
        if await self._is_wifi_adapter_osx(port_info["interface"]):
            raise NodeError("Connecting to a Wireless adapter is not supported on Mac OS")
        if port_info["interface"].startswith("vmnet"):
            # Use a special NIO to connect to VMware vmnet interfaces on OSX (libpcap doesn't support them)
            await self._ubridge_send('bridge add_nio_fusion_vmnet {name} "{interface}"'.format(name=bridge_name,
                                                                                               interface=port_info["interface"]))
            return
        if not gns3server.utils.interfaces.has_netmask(port_info["interface"]):
            raise NodeError("Interface {} has no netmask, interface down?".format(port_info["interface"]))
        await self._ubridge_send('bridge add_nio_ethernet {name} "{interface}"'.format(name=bridge_name, interface=port_info["interface"]))

    async def _add_windows_ethernet(self, port_info, bridge_name):
        """
        Connects an Ethernet interface on Windows.
        """

        if not gns3server.utils.interfaces.has_netmask(port_info["interface"]):
            raise NodeError("Interface {} has no netmask, interface down?".format(port_info["interface"]))
        await self._ubridge_send('bridge add_nio_ethernet {name} "{interface}"'.format(name=bridge_name, interface=port_info["interface"]))

    async def add_nio(self, nio, port_number):
        """
        Adds a NIO as new port on this cloud.

        :param nio: NIO instance to add
        :param port_number: port to allocate for the NIO
        """

        if port_number in self._nios:
            raise NodeError("Port {} isn't free".format(port_number))

        log.info('Cloud "{name}" [{id}]: NIO {nio} bound to port {port}'.format(name=self._name,
                                                                                id=self._id,
                                                                                nio=nio,
                                                                                port=port_number))
        try:
            await self.start()
            await self._add_ubridge_connection(nio, port_number)
            self._nios[port_number] = nio
        except (NodeError, UbridgeError) as e:
            log.error('Cannot add NIO on cloud "{name}": {error}'.format(name=self._name, error=e))
            await self._stop_ubridge()
            self.status = "stopped"
            self._nios[port_number] = nio
            self.project.emit("log.error", {"message": str(e)})

    async def update_nio(self, port_number, nio):
        """
        Update an nio on this node

        :param nio: NIO instance to add
        :param port_number: port to allocate for the NIO
        """

        bridge_name = "{}-{}".format(self._id, port_number)
        if self._ubridge_hypervisor and self._ubridge_hypervisor.is_running():
            await self._ubridge_apply_filters(bridge_name, nio.filters)

    async def _delete_ubridge_connection(self, port_number):
        """
        Deletes a connection in uBridge.

        :param port_number: adapter number
        """

        bridge_name = "{}-{}".format(self._id, port_number)
        await self._ubridge_send("bridge delete {name}".format(name=bridge_name))

    async def remove_nio(self, port_number):
        """
        Removes the specified NIO as member of cloud.

        :param port_number: allocated port number

        :returns: the NIO that was bound to the allocated port
        """

        if port_number not in self._nios:
            raise NodeError("Port {} is not allocated".format(port_number))

        await self.stop_capture(port_number)
        nio = self._nios[port_number]
        if isinstance(nio, NIOUDP):
            self.manager.port_manager.release_udp_port(nio.lport, self._project)

        log.info('Cloud "{name}" [{id}]: NIO {nio} removed from port {port}'.format(name=self._name,
                                                                                    id=self._id,
                                                                                    nio=nio,
                                                                                    port=port_number))

        del self._nios[port_number]
        if self._ubridge_hypervisor and self._ubridge_hypervisor.is_running():
            await self._delete_ubridge_connection(port_number)
        await self.start()
        return nio

    def get_nio(self, port_number):
        """
        Gets a port NIO binding.

        :param port_number: port number

        :returns: NIO instance
        """

        if not [port["port_number"] for port in self._ports_mapping if port_number == port["port_number"]]:
            raise NodeError("Port {port_number} doesn't exist on cloud '{name}'".format(name=self.name,
                                                                                        port_number=port_number))

        if port_number not in self._nios:
            raise NodeError("Port {} is not connected".format(port_number))

        nio = self._nios[port_number]

        return nio

    async def start_capture(self, port_number, output_file, data_link_type="DLT_EN10MB"):
        """
        Starts a packet capture.

        :param port_number: allocated port number
        :param output_file: PCAP destination file for the capture
        :param data_link_type: PCAP data link type (DLT_*), default is DLT_EN10MB
        """

        nio = self.get_nio(port_number)
        if nio.capturing:
            raise NodeError("Packet capture is already activated on port {port_number}".format(port_number=port_number))
        nio.start_packet_capture(output_file)
        bridge_name = "{}-{}".format(self._id, port_number)
        await self._ubridge_send('bridge start_capture {name} "{output_file}"'.format(name=bridge_name,
                                                                                           output_file=output_file))
        log.info("Cloud '{name}' [{id}]: starting packet capture on port {port_number}".format(name=self.name,
                                                                                               id=self.id,
                                                                                               port_number=port_number))

    async def stop_capture(self, port_number):
        """
        Stops a packet capture.

        :param port_number: allocated port number
        """

        nio = self.get_nio(port_number)
        if not nio.capturing:
            return
        nio.stop_packet_capture()
        bridge_name = "{}-{}".format(self._id, port_number)
        await self._ubridge_send("bridge stop_capture {name}".format(name=bridge_name))

        log.info("Cloud'{name}' [{id}]: stopping packet capture on port {port_number}".format(name=self.name,
                                                                                              id=self.id,
                                                                                              port_number=port_number))
