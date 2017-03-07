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
import asyncio
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

    def __init__(self, name, node_id, project, manager, ports=[]):

        super().__init__(name, node_id, project, manager)
        self._nios = {}
        # If the cloud is not configured we fill it with host interfaces
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
                "ports_mapping": self._ports_mapping,
                "interfaces": host_interfaces,
                "status": self.status,
                "node_directory": self.working_dir
                }

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
                raise NodeError("Can't modify a cloud already connected.")

            port_number = 0
            for port in ports:
                port["port_number"] = port_number
                port_number += 1

            self._ports_mapping = ports

    @asyncio.coroutine
    def create(self):
        """
        Creates this cloud.
        """

        yield from self.start()
        log.info('Cloud "{name}" [{id}] has been created'.format(name=self._name, id=self._id))

    @asyncio.coroutine
    def start(self):
        if self.status != "started":
            if self._ubridge_hypervisor and self._ubridge_hypervisor.is_running():
                yield from self._stop_ubridge()
            yield from self._start_ubridge()
            for port_number in self._nios:
                if self._nios[port_number]:
                    try:
                        yield from self._add_ubridge_connection(self._nios[port_number], port_number)
                    except (UbridgeError, NodeError) as e:
                        self.status = "stopped"
                        raise e
            self.status = "started"

    @asyncio.coroutine
    def close(self):
        """
        Closes this cloud.
        """

        if not (yield from super().close()):
            return False

        for nio in self._nios.values():
            if nio and isinstance(nio, NIOUDP):
                self.manager.port_manager.release_udp_port(nio.lport, self._project)

        yield from self._stop_ubridge()
        log.info('Cloud "{name}" [{id}] has been closed'.format(name=self._name, id=self._id))

    @asyncio.coroutine
    def _is_wifi_adapter_osx(self, adapter_name):

        try:
            output = yield from gns3server.utils.asyncio.subprocess_check_output("networksetup", "-listallhardwareports")
        except (FileNotFoundError, subprocess.SubprocessError) as e:
            log.warn("Could not execute networksetup: {}".format(e))
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

    @asyncio.coroutine
    def _add_ubridge_connection(self, nio, port_number):
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
        yield from self._ubridge_send("bridge create {name}".format(name=bridge_name))
        if not isinstance(nio, NIOUDP):
            raise NodeError("Source NIO is not UDP")
        yield from self._ubridge_send('bridge add_nio_udp {name} {lport} {rhost} {rport}'.format(name=bridge_name,
                                                                                                 lport=nio.lport,
                                                                                                 rhost=nio.rhost,
                                                                                                 rport=nio.rport))

        if port_info["type"] in ("ethernet", "tap"):

            if sys.platform.startswith("win"):
                yield from self._add_ubridge_ethernet_connection(bridge_name, port_info["interface"], block_host_traffic=False)

            else:

                if port_info["type"] == "ethernet":
                    network_interfaces = [interface["name"] for interface in self._interfaces()]
                    if not port_info["interface"] in network_interfaces:
                        raise NodeError("Interface '{}' could not be found on this system".format(port_info["interface"]))

                    if sys.platform.startswith("linux"):
                        yield from self._add_linux_ethernet(port_info, bridge_name)
                    elif sys.platform.startswith("darwin"):
                        yield from self._add_osx_ethernet(port_info, bridge_name)
                    else:
                        yield from self._add_windows_ethernet(port_info, bridge_name)

                elif port_info["type"] == "tap":
                    yield from self._ubridge_send('bridge add_nio_tap {name} "{interface}"'.format(name=bridge_name, interface=port_info["interface"]))

        elif port_info["type"] == "udp":
            yield from self._ubridge_send('bridge add_nio_udp {name} {lport} {rhost} {rport}'.format(name=bridge_name,
                                                                                                     lport=port_info["lport"],
                                                                                                     rhost=port_info["rhost"],
                                                                                                     rport=port_info["rport"]))

        if nio.capturing:
            yield from self._ubridge_send('bridge start_capture {name} "{pcap_file}"'.format(name=bridge_name,
                                                                                             pcap_file=nio.pcap_output_file))

        yield from self._ubridge_send('bridge start {name}'.format(name=bridge_name))

    @asyncio.coroutine
    def _add_linux_ethernet(self, port_info, bridge_name):
        """
        Use raw sockets on Linux.

        If interface is a bridge we connect a tap to it
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

            yield from self._ubridge_send('bridge add_nio_tap "{name}" "{interface}"'.format(name=bridge_name, interface=tap))
            yield from self._ubridge_send('brctl addif "{interface}" "{tap}"'.format(tap=tap, interface=interface))
        else:
            yield from self._ubridge_send('bridge add_nio_linux_raw {name} "{interface}"'.format(name=bridge_name, interface=interface))

    @asyncio.coroutine
    def _add_osx_ethernet(self, port_info, bridge_name):
        # Wireless adapters are not well supported by the libpcap on OSX
        if (yield from self._is_wifi_adapter_osx(port_info["interface"])):
            raise NodeError("Connecting to a Wireless adapter is not supported on Mac OS")
        if port_info["interface"].startswith("vmnet"):
            # Use a special NIO to connect to VMware vmnet interfaces on OSX (libpcap doesn't support them)
            yield from self._ubridge_send('bridge add_nio_fusion_vmnet {name} "{interface}"'.format(name=bridge_name,
                                                                                                    interface=port_info["interface"]))
            return
        if not gns3server.utils.interfaces.has_netmask(port_info["interface"]):
            raise NodeError("Interface {} has no netmask, interface down?".format(port_info["interface"]))
        yield from self._ubridge_send('bridge add_nio_ethernet {name} "{interface}"'.format(name=bridge_name, interface=port_info["interface"]))

    @asyncio.coroutine
    def _add_windows_ethernet(self, port_info, bridge_name):
        if not gns3server.utils.interfaces.has_netmask(port_info["interface"]):
            raise NodeError("Interface {} has no netmask, interface down?".format(port_info["interface"]))
        yield from self._ubridge_send('bridge add_nio_ethernet {name} "{interface}"'.format(name=bridge_name, interface=port_info["interface"]))

    @asyncio.coroutine
    def add_nio(self, nio, port_number):
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
            yield from self.start()
            yield from self._add_ubridge_connection(nio, port_number)
            self._nios[port_number] = nio
        except NodeError as e:
            self.project.emit("log.error", {"message": str(e)})
            yield from self._stop_ubridge()
            self.status = "stopped"
            self._nios[port_number] = nio
        # Cleanup stuff
        except UbridgeError as e:
            self.project.emit("log.error", {"message": str(e)})
            yield from self._stop_ubridge()
            self.status = "stopped"
            self._nios[port_number] = nio

    @asyncio.coroutine
    def _delete_ubridge_connection(self, port_number):
        """
        Deletes a connection in uBridge.

        :param port_number: adapter number
        """

        bridge_name = "{}-{}".format(self._id, port_number)
        yield from self._ubridge_send("bridge delete {name}".format(name=bridge_name))

    @asyncio.coroutine
    def remove_nio(self, port_number):
        """
        Removes the specified NIO as member of cloud.

        :param port_number: allocated port number

        :returns: the NIO that was bound to the allocated port
        """

        if port_number not in self._nios:
            raise NodeError("Port {} is not allocated".format(port_number))

        nio = self._nios[port_number]
        if isinstance(nio, NIOUDP):
            self.manager.port_manager.release_udp_port(nio.lport, self._project)

        log.info('Cloud "{name}" [{id}]: NIO {nio} removed from port {port}'.format(name=self._name,
                                                                                    id=self._id,
                                                                                    nio=nio,
                                                                                    port=port_number))

        del self._nios[port_number]
        if self._ubridge_hypervisor and self._ubridge_hypervisor.is_running():
            yield from self._delete_ubridge_connection(port_number)
        yield from self.start()
        return nio

    @asyncio.coroutine
    def start_capture(self, port_number, output_file, data_link_type="DLT_EN10MB"):
        """
        Starts a packet capture.

        :param port_number: allocated port number
        :param output_file: PCAP destination file for the capture
        :param data_link_type: PCAP data link type (DLT_*), default is DLT_EN10MB
        """

        if not [port["port_number"] for port in self._ports_mapping if port_number == port["port_number"]]:
            raise NodeError("Port {port_number} doesn't exist on cloud '{name}'".format(name=self.name,
                                                                                        port_number=port_number))

        if port_number not in self._nios:
            raise NodeError("Port {} is not connected".format(port_number))

        nio = self._nios[port_number]

        if nio.capturing:
            raise NodeError("Packet capture is already activated on port {port_number}".format(port_number=port_number))
        nio.startPacketCapture(output_file)
        bridge_name = "{}-{}".format(self._id, port_number)
        yield from self._ubridge_send('bridge start_capture {name} "{output_file}"'.format(name=bridge_name,
                                                                                           output_file=output_file))
        log.info("Cloud '{name}' [{id}]: starting packet capture on port {port_number}".format(name=self.name,
                                                                                               id=self.id,
                                                                                               port_number=port_number))

    @asyncio.coroutine
    def stop_capture(self, port_number):
        """
        Stops a packet capture.

        :param port_number: allocated port number
        """

        if not [port["port_number"] for port in self._ports_mapping if port_number == port["port_number"]]:
            raise NodeError("Port {port_number} doesn't exist on cloud '{name}'".format(name=self.name,
                                                                                        port_number=port_number))

        if port_number not in self._nios:
            raise NodeError("Port {} is not connected".format(port_number))

        nio = self._nios[port_number]
        nio.stopPacketCapture()
        bridge_name = "{}-{}".format(self._id, port_number)
        yield from self._ubridge_send("bridge stop_capture {name}".format(name=bridge_name))

        log.info("Cloud'{name}' [{id}]: stopping packet capture on port {port_number}".format(name=self.name,
                                                                                              id=self.id,
                                                                                              port_number=port_number))
