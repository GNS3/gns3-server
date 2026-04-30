#
# Copyright (C) 2026 GNS3 Technologies Inc.
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
import contextlib
import logging
import socket

import asyncssh

log = logging.getLogger(__name__)

READ_SIZE = 1024
BROADCAST_DRAIN_TIMEOUT = 10


class _NoAuthSSHServer(asyncssh.SSHServer):
    """Allow console transport without interactive SSH authentication prompts."""

    def begin_auth(self, username):
        return False


class _ManagedSSHListener:
    """Compatibility wrapper that owns AsyncioSSHServer shutdown."""

    def __init__(self, ssh_server, listener):
        self._ssh_server = ssh_server
        self._listener = listener
        self._close_task = None

    def close(self):
        if self._close_task is None:
            self._close_task = asyncio.create_task(self._ssh_server.close())

    async def wait_closed(self):
        self.close()
        with contextlib.suppress(asyncio.CancelledError):
            await self._close_task

    def __getattr__(self, attribute):
        return getattr(self._listener, attribute)


class AsyncioSSHServer:
    def __init__(self, reader=None, writer=None):
        self._reader = reader
        self._writer = writer
        self._sessions = {}
        self._sessions_lock = asyncio.Lock()
        self._writer_lock = asyncio.Lock()
        self._close_lock = asyncio.Lock()
        self._broadcast_task = None
        self._server = None
        self._server_handle = None
        self._host_key = asyncssh.generate_private_key("ssh-rsa")

    async def start(self, host, port):
        if self._server is not None:
            raise RuntimeError("AsyncioSSHServer is already started")

        self._server = await asyncssh.listen(
            host=host,
            port=port,
            server_factory=_NoAuthSSHServer,
            server_host_keys=[self._host_key],
            process_factory=self._run_client_session,
            encoding=None,
            reuse_address=True,
        )
        self._server_handle = _ManagedSSHListener(self, self._server)

        if self._reader is not None and self._broadcast_task is None:
            self._broadcast_task = asyncio.create_task(self._broadcast_from_upstream())

        return self._server_handle

    async def close(self):
        async with self._close_lock:
            if self._broadcast_task is not None:
                broadcast_task = self._broadcast_task
                self._broadcast_task = None
                broadcast_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await broadcast_task

            # Always disconnect all active SSH client sessions so that
            # server.wait_closed() does not block indefinitely waiting for
            # them to finish on their own.
            await self._disconnect_all_clients()

            if self._server is not None:
                self._server.close()
                await self._server.wait_closed()
                self._server = None

            self._server_handle = None

    async def _run_client_session(self, process):
        self._set_socket_options(process)

        async with self._sessions_lock:
            self._sessions[process] = process

        try:
            while True:
                data = await process.stdin.read(READ_SIZE)
                if not data:
                    break

                if self._writer is not None:
                    async with self._writer_lock:
                        self._writer.write(data)
                        await self._writer.drain()
        except asyncio.CancelledError:
            raise
        except (ConnectionError, OSError, asyncssh.Error):
            pass
        finally:
            await self._disconnect_client(process)

    async def _broadcast_from_upstream(self):
        try:
            while True:
                data = await self._reader.read(READ_SIZE)
                if not data:
                    break

                for process in await self._get_sessions_snapshot():
                    try:
                        process.stdout.write(data)
                        await asyncio.wait_for(process.stdout.drain(), timeout=BROADCAST_DRAIN_TIMEOUT)
                    except (OSError, ConnectionError, asyncio.TimeoutError, asyncssh.Error):
                        await self._disconnect_client(process)
        except asyncio.CancelledError:
            raise
        except (ConnectionError, OSError):
            pass
        finally:
            await self._disconnect_all_clients()

    async def _get_sessions_snapshot(self):
        async with self._sessions_lock:
            return list(self._sessions.keys())

    async def _disconnect_all_clients(self):
        async with self._sessions_lock:
            sessions = list(self._sessions.keys())

        for process in sessions:
            await self._disconnect_client(process)

    async def _disconnect_client(self, process):
        async with self._sessions_lock:
            self._sessions.pop(process, None)

        with contextlib.suppress(Exception):
            process.exit(0)

        channel = process.get_extra_info("channel")
        if channel is not None:
            with contextlib.suppress(Exception):
                channel.close()
            wait_closed = getattr(channel, "wait_closed", None)
            if callable(wait_closed):
                with contextlib.suppress(Exception):
                    await wait_closed()

    @staticmethod
    def _set_socket_options(process):
        sock = process.get_extra_info("socket")
        if sock is None:
            return

        with contextlib.suppress(OSError):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

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
            log.debug("Failed to tune TCP keepalive for SSH client; using OS defaults", exc_info=True)
