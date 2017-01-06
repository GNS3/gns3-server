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
Interface for UDP NIOs.
"""

import asyncio
import uuid
from .nio import NIO

import logging
log = logging.getLogger(__name__)


class NIOUDP(NIO):

    """
    Dynamips UDP NIO.

    :param hypervisor: Dynamips hypervisor instance
    :param lport: local port number
    :param rhost: remote address/host
    :param rport: remote port number
    """

    def __init__(self, hypervisor, lport, rhost, rport):

        # create an unique name
        name = 'udp-{}'.format(uuid.uuid4())
        self._lport = lport
        self._rhost = rhost
        self._rport = rport
        super().__init__(name, hypervisor)

    @asyncio.coroutine
    def create(self):
        if not self._hypervisor:
            return
        yield from self._hypervisor.send("nio create_udp {name} {lport} {rhost} {rport}".format(name=self._name,
                                                                                                lport=self._lport,
                                                                                                rhost=self._rhost,
                                                                                                rport=self._rport))

        log.info("NIO UDP {name} created with lport={lport}, rhost={rhost}, rport={rport}".format(name=self._name,
                                                                                                  lport=self._lport,
                                                                                                  rhost=self._rhost,
                                                                                                  rport=self._rport))

    @property
    def lport(self):
        """
        Returns the local port

        :returns: local port number
        """

        return self._lport

    @property
    def rhost(self):
        """
        Returns the remote host

        :returns: remote address/host
        """

        return self._rhost

    @property
    def rport(self):
        """
        Returns the remote port

        :returns: remote port number
        """

        return self._rport

    def __json__(self):

        return {"type": "nio_udp",
                "lport": self._lport,
                "rport": self._rport,
                "rhost": self._rhost}
