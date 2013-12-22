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
Interface for Dynamips virtual Cisco 2691 instances module ("c2691")
http://github.com/GNS3/dynamips/blob/master/README.hypervisor#L387
"""

from __future__ import unicode_literals
from .router import Router
from ..adapters.gt96100_fe import GT96100_FE


class C2691(Router):
    """
    Dynamips c2691 router.

    :param hypervisor: Dynamips hypervisor object
    :param name: name for this router
    """

    def __init__(self, hypervisor, name):
        Router.__init__(self, hypervisor, name, platform="c2691")

        # Set default values for this platform
        self._ram = 128
        self._nvram = 112
        self._disk0 = 16
        self._disk1 = 0
        self._iomem = 5  # percentage
        self._clock_divisor = 8

        self._create_slots(2)
        self._slots[0] = GT96100_FE()

    def list(self):
        """
        Returns all c2691 instances

        :returns: c2691 instance list
        """

        return self._hypervisor.send("c2691 list")

    @property
    def iomem(self):
        """
        Returns I/O memory size for this router.

        :returns: I/O memory size (integer)
        """

        return self._iomem

    @iomem.setter
    def iomem(self, iomem):
        """
        Set I/O memory size for this router.

        :param iomem: I/O memory size
        """

        self._hypervisor.send("c2691 set_iomem {name} {size}".format(name=self._name,
                                                                     size=iomem))
        self._iomem = iomem
