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

from .device import Device
from ..dynamips_error import DynamipsError


import logging
log = logging.getLogger(__name__)


class EthernetSwitch(Device):
    """
    Dynamips Ethernet switch.

    :param name: name for this switch
    :param node_id: Node instance identifier
    :param project: Project instance
    :param manager: Parent VM Manager
    :param hypervisor: Dynamips hypervisor instance
    """

    def __init__(self, name, node_id, project, manager, hypervisor=None):

        super().__init__(name, node_id, project, manager, hypervisor)
        self._nios = {}
        self._mapping = {}

    @asyncio.coroutine
    def create(self):

        if self._hypervisor is None:
            self._hypervisor = yield from self.manager.start_new_hypervisor()

        yield from self._hypervisor.send('ethsw create "{}"'.format(self._name))
        log.info('Ethernet switch "{name}" [{id}] has been created'.format(name=self._name, id=self._id))
        self._hypervisor.devices.append(self)

    @asyncio.coroutine
    def set_name(self, new_name):
        """
        Renames this Ethernet switch.

        :param new_name: New name for this switch
        """

        yield from self._hypervisor.send('ethsw rename "{name}" "{new_name}"'.format(name=self._name, new_name=new_name))
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
    def mapping(self):
        """
        Returns port mapping

        :returns: mapping list
        """

        return self._mapping

    @asyncio.coroutine
    def delete(self):
        """
        Deletes this Ethernet switch.
        """

        yield from self._hypervisor.send('ethsw delete "{}"'.format(self._name))
        log.info('Ethernet switch "{name}" [{id}] has been deleted'.format(name=self._name, id=self._id))
        self._hypervisor.devices.remove(self)
        self._instances.remove(self._id)

    @asyncio.coroutine
    def add_nio(self, nio, port_number):
        """
        Adds a NIO as new port on Ethernet switch.

        :param nio: NIO instance to add
        :param port_number: port to allocate for the NIO
        """

        if port_number in self._nios:
            raise DynamipsError("Port {} isn't free".format(port_number))

        yield from self._hypervisor.send('ethsw add_nio "{name}" {nio}'.format(name=self._name, nio=nio))

        log.info('Ethernet switch "{name}" [{id}]: NIO {nio} bound to port {port}'.format(name=self._name,
                                                                                          id=self._id,
                                                                                          nio=nio,
                                                                                          port=port_number))
        self._nios[port_number] = nio

    @asyncio.coroutine
    def remove_nio(self, port_number):
        """
        Removes the specified NIO as member of this Ethernet switch.

        :param port_number: allocated port number

        :returns: the NIO that was bound to the port
        """

        if port_number not in self._nios:
            raise DynamipsError("Port {} is not allocated".format(port_number))

        nio = self._nios[port_number]
        yield from self._hypervisor.send('ethsw remove_nio "{name}" {nio}'.format(name=self._name, nio=nio))

        log.info('Ethernet switch "{name}" [{id}]: NIO {nio} removed from port {port}'.format(name=self._name,
                                                                                              id=self._id,
                                                                                              nio=nio,
                                                                                              port=port_number))

        del self._nios[port_number]
        if port_number in self._mapping:
            del self._mapping[port_number]

        return nio

    @asyncio.coroutine
    def set_access_port(self, port_number, vlan_id):
        """
        Sets the specified port as an ACCESS port.

        :param port_number: allocated port number
        :param vlan_id: VLAN number membership
        """

        if port_number not in self._nios:
            raise DynamipsError("Port {} is not allocated".format(port_number))

        nio = self._nios[port_number]
        yield from self._hypervisor.send('ethsw set_access_port "{name}" {nio} {vlan_id}'.format(name=self._name,
                                                                                                 nio=nio,
                                                                                                 vlan_id=vlan_id))

        log.info('Ethernet switch "{name}" [{id}]: port {port} set as an access port in VLAN {vlan_id}'.format(name=self._name,
                                                                                                               id=self._id,
                                                                                                               port=port_number,
                                                                                                               vlan_id=vlan_id))
        self._mapping[port_number] = ("access", vlan_id)

    @asyncio.coroutine
    def set_dot1q_port(self, port_number, native_vlan):
        """
        Sets the specified port as a 802.1Q trunk port.

        :param port_number: allocated port number
        :param native_vlan: native VLAN for this trunk port
        """

        if port_number not in self._nios:
            raise DynamipsError("Port {} is not allocated".format(port_number))

        nio = self._nios[port_number]
        yield from self._hypervisor.send('ethsw set_dot1q_port "{name}" {nio} {native_vlan}'.format(name=self._name,
                                                                                                    nio=nio,
                                                                                                    native_vlan=native_vlan))

        log.info('Ethernet switch "{name}" [{id}]: port {port} set as a 802.1Q port with native VLAN {vlan_id}'.format(name=self._name,
                                                                                                                       id=self._id,
                                                                                                                       port=port_number,
                                                                                                                       vlan_id=native_vlan))

        self._mapping[port_number] = ("dot1q", native_vlan)

    @asyncio.coroutine
    def set_qinq_port(self, port_number, outer_vlan):
        """
        Sets the specified port as a trunk (QinQ) port.

        :param port_number: allocated port number
        :param outer_vlan: outer VLAN (transport VLAN) for this QinQ port
        """

        if port_number not in self._nios:
            raise DynamipsError("Port {} is not allocated".format(port_number))

        nio = self._nios[port_number]
        yield from self._hypervisor.send('ethsw set_qinq_port "{name}" {nio} {outer_vlan}'.format(name=self._name,
                                                                                                  nio=nio,
                                                                                                  outer_vlan=outer_vlan))

        log.info('Ethernet switch "{name}" [{id}]: port {port} set as a QinQ port with outer VLAN {vlan_id}'.format(name=self._name,
                                                                                                                    id=self._id,
                                                                                                                    port=port_number,
                                                                                                                    vlan_id=outer_vlan))
        self._mapping[port_number] = ("qinq", outer_vlan)

    @asyncio.coroutine
    def get_mac_addr_table(self):
        """
        Returns the MAC address table for this Ethernet switch.

        :returns: list of entries (Ethernet address, VLAN, NIO)
        """

        mac_addr_table = yield from self._hypervisor.send('ethsw show_mac_addr_table "{}"'.format(self._name))
        return mac_addr_table

    @asyncio.coroutine
    def clear_mac_addr_table(self):
        """
        Clears the MAC address table for this Ethernet switch.
        """

        yield from self._hypervisor.send('ethsw clear_mac_addr_table "{}"'.format(self._name))

    @asyncio.coroutine
    def start_capture(self, port_number, output_file, data_link_type="DLT_EN10MB"):
        """
        Starts a packet capture.

        :param port_number: allocated port number
        :param output_file: PCAP destination file for the capture
        :param data_link_type: PCAP data link type (DLT_*), default is DLT_EN10MB
        """

        if port_number not in self._nios:
            raise DynamipsError("Port {} is not allocated".format(port_number))

        nio = self._nios[port_number]

        data_link_type = data_link_type.lower()
        if data_link_type.startswith("dlt_"):
            data_link_type = data_link_type[4:]

        if nio.input_filter[0] is not None and nio.output_filter[0] is not None:
            raise DynamipsError("Port {} has already a filter applied".format(port_number))

        yield from nio.bind_filter("both", "capture")
        yield from nio.setup_filter("both", "{} {}".format(data_link_type, output_file))

        log.info('Ethernet switch "{name}" [{id}]: starting packet capture on {port}'.format(name=self._name,
                                                                                             id=self._id,
                                                                                             port=port_number))

    @asyncio.coroutine
    def stop_capture(self, port_number):
        """
        Stops a packet capture.

        :param port_number: allocated port number
        """

        if port_number not in self._nios:
            raise DynamipsError("Port {} is not allocated".format(port_number))

        nio = self._nios[port_number]
        yield from nio.unbind_filter("both")
        log.info('Ethernet switch "{name}" [{id}]: stopping packet capture on {port}'.format(name=self._name,
                                                                                             id=self._id,
                                                                                             port=port_number))
