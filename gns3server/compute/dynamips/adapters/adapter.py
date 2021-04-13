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


class Adapter:

    """
    Base class for adapters.

    :param interfaces: number of interfaces supported by this adapter.
    :param wics: number of wics supported by this adapter.
    """

    def __init__(self, interfaces=0, wics=0):

        self._interfaces = interfaces
        self._ports = {}
        for port_number in range(0, interfaces):
            self._ports[port_number] = None
        self._wics = wics * [None]

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

    def wic_slot_available(self, wic_slot_id):
        """
        Checks if a WIC slot is available

        :returns: True is the WIC slot is available,
        False otherwise.
        """

        if self._wics[wic_slot_id] is None:
            return True
        return False

    def install_wic(self, wic_slot_id, wic):
        """
        Installs a WIC on this adapter.

        :param wic_slot_id: WIC slot ID (integer)
        :param wic: WIC instance
        """

        self._wics[wic_slot_id] = wic

        # Dynamips WICs ports start on a multiple of 16 + port number
        # WIC1 port 1 = 16, WIC1 port 2 = 17
        # WIC2 port 1 = 32, WIC2 port 2 = 33
        # WIC3 port 1 = 48, WIC3 port 2 = 49
        base = 16 * (wic_slot_id + 1)
        for wic_port in range(0, wic.interfaces):
            port_number = base + wic_port
            self._ports[port_number] = None

    def uninstall_wic(self, wic_slot_id):
        """
        Removes a WIC from this adapter.

        :param wic_slot_id: WIC slot ID (integer)
        """

        wic = self._wics[wic_slot_id]

        # Dynamips WICs ports start on a multiple of 16 + port number
        # WIC1 port 1 = 16, WIC1 port 2 = 17
        # WIC2 port 1 = 32, WIC2 port 2 = 33
        # WIC3 port 1 = 48, WIC3 port 2 = 49
        base = 16 * (wic_slot_id + 1)
        for wic_port in range(0, wic.interfaces):
            port_number = base + wic_port
            del self._ports[port_number]
        self._wics[wic_slot_id] = None

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

    @property
    def wics(self):
        """
        Returns the wics adapters inserted in this adapter.

        :returns: list WIC instances
        """

        return self._wics
