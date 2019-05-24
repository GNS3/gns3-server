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

from gns3server.compute.nios import nio_udp
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

    def __init__(self, node, lport, rhost, rport):

        # create an unique name
        name = 'udp-{}'.format(uuid.uuid4())
        self._lport = lport
        self._rhost = rhost
        self._rport = rport
        self._local_tunnel_lport = None
        self._local_tunnel_rport = None
        self._node = node
        super().__init__(name, node.hypervisor)

    async def create(self):
        if not self._hypervisor:
            return
        # Ubridge is not supported
        if not hasattr(self._node, "add_ubridge_udp_connection"):
            await self._hypervisor.send("nio create_udp {name} {lport} {rhost} {rport}".format(name=self._name,
                                                                                                    lport=self._lport,
                                                                                                    rhost=self._rhost,
                                                                                                    rport=self._rport))
            return
        self._local_tunnel_lport = self._node.manager.port_manager.get_free_udp_port(self._node.project)
        self._local_tunnel_rport = self._node.manager.port_manager.get_free_udp_port(self._node.project)
        self._bridge_name = 'DYNAMIPS-{}-{}'.format(self._local_tunnel_lport, self._local_tunnel_rport)
        await self._hypervisor.send("nio create_udp {name} {lport} {rhost} {rport}".format(name=self._name,
                                                                                                lport=self._local_tunnel_lport,
                                                                                                rhost='127.0.0.1',
                                                                                                rport=self._local_tunnel_rport))

        log.info("NIO UDP {name} created with lport={lport}, rhost={rhost}, rport={rport}".format(name=self._name,
                                                                                                  lport=self._lport,
                                                                                                  rhost=self._rhost,
                                                                                                  rport=self._rport))

        self._source_nio = nio_udp.NIOUDP(self._local_tunnel_rport,
                                          '127.0.0.1',
                                          self._local_tunnel_lport)
        self._destination_nio = nio_udp.NIOUDP(self._lport,
                                               self._rhost,
                                               self._rport)
        self._destination_nio.filters = self._filters
        await self._node.add_ubridge_udp_connection(
            self._bridge_name,
            self._source_nio,
            self._destination_nio
        )

    async def update(self):
        self._destination_nio.filters = self._filters
        await self._node.update_ubridge_udp_connection(
            self._bridge_name,
            self._source_nio,
            self._destination_nio)

    async def close(self):
        if self._local_tunnel_lport:
            await self._node.ubridge_delete_bridge(self._bridge_name)
            self._node.manager.port_manager.release_udp_port(self._local_tunnel_lport, self ._node.project)
        if self._local_tunnel_rport:
            self._node.manager.port_manager.release_udp_port(self._local_tunnel_rport, self._node.project)
        self._node.manager.port_manager.release_udp_port(self._lport, self._node.project)

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
