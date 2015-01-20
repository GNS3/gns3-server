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

import socket
import ipaddress
import asyncio
from aiohttp.web import HTTPConflict


class PortManager:

    """
    :param host: IP address to bind for console connections
    """

    def __init__(self, host="127.0.0.1", console_bind_to_any=False):

        self._console_host = host
        self._udp_host = host
        self._console_port_range = (2000, 4000)
        self._udp_port_range = (10000, 20000)

        self._used_tcp_ports = set()
        self._used_udp_ports = set()

        if console_bind_to_any:
            if ipaddress.ip_address(host).version == 6:
                self._console_host = "::"
            else:
                self._console_host = "0.0.0.0"
        else:
            self._console_host = host

    @classmethod
    def instance(cls):
        """
        Singleton to return only one instance of BaseManager.

        :returns: instance of Manager
        """

        if not hasattr(cls, "_instance") or cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    @asyncio.coroutine  # FIXME: why coroutine?
    def destroy(cls):

        cls._instance = None

    @property
    def console_host(self):

        return self._console_host

    @console_host.setter
    def host(self, new_host):

        self._console_host = new_host

    @property
    def console_port_range(self):

        return self._console_port_range

    @console_host.setter
    def console_port_range(self, new_range):

        assert isinstance(new_range, tuple)
        self._console_port_range = new_range

    @property
    def udp_host(self):

        return self._udp_host

    @udp_host.setter
    def host(self, new_host):

        self._udp_host = new_host

    @property
    def udp_port_range(self):

        return self._udp_port_range

    @udp_host.setter
    def udp_port_range(self, new_range):

        assert isinstance(new_range, tuple)
        self._udp_port_range = new_range

    @staticmethod
    def find_unused_port(start_port, end_port, host="127.0.0.1", socket_type="TCP", ignore_ports=[]):
        """
        Finds an unused port in a range.

        :param start_port: first port in the range
        :param end_port: last port in the range
        :param host: host/address for bind()
        :param socket_type: TCP (default) or UDP
        :param ignore_ports: list of port to ignore within the range
        """

        if end_port < start_port:
            raise Exception("Invalid port range {}-{}".format(start_port, end_port))

        if socket_type == "UDP":
            socket_type = socket.SOCK_DGRAM
        else:
            socket_type = socket.SOCK_STREAM

        last_exception = None
        for port in range(start_port, end_port + 1):
            if port in ignore_ports:
                continue
            try:
                if ":" in host:
                    # IPv6 address support
                    with socket.socket(socket.AF_INET6, socket_type) as s:
                        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                        s.bind((host, port))  # the port is available if bind is a success
                else:
                    with socket.socket(socket.AF_INET, socket_type) as s:
                        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                        s.bind((host, port))  # the port is available if bind is a success
                return port
            except OSError as e:
                last_exception = e
                if port + 1 == end_port:
                    break
                else:
                    continue

        raise HTTPConflict(reason="Could not find a free port between {} and {} on host {}, last exception: {}".format(start_port,
                                                                                                                       end_port,
                                                                                                                       host,
                                                                                                                       last_exception))

    def get_free_console_port(self):
        """
        Get an available TCP console port and reserve it
        """

        port = self.find_unused_port(self._console_port_range[0],
                                     self._console_port_range[1],
                                     host=self._console_host,
                                     socket_type="TCP",
                                     ignore_ports=self._used_tcp_ports)

        self._used_tcp_ports.add(port)
        return port

    def reserve_console_port(self, port):
        """
        Reserve a specific TCP console port number

        :param port: TCP port number
        """

        if port in self._used_tcp_ports:
            raise HTTPConflict(reason="TCP port already {} in use on host".format(port, self._console_host))
        self._used_tcp_ports.add(port)
        return port

    def release_console_port(self, port):
        """
        Release a specific TCP console port number

        :param port: TCP port number
        """

        self._used_tcp_ports.remove(port)

    def get_free_udp_port(self):
        """
        Get an available UDP port and reserve it
        """

        port = self.find_unused_port(self._udp_port_range[0],
                                     self._udp_port_range[1],
                                     host=self._udp_host,
                                     socket_type="UDP",
                                     ignore_ports=self._used_udp_ports)

        self._used_udp_ports.add(port)
        return port

    def reserve_udp_port(self, port):
        """
        Reserve a specific UDP port number

        :param port: UDP port number
        """

        if port in self._used_udp_ports:
            raise Exception("UDP port already {} in use on host".format(port, self._host))
        self._used_udp_ports.add(port)

    def release_udp_port(self, port):
        """
        Release a specific UDP port number

        :param port: UDP port number
        """

        self._used_udp_ports.remove(port)
