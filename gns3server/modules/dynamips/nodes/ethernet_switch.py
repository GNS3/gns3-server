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

import os
from ..dynamips_error import DynamipsError

import logging
log = logging.getLogger(__name__)


class EthernetSwitch(object):
    """
    Dynamips Ethernet switch.

    :param hypervisor: Dynamips hypervisor instance
    :param name: name for this switch
    """

    _instances = []

    def __init__(self, hypervisor, name):

         # find an instance identifier (0 < id <= 4096)
        self._id = 0
        for identifier in range(1, 4097):
            if identifier not in self._instances:
                self._id = identifier
                self._instances.append(self._id)
                break

        if self._id == 0:
            raise DynamipsError("Maximum number of instances reached")

        self._hypervisor = hypervisor
        self._name = '"' + name + '"'  # put name into quotes to protect spaces
        self._hypervisor.send("ethsw create {}".format(self._name))

        log.info("Ethernet switch {name} [id={id}] has been created".format(name=self._name,
                                                                            id=self._id))

        self._hypervisor.devices.append(self)
        self._nios = {}
        self._mapping = {}

    @classmethod
    def reset(cls):
        """
        Resets the instance count and the allocated instances list.
        """

        cls._instances.clear()

    @property
    def id(self):
        """
        Returns the unique ID for this Ethernet switch.

        :returns: id (integer)
        """

        return self._id

    @property
    def name(self):
        """
        Returns the current name of this Ethernet switch.

        :returns: Ethernet switch name
        """

        return self._name[1:-1]  # remove quotes

    @name.setter
    def name(self, new_name):
        """
        Renames this Ethernet switch.

        :param new_name: New name for this switch
        """

        new_name = '"' + new_name + '"'  # put the new name into quotes to protect spaces
        self._hypervisor.send("ethsw rename {name} {new_name}".format(name=self._name,
                                                                      new_name=new_name))

        log.info("Ethernet switch {name} [id={id}]: renamed to {new_name}".format(name=self._name,
                                                                                  id=self._id,
                                                                                  new_name=new_name))

        self._name = new_name

    @property
    def hypervisor(self):
        """
        Returns the current hypervisor.

        :returns: hypervisor instance
        """

        return self._hypervisor

    def list(self):
        """
        Returns all Ethernet switches instances.

        :returns: list of all Ethernet switches
        """

        return self._hypervisor.send("ethsw list")

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

    def delete(self):
        """
        Deletes this Ethernet switch.
        """

        self._hypervisor.send("ethsw delete {}".format(self._name))

        log.info("Ethernet switch {name} [id={id}] has been deleted".format(name=self._name,
                                                                            id=self._id))
        self._hypervisor.devices.remove(self)
        self._instances.remove(self._id)

    def add_nio(self, nio, port):
        """
        Adds a NIO as new port on Ethernet switch.

        :param nio: NIO instance to add
        :param port: port to allocate for the NIO
        """

        if port in self._nios:
            raise DynamipsError("Port {} isn't free".format(port))

        self._hypervisor.send("ethsw add_nio {name} {nio}".format(name=self._name,
                                                                  nio=nio))

        log.info("Ethernet switch {name} [id={id}]: NIO {nio} bound to port {port}".format(name=self._name,
                                                                                           id=self._id,
                                                                                           nio=nio,
                                                                                           port=port))
        self._nios[port] = nio

    def remove_nio(self, port):
        """
        Removes the specified NIO as member of this Ethernet switch.

        :param port: allocated port

        :returns: the NIO that was bound to the port
        """

        if port not in self._nios:
            raise DynamipsError("Port {} is not allocated".format(port))

        nio = self._nios[port]
        self._hypervisor.send("ethsw remove_nio {name} {nio}".format(name=self._name,
                                                                     nio=nio))

        log.info("Ethernet switch {name} [id={id}]: NIO {nio} removed from port {port}".format(name=self._name,
                                                                                               id=self._id,
                                                                                               nio=nio,
                                                                                               port=port))

        del self._nios[port]

        if port in self._mapping:
            del self._mapping[port]

        return nio

    def set_access_port(self, port, vlan_id):
        """
        Sets the specified port as an ACCESS port.

        :param port: allocated port
        :param vlan_id: VLAN number membership
        """

        if port not in self._nios:
            raise DynamipsError("Port {} is not allocated".format(port))

        nio = self._nios[port]
        self._hypervisor.send("ethsw set_access_port {name} {nio} {vlan_id}".format(name=self._name,
                                                                                    nio=nio,
                                                                                    vlan_id=vlan_id))

        log.info("Ethernet switch {name} [id={id}]: port {port} set as an access port in VLAN {vlan_id}".format(name=self._name,
                                                                                                                id=self._id,
                                                                                                                port=port,
                                                                                                                vlan_id=vlan_id))
        self._mapping[port] = ("access", vlan_id)

    def set_dot1q_port(self, port, native_vlan):
        """
        Sets the specified port as a 802.1Q trunk port.

        :param port: allocated port
        :param native_vlan: native VLAN for this trunk port
        """

        if port not in self._nios:
            raise DynamipsError("Port {} is not allocated".format(port))

        nio = self._nios[port]
        self._hypervisor.send("ethsw set_dot1q_port {name} {nio} {native_vlan}".format(name=self._name,
                                                                                       nio=nio,
                                                                                       native_vlan=native_vlan))

        log.info("Ethernet switch {name} [id={id}]: port {port} set as a 802.1Q port with native VLAN {vlan_id}".format(name=self._name,
                                                                                                                        id=self._id,
                                                                                                                        port=port,
                                                                                                                        vlan_id=native_vlan))

        self._mapping[port] = ("dot1q", native_vlan)

    def set_qinq_port(self, port, outer_vlan):
        """
        Sets the specified port as a trunk (QinQ) port.

        :param port: allocated port
        :param outer_vlan: outer VLAN (transport VLAN) for this QinQ port
        """

        if port not in self._nios:
            raise DynamipsError("Port {} is not allocated".format(port))

        nio = self._nios[port]
        self._hypervisor.send("ethsw set_qinq_port {name} {nio} {outer_vlan}".format(name=self._name,
                                                                                     nio=nio,
                                                                                     outer_vlan=outer_vlan))

        log.info("Ethernet switch {name} [id={id}]: port {port} set as a QinQ port with outer VLAN {vlan_id}".format(name=self._name,
                                                                                                                       id=self._id,
                                                                                                                       port=port,
                                                                                                                       vlan_id=outer_vlan))
        self._mapping[port] = ("qinq", outer_vlan)

    def get_mac_addr_table(self):
        """
        Returns the MAC address table for this Ethernet switch.

        :returns: list of entries (Ethernet address, VLAN, NIO)
        """

        return self._hypervisor.send("ethsw show_mac_addr_table {}".format(self._name))

    def clear_mac_addr_table(self):
        """
        Clears the MAC address table for this Ethernet switch.
        """

        self._hypervisor.send("ethsw clear_mac_addr_table {}".format(self._name))

    def start_capture(self, port, output_file, data_link_type="DLT_EN10MB"):
        """
        Starts a packet capture.

        :param port: allocated port
        :param output_file: PCAP destination file for the capture
        :param data_link_type: PCAP data link type (DLT_*), default is DLT_EN10MB
        """

        if port not in self._nios:
            raise DynamipsError("Port {} is not allocated".format(port))

        nio = self._nios[port]

        data_link_type = data_link_type.lower()
        if data_link_type.startswith("dlt_"):
            data_link_type = data_link_type[4:]

        if nio.input_filter[0] is not None and nio.output_filter[0] is not None:
            raise DynamipsError("Port {} has already a filter applied".format(port))

        try:
            os.makedirs(os.path.dirname(output_file))
        except FileExistsError:
            pass
        except OSError as e:
            raise DynamipsError("Could not create captures directory {}".format(e))

        nio.bind_filter("both", "capture")
        nio.setup_filter("both", "{} {}".format(data_link_type, output_file))

        log.info("Ethernet switch {name} [id={id}]: starting packet capture on {port}".format(name=self._name,
                                                                                              id=self._id,
                                                                                              port=port))

    def stop_capture(self, port):
        """
        Stops a packet capture.

        :param port: allocated port
        """

        if port not in self._nios:
            raise DynamipsError("Port {} is not allocated".format(port))

        nio = self._nios[port]
        nio.unbind_filter("both")
        log.info("Ethernet switch {name} [id={id}]: stopping packet capture on {port}".format(name=self._name,
                                                                                              id=self._id,
                                                                                              port=port))
