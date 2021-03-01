# -*- coding: utf-8 -*-
#
# Copyright (C) 2013 GNS3 Technologies Inc.
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
Interface for Dynamips virtual Ethernet switch module ("ethsw").
http://github.com/GNS3/dynamips/blob/master/README.hypervisor#L558
"""

import asyncio
from gns3server.utils import parse_version
#from gns3server.utils.asyncio.embed_shell import EmbedShell, create_telnet_shell


from .device import Device
from ..nios.nio_udp import NIOUDP
from ..dynamips_error import DynamipsError
from ...error import NodeError

import logging
log = logging.getLogger(__name__)


# class EthernetSwitchConsole(EmbedShell):
#     """
#     Console for the ethernet switch
#     """
#
#     def __init__(self, node):
#         super().__init__(welcome_message="Welcome to GNS3 builtin Ethernet switch.\n\nType help for available commands\n")
#         self._node = node
#
#     async def mac(self):
#         """
#         Show MAC address table
#         """
#         res = 'Port       Mac                VLAN\n'
#         result = (await self._node._hypervisor.send('ethsw show_mac_addr_table {}'.format(self._node.name)))
#         for line in result:
#             mac, vlan, nio = line.replace('  ', ' ').split(' ')
#             mac = mac.replace('.', '')
#             mac = "{}:{}:{}:{}:{}:{}".format(
#                 mac[0:2],
#                 mac[2:4],
#                 mac[4:6],
#                 mac[6:8],
#                 mac[8:10],
#                 mac[10:12])
#             for port_number, switch_nio in self._node.nios.items():
#                 if switch_nio.name == nio:
#                     res += 'Ethernet' + str(port_number) + '  ' + mac + '  ' + vlan + '\n'
#                     break
#         return res


class EthernetSwitch(Device):

    """
    Dynamips Ethernet switch.

    :param name: name for this switch
    :param node_id: Node instance identifier
    :param project: Project instance
    :param manager: Parent VM Manager
    :param ports: initial switch ports
    :param hypervisor: Dynamips hypervisor instance
    """

    def __init__(self, name, node_id, project, manager, console=None, console_type=None, ports=None, hypervisor=None):

        super().__init__(name, node_id, project, manager, hypervisor)
        self._nios = {}
        self._mappings = {}
        self._telnet_console = None
        #self._telnet_shell = None
        #self._telnet_server = None
        self._console = console
        self._console_type = console_type

        if self._console_type is None:
            self._console_type = "none"

        if self._console is not None:
            self._console = self._manager.port_manager.reserve_tcp_port(self._console, self._project)
        else:
            self._console = self._manager.port_manager.get_free_tcp_port(self._project)

        if ports is None:
            # create 8 ports by default
            self._ports = []
            for port_number in range(0, 8):
                self._ports.append({"port_number": port_number,
                                    "name": "Ethernet{}".format(port_number),
                                    "type": "access",
                                    "vlan": 1})
        else:
            self._ports = ports

    def __json__(self):

        ethernet_switch_info = {"name": self.name,
                                "console": self.console,
                                "console_type": self.console_type,
                                "node_id": self.id,
                                "project_id": self.project.id,
                                "ports_mapping": self._ports,
                                "status": "started"}

        return ethernet_switch_info

    @property
    def console(self):
        return self._console

    @console.setter
    def console(self, console):
        self._console = console

    @property
    def console_type(self):
        return self._console_type

    @console_type.setter
    def console_type(self, console_type):

        if self._console_type != console_type:
            if console_type == "telnet":
                self.project.emit("log.warning", {
                    "message": '"{name}": Telnet access for switches is not available in this version of GNS3'.format(name=self._name)})
            self._console_type = console_type

    @property
    def ports_mapping(self):
        """
        Ports on this switch

        :returns: ports info
        """

        return self._ports

    @ports_mapping.setter
    def ports_mapping(self, ports):
        """
        Set the ports on this switch

        :param ports: ports info
        """
        if ports != self._ports:
            if len(self._nios) > 0 and len(ports) != len(self._ports):
                raise NodeError("Can't modify a switch already connected.")

            port_number = 0
            for port in ports:
                port["name"] = "Ethernet{}".format(port_number)
                port["port_number"] = port_number
                port_number += 1

            self._ports = ports

    async def update_port_settings(self):
        for port_settings in self._ports:
            port_number = port_settings["port_number"]
            if port_number in self._nios and self._nios[port_number] is not None:
                await self.set_port_settings(port_number, port_settings)

    async def create(self):

        if self._hypervisor is None:
            module_workdir = self.project.module_working_directory(self.manager.module_name.lower())
            self._hypervisor = await self.manager.start_new_hypervisor(working_dir=module_workdir)

        await self._hypervisor.send('ethsw create "{}"'.format(self._name))
        log.info('Ethernet switch "{name}" [{id}] has been created'.format(name=self._name, id=self._id))

        #self._telnet_shell = EthernetSwitchConsole(self)
        #self._telnet_shell.prompt = self._name + '> '
        #self._telnet = create_telnet_shell(self._telnet_shell)
        #try:
        #    self._telnet_server = (await asyncio.start_server(self._telnet.run, self._manager.port_manager.console_host, self.console))
        #except OSError as e:
        #    self.project.emit("log.warning", {"message": "Could not start Telnet server on socket {}:{}: {}".format(self._manager.port_manager.console_host, self.console, e)})
        if self._console_type == "telnet":
            self.project.emit("log.warning", {"message": '"{name}": Telnet access for switches is not available in this version of GNS3'.format(name=self._name)})
        self._hypervisor.devices.append(self)

    async def set_name(self, new_name):
        """
        Renames this Ethernet switch.

        :param new_name: New name for this switch
        """

        await self._hypervisor.send('ethsw rename "{name}" "{new_name}"'.format(name=self._name, new_name=new_name))
        log.info('Ethernet switch "{name}" [{id}]: renamed to "{new_name}"'.format(name=self._name,
                                                                                   id=self._id,
                                                                                   new_name=new_name))
        self._name = new_name

    @property
    def nios(self):
        """
        Returns all the NIOs member of this Ethernet switch.

        :returns: nio list
        """

        return self._nios

    @property
    def mappings(self):
        """
        Returns port mappings

        :returns: mappings list
        """

        return self._mappings

    async def delete(self):
        return (await self.close())

    async def close(self):
        """
        Deletes this Ethernet switch.
        """

        #await self._telnet.close()
        #if self._telnet_server:
        #    self._telnet_server.close()

        for nio in self._nios.values():
            if nio:
                await nio.close()
        self.manager.port_manager.release_tcp_port(self._console, self._project)
        if self._hypervisor:
            try:
                await self._hypervisor.send('ethsw delete "{}"'.format(self._name))
                log.info('Ethernet switch "{name}" [{id}] has been deleted'.format(name=self._name, id=self._id))
            except DynamipsError:
                log.debug("Could not properly delete Ethernet switch {}".format(self._name))
        if self._hypervisor and self in self._hypervisor.devices:
            self._hypervisor.devices.remove(self)
        if self._hypervisor and not self._hypervisor.devices:
            await self.hypervisor.stop()
            self._hypervisor = None
        return True

    async def add_nio(self, nio, port_number):
        """
        Adds a NIO as new port on Ethernet switch.

        :param nio: NIO instance to add
        :param port_number: port to allocate for the NIO
        """

        if port_number in self._nios:
            raise DynamipsError("Port {} isn't free".format(port_number))

        await self._hypervisor.send('ethsw add_nio "{name}" {nio}'.format(name=self._name, nio=nio))

        log.info('Ethernet switch "{name}" [{id}]: NIO {nio} bound to port {port}'.format(name=self._name,
                                                                                          id=self._id,
                                                                                          nio=nio,
                                                                                          port=port_number))
        self._nios[port_number] = nio
        for port_settings in self._ports:
            if port_settings["port_number"] == port_number:
                await self.set_port_settings(port_number, port_settings)
                break

    async def remove_nio(self, port_number):
        """
        Removes the specified NIO as member of this Ethernet switch.

        :param port_number: allocated port number

        :returns: the NIO that was bound to the port
        """

        if port_number not in self._nios:
            raise DynamipsError("Port {} is not allocated".format(port_number))

        await self.stop_capture(port_number)
        nio = self._nios[port_number]
        if isinstance(nio, NIOUDP):
            self.manager.port_manager.release_udp_port(nio.lport, self._project)
        if self._hypervisor:
            await self._hypervisor.send('ethsw remove_nio "{name}" {nio}'.format(name=self._name, nio=nio))

        log.info('Ethernet switch "{name}" [{id}]: NIO {nio} removed from port {port}'.format(name=self._name,
                                                                                              id=self._id,
                                                                                              nio=nio,
                                                                                              port=port_number))

        del self._nios[port_number]
        if port_number in self._mappings:
            del self._mappings[port_number]

        return nio

    def get_nio(self, port_number):
        """
        Gets a port NIO binding.

        :param port_number: port number

        :returns: NIO instance
        """

        if port_number not in self._nios:
            raise DynamipsError("Port {} is not allocated".format(port_number))

        nio = self._nios[port_number]

        if not nio:
            raise DynamipsError("Port {} is not connected".format(port_number))

        return nio

    async def set_port_settings(self, port_number, settings):
        """
        Applies port settings to a specific port.

        :param port_number: port number to set the settings
        :param settings: port settings
        """

        if settings["type"] == "access":
            await self.set_access_port(port_number, settings["vlan"])
        elif settings["type"] == "dot1q":
            await self.set_dot1q_port(port_number, settings["vlan"])
        elif settings["type"] == "qinq":
            await self.set_qinq_port(port_number, settings["vlan"], settings.get("ethertype"))

    async def set_access_port(self, port_number, vlan_id):
        """
        Sets the specified port as an ACCESS port.

        :param port_number: allocated port number
        :param vlan_id: VLAN number membership
        """

        if port_number not in self._nios:
            raise DynamipsError("Port {} is not allocated".format(port_number))

        nio = self._nios[port_number]
        await self._hypervisor.send('ethsw set_access_port "{name}" {nio} {vlan_id}'.format(name=self._name,
                                                                                                 nio=nio,
                                                                                                 vlan_id=vlan_id))

        log.info('Ethernet switch "{name}" [{id}]: port {port} set as an access port in VLAN {vlan_id}'.format(name=self._name,
                                                                                                               id=self._id,
                                                                                                               port=port_number,
                                                                                                               vlan_id=vlan_id))
        self._mappings[port_number] = ("access", vlan_id)

    async def set_dot1q_port(self, port_number, native_vlan):
        """
        Sets the specified port as a 802.1Q trunk port.

        :param port_number: allocated port number
        :param native_vlan: native VLAN for this trunk port
        """

        if port_number not in self._nios:
            raise DynamipsError("Port {} is not allocated".format(port_number))

        nio = self._nios[port_number]
        await self._hypervisor.send('ethsw set_dot1q_port "{name}" {nio} {native_vlan}'.format(name=self._name,
                                                                                                    nio=nio,
                                                                                                    native_vlan=native_vlan))

        log.info('Ethernet switch "{name}" [{id}]: port {port} set as a 802.1Q port with native VLAN {vlan_id}'.format(name=self._name,
                                                                                                                       id=self._id,
                                                                                                                       port=port_number,
                                                                                                                       vlan_id=native_vlan))

        self._mappings[port_number] = ("dot1q", native_vlan)

    async def set_qinq_port(self, port_number, outer_vlan, ethertype):
        """
        Sets the specified port as a trunk (QinQ) port.

        :param port_number: allocated port number
        :param outer_vlan: outer VLAN (transport VLAN) for this QinQ port
        """

        if port_number not in self._nios:
            raise DynamipsError("Port {} is not allocated".format(port_number))

        nio = self._nios[port_number]
        if ethertype != "0x8100" and parse_version(self.hypervisor.version) < parse_version('0.2.16'):
            raise DynamipsError("Dynamips version required is >= 0.2.16 to change the default QinQ Ethernet type, detected version is {}".format(self.hypervisor.version))

        await self._hypervisor.send('ethsw set_qinq_port "{name}" {nio} {outer_vlan} {ethertype}'.format(name=self._name,
                                                                                                              nio=nio,
                                                                                                              outer_vlan=outer_vlan,
                                                                                                              ethertype=ethertype if ethertype != "0x8100" else ""))

        log.info('Ethernet switch "{name}" [{id}]: port {port} set as a QinQ ({ethertype}) port with outer VLAN {vlan_id}'.format(name=self._name,
                                                                                                                                  id=self._id,
                                                                                                                                  port=port_number,
                                                                                                                                  vlan_id=outer_vlan,
                                                                                                                                  ethertype=ethertype))
        self._mappings[port_number] = ("qinq", outer_vlan, ethertype)

    async def get_mac_addr_table(self):
        """
        Returns the MAC address table for this Ethernet switch.

        :returns: list of entries (Ethernet address, VLAN, NIO)
        """

        mac_addr_table = await self._hypervisor.send('ethsw show_mac_addr_table "{}"'.format(self._name))
        return mac_addr_table

    async def clear_mac_addr_table(self):
        """
        Clears the MAC address table for this Ethernet switch.
        """

        await self._hypervisor.send('ethsw clear_mac_addr_table "{}"'.format(self._name))

    async def start_capture(self, port_number, output_file, data_link_type="DLT_EN10MB"):
        """
        Starts a packet capture.

        :param port_number: allocated port number
        :param output_file: PCAP destination file for the capture
        :param data_link_type: PCAP data link type (DLT_*), default is DLT_EN10MB
        """

        nio = self.get_nio(port_number)
        data_link_type = data_link_type.lower()
        if data_link_type.startswith("dlt_"):
            data_link_type = data_link_type[4:]

        if nio.input_filter[0] is not None and nio.output_filter[0] is not None:
            raise DynamipsError("Port {} has already a filter applied".format(port_number))

        await nio.start_packet_capture(output_file, data_link_type)
        log.info('Ethernet switch "{name}" [{id}]: starting packet capture on port {port}'.format(name=self._name,
                                                                                                  id=self._id,
                                                                                                  port=port_number))

    async def stop_capture(self, port_number):
        """
        Stops a packet capture.

        :param port_number: allocated port number
        """

        nio = self.get_nio(port_number)
        if not nio.capturing:
            return
        await nio.stop_packet_capture()
        log.info('Ethernet switch "{name}" [{id}]: stopping packet capture on port {port}'.format(name=self._name,
                                                                                                  id=self._id,
                                                                                                  port=port_number))
