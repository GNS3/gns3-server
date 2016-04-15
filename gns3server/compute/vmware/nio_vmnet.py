# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 GNS3 Technologies Inc.
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
Interface for VMnet NIOs.
"""

from ..nios.nio import NIO


class NIOVMNET(NIO):

    """
    VMnet NIO.
    """

    def __init__(self, vmnet):

        super().__init__()
        self._vmnet = vmnet

    @property
    def vmnet(self):
        """
        Returns vmnet interface used by this NIO.

        :returns: vmnet interface name
        """

        return self._vmnet

    def __str__(self):

        return "NIO VMNET"

    def __json__(self):

        return {"type": "nio_vmnet",
                "vmnet": self._vmnet}
