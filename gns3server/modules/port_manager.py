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
import sys
import ipaddress
from aiohttp.web import HTTPConflict
from gns3server.config import Config

import logging
log = logging.getLogger(__name__)


class PortManager:

    """
    :param host: IP address to bind for console connections
    """

    def __init__(self, host="127.0.0.1"):

        self._console_host = host
        self._udp_host = host

        self._used_tcp_ports = set()
        self._used_udp_ports = set()

        server_config = Config.instance().get_section_config("Server")
        remote_console_connections = server_config.getboolean("allow_remote_console")

        console_start_port_range = server_config.getint("console_start_port_range", 2000)
        console_end_port_range = server_config.getint("console_end_port_range", 5000)
        self._console_port_range = (console_start_port_range, console_end_port_range)
        log.debug("Console port range is {}-{}".format(console_start_port_range, console_end_port_range))

        udp_start_port_range = server_config.getint("udp_start_port_range", 10000)
        udp_end_port_range = server_config.getint("udp_end_port_range", 20000)
        self._udp_port_range = (udp_start_port_range, udp_end_port_range)
        log.debug("UDP port range is {}-{}".format(udp_start_port_range, udp_end_port_range))

        if remote_console_connections:
            log.warning("Remote console connections are allowed")
            if ipaddress.ip_address(host).version == 6:
                self._console_host = "::"
            else:
                self._console_host = "0.0.0.0"
        else:
            self._console_host = host

        PortManager._instance = self

    @classmethod
    def instance(cls):
        """
        Singleton to return only one instance of PortManager.

        :returns: instance of PortManager
        """

        if not hasattr(cls, "_instance") or cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def console_host(self):

        return self._console_host

    @console_host.setter
    def console_host(self, new_host):

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

    @property
    def tcp_ports(self):

        return self._used_tcp_ports

    @property
    def udp_ports(self):

        return self._used_udp_ports

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
            raise HTTPConflict(text="Invalid port range {}-{}".format(start_port, end_port))

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

        raise HTTPConflict(text="Could not find a free port between {} and {} on host {}, last exception: {}".format(start_port,
                                                                                                                     end_port,
                                                                                                                     host,
                                                                                                                     last_exception))

    def get_free_tcp_port(self, project):
        """
        Get an available TCP port and reserve it

        :param project: Project instance
        """

        port = self.find_unused_port(self._console_port_range[0],
                                     self._console_port_range[1],
                                     host=self._console_host,
                                     socket_type="TCP",
                                     ignore_ports=self._used_tcp_ports)

        self._used_tcp_ports.add(port)
        project.record_tcp_port(port)
        log.debug("TCP port {} has been allocated".format(port))
        return port

    def reserve_tcp_port(self, port, project):
        """
        Reserve a specific TCP port number

        :param port: TCP port number
        :param project: Project instance
        """

        if port in self._used_tcp_ports:
            raise HTTPConflict(text="TCP port {} already in use on host".format(port, self._console_host))
        self._used_tcp_ports.add(port)
        project.record_tcp_port(port)
        log.debug("TCP port {} has been reserved".format(port))
        return port

    def release_tcp_port(self, port, project):
        """
        Release a specific TCP port number

        :param port: TCP port number
        :param project: Project instance
        """

        if port in self._used_tcp_ports:
            self._used_tcp_ports.remove(port)
            project.remove_tcp_port(port)
            log.debug("TCP port {} has been released".format(port))

    def get_free_udp_port(self, project):
        """
        Get an available UDP port and reserve it

        :param project: Project instance
        """

        port = self.find_unused_port(self._udp_port_range[0],
                                     self._udp_port_range[1],
                                     host=self._udp_host,
                                     socket_type="UDP",
                                     ignore_ports=self._used_udp_ports)

        self._used_udp_ports.add(port)
        project.record_udp_port(port)
        log.debug("UDP port {} has been allocated".format(port))
        return port

    def reserve_udp_port(self, port, project):
        """
        Reserve a specific UDP port number

        :param port: UDP port number
        :param project: Project instance
        """

        if port in self._used_udp_ports:
            raise HTTPConflict(text="UDP port {} already in use on host".format(port, self._console_host))
        self._used_udp_ports.add(port)
        project.record_udp_port(port)
        log.debug("UDP port {} has been reserved".format(port))

    def release_udp_port(self, port, project):
        """
        Release a specific UDP port number

        :param port: UDP port number
        :param project: Project instance
        """

        if port in self._used_udp_ports:
            self._used_udp_ports.remove(port)
            project.remove_udp_port(port)
            log.debug("UDP port {} has been released".format(port))
