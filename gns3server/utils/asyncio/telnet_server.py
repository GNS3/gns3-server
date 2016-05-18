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

import re
import asyncio
import asyncio.subprocess

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


class AsyncioTelnetServer:

    def __init__(self, reader=None, writer=None, binary=True, echo=False):
        self._reader = reader
        self._writer = writer
        self._clients = set()
        self._lock = asyncio.Lock()
        self._reader_process = None
        self._current_read = None

        self._binary = binary
        # If echo is true when the client send data
        # the data is echo on his terminal by telnet otherwise
        # it's our job (or the wrapped app) to send back the data
        self._echo = echo

    @asyncio.coroutine
    def run(self, network_reader, network_writer):
        # Keep track of connected clients
        self._clients.add(network_writer)

        try:
            # Send initial telnet session opening
            if self._echo:
                network_writer.write(bytes([IAC, WILL, ECHO]))
            else:
                network_writer.write(bytes([
                                     IAC, WONT, ECHO,
                                     IAC, DONT, ECHO]))

            if self._binary:
                network_writer.write(bytes([
                    IAC, WILL, SGA,
                    IAC, WILL, BINARY,
                    IAC, DO, BINARY]))
            else:
                network_writer.write(bytes([
                    IAC, WONT, SGA,
                    IAC, DONT, SGA,
                    IAC, WONT, BINARY,
                    IAC, DONT, BINARY]))
            yield from network_writer.drain()

            yield from self._process(network_reader, network_writer)
        except ConnectionResetError:
            with (yield from self._lock):

                network_writer.close()

                if self._reader_process == network_reader:
                    self._reader_process = None
                    # Cancel current read from this reader
                    self._current_read.cancel()
            self._clients.remove(network_writer)

    @asyncio.coroutine
    def _get_reader(self, network_reader):
        """
        Get a reader or None if another reader is already reading.
        """
        with (yield from self._lock):
            if self._reader_process is None:
                self._reader_process = network_reader
            if self._reader_process == network_reader:
                self._current_read = asyncio.async(self._reader.read(READ_SIZE))
                return self._current_read
        return None

    @asyncio.coroutine
    def _process(self, network_reader, network_writer):
        network_read = asyncio.async(network_reader.read(READ_SIZE))
        reader_read = yield from self._get_reader(network_reader)

        while True:
            if reader_read is None:
                reader_read = yield from self._get_reader(network_reader)
            if reader_read is None:
                done, pending = yield from asyncio.wait(
                    [
                        network_read,
                    ],
                    timeout=1,
                    return_when=asyncio.FIRST_COMPLETED)
            else:
                done, pending = yield from asyncio.wait(
                    [
                        network_read,
                        reader_read
                    ],
                    return_when=asyncio.FIRST_COMPLETED)
            for coro in done:
                data = coro.result()

                if coro == network_read:
                    if network_reader.at_eof():
                        raise ConnectionResetError()

                    network_read = asyncio.async(network_reader.read(READ_SIZE))

                    if IAC in data:
                        data = yield from self._IAC_parser(data, network_reader, network_writer)
                    if len(data) == 0:
                        continue

                    if not self._binary:
                        data = data.replace(b"\r\n", b"\n")

                    if self._writer:
                        self._writer.write(data)
                        yield from self._writer.drain()
                elif coro == reader_read:
                    if self._reader.at_eof():
                        raise ConnectionResetError()

                    reader_read = yield from self._get_reader(network_reader)

                    # Replicate the output on all clients
                    for writer in self._clients:
                        writer.write(data)
                        yield from writer.drain()

    def _IAC_parser(self, buf, network_reader, network_writer):
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
                d = yield from network_reader.read(1)
                buf.extend(d)
                iac_cmd.append(buf[iac_loc + 1])

            # Is this just a 2-byte TELNET command?
            if iac_cmd[1] not in [WILL, WONT, DO, DONT]:
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

            # This must be a 3-byte TELNET command
            else:
                try:
                    iac_cmd.append(buf[iac_loc + 2])
                except IndexError:
                    d = yield from network_reader.read(1)
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

            yield from network_writer.drain()

        # Return the new copy of the buffer, minus telnet commands
        return buf

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    loop = asyncio.get_event_loop()

    process = loop.run_until_complete(asyncio.async(asyncio.subprocess.create_subprocess_exec("/bin/sh", "-i",
                                                                                              stdout=asyncio.subprocess.PIPE,
                                                                                              stderr=asyncio.subprocess.STDOUT,
                                                                                              stdin=asyncio.subprocess.PIPE)))
    server = AsyncioTelnetServer(reader=process.stdout, writer=process.stdin, binary=False, echo=False)

    coro = asyncio.start_server(server.run, '127.0.0.1', 4444, loop=loop)
    s = loop.run_until_complete(coro)

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    # Close the server
    s.close()
    loop.run_until_complete(s.wait_closed())
    loop.close()
