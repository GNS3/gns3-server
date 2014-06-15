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
Interface for Dynamips virtual Cisco 3600 instances module ("c3600")
http://github.com/GNS3/dynamips/blob/master/README.hypervisor#L366
"""

from .router import Router
from ..adapters.leopard_2fe import Leopard_2FE

import logging
log = logging.getLogger(__name__)


class C3600(Router):
    """
    Dynamips c3600 router.

    :param hypervisor: Dynamips hypervisor instance
    :param name: name for this router
    :param router_id: router instance ID
    :param chassis: chassis for this router:
    3620, 3640 or 3660 (default = 3640).
    """

    def __init__(self, hypervisor, name, router_id=None, chassis="3640"):
        Router.__init__(self, hypervisor, name, router_id, platform="c3600")

        # Set default values for this platform
        self._ram = 128
        self._nvram = 128
        self._disk0 = 0
        self._disk1 = 0
        self._iomem = 5  # percentage
        self._chassis = chassis
        self._clock_divisor = 4

        if chassis != "3640":
            self.chassis = chassis

        self._setup_chassis()

    def defaults(self):
        """
        Returns all the default attribute values for this platform.

        :returns: default values (dictionary)
        """

        router_defaults = Router.defaults(self)

        platform_defaults = {"ram": self._ram,
                             "nvram": self._nvram,
                             "disk0": self._disk0,
                             "disk1": self._disk1,
                             "iomem": self._iomem,
                             "chassis": self._chassis,
                             "clock_divisor": self._clock_divisor}

        # update the router defaults with the platform specific defaults
        router_defaults.update(platform_defaults)
        return router_defaults

    def list(self):
        """
        Returns all c3600 instances

        :returns: c3600 instance list
        """

        return self._hypervisor.send("c3600 list")

    def _setup_chassis(self):
        """
        Sets up the router with the corresponding chassis
        (create slots and insert default adapters).
        """

        if self._chassis == "3620":
            self._create_slots(2)
        elif self._chassis == "3640":
            self._create_slots(4)
        elif self._chassis == "3660":
            self._create_slots(7)
            self._slots[0] = Leopard_2FE()

    @property
    def chassis(self):
        """
        Returns the chassis.

        :returns: chassis string
        """

        return self._chassis

    @chassis.setter
    def chassis(self, chassis):
        """
        Sets the chassis.

        :param: chassis string: 3620, 3640 or 3660
        """

        self._hypervisor.send("c3600 set_chassis {name} {chassis}".format(name=self._name,
                                                                          chassis=chassis))

        log.info("router {name} [id={id}]: chassis set to {chassis}".format(name=self._name,
                                                                            id=self._id,
                                                                            chassis=chassis))

        self._chassis = chassis
        self._setup_chassis()

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

        self._hypervisor.send("c3600 set_iomem {name} {size}".format(name=self._name,
                                                                     size=iomem))

        log.info("router {name} [id={id}]: I/O memory updated from {old_iomem}% to {new_iomem}%".format(name=self._name,
                                                                                                        id=self._id,
                                                                                                        old_iomem=self._iomem,
                                                                                                        new_iomem=iomem))
        self._iomem = iomem
