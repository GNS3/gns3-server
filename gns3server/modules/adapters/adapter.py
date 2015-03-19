# -*- coding: utf-8 -*-
#
# Copyright (C) 2014 GNS3 Technologies Inc.
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


class Adapter(object):

    """
    Base class for adapters.

    :param interfaces: number of interfaces supported by this adapter.
    """

    def __init__(self, interfaces=1):

        self._interfaces = interfaces

        self._ports = {}
        for port_number in range(0, interfaces):
            self._ports[port_number] = None

    def removable(self):
        """
        Returns True if the adapter can be removed from a slot
        and False if not.

        :returns: boolean
        """

        return True

    def port_exists(self, port_number):
        """
        Checks if a port exists on this adapter.

        :returns: True is the port exists,
        False otherwise.
        """

        if port_number in self._ports:
            return True
        return False

    def add_nio(self, port_number, nio):
        """
        Adds a NIO to a port on this adapter.

        :param port_number: port number (integer)
        :param nio: NIO instance
        """

        self._ports[port_number] = nio

    def remove_nio(self, port_number):
        """
        Removes a NIO from a port on this adapter.

        :param port_number: port number (integer)
        """

        self._ports[port_number] = None

    def get_nio(self, port_number):
        """
        Returns the NIO assigned to a port.

        :params port_number: port number (integer)

        :returns: NIO instance
        """

        return self._ports[port_number]

    @property
    def ports(self):
        """
        Returns port to NIO mapping

        :returns: dictionary port -> NIO
        """

        return self._ports

    @property
    def interfaces(self):
        """
        Returns the number of interfaces supported by this adapter.

        :returns: number of interfaces
        """

        return self._interfaces
