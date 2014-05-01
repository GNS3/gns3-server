# -*- coding: utf-8 -*-
#
# Copyright (C) 2014 GNS3 Technologies Inc.
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
Useful functions... in the attic ;)
"""

import socket
import errno


def find_unused_port(start_port, end_port, host='127.0.0.1', socket_type="TCP", ignore_ports=[]):
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

    for port in range(start_port, end_port + 1):
        if port in ignore_ports:
            continue
        try:
            if ":" in host:
                # IPv6 address support
                with socket.socket(socket.AF_INET6, socket_type) as s:
                    s.bind((host, port))  # the port is available if bind is a success
            else:
                with socket.socket(socket.AF_INET, socket_type) as s:
                    s.bind((host, port))  # the port is available if bind is a success
            return port
        except OSError as e:
            if e.errno == errno.EADDRINUSE:  # socket already in use
                if port + 1 == end_port:
                    break
                else:
                    continue
            else:
                raise Exception("Could not find an unused port: {}".format(e))

    raise Exception("Could not find a free port between {0} and {1}".format(start_port, end_port))
