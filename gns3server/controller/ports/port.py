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


class Port:
    """
    Base class for port objects.
    """

    def __init__(self, name, interface_number, adapter_number, port_number):
        self._interface_number = interface_number
        self._adapter_number = adapter_number
        self._port_number = port_number
        self._name = name

    @property
    def adapter_number(self):
        return self._adapter_number

    @property
    def port_number(self):
        return self._port_number

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

    def __json__(self):
        return {
            "name": self._name,
            "short_name": self.short_name_type + "{}/{}".format(self._interface_number, self._port_number),
            "data_link_types": self.data_link_types,
            "port_number": self._port_number,
            "adapter_number": self._adapter_number,
            "link_type": self.link_type
        }
