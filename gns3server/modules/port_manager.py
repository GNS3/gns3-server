# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 GNS3 Technologies Inc.
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

import ipaddress
from .attic import find_unused_port

class PortManager:
    """
    :param console: TCP console port
    :param console_host: IP address to bind for console connections
    :param console_start_port_range: TCP console port range start
    :param console_end_port_range: TCP console port range end
    """
    def __init__(self,
            console_host,
            console_bind_to_any,
            console_start_port_range=10000,
            console_end_port_range=15000):

        self._console_start_port_range = console_start_port_range
        self._console_end_port_range = console_end_port_range
        self._used_ports = set()

        if console_bind_to_any:
            if ipaddress.ip_address(console_host).version == 6:
                self._console_host = "::"
            else:
                self._console_host = "0.0.0.0"
        else:
            self._console_host = console_host

    def get_free_port(self):
        """Get an available console port and reserve it"""
        port = find_unused_port(self._console_start_port_range,
                                self._console_end_port_range,
                                host=self._console_host,
                                socket_type='TCP',
                                ignore_ports=self._used_ports)
        self._used_ports.add(port)
        return port

    def reserve_port(port):
        """
        Reserve a specific port number

        :param port: Port number
        """
        if port in self._used_ports:
            raise Exception("Port already {} in use".format(port))
        self._used_ports.add(port)

    def release_port(port):
        """
        Release a specific port number

        :param port: Port number
        """
        self._used_ports.remove(port)

