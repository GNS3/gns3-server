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
Interface for VDE (Virtual Distributed Ethernet) NIOs (Unix based OSes only).
"""

import asyncio
import uuid
from .nio import NIO

import logging

log = logging.getLogger(__name__)


class NIOVDE(NIO):

    """
    Dynamips VDE NIO.

    :param hypervisor: Dynamips hypervisor instance
    :param control_file: VDE control filename
    :param local_file: VDE local filename
    """

    def __init__(self, hypervisor, control_file, local_file):

        # create an unique name
        name = f"vde-{uuid.uuid4()}"
        self._control_file = control_file
        self._local_file = local_file
        super().__init__(name, hypervisor)

    async def create(self):

        await self._hypervisor.send(
            "nio create_vde {name} {control} {local}".format(
                name=self._name, control=self._control_file, local=self._local_file
            )
        )

        log.info(
            "NIO VDE {name} created with control={control}, local={local}".format(
                name=self._name, control=self._control_file, local=self._local_file
            )
        )

    @property
    def control_file(self):
        """
        Returns the VDE control file.

        :returns: VDE control filename
        """

        return self._control_file

    @property
    def local_file(self):
        """
        Returns the VDE local file.

        :returns: VDE local filename
        """

        return self._local_file

    def asdict(self):

        return {
            "type": "nio_vde",
            "local_file": self._local_file,
            "control_file": self._control_file
        }
