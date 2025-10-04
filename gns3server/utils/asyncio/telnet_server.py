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

import socket
import asyncio
import asyncio.subprocess

from dataclasses import dataclass
from typing import Optional, Union

import logging

from telnetlib3.stream_writer import TelnetWriter
from telnetlib3.telopt import (
    AYT,
    BINARY,
    DONT,
    DO,
    ECHO,
    GA,
    IAC,
    LINEMODE,
    NAWS,
    NOP,
    SB,
    SE,
    SGA,
    WILL,
    WONT,
)

log = logging.getLogger(__name__)

READ_SIZE = 1024

_C1_ESCAPE_MAP = {value: b"\x1b" + bytes([value - 0x40]) for value in range(0x80, 0xA0)}

_IAC_BYTE = IAC[0]
_SB_BYTE = SB[0]
_SE_BYTE = SE[0]
_IAC_COMMAND_WITH_OPTION = {DO[0], DONT[0], WILL[0], WONT[0]}


class _TelnetCommandFilter:
    """Stateful filter removing telnet IAC negotiation sequences from byte streams."""

    _STATE_DATA = 0
    _STATE_IAC = 1
    _STATE_IAC_OPTION = 2
    _STATE_SB_OPTION = 3
    _STATE_SB = 4
    _STATE_SB_IAC = 5

    def __init__(self):
        self._state = self._STATE_DATA

    def reset(self):
        self._state = self._STATE_DATA

    def feed(self, data: bytes) -> bytes:
        if not data:
            return data

        output = bytearray()

        for byte in data:
            if self._state == self._STATE_DATA:
                if byte == _IAC_BYTE:
                    self._state = self._STATE_IAC
                else:
                    output.append(byte)
            elif self._state == self._STATE_IAC:
                if byte == _IAC_BYTE:
                    # Escaped 0xFF
                    output.append(_IAC_BYTE)
                    self._state = self._STATE_DATA
                elif byte == _SB_BYTE:
                    self._state = self._STATE_SB_OPTION
                elif byte in _IAC_COMMAND_WITH_OPTION:
                    self._state = self._STATE_IAC_OPTION
                else:
                    # One-byte command (e.g. NOP, AYT, GA...)
                    self._state = self._STATE_DATA
            elif self._state == self._STATE_IAC_OPTION:
                # Skip single option byte
                self._state = self._STATE_DATA
            elif self._state == self._STATE_SB_OPTION:
                # Skip the option identifier and enter subnegotiation body
                self._state = self._STATE_SB
            elif self._state == self._STATE_SB:
                if byte == _IAC_BYTE:
                    self._state = self._STATE_SB_IAC
                # Everything else inside SB is ignored
            elif self._state == self._STATE_SB_IAC:
                if byte == _SE_BYTE:
                    self._state = self._STATE_DATA
                elif byte == _IAC_BYTE:
                    # Escaped 0xFF inside subnegotiation, continue consuming
                    self._state = self._STATE_SB
                else:
                    # Unexpected command inside SB; keep consuming the body
                    self._state = self._STATE_SB

        return bytes(output)


def _translate_c1_controls(data: bytes) -> bytes:
    """Convert 8-bit C1 control bytes to their 7-bit ``ESC``-prefixed versions."""

    if not data:
        return data

    for index, byte in enumerate(data):
        replacement = _C1_ESCAPE_MAP.get(byte)
        if replacement is not None:
            break
    else:
        return data

    translated = bytearray(data[:index])
    translated.extend(replacement)

    for byte in data[index + 1 :]:
        replacement = _C1_ESCAPE_MAP.get(byte)
        if replacement is not None:
            translated.extend(replacement)
        else:
            translated.append(byte)

    return bytes(translated)


class _StreamWriterTransportAdapter:
    """Adapter exposing the minimal transport API expected by TelnetWriter."""

    def __init__(self, writer: asyncio.StreamWriter):
        self._writer = writer

    def write(self, data: bytes) -> None:
        self._writer.write(data)

    def write_eof(self) -> None:
        try:
            self._writer.write_eof()
        except (AttributeError, RuntimeError):
            pass

    def can_write_eof(self) -> bool:
        if hasattr(self._writer, "can_write_eof"):
            try:
                return self._writer.can_write_eof()
            except Exception:
                return False
        return False

    def close(self) -> None:
        try:
            self._writer.close()
        except Exception:
            pass

    def is_closing(self) -> bool:
        if hasattr(self._writer, "is_closing"):
            try:
                return self._writer.is_closing()
            except Exception:
                return True
        return True

    def get_extra_info(self, name, default=None):
        return self._writer.get_extra_info(name, default)


class _StreamWriterProtocolAdapter:
    """Minimal protocol adapter used by TelnetWriter."""

    def __init__(self, writer: asyncio.StreamWriter):
        self._writer = writer

    def get_extra_info(self, name, default=None):
        return self._writer.get_extra_info(name, default)

    async def _drain_helper(self):
        await self._writer.drain()

    def connection_lost(self, exc):
        # Nothing special to do here; the server owns the lifecycle.
        pass

    def encoding(self, *, outgoing=False, incoming=False):
        # Binary by default; let higher level handle newline conversions.
        return None


@dataclass
class _TelnetSession:
    writer: TelnetWriter
    transport: _StreamWriterTransportAdapter
    protocol: _StreamWriterProtocolAdapter


class TelnetConnection:
    """Default implementation of telnet connection which may but may not be used."""

    def __init__(self, reader, writer, window_size_changed_callback=None):
        self.is_closing = False
        self._reader = reader
        self._writer = writer
        self._window_size_changed_callback = window_size_changed_callback
        self.telnet_writer: Optional[TelnetWriter] = None

    @property
    def reader(self):
        return self._reader

    @property
    def writer(self):
        return self._writer

    async def connected(self):
        """Method called when client is connected"""
        pass

    async def disconnected(self):
        """Method called when client is disconnecting"""
        pass

    async def window_size_changed(self, columns, rows):
        """Method called when window size changed, only can occur when
        `naws` flag is enable in server configuration."""

        if self._window_size_changed_callback:
            await self._window_size_changed_callback(columns, rows)

    async def feed(self, data):
        """
        Handles incoming data
        :return:
        """

    def send(self, data):
        """
        Sending data back to client
        :return:
        """
        try:
            if not isinstance(data, (bytes, bytearray)):
                raise TypeError("Expected bytes-like object")
            text = _translate_c1_controls(bytes(data))
            payload = text.decode(errors="ignore").replace("\n", "\r\n").encode()
            if self.telnet_writer is not None:
                self.telnet_writer.write(payload)
            else:
                self.writer.write(payload)
        except Exception as exc:
            log.error("Failed to send data to telnet client: %s", exc)

    def close(self):
        """
        Closes current connection
        :return:
        """
        try:
            self.is_closing = True
            if self.telnet_writer is not None:
                self.telnet_writer.close()
        except Exception as exc:
            log.error("Failed to close telnet connection cleanly: %s", exc)


class AsyncioTelnetServer:

    def __init__(
        self,
        reader=None,
        writer=None,
        binary=True,
        echo=False,
        naws=False,
        window_size_changed_callback=None,
        connection_factory=None,
    ):
        """
        Initializes telnet server
        :param naws when True make a window size negotiation
        :param connection_factory: when set it's possible to inject own implementation of connection
        """
        assert connection_factory is None or (
            connection_factory is not None and reader is None and writer is None
        ), "Please use either reader and writer either connection_factory, otherwise duplicate data may be produced."

        self._reader = reader
        self._writer = writer
        self._connections = dict()
        self._sessions = dict()
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
            return TelnetConnection(reader, writer, window_size_changed_callback)

        if connection_factory is None:
            connection_factory = default_connection_factory

        self._connection_factory = connection_factory
        self._backend_filter = _TelnetCommandFilter()

    @staticmethod
    async def write_client_intro(writer, echo=False):
        # Send initial telnet session opening
        if echo:
            writer.write(IAC + WILL + ECHO)
        else:
            writer.write(IAC + WONT + ECHO + IAC + DONT + ECHO)
        await writer.drain()

    async def _write_intro(self, telnet_writer: TelnetWriter, binary=False, echo=False, naws=False):
        # Configure negotiation preferences through telnetlib3 writer
        if echo:
            telnet_writer.iac(WILL, ECHO)
        else:
            telnet_writer.iac(WONT, ECHO)
            telnet_writer.iac(DONT, ECHO)

        if binary:
            telnet_writer.iac(WILL, SGA)
            telnet_writer.iac(WILL, BINARY)
            telnet_writer.iac(DO, BINARY)
        else:
            telnet_writer.iac(WONT, SGA)
            telnet_writer.iac(DONT, SGA)
            telnet_writer.iac(WONT, BINARY)
            telnet_writer.iac(DONT, BINARY)

        if naws:
            telnet_writer.iac(DO, NAWS)

        await telnet_writer.drain()

    def _create_telnet_session(self, network_writer: asyncio.StreamWriter, connection: TelnetConnection) -> _TelnetSession:
        session = self._sessions.get(network_writer)
        if session is not None:
            return session

        transport = _StreamWriterTransportAdapter(network_writer)
        protocol = _StreamWriterProtocolAdapter(network_writer)
        telnet_writer = TelnetWriter(transport=transport, protocol=protocol, server=True)

        loop = asyncio.get_running_loop()

        if self._naws:
            def _on_naws(rows, cols):
                loop.create_task(self._handle_naws_update(connection, rows, cols))

            telnet_writer.set_ext_callback(NAWS, _on_naws)

        def _on_ayt(_cmd):
            telnet_writer.write(b"\r\nYour Are-You-There received. I am here.\r\n")

        telnet_writer.set_iac_callback(AYT, _on_ayt)
        telnet_writer.set_iac_callback(NOP, lambda _cmd: None)

        session = _TelnetSession(writer=telnet_writer, transport=transport, protocol=protocol)
        self._sessions[network_writer] = session
        connection.telnet_writer = telnet_writer
        return session

    async def _handle_naws_update(self, connection: TelnetConnection, rows: int, cols: int) -> None:
        try:
            # Telnetlib3 provides rows first, columns second; convert back to original order.
            await connection.window_size_changed(cols, rows)
        except Exception:  # pragma: no cover - defensive logging only
            log.exception("Failed to propagate NAWS update to connection")

    def _consume_network_data(self, data: Union[bytes, bytearray], session: _TelnetSession) -> bytes:
        if not data:
            return b""

        payload = bytearray()
        for byte in data:
            raw_byte = bytes([byte]) if isinstance(byte, int) else bytes(byte)
            try:
                in_band = session.writer.feed_byte(raw_byte)
            except Exception:  # pragma: no cover - telnetlib3 handles negotiation extensively
                log.exception("Failed to interpret telnet byte during negotiation")
                continue
            if in_band:
                payload.extend(raw_byte)
        return bytes(payload)

    async def run(self, network_reader, network_writer):

        sock = network_writer.get_extra_info("socket")
        if sock is not None:
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                # 60 sec keep alives, close tcp session after 4 missed
                # Will keep a firewall from aging out telnet console.
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 60)
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 4)
            except OSError:
                log.debug("Failed to configure TCP keepalive for telnet client", exc_info=True)

        connection = self._connection_factory(network_reader, network_writer, self._window_size_changed_callback)
        self._connections[network_writer] = connection

        session = self._create_telnet_session(network_writer, connection)

        try:
            await self._write_intro(session.writer, echo=self._echo, binary=self._binary, naws=self._naws)
            await connection.connected()
            await self._process(network_reader, network_writer, connection)
        except ConnectionError:
            async with self._lock:
                network_writer.close()
                # await network_writer.wait_closed()  # this doesn't work in Python 3.6
                if self._reader_process == network_reader:
                    self._reader_process = None
                    # Cancel current read from this reader
                    if self._current_read is not None:
                        self._current_read.cancel()

            await connection.disconnected()
            del self._connections[network_writer]
            session = self._sessions.pop(network_writer, None)
            if session is not None:
                connection.telnet_writer = None
                try:
                    session.writer.close()
                except Exception:
                    pass

    async def close(self):
        for writer, connection in list(self._connections.items()):
            try:
                writer.write_eof()
                await writer.drain()
                writer.close()
                # await writer.wait_closed()  # this doesn't work in Python 3.6
            except (AttributeError, ConnectionError):
                continue
            session = self._sessions.pop(writer, None)
            if session is not None:
                try:
                    session.writer.close()
                except Exception:
                    pass
            connection.telnet_writer = None
            self._connections.pop(writer, None)

    async def client_connected_hook(self):
        pass

    async def _get_reader(self, network_reader):
        """
        Get a reader or None if another reader is already reading.
        """
        async with self._lock:
            if self._reader_process is None:
                self._reader_process = network_reader
            if self._reader:
                if self._reader_process == network_reader:
                    self._current_read = asyncio.ensure_future(self._reader.read(READ_SIZE))
                    return self._current_read
        return None

    async def _process(self, network_reader, network_writer, connection):
        network_read = asyncio.ensure_future(network_reader.read(READ_SIZE))
        reader_read = await self._get_reader(network_reader)
        session = self._sessions.get(network_writer)

        while True:
            if reader_read is None:
                reader_read = await self._get_reader(network_reader)
            if reader_read is None:
                done, pending = await asyncio.wait(
                    [
                        network_read,
                    ],
                    timeout=1,
                    return_when=asyncio.FIRST_COMPLETED,
                )
            else:
                done, pending = await asyncio.wait([network_read, reader_read], return_when=asyncio.FIRST_COMPLETED)
            for coro in done:
                data = coro.result()
                if coro == network_read:
                    if network_reader.at_eof():
                        raise ConnectionResetError()

                    network_read = asyncio.ensure_future(network_reader.read(READ_SIZE))

                    if session is not None:
                        data = self._consume_network_data(data, session)

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

                    data = self._backend_filter.feed(data)
                    if not data:
                        continue

                    # Replicate the output on all clients
                    outbound = _translate_c1_controls(data)
                    for connection_key in list(self._connections.keys()):
                        client_info = connection_key.get_extra_info("socket", None)
                        client_connection = self._connections[connection_key]
                        client_session = self._sessions.get(connection_key)

                        try:
                            if client_session is not None:
                                client_session.writer.write(outbound)
                                await asyncio.wait_for(client_session.writer.drain(), timeout=10)
                            else:
                                client_connection.writer.write(outbound)
                                await asyncio.wait_for(client_connection.writer.drain(), timeout=10)
                        except:
                            log.debug(
                                "Timeout while sending data to client: %s, closing and removing from connection table.",
                                client_info,
                            )
                            client_connection.close()
                            del self._connections[connection_key]
                            self._sessions.pop(connection_key, None)



if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    loop = asyncio.get_event_loop()

    process = loop.run_until_complete(
        asyncio.ensure_future(
            asyncio.subprocess.create_subprocess_exec(
                "/bin/sh",
                "-i",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                stdin=asyncio.subprocess.PIPE,
            )
        )
    )
    server = AsyncioTelnetServer(reader=process.stdout, writer=process.stdin, binary=False, echo=False)

    coro = asyncio.start_server(server.run, "127.0.0.1", 4444)
    s = loop.run_until_complete(coro)

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    # Close the server
    s.close()
    loop.run_until_complete(s.wait_closed())
    loop.close()
