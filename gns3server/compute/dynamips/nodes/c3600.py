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

import asyncio
from .router import Router
from ..adapters.leopard_2fe import Leopard_2FE

import logging
log = logging.getLogger(__name__)


class C3600(Router):

    """
    Dynamips c3600 router.

    :param name: The name of this router
    :param node_id: Node identifier
    :param project: Project instance
    :param manager: Parent VM Manager
    :param dynamips_id: ID to use with Dynamips
    :param console: console port
    :param aux: auxiliary console port
    :param chassis: chassis for this router:
    3620, 3640 or 3660 (default = 3640).
    """

    def __init__(self, name, node_id, project, manager, dynamips_id, console=None, aux=None, chassis="3640"):

        super().__init__(name, node_id, project, manager, dynamips_id, console, aux, platform="c3600")

        # Set default values for this platform (must be the same as Dynamips)
        self._ram = 128
        self._nvram = 128
        self._disk0 = 0
        self._disk1 = 0
        self._iomem = 5  # percentage
        self._chassis = chassis
        self._clock_divisor = 4

    def __json__(self):

        c3600_router_info = {"iomem": self._iomem,
                             "chassis": self._chassis}

        router_info = Router.__json__(self)
        router_info.update(c3600_router_info)
        return router_info

    @asyncio.coroutine
    def create(self):

        yield from Router.create(self)
        if self._chassis != "3640":
            yield from self.set_chassis(self._chassis)
        self._setup_chassis()

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

    @asyncio.coroutine
    def set_chassis(self, chassis):
        """
        Sets the chassis.

        :param: chassis string: 3620, 3640 or 3660
        """

        yield from self._hypervisor.send('c3600 set_chassis "{name}" {chassis}'.format(name=self._name, chassis=chassis))

        log.info('Router "{name}" [{id}]: chassis set to {chassis}'.format(name=self._name,
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

    @asyncio.coroutine
    def set_iomem(self, iomem):
        """
        Set I/O memory size for this router.

        :param iomem: I/O memory size
        """

        yield from self._hypervisor.send('c3600 set_iomem "{name}" {size}'.format(name=self._name, size=iomem))

        log.info('Router "{name}" [{id}]: I/O memory updated from {old_iomem}% to {new_iomem}%'.format(name=self._name,
                                                                                                       id=self._id,
                                                                                                       old_iomem=self._iomem,
                                                                                                       new_iomem=iomem))
        self._iomem = iomem
