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
Interface for Dynamips virtual Cisco 1700 instances module ("c1700")
http://github.com/GNS3/dynamips/blob/master/README.hypervisor#L428
"""

import asyncio
from .router import Router
from ..adapters.c1700_mb_1fe import C1700_MB_1FE
from ..adapters.c1700_mb_wic1 import C1700_MB_WIC1

import logging
log = logging.getLogger(__name__)


class C1700(Router):

    """
    Dynamips c1700 router.

    :param name: The name of this router
    :param node_id: Node instance identifier
    :param project: Project instance
    :param manager: Parent VM Manager
    :param dynamips_id: ID to use with Dynamips
    :param console: console port
    :param aux: auxiliary console port
    :param chassis: chassis for this router:
    1720, 1721, 1750, 1751 or 1760 (default = 1720).
    1710 is not supported.
    """

    def __init__(self, name, node_id, project, manager, dynamips_id, console=None, aux=None, chassis="1720"):

        super().__init__(name, node_id, project, manager, dynamips_id, console, aux, platform="c1700")

        # Set default values for this platform (must be the same as Dynamips)
        self._ram = 64
        self._nvram = 32
        self._disk0 = 0
        self._disk1 = 0
        self._chassis = chassis
        self._iomem = 15  # percentage
        self._clock_divisor = 8
        self._sparsemem = False  # never activate sparsemem for c1700 (unstable)

    def __json__(self):

        c1700_router_info = {"iomem": self._iomem,
                             "chassis": self._chassis,
                             "sparsemem": self._sparsemem}

        router_info = Router.__json__(self)
        router_info.update(c1700_router_info)
        return router_info

    @asyncio.coroutine
    def create(self):

        yield from Router.create(self)
        if self._chassis != "1720":
            yield from self.set_chassis(self._chassis)
        self._setup_chassis()

    def _setup_chassis(self):
        """
        Sets up the router with the corresponding chassis
        (create slots and insert default adapters).
        """

        # With 1751 and 1760, WICs in WIC slot 1 show up as in slot 1, not 0
        # e.g. s1/0 not s0/2
        if self._chassis in ['1751', '1760']:
            self._create_slots(2)
            self._slots[1] = C1700_MB_WIC1()
        else:
            self._create_slots(1)
        self._slots[0] = C1700_MB_1FE()

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

        :param: chassis string:
        1720, 1721, 1750, 1751 or 1760
        """

        yield from self._hypervisor.send('c1700 set_chassis "{name}" {chassis}'.format(name=self._name, chassis=chassis))

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
        Sets I/O memory size for this router.

        :param iomem: I/O memory size
        """

        yield from self._hypervisor.send('c1700 set_iomem "{name}" {size}'.format(name=self._name, size=iomem))

        log.info('Router "{name}" [{id}]: I/O memory updated from {old_iomem}% to {new_iomem}%'.format(name=self._name,
                                                                                                       id=self._id,
                                                                                                       old_iomem=self._iomem,
                                                                                                       new_iomem=iomem))
        self._iomem = iomem
