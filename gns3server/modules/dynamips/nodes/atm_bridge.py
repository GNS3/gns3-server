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
Interface for Dynamips virtual ATM bridge module ("atm_bridge").
http://github.com/GNS3/dynamips/blob/master/README.hypervisor#L622
"""

from ..dynamips_error import DynamipsError


class ATMBridge(object):
    """
    Dynamips bridge switch.

    :param hypervisor: Dynamips hypervisor instance
    :param name: name for this switch
    """

    def __init__(self, hypervisor, name):

        #FIXME: instance tracking
        self._hypervisor = hypervisor
        self._name = '"' + name + '"'  # put name into quotes to protect spaces
        self._hypervisor.send("atm_bridge create {}".format(self._name))
        self._hypervisor.devices.append(self)
        self._nios = {}
        self._mapping = {}

    @property
    def name(self):
        """
        Returns the current name of this ATM bridge.

        :returns: ATM bridge name
        """

        return self._name[1:-1]  # remove quotes

    @name.setter
    def name(self, new_name):
        """
        Renames this ATM bridge.

        :param new_name: New name for this bridge
        """

        new_name = '"' + new_name + '"'  # put the new name into quotes to protect spaces
        self._hypervisor.send("atm_bridge rename {name} {new_name}".format(name=self._name,
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
        Returns all ATM bridge instances.

        :returns: list of all ATM bridges
        """

        return self._hypervisor.send("atm_bridge list")

    @property
    def nios(self):
        """
        Returns all the NIOs member of this ATM bridge.

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
        Deletes this ATM bridge.
        """

        self._hypervisor.send("atm_bridge delete {}".format(self._name))
        self._hypervisor.devices.remove(self)

    def add_nio(self, nio, port):
        """
        Adds a NIO as new port on ATM bridge.

        :param nio: NIO instance to add
        :param port: port to allocate for the NIO
        """

        if port in self._nios:
            raise DynamipsError("Port {} isn't free".format(port))

        self._nios[port] = nio

    def remove_nio(self, port):
        """
        Removes the specified NIO as member of this ATM switch.

        :param port: allocated port
        """

        if port not in self._nios:
            raise DynamipsError("Port {} is not allocated".format(port))

        del self._nios[port]

    def configure(self, eth_port, atm_port, atm_vpi, atm_vci):
        """
        Configures this ATM bridge.

        :param eth_port: Ethernet port
        :param atm_port: ATM port
        :param atm_vpi: ATM VPI
        :param atm_vci: ATM VCI
        """

        if eth_port not in self._nios:
            raise DynamipsError("Ethernet port {} is not allocated".format(eth_port))

        if atm_port not in self._nios:
            raise DynamipsError("ATM port {} is not allocated".format(atm_port))

        eth_nio = self._nios[eth_port]
        atm_nio = self._nios[atm_port]

        self._hypervisor.send("atm_bridge configure {name} {eth_nio} {atm_nio} {vpi} {vci}".format(name=self._name,
                                                                                                   eth_nio=eth_nio,
                                                                                                   atm_nio=atm_nio,
                                                                                                   vpi=atm_vpi,
                                                                                                   vci=atm_vci))
        self._mapping[eth_port] = (atm_port, atm_vpi, atm_vci)

    def unconfigure(self):
        """
        Unconfigures this ATM bridge.
        """

        self._hypervisor.send("atm_bridge unconfigure  {}".format(self._name))
        del self._mapping
