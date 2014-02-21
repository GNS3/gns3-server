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


from __future__ import unicode_literals
from ..dynamips_error import DynamipsError

import logging
log = logging.getLogger(__name__)


class EthernetSwitch(object):
    """
    Dynamips Ethernet switch.

    :param hypervisor: Dynamips hypervisor object
    :param name: name for this switch
    """

    _allocated_names = []
    _instance_count = 1

    def __init__(self, hypervisor, name=None):

        # create an unique ID
        self._id = EthernetSwitch._instance_count
        EthernetSwitch._instance_count += 1

        # let's create a unique name if none has been chosen
        if not name:
            name_id = self._id
            while True:
                name = "SW" + str(name_id)
                # check if the name has already been allocated to another switch
                if name not in self._allocated_names:
                    break
                name_id += 1

        self._allocated_names.append(name)
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
        Resets the instance count and the allocated names list.
        """

        cls._instance_count = 1
        cls._allocated_names.clear()

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

        new_name_no_quotes = new_name
        new_name = '"' + new_name + '"'  # put the new name into quotes to protect spaces
        self._hypervisor.send("ethsw rename {name} {new_name}".format(name=self._name,
                                                                      new_name=new_name))

        log.info("Ethernet switch {name} [id={id}]: renamed to {new_name}".format(name=self._name,
                                                                                  id=self._id,
                                                                                  new_name=new_name))

        self._allocated_names.remove(self.name)
        self._name = new_name
        self._allocated_names.append(new_name_no_quotes)

    @property
    def hypervisor(self):
        """
        Returns the current hypervisor.

        :returns: hypervisor object
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
        self._allocated_names.remove(self.name)

    def add_nio(self, nio, port):
        """
        Adds a NIO as new port on Ethernet switch.

        :param nio: NIO object to add
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
