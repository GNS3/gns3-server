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

from .nio import NIO

import logging
log = logging.getLogger(__name__)


class NIO_UDP(NIO):
    """
    Dynamips UDP NIO.

    :param hypervisor: Dynamips hypervisor instance
    :param lport: local port number
    :param rhost: remote address/host
    :param rport: remote port number
    """

    _instance_count = 0

    def __init__(self, hypervisor, lport, rhost, rport):

        NIO.__init__(self, hypervisor)

        # create an unique ID
        self._id = NIO_UDP._instance_count
        NIO_UDP._instance_count += 1
        self._name = 'nio_udp' + str(self._id)
        self._lport = lport
        self._rhost = rhost
        self._rport = rport

        self._hypervisor.send("nio create_udp {name} {lport} {rhost} {rport}".format(name=self._name,
                                                                                     lport=lport,
                                                                                     rhost=rhost,
                                                                                     rport=rport))

        log.info("NIO UDP {name} created with lport={lport}, rhost={rhost}, rport={rport}".format(name=self._name,
                                                                                                  lport=lport,
                                                                                                  rhost=rhost,
                                                                                                  rport=rport))

    @classmethod
    def reset(cls):
        """
        Reset the instance count.
        """

        cls._instance_count = 0

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
