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
Interface for Linux Ethernet NIOs (Linux only).
"""

import asyncio
import uuid
from .nio import NIO

import logging

log = logging.getLogger(__name__)


class NIOLinuxEthernet(NIO):

    """
    Dynamips Linux Ethernet NIO.

    :param hypervisor: Dynamips hypervisor instance
    :param ethernet_device: Ethernet device name (e.g. eth0)
    """

    def __init__(self, hypervisor, ethernet_device):
        # create an unique name
        name = f"linux_ethernet-{uuid.uuid4()}"
        self._ethernet_device = ethernet_device
        super().__init__(name, hypervisor)

    async def create(self):

        await self._hypervisor.send(
            "nio create_linux_eth {name} {eth_device}".format(name=self._name, eth_device=self._ethernet_device)
        )

        log.info(
            "NIO Linux Ethernet {name} created with device {device}".format(
                name=self._name, device=self._ethernet_device
            )
        )

    @property
    def ethernet_device(self):
        """
        Returns the Ethernet device used by this NIO.

        :returns: the Ethernet device name
        """

        return self._ethernet_device

    def asdict(self):

        return {
            "type": "nio_linux_ethernet",
            "ethernet_device": self._ethernet_device
        }
