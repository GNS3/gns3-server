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
Interface for Dynamips virtual ATM switch module ("atmsw").
http://github.com/GNS3/dynamips/blob/master/README.hypervisor#L593
"""

from __future__ import unicode_literals
from ..dynamips_error import DynamipsError


class ATMSwitch(object):
    """
    Dynamips ATM switch.

    :param hypervisor: Dynamips hypervisor object
    :param name: name for this switch
    """

    def __init__(self, hypervisor, name):

        self._hypervisor = hypervisor
        self._name = '"' + name + '"'  # put name into quotes to protect spaces
        self._hypervisor.send("atmsw create {}".format(self._name))
        self._hypervisor.devices.append(self)
        self._nios = {}
        self._mapping = {}

    @property
    def name(self):
        """
        Returns the current name of this ATM switch.

        :returns: ATM switch name
        """

        return self._name[1:-1]  # remove quotes

    @property
    def hypervisor(self):
        """
        Returns the current hypervisor.

        :returns: hypervisor object
        """

        return self._hypervisor

    def list(self):
        """
        Returns all ATM switches instances.

        :returns: list of all ATM switches
        """

        return self._hypervisor.send("atmsw list")

    @property
    def nios(self):
        """
        Returns all the NIOs member of this ATM switch.

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

    def rename(self, new_name):
        """
        Renames this ATM switch.

        :param new_name: New name for this switch
        """

        new_name = '"' + new_name + '"'  # put the new name into quotes to protect spaces
        self._hypervisor.send("atmsw rename {name} {new_name}".format(name=self._name,
                                                                      new_name=new_name))
        self._name = new_name

    def delete(self):
        """
        Deletes this ATM switch.
        """

        self._hypervisor.send("atmsw delete {}".format(self._name))
        self._hypervisor.devices.remove(self)

    def add_nio(self, nio, port):
        """
        Adds a NIO as new port on ATM switch.

        :param nio: NIO object to add
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

    def map_vp(self, port1, vpi1, port2, vpi2):
        """
        Creates a new Virtual Path connection.

        :param port1: input port
        :param vpi1: input vpi
        :param port2: output port
        :param vpi2: output vpi
        """

        if port1 not in self._nios:
            raise DynamipsError("Port {} is not allocated".format(port1))

        if port2 not in self._nios:
            raise DynamipsError("Port {} is not allocated".format(port2))

        nio1 = self._nios[port1]
        nio2 = self._nios[port2]

        self._hypervisor.send("atmsw create_vpc {name} {input_nio} {input_vpi} {output_nio} {output_vpi}".format(name=self._name,
                                                                                                                 input_nio=nio1,
                                                                                                                 input_vpi=vpi1,
                                                                                                                 output_nio=nio2,
                                                                                                                 output_vpi=vpi2))
        self._mapping[(port1, vpi1)] = (port2, vpi2)

    def unmap_vp(self, port1, vpi1, port2, vpi2):
        """
        Deletes a new Virtual Path connection.

        :param port1: input port
        :param vpi1: input vpi
        :param port2: output port
        :param vpi2: output vpi
        """

        if port1 not in self._nios:
            raise DynamipsError("Port {} is not allocated".format(port1))

        if port2 not in self._nios:
            raise DynamipsError("Port {} is not allocated".format(port2))

        nio1 = self._nios[port1]
        nio2 = self._nios[port2]

        self._hypervisor.send("atmsw delete_vpc {name} {input_nio} {input_vpi} {output_nio} {output_vpi}".format(name=self._name,
                                                                                                                 input_nio=nio1,
                                                                                                                 input_vpi=vpi1,
                                                                                                                 output_nio=nio2,
                                                                                                                 output_vpi=vpi2))
        del self._mapping[(port1, vpi1)]

    def map_pvc(self, port1, vpi1, vci1, port2, vpi2, vci2):
        """
        Creates a new Virtual Channel connection (unidirectional).

        :param port1: input port
        :param vpi1: input vpi
        :param vci1: input vci
        :param port2: output port
        :param vpi2: output vpi
        :param vci2: output vci
        """

        if port1 not in self._nios:
            raise DynamipsError("Port {} is not allocated".format(port1))

        if port2 not in self._nios:
            raise DynamipsError("Port {} is not allocated".format(port2))

        nio1 = self._nios[port1]
        nio2 = self._nios[port2]

        self._hypervisor.send("atmsw create_vcc {name} {input_nio} {input_vpi} {input_vci} {output_nio} {output_vpi} {output_vci}".format(name=self._name,
                                                                                                                                          input_nio=nio1,
                                                                                                                                          input_vpi=vpi1,
                                                                                                                                          input_vci=vci1,
                                                                                                                                          output_nio=nio2,
                                                                                                                                          output_vpi=vpi2,
                                                                                                                                          output_vci=vci2))
        self._mapping[(port1, vpi1, vci1)] = (port2, vpi2, vci2)

    def unmap_pvc(self, port1, vpi1, vci1, port2, vpi2, vci2):
        """
        Deletes a new Virtual Channel connection (unidirectional).

        :param port1: input port
        :param vpi1: input vpi
        :param vci1: input vci
        :param port2: output port
        :param vpi2: output vpi
        :param vci2: output vci
        """

        if port1 not in self._nios:
            raise DynamipsError("Port {} is not allocated".format(port1))

        if port2 not in self._nios:
            raise DynamipsError("Port {} is not allocated".format(port2))

        nio1 = self._nios[port1]
        nio2 = self._nios[port2]

        self._hypervisor.send("atmsw delete_vcc {name} {input_nio} {input_vpi} {input_vci} {output_nio} {output_vpi} {output_vci}".format(name=self._name,
                                                                                                                                          input_nio=nio1,
                                                                                                                                          input_vpi=vpi1,
                                                                                                                                          input_vci=vci1,
                                                                                                                                          output_nio=nio2,
                                                                                                                                          output_vpi=vpi2,
                                                                                                                                          output_vci=vci2))
        del self._mapping[(port1, vpi1, vci1)]
