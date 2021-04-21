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


class Port:
    """
    Base class for port objects.
    """

    def __init__(self, name, interface_number, adapter_number, port_number, short_name=None):
        self._interface_number = interface_number
        self._adapter_number = adapter_number
        self._port_number = port_number
        self._name = name
        self._short_name = short_name
        self._adapter_type = None
        self._mac_address = None
        self._link = None

    @property
    def link(self):
        """
        Link connected to the port
        """
        return self._link

    @link.setter
    def link(self, val):
        self._link = val

    @property
    def adapter_number(self):
        return self._adapter_number

    @property
    def port_number(self):
        return self._port_number

    @property
    def adapter_type(self):
        return self._adapter_type

    @adapter_type.setter
    def adapter_type(self, val):
        self._adapter_type = val

    @property
    def mac_address(self):
        return self._mac_address

    @mac_address.setter
    def mac_address(self, val):
        self._mac_address = val

    @property
    def data_link_types(self):
        """
        Returns the supported PCAP DLTs.

        :return: dictionary
        """
        return {"Ethernet": "DLT_EN10MB"}

    @property
    def link_type(self):
        return "ethernet"

    @property
    def short_name(self):
        # If port name format has changed we use the port name as the short name (1.X behavior)
        if self._short_name:
            return self._short_name
        elif "/" in self._name:
            return self._name.replace(self.long_name_type(), self.short_name_type())
        elif self._name.startswith(f"{self.long_name_type()}{self._interface_number}"):
            return self.short_name_type() + f"{self._interface_number}"
        return self._name

    @short_name.setter
    def short_name(self, val):
        self._short_name = val

    def asdict(self):
        info = {
            "name": self._name,
            "short_name": self.short_name,
            "data_link_types": self.data_link_types,
            "port_number": self._port_number,
            "adapter_number": self._adapter_number,
            "link_type": self.link_type,
        }
        if self._adapter_type:
            info["adapter_type"] = self._adapter_type
        if self._mac_address:
            info["mac_address"] = self._mac_address
        return info
