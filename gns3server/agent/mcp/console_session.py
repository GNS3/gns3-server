#
# Copyright (C) 2026 GNS3 Technologies Inc.
# Author: Yue Guobin
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
#

"""
Interactive console sessions for the MCP console tools.

A ConsoleSession is a persistent netmiko connection to one node's console,
keyed by (username, project_id, node_id). The API the tools expose is
stateless; the connection underneath is not — consecutive calls reuse the
same console so the shell session (working directory, environment, a
started-but-unfinished command) survives across tool calls. The console
tools serve Linux shells (gns3_linux_telnet); this layer stays
driver-agnostic and would carry other drivers unchanged:

  - exec()     — driver send_command, run in a thread under the session lock
  - send_raw() — write_channel (control keys like \x03 pass through)
  - read_raw() — drain read_channel with a bounded wait (never blocks long)
  - close()    — disconnect; closing the PTY also kills any hung process

netmiko is imported lazily: it comes from the AI-features extra, and this
module must stay importable without it (mirrors device_config.py).
"""

import asyncio
import logging
import time
from typing import Any, Callable

log = logging.getLogger(__name__)

DEFAULT_SESSION_TTL = 60.0  # seconds without send/read activity before reap
MAX_SESSIONS = 64  # total across all users; LRU-evicted when exceeded


class ConsoleSessionError(Exception):
    """Raised for session-level failures (connect, unsupported console, ...)."""


class ConsoleSession:
    """One persistent console connection, self-reaping after an idle TTL."""

    def __init__(
        self,
        key: tuple[str, str, str],
        node_info: dict[str, Any],
        ttl: float = DEFAULT_SESSION_TTL,
        conn_factory: Callable[[], Any] | None = None,
    ):
        """
        Args:
            key: (username, project_id, node_id)
            node_info: node fields — device_type, console_host, console,
                       default_username, default_password, name
            ttl: idle seconds before the session closes itself
            conn_factory: override for tests; production path builds a
                          netmiko ConnectHandler in a thread
        """
        self.key = key
        self.node_info = node_info
        self.ttl = ttl
        self._conn_factory = conn_factory
        self._conn: Any = None
        self.lock = asyncio.Lock()
        self.last_activity = time.monotonic()
        self.closed = False
        self.close_reason: str | None = None
        self._reaper: asyncio.Task | None = asyncio.create_task(self._reap_when_idle())

    # ── lifecycle ─────────────────────────────────────────────────────────

    def touch(self) -> None:
        self.last_activity = time.monotonic()

    async def _reap_when_idle(self) -> None:
        """Close the session once it has seen no send/read for ttl seconds."""
        try:
            while not self.closed:
                await asyncio.sleep(self.ttl)
                if self.closed:
                    return
                if time.monotonic() - self.last_activity >= self.ttl:
                    await self.close("idle timeout")
                    return
        except asyncio.CancelledError:
            pass

    async def close(self, reason: str = "closed") -> None:
        if self.closed:
            return
        self.closed = True
        self.close_reason = reason
        # Do not cancel ourselves: when the reaper calls close(), cancelling
        # the current task would abort the disconnect below.
        if self._reaper is not None and not self._reaper.done() and asyncio.current_task() is not self._reaper:
            self._reaper.cancel()
        conn, self._conn = self._conn, None
        if conn is not None:
            with _suppress_and_log(f"error disconnecting console session {self.key}"):
                await asyncio.to_thread(conn.disconnect)
        log.debug("Console session %s closed (%s)", self.key, reason)

    # ── connection ────────────────────────────────────────────────────────

    async def _ensure_conn(self):
        if self._conn is not None:
            return self._conn
        if self._conn_factory is not None:
            self._conn = await asyncio.to_thread(self._conn_factory)
            return self._conn

        # Production path: netmiko over the node's telnet console port.
        try:
            from netmiko import ConnectHandler  # lazy: AI-features extra
        except ImportError as e:
            raise ConsoleSessionError(
                "netmiko is not installed. Install AI dependencies with: pip install gns3-server[ai-features]"
            ) from e

        device: dict[str, Any] = {
            "device_type": self.node_info["device_type"],
            "host": self.node_info["console_host"],
            "port": self.node_info["console"],
            "global_delay_factor": 1.0,
        }
        # Credentials for consoles with a login prompt (node/template fields,
        # seeded from appliance metadata). Consoles without login ignore them.
        if self.node_info.get("default_username"):
            device["username"] = self.node_info["default_username"]
        if self.node_info.get("default_password"):
            device["password"] = self.node_info["default_password"]

        log.info(
            "Opening console session %s (%s @ %s:%s)", self.key, device["device_type"], device["host"], device["port"]
        )
        try:
            self._conn = await asyncio.to_thread(ConnectHandler, **device)
        except ConsoleSessionError:
            raise
        except Exception as e:
            raise ConsoleSessionError(f"Could not open console connection: {e}") from e
        return self._conn

    @property
    def alive(self) -> bool:
        return not self.closed

    # ── operations (all serialized by the session lock) ───────────────────

    async def exec(self, command: str, read_timeout: float = 30.0) -> dict[str, Any]:
        """Run one command through the driver and return output + exit code."""
        self.touch()
        async with self.lock:
            conn = await self._ensure_conn()
            try:
                output = await asyncio.to_thread(conn.send_command, command, read_timeout=read_timeout)
            except Exception as e:
                raise ConsoleSessionError(f"Command execution failed: {e}") from e
            self.touch()
            # Only the linux-shell driver parses an exit code from its marker.
            exit_code = getattr(conn, "last_exit_code", None)
            return {"output": output or "", "exit_code": exit_code}

    async def send_raw(self, text: str) -> None:
        """Write raw text (including control keys such as \\x03) to the console."""
        self.touch()
        async with self.lock:
            conn = await self._ensure_conn()
            try:
                await asyncio.to_thread(conn.write_channel, text)
            except Exception as e:
                raise ConsoleSessionError(f"Console write failed: {e}") from e

    async def read_raw(self, wait: float = 5.0, idle: float = 1.0, max_chars: int = 20000) -> str:
        """Drain console output: wait up to `wait` seconds for new data; once
        data is flowing, return after a short `idle` gap. Never blocks long."""
        self.touch()
        async with self.lock:
            conn = await self._ensure_conn()
            collected: list[str] = []
            total = 0
            deadline = time.monotonic() + wait
            last_data = 0.0
            while time.monotonic() < deadline:
                data = await asyncio.to_thread(conn.read_channel)
                if data:
                    collected.append(data)
                    total += len(data)
                    last_data = time.monotonic()
                    if total >= max_chars:
                        break
                elif collected and time.monotonic() - last_data >= idle:
                    break  # data came, then went quiet — good enough
                await asyncio.sleep(0.05)
            self.touch()
            output = "".join(collected)
            return output[:max_chars]


class ConsoleSessionManager:
    """Registry of live console sessions, keyed by (username, project_id, node_id)."""

    def __init__(self, max_sessions: int = MAX_SESSIONS):
        self._sessions: dict[tuple[str, str, str], ConsoleSession] = {}
        self._lock = asyncio.Lock()
        self.max_sessions = max_sessions

    async def get_or_open(
        self,
        username: str,
        project_id: str,
        node_id: str,
        node_info: dict[str, Any],
        ttl: float = DEFAULT_SESSION_TTL,
    ) -> ConsoleSession:
        key = (username, project_id, node_id)
        async with self._lock:
            session = self._sessions.get(key)
            if session is not None and session.alive:
                session.touch()
                return session
            # Evict stale entries, then LRU-evict if still at capacity.
            for stale_key in [k for k, s in self._sessions.items() if not s.alive]:
                del self._sessions[stale_key]
            while len(self._sessions) >= self.max_sessions:
                oldest = min(self._sessions, key=lambda k: self._sessions[k].last_activity)
                evicted = self._sessions.pop(oldest)
                await evicted.close("evicted (session limit)")
            session = ConsoleSession(key, node_info, ttl=ttl)
            self._sessions[key] = session
            return session

    async def get(self, username: str, project_id: str, node_id: str) -> ConsoleSession | None:
        session = self._sessions.get((username, project_id, node_id))
        if session is not None and session.alive:
            return session
        return None

    async def close(self, username: str, project_id: str, node_id: str) -> bool:
        session = self._sessions.pop((username, project_id, node_id), None)
        if session is None:
            return False
        await session.close("closed by client")
        return True

    async def close_all(self) -> None:
        async with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
            for session in sessions:
                await session.close("server shutdown")


_console_session_manager: ConsoleSessionManager | None = None


def get_console_session_manager() -> ConsoleSessionManager:
    global _console_session_manager
    if _console_session_manager is None:
        _console_session_manager = ConsoleSessionManager()
    return _console_session_manager


class _suppress_and_log:
    """contextlib.suppress that logs the exception at debug level."""

    def __init__(self, msg: str):
        self.msg = msg

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc is not None:
            log.debug("%s: %s", self.msg, exc)
        return True
