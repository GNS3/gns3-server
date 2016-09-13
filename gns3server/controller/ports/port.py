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

    @staticmethod
    def dataLinkTypes():
        """
        Returns the supported PCAP DLTs.

        :return: dictionary
        """
        return {"Ethernet": "DLT_EN10MB"}

    @staticmethod
    def linkType():
        return "Ethernet"

    def __json__(self):
        return {
            "name": self._name,
            "short_name": self.shortNameType() + "{}/{}".format(self._interface_number, self._port_number),
            "data_link_types": self.dataLinkTypes(),
            "port_number": self._port_number,
            "adapter_number": self._adapter_number,
            "link_type": self.linkType().lower()
        }
