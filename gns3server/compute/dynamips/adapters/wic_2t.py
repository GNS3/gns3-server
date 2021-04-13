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


class WIC_2T:

    """
    WIC-2T Serial
    """

    def __init__(self):

        self._interfaces = 2

    def __str__(self):

        return "WIC-2T"

    @property
    def interfaces(self):
        """
        Returns the number of interfaces supported by this WIC.

        :returns: number of interfaces
        """

        return self._interfaces
