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
from fastapi import HTTPException, status
from gns3server.config import Config

import logging

log = logging.getLogger(__name__)


# These ports are disallowed by Chrome and Firefox to avoid issues, we skip them as well
BANNED_PORTS = {
    1,
    7,
    9,
    11,
    13,
    15,
    17,
    19,
    20,
    21,
    22,
    23,
    25,
    37,
    42,
    43,
    53,
    77,
    79,
    87,
    95,
    101,
    102,
    103,
    104,
    109,
    110,
    111,
    113,
    115,
    117,
    119,
    123,
    135,
    139,
    143,
    179,
    389,
    465,
    512,
    513,
    514,
    515,
    526,
    530,
    531,
    532,
    540,
    556,
    563,
    587,
    601,
    636,
    993,
    995,
    2049,
    3659,
    4045,
    6000,
    6665,
    6666,
    6667,
    6668,
    6669,
}


class PortManager:

    """
    :param host: IP address to bind for console connections
    """

    def __init__(self):
        self._console_host = None
        # UDP host must be 0.0.0.0, reason: https://github.com/GNS3/gns3-server/issues/265
        self._udp_host = "0.0.0.0"
        self._used_tcp_ports = set()
        self._used_udp_ports = set()

        console_start_port_range = Config.instance().settings.Server.console_start_port_range
        console_end_port_range = Config.instance().settings.Server.console_end_port_range
        self._console_port_range = (console_start_port_range, console_end_port_range)
        log.debug(f"Console port range is {console_start_port_range}-{console_end_port_range}")

        udp_start_port_range = Config.instance().settings.Server.udp_start_port_range
        udp_end_port_range = Config.instance().settings.Server.udp_end_port_range
        self._udp_port_range = (udp_start_port_range, udp_end_port_range)
        log.debug(f"UDP port range is {udp_start_port_range}-{udp_end_port_range}")

    @classmethod
    def instance(cls):
        """
        Singleton to return only one instance of PortManager.

        :returns: instance of PortManager
        """

        if not hasattr(cls, "_instance") or cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def asdict(self):

        return {
            "console_port_range": self._console_port_range,
            "console_ports": list(self._used_tcp_ports),
            "udp_port_range": self._udp_port_range,
            "udp_ports": list(self._used_udp_ports),
        }

    @property
    def console_host(self):

        assert self._console_host is not None
        return self._console_host

    @console_host.setter
    def console_host(self, new_host):
        """
        Bind console host to 0.0.0.0 or :: if remote connections are allowed.
        """

        remote_console_connections = Config.instance().settings.Server.allow_remote_console
        if remote_console_connections:
            log.warning("Remote console connections are allowed")
            self._console_host = "0.0.0.0"
            try:
                ip = ipaddress.ip_address(new_host)
                if isinstance(ip, ipaddress.IPv6Address):
                    self._console_host = "::"
            except ValueError:
                log.warning("Could not determine IP address type for console host")
        else:
            self._console_host = new_host

    @property
    def console_port_range(self):

        return self._console_port_range

    @console_port_range.setter
    def console_port_range(self, new_range):

        assert isinstance(new_range, tuple)
        self._console_port_range = new_range

    @property
    def udp_host(self):

        return self._udp_host

    @udp_host.setter
    def udp_host(self, new_host):

        self._udp_host = new_host

    @property
    def udp_port_range(self):

        return self._udp_port_range

    @udp_port_range.setter
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
    def find_unused_port(start_port, end_port, host="127.0.0.1", socket_type="TCP", ignore_ports=None):
        """
        Finds an unused port in a range.

        :param start_port: first port in the range
        :param end_port: last port in the range
        :param host: host/address for bind()
        :param socket_type: TCP (default) or UDP
        :param ignore_ports: list of port to ignore within the range
        """

        if end_port < start_port:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=f"Invalid port range {start_port}-{end_port}"
            )

        last_exception = None
        for port in range(start_port, end_port + 1):
            if ignore_ports and (port in ignore_ports or port in BANNED_PORTS):
                continue

            try:
                PortManager._check_port(host, port, socket_type)
                if host != "0.0.0.0":
                    PortManager._check_port("0.0.0.0", port, socket_type)
                return port
            except OSError as e:
                last_exception = e
                if port + 1 == end_port:
                    break
                else:
                    continue

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Could not find a free port between {start_port} and {end_port} on host {host},"
            f" last exception: {last_exception}",
        )

    @staticmethod
    def _check_port(host, port, socket_type):
        """
        Check if an a port is available and raise an OSError if port is not available

        :returns: boolean
        """
        if socket_type == "UDP":
            socket_type = socket.SOCK_DGRAM
        else:
            socket_type = socket.SOCK_STREAM

        for res in socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket_type, 0, socket.AI_PASSIVE):
            af, socktype, proto, _, sa = res
            with socket.socket(af, socktype, proto) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(sa)  # the port is available if bind is a success
            return True

    def get_free_tcp_port(self, project, port_range_start=None, port_range_end=None):
        """
        Get an available TCP port and reserve it

        :param project: Project instance
        """

        # use the default range is not specific one is given
        if port_range_start is None and port_range_end is None:
            port_range_start = self._console_port_range[0]
            port_range_end = self._console_port_range[1]

        port = self.find_unused_port(
            port_range_start,
            port_range_end,
            host=self._console_host,
            socket_type="TCP",
            ignore_ports=self._used_tcp_ports,
        )

        self._used_tcp_ports.add(port)
        project.record_tcp_port(port)
        log.debug(f"TCP port {port} has been allocated")
        return port

    def reserve_tcp_port(self, port, project, port_range_start=None, port_range_end=None):
        """
        Reserve a specific TCP port number. If not available replace it
        by another.

        :param port: TCP port number
        :param project: Project instance
        :param port_range_start: Port range to use
        :param port_range_end: Port range to use
        :returns: The TCP port
        """

        # use the default range is not specific one is given
        if port_range_start is None and port_range_end is None:
            port_range_start = self._console_port_range[0]
            port_range_end = self._console_port_range[1]

        if port in self._used_tcp_ports:
            old_port = port
            port = self.get_free_tcp_port(project, port_range_start=port_range_start, port_range_end=port_range_end)
            msg = f"TCP port {old_port} already in use on host {self._console_host}. Port has been replaced by {port}"
            log.debug(msg)
            return port
        if port < port_range_start or port > port_range_end:
            old_port = port
            port = self.get_free_tcp_port(project, port_range_start=port_range_start, port_range_end=port_range_end)
            msg = (
                f"TCP port {old_port} is outside the range {port_range_start}-{port_range_end} on host "
                f"{self._console_host}. Port has been replaced by {port}"
            )
            log.debug(msg)
            return port
        try:
            PortManager._check_port(self._console_host, port, "TCP")
        except OSError:
            old_port = port
            port = self.get_free_tcp_port(project, port_range_start=port_range_start, port_range_end=port_range_end)
            msg = f"TCP port {old_port} already in use on host {self._console_host}. Port has been replaced by {port}"
            log.debug(msg)
            return port

        self._used_tcp_ports.add(port)
        project.record_tcp_port(port)
        log.debug(f"TCP port {port} has been reserved")
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
            log.debug(f"TCP port {port} has been released")

    def get_free_udp_port(self, project):
        """
        Get an available UDP port and reserve it

        :param project: Project instance
        """
        port = self.find_unused_port(
            self._udp_port_range[0],
            self._udp_port_range[1],
            host=self._udp_host,
            socket_type="UDP",
            ignore_ports=self._used_udp_ports,
        )

        self._used_udp_ports.add(port)
        project.record_udp_port(port)
        log.debug(f"UDP port {port} has been allocated")
        return port

    def reserve_udp_port(self, port, project):
        """
        Reserve a specific UDP port number

        :param port: UDP port number
        :param project: Project instance
        """

        if port in self._used_udp_ports:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"UDP port {port} already in use on host {self._console_host}",
            )
        if port < self._udp_port_range[0] or port > self._udp_port_range[1]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"UDP port {port} is outside the range " f"{self._udp_port_range[0]}-{self._udp_port_range[1]}",
            )
        self._used_udp_ports.add(port)
        project.record_udp_port(port)
        log.debug(f"UDP port {port} has been reserved")

    def release_udp_port(self, port, project):
        """
        Release a specific UDP port number

        :param port: UDP port number
        :param project: Project instance
        """

        if port in self._used_udp_ports:
            self._used_udp_ports.remove(port)
            project.remove_udp_port(port)
            log.debug(f"UDP port {port} has been released")
