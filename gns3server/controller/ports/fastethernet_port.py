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

"""
FastEthernet port for Ethernet link end points.
"""

from .port import Port


class FastEthernetPort(Port):
    @staticmethod
    def long_name_type():
        """
        Returns the long name type for this port.

        :returns: string
        """

        return "FastEthernet"

    @staticmethod
    def short_name_type():
        """
        Returns the short name type for this port.

        :returns: string
        """

        return "f"
