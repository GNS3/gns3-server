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
Interface for Dynamips virtual Cisco 2600 instances module ("c2600")
http://github.com/GNS3/dynamips/blob/master/README.hypervisor#L404
"""

import asyncio
from .router import Router
from ..adapters.c2600_mb_1e import C2600_MB_1E
from ..adapters.c2600_mb_2e import C2600_MB_2E
from ..adapters.c2600_mb_1fe import C2600_MB_1FE
from ..adapters.c2600_mb_2fe import C2600_MB_2FE

import logging
log = logging.getLogger(__name__)


class C2600(Router):

    """
    Dynamips c2600 router.

    :param name: The name of this router
    :param node_id: Node identifier
    :param project: Project instance
    :param manager: Parent VM Manager
    :param dynamips_id: ID to use with Dynamips
    :param console: console port
    :param aux: auxiliary console port
    :param chassis: chassis for this router:
    2610, 2611, 2620, 2621, 2610XM, 2611XM
    2620XM, 2621XM, 2650XM or 2651XM (default = 2610).
    """

    # adapters to insert by default corresponding the
    # chosen chassis.
    integrated_adapters = {"2610": C2600_MB_1E,
                           "2611": C2600_MB_2E,
                           "2620": C2600_MB_1FE,
                           "2621": C2600_MB_2FE,
                           "2610XM": C2600_MB_1FE,
                           "2611XM": C2600_MB_2FE,
                           "2620XM": C2600_MB_1FE,
                           "2621XM": C2600_MB_2FE,
                           "2650XM": C2600_MB_1FE,
                           "2651XM": C2600_MB_2FE}

    def __init__(self, name, node_id, project, manager, dynamips_id, console=None, aux=None, chassis="2610"):

        super().__init__(name, node_id, project, manager, dynamips_id, console, aux, platform="c2600")

        # Set default values for this platform (must be the same as Dynamips)
        self._ram = 64
        self._nvram = 128
        self._disk0 = 0
        self._disk1 = 0
        self._chassis = chassis
        self._iomem = 15  # percentage
        self._clock_divisor = 8
        self._sparsemem = False  # never activate sparsemem for c2600 (unstable)

    def __json__(self):

        c2600_router_info = {"iomem": self._iomem,
                             "chassis": self._chassis,
                             "sparsemem": self._sparsemem}

        router_info = Router.__json__(self)
        router_info.update(c2600_router_info)
        return router_info

    @asyncio.coroutine
    def create(self):

        yield from Router.create(self)
        if self._chassis != "2610":
            yield from self.set_chassis(self._chassis)
        self._setup_chassis()

    def _setup_chassis(self):
        """
        Sets up the router with the corresponding chassis
        (create slots and insert default adapters).
        """

        self._create_slots(2)
        self._slots[0] = self.integrated_adapters[self._chassis]()

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
        2610, 2611, 2620, 2621, 2610XM, 2611XM
        2620XM, 2621XM, 2650XM or 2651XM
        """

        yield from self._hypervisor.send('c2600 set_chassis "{name}" {chassis}'.format(name=self._name, chassis=chassis))

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

        yield from self._hypervisor.send('c2600 set_iomem "{name}" {size}'.format(name=self._name, size=iomem))

        log.info('Router "{name}" [{id}]: I/O memory updated from {old_iomem}% to {new_iomem}%'.format(name=self._name,
                                                                                                       id=self._id,
                                                                                                       old_iomem=self._iomem,
                                                                                                       new_iomem=iomem))
        self._iomem = iomem
