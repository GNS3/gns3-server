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

import asyncio
import asyncio.subprocess
import contextlib
import logging
import socket

import telnetlib3
from telnetlib3.server import TelnetServer
from telnetlib3.telopt import DONT, ECHO, IAC, NAWS, NOP, WILL, WONT

log = logging.getLogger(__name__)

READ_SIZE = 1024
BROADCAST_DRAIN_TIMEOUT = 10
KEEPALIVE_INTERVAL = 60  # Send NOP every 60 seconds


class _ManagedTelnetListener:
    """Compatibility wrapper that owns AsyncioTelnetServer shutdown."""

    def __init__(self, telnet_server, listener):
        self._telnet_server = telnet_server
        self._listener = listener
        self._close_task = None

    def close(self):
        if self._close_task is None:
            self._close_task = asyncio.create_task(self._telnet_server.close())

    async def wait_closed(self):
        self.close()
        with contextlib.suppress(asyncio.CancelledError):
            await self._close_task

    def __getattr__(self, attribute):
        return getattr(self._listener, attribute)


class TelnetConnection:
    """Default implementation of telnet connection which may but may not be used."""

    def __init__(self, reader, writer, window_size_changed_callback=None):
        self.is_closing = False
        self._reader = reader
        self._writer = writer
        self._window_size_changed_callback = window_size_changed_callback

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
        `naws` flag is enabled in server configuration."""

        if self._window_size_changed_callback:
            await self._window_size_changed_callback(columns, rows)

    async def feed(self, data):
        """Handles incoming data."""

    def send(self, data):
        """Send data back to client."""

        data = data.decode().replace("\n", "\r\n")
        self.writer.write(data.encode())

    def close(self):
        """Close current connection."""

        self.is_closing = True


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
        keepalive_interval=KEEPALIVE_INTERVAL,
    ):
        """
        Initialize telnet server.

        :param naws: when True, window size negotiation callbacks are enabled.
        :param connection_factory: optional factory to inject a custom connection implementation.
        :param keepalive_interval: interval in seconds for sending NOP keep-alive (0 to disable).
        """

        assert connection_factory is None or (
            connection_factory is not None and reader is None and writer is None
        ), "Please use either reader and writer either connection_factory, otherwise duplicate data may be produced."

        self._reader = reader
        self._writer = writer
        self._window_size_changed_callback = window_size_changed_callback
        self._binary = binary
        self._echo = echo
        self._naws = naws
        self._keepalive_interval = keepalive_interval

        self._connections = {}
        self._pending_window_sizes = {}
        self._connections_lock = asyncio.Lock()
        self._close_lock = asyncio.Lock()
        self._broadcast_task = None
        self._keepalive_task = None
        self._server = None
        self._server_handle = None

        def default_connection_factory(reader, writer, window_size_changed_callback):
            return TelnetConnection(reader, writer, window_size_changed_callback)

        if connection_factory is None:
            connection_factory = default_connection_factory

        self._connection_factory = connection_factory

    @staticmethod
    async def write_client_intro(writer, echo=False):
        """Write a minimal telnet intro to an upstream console endpoint."""

        if echo:
            writer.write(IAC + WILL + ECHO)
        else:
            writer.write(IAC + WONT + ECHO + IAC + DONT + ECHO)
        await writer.drain()

    async def start(self, host, port):
        """Start a telnetlib3-backed listener and return a managed server handle."""

        if self._server is not None:
            raise RuntimeError("AsyncioTelnetServer is already started")

        protocol_factory = self._build_protocol_factory()
        self._server = await telnetlib3.create_server(
            host=host,
            port=port,
            protocol_factory=protocol_factory,
            shell=self._run_client_session,
            encoding=False,
            force_binary=self._binary,
            never_send_ga=True,
            line_mode=not self._binary,
            timeout=0,
            connect_maxwait=1.0,
        )
        self._server_handle = _ManagedTelnetListener(self, self._server)

        if self._reader is not None and self._broadcast_task is None:
            self._broadcast_task = asyncio.create_task(self._broadcast_from_upstream())

        if self._keepalive_interval > 0 and self._keepalive_task is None:
            self._keepalive_task = asyncio.create_task(self._send_keepalives())

        return self._server_handle

    async def run(self, network_reader, network_writer):
        """Backward-compatible entrypoint for asyncio.start_server(server.run, ...)."""

        await self._run_client_session(network_reader, network_writer)

    async def close(self):
        async with self._close_lock:
            if self._keepalive_task is not None:
                keepalive_task = self._keepalive_task
                self._keepalive_task = None
                keepalive_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await keepalive_task

            if self._broadcast_task is not None:
                broadcast_task = self._broadcast_task
                self._broadcast_task = None
                broadcast_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await broadcast_task
            else:
                await self._disconnect_all_clients()

            if self._server is not None:
                self._server.close()
                await self._server.wait_closed()
                self._server = None

            self._server_handle = None

    async def client_connected_hook(self):
        pass

    def _build_protocol_factory(self):
        parent = self

        class GNS3TelnetServer(TelnetServer):
            def _negotiate_echo(self):
                if self._echo_negotiated:
                    return
                self._echo_negotiated = True

                if self.line_mode:
                    return

                if parent._echo:
                    self.writer.iac(WILL, ECHO)
                else:
                    self.writer.iac(WONT, ECHO)
                    self.writer.iac(DONT, ECHO)

            def begin_advanced_negotiation(self):
                super().begin_advanced_negotiation()
                if not parent._naws:
                    self.writer.iac(DONT, NAWS)

            def on_naws(self, rows, cols):
                super().on_naws(rows, cols)
                parent._handle_naws(self.writer, cols, rows)

        return GNS3TelnetServer

    def _handle_naws(self, writer, columns, rows):
        if not self._naws:
            return
        asyncio.create_task(self._dispatch_window_size(writer, columns, rows))

    async def _dispatch_window_size(self, writer, columns, rows):
        async with self._connections_lock:
            connection = self._connections.get(writer)
            if connection is None:
                self._pending_window_sizes[writer] = (columns, rows)
                return

        await self._invoke_window_size_changed(connection, columns, rows)

    async def _invoke_window_size_changed(self, connection, columns, rows):
        try:
            await connection.window_size_changed(columns, rows)
        except asyncio.CancelledError:
            raise
        except (ConnectionError, OSError):
            connection.close()
        except Exception:
            log.exception("Unhandled exception in window_size_changed callback for %r", connection)

    async def _run_client_session(self, network_reader, network_writer):
        self._set_socket_options(network_writer)

        connection = self._connection_factory(network_reader, network_writer, self._window_size_changed_callback)

        async with self._connections_lock:
            self._connections[network_writer] = connection
            pending_window_size = self._pending_window_sizes.pop(network_writer, None)

        if pending_window_size is not None:
            columns, rows = pending_window_size
            await self._invoke_window_size_changed(connection, columns, rows)

        try:
            await connection.connected()
            await self.client_connected_hook()

            while True:
                data = await network_reader.read(READ_SIZE)
                if not data:
                    break

                if not self._binary:
                    data = data.replace(b"\r\n", b"\n")

                if self._writer is not None:
                    self._writer.write(data)
                    await self._writer.drain()

                await connection.feed(data)
                if connection.is_closing:
                    break

        except asyncio.CancelledError:
            raise
        except (ConnectionError, OSError):
            pass
        finally:
            await self._disconnect_client(network_writer)

    async def _broadcast_from_upstream(self):
        try:
            while True:
                data = await self._reader.read(READ_SIZE)
                if not data:
                    break

                for network_writer, connection in await self._get_connections_snapshot():
                    try:
                        connection.writer.write(data)
                        await asyncio.wait_for(connection.writer.drain(), timeout=BROADCAST_DRAIN_TIMEOUT)
                    except (OSError, ConnectionError, asyncio.TimeoutError) as e:
                        client_info = self._get_peername(network_writer)
                        log.debug(
                            "Error sending data to client %s: %s, closing and removing from connection table.",
                            client_info,
                            e,
                        )
                        connection.close()
                        await self._disconnect_client(network_writer)
        except asyncio.CancelledError:
            raise
        except (ConnectionError, OSError):
            pass
        finally:
            await self._disconnect_all_clients()

    async def _send_keepalives(self):
        """Periodically send IAC NOP to all connected clients to keep sessions alive."""

        try:
            while True:
                await asyncio.sleep(self._keepalive_interval)
                for network_writer, connection in await self._get_connections_snapshot():
                    client_info = self._get_peername(network_writer)
                    try:
                        log.debug("Sending keepalive to client %s", client_info)
                        connection.writer.send_iac(IAC + NOP)
                        await asyncio.wait_for(connection.writer.drain(), timeout=BROADCAST_DRAIN_TIMEOUT)
                    except (OSError, ConnectionError, asyncio.TimeoutError) as e:
                        log.debug(
                            "Keepalive failed for client %s: %s, closing connection.",
                            client_info,
                            e,
                        )
                        connection.close()
                        await self._disconnect_client(network_writer)
        except asyncio.CancelledError:
            raise

    async def _get_connections_snapshot(self):
        async with self._connections_lock:
            return list(self._connections.items())

    async def _disconnect_all_clients(self):
        async with self._connections_lock:
            writers = list(self._connections.keys())

        for network_writer in writers:
            await self._disconnect_client(network_writer)

    async def _disconnect_client(self, network_writer):
        async with self._connections_lock:
            connection = self._connections.pop(network_writer, None)
            self._pending_window_sizes.pop(network_writer, None)

        if connection is not None:
            with contextlib.suppress(Exception):
                await connection.disconnected()

        with contextlib.suppress(AttributeError, OSError):
            network_writer.close()

        wait_closed = getattr(network_writer, "wait_closed", None)
        if callable(wait_closed):
            with contextlib.suppress(ConnectionError, OSError):
                await wait_closed()

    @staticmethod
    def _get_peername(network_writer):
        with contextlib.suppress(OSError, AttributeError):
            sock = network_writer.get_extra_info("socket")
            if sock is not None:
                return sock.getpeername()
        return network_writer.get_extra_info("peername")

    @staticmethod
    def _set_socket_options(network_writer):
        sock = network_writer.get_extra_info("socket")
        if sock is None:
            return

        with contextlib.suppress(OSError):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        # 60 sec keep alives, close tcp session after 4 missed.
        # This keeps stateful firewalls from aging out long-lived sessions.
        try:
            if hasattr(socket, "TCP_KEEPIDLE"):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 60)
            elif hasattr(socket, "TCP_KEEPALIVE"):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPALIVE, 60)
            else:
                raise AttributeError("No TCP keepalive idle socket option is available")

            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 4)
        except (AttributeError, OSError):
            log.debug("Failed to tune TCP keepalive for telnet client; using OS defaults", exc_info=True)


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

    loop.run_until_complete(server.start("127.0.0.1", 4444))

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass

    loop.run_until_complete(server.close())
    loop.close()
