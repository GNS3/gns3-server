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
Interface for Dynamips virtual Cisco 3725 instances module ("c3725")
http://github.com/GNS3/dynamips/blob/master/README.hypervisor#L346
"""

import asyncio
from .router import Router
from ..adapters.gt96100_fe import GT96100_FE
from ..dynamips_error import DynamipsError

import logging

log = logging.getLogger(__name__)


class C3725(Router):

    """
    Dynamips c3725 router.

    :param name: The name of this router
    :param node_id: Node identifier
    :param project: Project instance
    :param manager: Parent VM Manager
    :param dynamips_id: ID to use with Dynamips
    :param console: console port
    :param console_type: console type
    :param aux: auxiliary console port
    :param aux_type: auxiliary console type
    """

    def __init__(
        self,
        name,
        node_id,
        project,
        manager,
        dynamips_id,
        console=None,
        console_type="telnet",
        aux=None,
        aux_type="none",
        chassis=None,
    ):

        super().__init__(
            name, node_id, project, manager, dynamips_id, console, console_type, aux, aux_type, platform="c3725"
        )

        # Set default values for this platform (must be the same as Dynamips)
        self._ram = 128
        self._nvram = 112
        self._disk0 = 16
        self._disk1 = 0
        self._iomem = 5  # percentage
        self._clock_divisor = 8

        self._create_slots(3)
        self._slots[0] = GT96100_FE()

        if chassis is not None:
            raise DynamipsError("c3725 routers do not have chassis")

    def asdict(self):

        c3725_router_info = {"iomem": self._iomem}

        router_info = Router.asdict(self)
        router_info.update(c3725_router_info)
        return router_info

    @property
    def iomem(self):
        """
        Returns I/O memory size for this router.

        :returns: I/O memory size (integer)
        """

        return self._iomem

    async def set_iomem(self, iomem):
        """
        Sets I/O memory size for this router.

        :param iomem: I/O memory size
        """

        await self._hypervisor.send(f'c3725 set_iomem "{self._name}" {iomem}')

        log.info(
            'Router "{name}" [{id}]: I/O memory updated from {old_iomem}% to {new_iomem}%'.format(
                name=self._name, id=self._id, old_iomem=self._iomem, new_iomem=iomem
            )
        )
        self._iomem = iomem
