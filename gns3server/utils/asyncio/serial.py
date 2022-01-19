#!/usr/bin/env python
#
# Copyright (C) 2016 GNS3 Technologies Inc.
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

import asyncio

from gns3server.utils.asyncio import wait_for_file_creation
from gns3server.compute.error import NodeError

"""
This module handle connection to unix socket
"""


class SerialReaderWriterProtocol(asyncio.Protocol):
    def __init__(self):
        self._output = asyncio.StreamReader()
        self._closed = False
        self.transport = None

    def read(self, n=-1):
        return self._output.read(n=n)

    def at_eof(self):
        return self._output.at_eof()

    def write(self, data):
        if self.transport:
            self.transport.write(data)

    async def drain(self):
        pass

    def connection_made(self, transport):
        self.transport = transport

    def data_received(self, data):
        if not self._closed:
            self._output.feed_data(data)

    def close(self):
        self._closed = True
        self._output.feed_eof()


async def _asyncio_open_serial_unix(path):
    """
    Open a unix socket or a windows named pipe

    :returns: An IO like object
    """

    try:
        # wait for VM to create the pipe file.
        await wait_for_file_creation(path)
    except asyncio.TimeoutError:
        raise NodeError(f'Pipe file "{path}" is missing')

    output = SerialReaderWriterProtocol()
    try:
        await asyncio.get_event_loop().create_unix_connection(lambda: output, path)
    except ConnectionRefusedError:
        raise NodeError(f'Can\'t open pipe file "{path}"')
    return output


async def asyncio_open_serial(path):
    """
    Open an unix socket

    :returns: An IO like object
    """

    return await _asyncio_open_serial_unix(path)
