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
Interface for Dynamips virtual Frame-Relay switch module.
http://github.com/GNS3/dynamips/blob/master/README.hypervisor#L642
"""

from __future__ import unicode_literals
from ..dynamips_error import DynamipsError


class FrameRelaySwitch(object):
    """
    Dynamips Frame Relay switch.

    :param hypervisor: Dynamips hypervisor object
    :param name: name for this switch
    """

    def __init__(self, hypervisor, name):

        self._hypervisor = hypervisor
        self._name = '"' + name + '"'  # put name into quotes to protect spaces
        self._hypervisor.send("frsw create {}".format(self._name))
        self._hypervisor.devices.append(self)
        self._nios = {}
        self._mapping = {}

    @property
    def name(self):
        """
        Returns the current name of this Frame Relay switch.

        :returns: Frame Relay switch name
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
        Returns all Frame Relay switches instances.

        :returns: list of all Frame Relay switches
        """

        return self._hypervisor.send("frsw list")

    @property
    def nios(self):
        """
        Returns all the NIOs member of this Frame Relay switch.

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
        Renames this Frame Relay switch.

        :param new_name: New name for this switch
        """

        new_name = '"' + new_name + '"'  # put the new name into quotes to protect spaces
        self._hypervisor.send("frsw rename {name} {new_name}".format(name=self._name,
                                                                     new_name=new_name))
        self._name = new_name

    def delete(self):
        """
        Deletes this Frame Relay switch.
        """

        self._hypervisor.send("frsw delete {}".format(self._name))
        self._hypervisor.devices.remove(self)

    def add_nio(self, nio, port):
        """
        Adds a NIO as new port on Frame Relay switch.

        :param nio: NIO object to add
        :param port: port to allocate for the NIO
        """

        if port in self._nios:
            raise DynamipsError("Port {} isn't free".format(port))

        self._nios[port] = nio

    def remove_nio(self, port):
        """
        Removes the specified NIO as member of this Frame Relay switch.

        :param port: allocated port
        """

        if port not in self._nios:
            raise DynamipsError("Port {} is not allocated".format(port))

        del self._nios[port]

    def map_vc(self, port1, dlci1, port2, dlci2):
        """
        Creates a new Virtual Circuit connection (unidirectional).

        :param port1: input port
        :param dlci1: input DLCI
        :param port2: output port
        :param dlci2: output DLCI
        """

        if port1 not in self._nios:
            raise DynamipsError("Port {} is not allocated".format(port1))

        if port2 not in self._nios:
            raise DynamipsError("Port {} is not allocated".format(port2))

        nio1 = self._nios[port1]
        nio2 = self._nios[port2]

        self._hypervisor.send("frsw create_vc {name} {input_nio} {input_dlci} {output_nio} {output_dlci}".format(name=self._name,
                                                                                                                 input_nio=nio1,
                                                                                                                 input_dlci=dlci1,
                                                                                                                 output_nio=nio2,
                                                                                                                 output_dlci=dlci2))
        self._mapping[(port1, dlci1)] = (port2, dlci2)

    def unmap_vc(self, port1, dlci1, port2, dlci2):
        """
        Deletes a Virtual Circuit connection (unidirectional).

        :param port1: input port
        :param dlci1: input DLCI
        :param port2: output port
        :param dlci2: output DLCI
        """

        if port1 not in self._nios:
            raise DynamipsError("Port {} is not allocated".format(port1))

        if port2 not in self._nios:
            raise DynamipsError("Port {} is not allocated".format(port2))

        nio1 = self._nios[port1]
        nio2 = self._nios[port2]

        self._hypervisor.send("frsw delete_vc {name} {input_nio} {input_dlci} {output_nio} {output_dlci}".format(name=self._name,
                                                                                                                 input_nio=nio1,
                                                                                                                 input_dlci=dlci1,
                                                                                                                 output_nio=nio2,
                                                                                                                 output_dlci=dlci2))
        del self._mapping[(port1, dlci1)]
