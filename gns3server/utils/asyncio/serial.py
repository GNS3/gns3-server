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

import sys
import asyncio

from gns3server.utils.asyncio import wait_for_file_creation, wait_for_named_pipe_creation
from gns3server.compute.error import NodeError

"""
This module handle connection to unix socket or Windows named pipe
"""
if sys.platform.startswith("win"):
    import win32file
    import win32pipe
    import msvcrt


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

    @asyncio.coroutine
    def drain(self):
        pass

    def connection_made(self, transport):
        self.transport = transport

    def data_received(self, data):
        if not self._closed:
            self._output.feed_data(data)

    def close(self):
        self._closed = True
        self._output.feed_eof()


class WindowsPipe:
    """
    Write input and output stream to the same object
    """

    def __init__(self, path):
        self._handle = open(path, "a+b")
        self._pipe = msvcrt.get_osfhandle(self._handle.fileno())

    @asyncio.coroutine
    def read(self, n=-1):
        (read, num_avail, num_message) = win32pipe.PeekNamedPipe(self._pipe, 0)
        if num_avail > 0:
            (error_code, output) = win32file.ReadFile(self._pipe, num_avail, None)
            return output
        yield from asyncio.sleep(0.01)
        return b""

    def at_eof(self):
        return False

    def write(self, data):
        win32file.WriteFile(self._pipe, data)

    @asyncio.coroutine
    def drain(self):
        return

    def close(self):
        pass


@asyncio.coroutine
def _asyncio_open_serial_windows(path):
    """
    Open a windows named pipe

    :returns: An IO like object
    """

    try:
        yield from wait_for_named_pipe_creation(path)
    except asyncio.TimeoutError:
        raise NodeError('Pipe file "{}" is missing'.format(path))
    return WindowsPipe(path)


@asyncio.coroutine
def _asyncio_open_serial_unix(path):
    """
    Open a unix socket or a windows named pipe

    :returns: An IO like object
    """

    try:
        # wait for VM to create the pipe file.
        yield from wait_for_file_creation(path)
    except asyncio.TimeoutError:
        raise NodeError('Pipe file "{}" is missing'.format(path))

    output = SerialReaderWriterProtocol()
    try:
        yield from asyncio.get_event_loop().create_unix_connection(lambda: output, path)
    except ConnectionRefusedError:
        raise NodeError('Can\'t open pipe file "{}"'.format(path))
    return output


@asyncio.coroutine
def asyncio_open_serial(path):
    """
    Open a unix socket or a windows named pipe

    :returns: An IO like object
    """

    if sys.platform.startswith("win"):
        return (yield from _asyncio_open_serial_windows(path))
    else:
        return (yield from _asyncio_open_serial_unix(path))
