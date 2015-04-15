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
Interface for FIFO NIOs.
"""

import asyncio
import uuid
from .nio import NIO

import logging
log = logging.getLogger(__name__)


class NIOFIFO(NIO):

    """
    Dynamips FIFO NIO.

    :param hypervisor: Dynamips hypervisor instance
    """

    def __init__(self, hypervisor):

        # create an unique name
        name = 'fifo-{}'.format(uuid.uuid4())
        super().__init__(name, hypervisor)

    @asyncio.coroutine
    def create(self):

        yield from self._hypervisor.send("nio create_fifo {}".format(self._name))
        log.info("NIO FIFO {name} created.".format(name=self._name))

    @asyncio.coroutine
    def crossconnect(self, nio):
        """
        Establishes a cross-connect between this FIFO NIO and another one.

        :param nio: FIFO NIO instance
        """

        yield from self._hypervisor.send("nio crossconnect_fifo {name} {nio}".format(name=self._name,
                                                                                     nio=nio))

        log.info("NIO FIFO {name} crossconnected with {nio_name}.".format(name=self._name, nio_name=nio.name))

    def __json__(self):

        return {"type": "nio_fifo"}
