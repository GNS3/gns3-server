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

import sys
import socket
import asyncio
import asyncio.subprocess
import struct

import logging
log = logging.getLogger(__name__)

# Mostly from https://code.google.com/p/miniboa/source/browse/trunk/miniboa/telnet.py

# Telnet Commands
SE = 240    # End of sub-negotiation parameters
NOP = 241    # No operation
DATMK = 242    # Data stream portion of a sync.
BREAK = 243    # NVT Character BRK
IP = 244    # Interrupt Process
AO = 245    # Abort Output
AYT = 246    # Are you there
EC = 247    # Erase Character
EL = 248    # Erase Line
GA = 249    # The Go Ahead Signal
SB = 250    # Sub-option to follow
WILL = 251    # Will; request or confirm option begin
WONT = 252    # Wont; deny option request
DO = 253    # Do = Request or confirm remote option
DONT = 254    # Don't = Demand or confirm option halt
IAC = 255    # Interpret as Command
SEND = 1      # Sub-process negotiation SEND command
IS = 0      # Sub-process negotiation IS command

# Telnet Options
BINARY = 0      # Transmit Binary
ECHO = 1      # Echo characters back to sender
RECON = 2      # Reconnection
SGA = 3      # Suppress Go-Ahead
TMARK = 6      # Timing Mark
TTYPE = 24     # Terminal Type
NAWS = 31     # Negotiate About Window Size
LINEMO = 34     # Line Mode

READ_SIZE = 1024


class TelnetConnection(object):
    """Default implementation of telnet connection which may but may not be used."""
    def __init__(self, reader, writer, window_size_changed_callback=None):
        log.debug(f"Start TelnetConnection init")
        self.is_closing = False
        self._reader = reader
        self._writer = writer
        self._window_size_changed_callback = window_size_changed_callback

    @property
    def reader(self):
        log.debug(f"Start TelnetConnection reader")
        return self._reader

    @property
    def writer(self):
        return self._writer

    async def connected(self):
        """Method called when client is connected"""
        log.debug(f"Start TelnetConnection connected")
        pass

    async def disconnected(self):
        """Method called when client is disconnecting"""
        log.debug(f"Start TelnetConnection disconnected")
        pass

    async def window_size_changed(self, columns, rows):
        """Method called when window size changed, only can occur when
         `naws` flag is enable in server configuration."""
        log.debug(f"Start TelnetConnection window_size_changed")

        if self._window_size_changed_callback:
            await self._window_size_changed_callback(columns, rows)

    async def feed(self, data):
        """
        Handles incoming data
        :return:
        """
        log.debug(f"Start TelnetConnection feed")

    def send(self, data):
        """
        Sending data back to client
        :return:
        """
        log.debug(f"Start TelnetConnection send")
        data = data.decode().replace("\n", "\r\n")
        self.writer.write(data.encode())

    def close(self):
        """
        Closes current connection
        :return:
        """
        log.debug(f"Start TelnetConnection close")
        self.is_closing = True


class AsyncioTelnetServer:
    MAX_NEGOTIATION_READ = 10

    def __init__(self, reader=None, writer=None, binary=True, echo=False, naws=False, window_size_changed_callback=None, connection_factory=None):
        log.debug(f"Start AsyncioTelnetServer init")
        """
        Initializes telnet server
        :param naws when True make a window size negotiation
        :param connection_factory: when set it's possible to inject own implementation of connection
        """
        assert connection_factory is None or (connection_factory is not None and reader is None and writer is None), \
            "Please use either reader and writer either connection_factory, otherwise duplicate data may be produced."

        self._reader = reader
        self._writer = writer
        self._connections = dict()
        self._lock = asyncio.Lock()
        self._reader_process = None
        self._current_read = None
        self._window_size_changed_callback = window_size_changed_callback

        self._binary = binary
        # If echo is true when the client send data
        # the data is echo on his terminal by telnet otherwise
        # it's our job (or the wrapped app) to send back the data
        self._echo = echo
        self._naws = naws

        def default_connection_factory(reader, writer, window_size_changed_callback):
            log.debug(f"Start connection factory")
            return TelnetConnection(reader, writer, window_size_changed_callback)

        if connection_factory is None:
            connection_factory = default_connection_factory

        self._connection_factory = connection_factory

    @staticmethod
    async def write_client_intro(writer, echo=False):
        log.debug(f"Start async write_clien_intro")
        # Send initial telnet session opening
        if echo:
            writer.write(bytes([IAC, WILL, ECHO]))
        else:
            writer.write(bytes([
                IAC, WONT, ECHO,
                IAC, DONT, ECHO]))
        await writer.drain()

    async def _write_intro(self, writer, binary=False, echo=False, naws=False):
        log.debug(f"Start async _write_intro")
        # Send initial telnet session opening
        if echo:
            writer.write(bytes([IAC, WILL, ECHO]))
        else:
            writer.write(bytes([
                IAC, WONT, ECHO,
                IAC, DONT, ECHO]))

        if binary:
            writer.write(bytes([
                IAC, WILL, SGA,
                IAC, WILL, BINARY,
                IAC, DO, BINARY]))
        else:
            writer.write(bytes([
                IAC, WONT, SGA,
                IAC, DONT, SGA,
                IAC, WONT, BINARY,
                IAC, DONT, BINARY]))

        if naws:
            writer.write(bytes([
                IAC, DO, NAWS
            ]))
        await writer.drain()

    async def run(self, network_reader, network_writer):

        log.debug(f"Start async run")
        sock = network_writer.get_extra_info("socket")
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        #log.debug("New connection from {}".format(sock.getpeername()))

        # Keep track of connected clients
        connection = self._connection_factory(network_reader, network_writer, self._window_size_changed_callback)
        self._connections[network_writer] = connection

        try:
            await self._write_intro(network_writer, echo=self._echo, binary=self._binary, naws=self._naws)
            await connection.connected()
            await self._process(network_reader, network_writer, connection)
        except ConnectionError:
            log.info("Async ConnectionError")
            async with self._lock:
                network_writer.close()
                # await network_writer.wait_closed()  # this doesn't work in Python 3.6
                log.debug(f"self._reader_process == network_reader")
                log.debug(f"{self._reader_process} == {network_reader}")
                if self._reader_process == network_reader:
                    self._reader_process = None
                    # Cancel current read from this reader
                    if self._current_read is not None:
                        self._current_read.cancel()

            await connection.disconnected()
            del self._connections[network_writer]

    async def close(self):
        log.debug(f"Start async close")
        for writer, connection in self._connections.items():
            try:
                writer.write_eof()
                await writer.drain()
                writer.close()
                # await writer.wait_closed()  # this doesn't work in Python 3.6
            except (AttributeError, ConnectionError):
                continue

    async def client_connected_hook(self):
        log.debug(f"Start async client_connected_hook")
        pass

    async def _get_reader(self, network_reader):
        """
        Get a reader or None if another reader is already reading.
        """
        log.debug(f"Start async _get_reader")
        async with self._lock:
            if self._reader_process is None:
                self._reader_process = network_reader
            if self._reader:
                log.debug(f"self._reader_process == network_reader")
                log.debug(f"{self._reader_process} == {network_reader}")
                if self._reader_process == network_reader:
                    self._current_read = asyncio.ensure_future(self._reader.read(READ_SIZE))
                    return self._current_read

        log.debug(f"_get_reader Returning None")
        return None

    async def _process(self, network_reader, network_writer, connection):
        log.debug(f"Start async _process")
        network_read = asyncio.ensure_future(network_reader.read(READ_SIZE))
        reader_read = await self._get_reader(network_reader)

        while True:
            log.debug(f"__process True loop")
            if reader_read is None:
                log.debug(f"__process  reader_read is None")
                reader_read = await self._get_reader(network_reader)
                log.debug(f"__process reader_read is still 2nd None")
            if reader_read is None:
                log.debug(f"__process reader_read is still 3rd None")
                done, pending = await asyncio.wait(
                    [
                        network_read,
                    ],
                    timeout=1,
                    return_when=asyncio.FIRST_COMPLETED)
            else:
                log.debug(f"__process reader_read else")
                done, pending = await asyncio.wait(
                    [
                        network_read,
                        reader_read
                    ],
                    return_when=asyncio.FIRST_COMPLETED)
            log.debug(f"__process just before coro done check")
            log.debug(f"")
            log.debug(f"")
            log.debug(f"")
            for coro in done:
                log.debug(f"__process coro can has done?")
                data = coro.result()
                if coro == network_read:
                    if network_reader.at_eof():
                        raise ConnectionResetError()

                    network_read = asyncio.ensure_future(network_reader.read(READ_SIZE))

                    if IAC in data:
                        data = await self._IAC_parser(data, network_reader, network_writer, connection)

                    if len(data) == 0:
                        continue

                    if not self._binary:
                        data = data.replace(b"\r\n", b"\n")

                    if self._writer:
                        self._writer.write(data)
                        await self._writer.drain()

                    await connection.feed(data)
                    if connection.is_closing:
                        raise ConnectionResetError()

                elif coro == reader_read:
                    if self._reader and self._reader.at_eof():
                        raise ConnectionResetError()

                    reader_read = await self._get_reader(network_reader)

                    # Replicate the output on all clients
                    for connection in self._connections.values():
                        connection.writer.write(data)
                        await connection.writer.drain()

    async def _read(self, cmd, buffer, location, reader):
        """ Reads next op from the buffer or reader"""
        log.debug(f"Start async _read")
        try:
            op = buffer[location]
            cmd.append(op)
            return op
        except IndexError:
            op = await reader.read(1)
            buffer.extend(op)
            cmd.append(buffer[location])
            return op

    async def _negotiate(self, data, connection):
        """ Performs negotiation commands"""
        log.debug(f"Start async _negotiate")

        command, payload = data[0], data[1:]
        if command == NAWS:
            if len(payload) == 4:
                columns, rows = struct.unpack(str('!HH'), bytes(payload))
                await connection.window_size_changed(columns, rows)
            else:
                log.warning('Wrong number of NAWS bytes')
        else:
            log.debug("Not supported negotiation sequence, received {} bytes", len(data))

    async def _IAC_parser(self, buf, network_reader, network_writer, connection):
        log.debug(f"Start async _IAC_parser")
        """
        Processes and removes any Telnet commands from the buffer.

        :param buf: buffer
        :returns: buffer minus Telnet commands
        """


        skip_to = 0
        while True:
            # Locate an IAC to process
            iac_loc = buf.find(IAC, skip_to)
            if iac_loc < 0:
                break

            # Get the TELNET command
            iac_cmd = bytearray([IAC])
            try:
                iac_cmd.append(buf[iac_loc + 1])
            except IndexError:
                d = await network_reader.read(1)
                buf.extend(d)
                iac_cmd.append(buf[iac_loc + 1])

            # Is this just a 2-byte TELNET command?
            if iac_cmd[1] not in [WILL, WONT, DO, DONT, SB]:
                if iac_cmd[1] == AYT:
                    log.debug("Telnet server received Are-You-There (AYT)")
                    network_writer.write(b'\r\nYour Are-You-There received. I am here.\r\n')
                elif iac_cmd[1] == IAC:
                    # It's data, not an IAC
                    iac_cmd.pop()
                    # This prevents the 0xff from being
                    # interrupted as yet another IAC
                    skip_to = iac_loc + 1
                    log.debug("Received IAC IAC")
                elif iac_cmd[1] == NOP:
                    pass
                else:
                    log.debug("Unhandled telnet command: "
                              "{0:#x} {1:#x}".format(*iac_cmd))
            elif iac_cmd[1] == SB:  # starts negotiation commands
                negotiation = []
                for pos in range(2, self.MAX_NEGOTIATION_READ):
                    op = await self._read(iac_cmd, buf, iac_loc + pos, network_reader)
                    negotiation.append(op)
                    if op == SE:
                        # ends negotiation commands
                        break

                # SE command is followed by IAC, remove the last two operations from stack
                await self._negotiate(negotiation[0:-2], connection)

            # This must be a 3-byte TELNET command
            else:
                try:
                    iac_cmd.append(buf[iac_loc + 2])
                except IndexError:
                    d = await network_reader.read(1)
                    buf.extend(d)
                    iac_cmd.append(buf[iac_loc + 2])
                # We do ECHO, SGA, and BINARY. Period.
                if iac_cmd[1] == DO:
                    if iac_cmd[2] not in [ECHO, SGA, BINARY]:
                        network_writer.write(bytes([IAC, WONT, iac_cmd[2]]))
                        log.debug("Telnet WON'T {:#x}".format(iac_cmd[2]))
                    else:
                        if iac_cmd[2] == SGA:
                            if self._binary:
                                network_writer.write(bytes([IAC, WILL, iac_cmd[2]]))
                            else:
                                network_writer.write(bytes([IAC, WONT, iac_cmd[2]]))
                                log.debug("Telnet WON'T {:#x}".format(iac_cmd[2]))

                elif iac_cmd[1] == DONT:
                    log.debug("Unhandled DONT telnet command: "
                              "{0:#x} {1:#x} {2:#x}".format(*iac_cmd))
                elif iac_cmd[1] == WILL:
                    if iac_cmd[2] not in [BINARY, NAWS]:
                        log.debug("Unhandled WILL telnet command: "
                                  "{0:#x} {1:#x} {2:#x}".format(*iac_cmd))
                elif iac_cmd[1] == WONT:
                    log.debug("Unhandled WONT telnet command: "
                              "{0:#x} {1:#x} {2:#x}".format(*iac_cmd))
                else:
                    log.debug("Unhandled telnet command: "
                              "{0:#x} {1:#x} {2:#x}".format(*iac_cmd))

            # Remove the entire TELNET command from the buffer
            buf = buf.replace(iac_cmd, b'', 1)

            await network_writer.drain()

        # Return the new copy of the buffer, minus telnet commands
        return buf

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    loop = asyncio.get_event_loop()

    process = loop.run_until_complete(asyncio.ensure_future(asyncio.subprocess.create_subprocess_exec("/bin/sh", "-i",
                                                                                                      stdout=asyncio.subprocess.PIPE,
                                                                                                      stderr=asyncio.subprocess.STDOUT,
                                                                                                      stdin=asyncio.subprocess.PIPE)))
    server = AsyncioTelnetServer(reader=process.stdout, writer=process.stdin, binary=False, echo=False)

    coro = asyncio.start_server(server.run, '127.0.0.1', 4444)
    s = loop.run_until_complete(coro)

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    # Close the server
    s.close()
    loop.run_until_complete(s.wait_closed())
    loop.close()
