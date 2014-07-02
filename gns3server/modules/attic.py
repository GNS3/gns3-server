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

import sys
import os
import struct
import socket
import stat
import errno
import time

import logging
log = logging.getLogger(__name__)


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


def wait_socket_is_ready(host, port, wait=2.0, socket_timeout=10):
    """
    Waits for a socket to be ready for wait time.

    :param host: host/address to connect to
    :param port: port to connect to
    :param wait: maximum wait time
    :param socket_timeout: timeout for the socket

    :returns: tuple with boolean indicating if the socket is ready and the last exception
    that occurred when connecting to the socket
    """

    # connect to a local address by default
    # if listening to all addresses (IPv4 or IPv6)
    if host == "0.0.0.0":
        host = "127.0.0.1"
    elif host == "::":
        host = "::1"

    connection_success = False
    begin = time.time()
    last_exception = None
    while time.time() - begin < wait:
        time.sleep(0.01)
        try:
            with socket.create_connection((host, port), socket_timeout):
                pass
        except OSError as e:
            last_exception = e
            continue
        connection_success = True
        break

    return connection_success, last_exception


def has_privileged_access(executable):
    """
    Check if an executable can access Ethernet and TAP devices in
    RAW mode.

    :param executable: executable path

    :returns: True or False
    """

    if sys.platform.startswith("win"):
        # do not check anything on Windows
        return True

    if os.geteuid() == 0:
        # we are root, so we should have privileged access.
        return True
    if os.stat(executable).st_mode & stat.S_ISVTX == stat.S_ISVTX:
        # the executable has a sticky bit.
        return True

    # test if the executable has the CAP_NET_RAW capability (Linux only)
    if sys.platform.startswith("linux") and "security.capability" in os.listxattr(executable):
        try:
            caps = os.getxattr(executable, "security.capability")
            # test the 2nd byte and check if the 13th bit (CAP_NET_RAW) is set
            if struct.unpack("<IIIII", caps)[1] & 1 << 13:
                return True
        except Exception as e:
            log.error("could not determine if CAP_NET_RAW capability is set for {}: {}".format(executable, e))

    return False
