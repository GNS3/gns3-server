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
Interface for automatic UDP NIOs.
"""

from .nio import NIO

import logging
log = logging.getLogger(__name__)


class NIO_UDP_auto(NIO):
    """
    Dynamips auto UDP NIO.

    :param hypervisor: Dynamips hypervisor instance
    :param laddr: local address
    :param lport_start: start local port range
    :param lport_end: end local port range
    """

    _instance_count = 0

    def __init__(self, hypervisor, laddr, lport_start, lport_end):

        NIO.__init__(self, hypervisor)

        # create an unique ID
        self._id = NIO_UDP_auto._instance_count
        NIO_UDP_auto._instance_count += 1
        self._name = 'nio_udp_auto' + str(self._id)

        self._laddr = laddr
        self._lport = int(self._hypervisor.send("nio create_udp_auto {name} {laddr} {lport_start} {lport_end}".format(name=self._name,
                                                                                                                      laddr=laddr,
                                                                                                                      lport_start=lport_start,
                                                                                                                      lport_end=lport_end))[0])

        log.info("NIO UDP AUTO {name} created with laddr={laddr}, lport_start={start}, lport_end={end}".format(name=self._name,
                                                                                                               laddr=laddr,
                                                                                                               start=lport_start,
                                                                                                               end=lport_end))
        self._raddr = None
        self._rport = None

    @classmethod
    def reset(cls):
        """
        Reset the instance count.
        """

        cls._instance_count = 0

    @property
    def laddr(self):
        """
        Returns the local address

        :returns: local address
        """

        return self._laddr

    @property
    def lport(self):
        """
        Returns the local port

        :returns: local port number
        """

        return self._lport

    @property
    def raddr(self):
        """
        Returns the remote address

        :returns: remote address
        """

        return self._raddr

    @property
    def rport(self):
        """
        Returns the remote port

        :returns: remote port number
        """

        return self._rport

    def connect(self, raddr, rport):
        """
        Connects this NIO to a remote socket

        :param raddr: remote address
        :param rport: remote port number
        """

        self._hypervisor.send("nio connect_udp_auto {name} {raddr} {rport}".format(name=self._name,
                                                                                   raddr=raddr,
                                                                                   rport=rport))
        self._raddr = raddr
        self._rport = rport

        log.info("NIO UDP AUTO {name} connected to {raddr}:{rport}".format(name=self._name,
                                                                           raddr=raddr,
                                                                           rport=rport))
