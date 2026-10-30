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
Unit tests for the MCP console session layer (fake connection, no I/O).
"""

import asyncio
import time

import pytest

from gns3server.agent.mcp.console_session import (
    ConsoleSession,
    ConsoleSessionError,
    ConsoleSessionManager,
)


class FakeConnection:
    """Minimal netmiko-shaped connection for tests."""

    def __init__(self, outputs: list[str] | None = None, fail_on_exec: bool = False):
        self.outputs = list(outputs or [])
        self.writes: list[str] = []
        self.disconnected = False
        self.fail_on_exec = fail_on_exec
        self.last_exit_code = None

    def send_command(self, command, read_timeout=None, **kwargs):
        if self.fail_on_exec:
            raise RuntimeError("device exploded")
        self.writes.append(command)
        self.last_exit_code = 0
        return self.outputs.pop(0) if self.outputs else ""

    def write_channel(self, data):
        self.writes.append(data)

    def read_channel(self):
        return self.outputs.pop(0) if self.outputs else ""

    def disconnect(self):
        self.disconnected = True


NODE_INFO = {
    "device_type": "gns3_linux_telnet",
    "console_host": "127.0.0.1",
    "console": 5001,
    "name": "n1",
}


async def _make_session(outputs=None, ttl=60.0, fail_on_exec: bool = False) -> tuple[ConsoleSession, FakeConnection]:
    fake = FakeConnection(outputs, fail_on_exec=fail_on_exec)
    session = ConsoleSession(("alice", "p1", "n1"), NODE_INFO, ttl=ttl, conn_factory=lambda: fake)
    return session, fake


@pytest.mark.asyncio
async def test_exec_returns_output_and_exit_code():
    session, fake = await _make_session(outputs=["hello\nworld"])
    result = await session.exec("uptime")
    assert result["output"] == "hello\nworld"
    assert result["exit_code"] == 0
    assert fake.writes == ["uptime"]
    await session.close()


@pytest.mark.asyncio
async def test_exec_without_exit_code_attribute():
    """netmiko network drivers have no last_exit_code — must be None, not raise."""

    class NoExitCodeConn(FakeConnection):
        def send_command(self, command, read_timeout=None, **kwargs):
            self.writes.append(command)
            return "Version 15.x"

    conn = NoExitCodeConn()
    session = ConsoleSession(("alice", "p1", "n1"), NODE_INFO, conn_factory=lambda: conn)
    result = await session.exec("show version")
    assert result["exit_code"] is None
    assert result["output"] == "Version 15.x"
    await session.close()


@pytest.mark.asyncio
async def test_exec_timeout_reports_still_running():
    """A driver-reported timeout is a result, not an error: partial output,
    no exit code, timed_out True (the command keeps running)."""

    class SlowConn(FakeConnection):
        last_timed_out = True

        def send_command(self, command, read_timeout=None, **kwargs):
            self.writes.append(command)
            return "64 bytes from 10.0.0.1"  # partial output before the deadline

    conn = SlowConn()
    session = ConsoleSession(("alice", "p1", "n1"), NODE_INFO, conn_factory=lambda: conn)
    result = await session.exec("ping 10.0.0.1", read_timeout=5)
    assert result["timed_out"] is True
    assert result["exit_code"] is None
    assert "64 bytes" in result["output"]
    await session.close()


@pytest.mark.asyncio
async def test_exec_failure_wrapped():
    session, fake = await _make_session(fail_on_exec=True)
    with pytest.raises(ConsoleSessionError, match="Command execution failed"):
        await session.exec("boom")
    await session.close()


@pytest.mark.asyncio
async def test_send_raw_passes_control_keys():
    session, fake = await _make_session()
    await session.send_raw("\x03")
    assert fake.writes == ["\x03"]
    await session.close()


@pytest.mark.asyncio
async def test_read_raw_collects_and_stops_on_idle():
    outputs = ["chunk1 ", "chunk2 ", "", "", ""]
    session, fake = await _make_session(outputs=outputs)
    data = await session.read_raw(wait=2.0, idle=0.2)
    assert "chunk1" in data and "chunk2" in data
    await session.close()


@pytest.mark.asyncio
async def test_read_raw_timeout_with_no_data():
    session, _ = await _make_session()
    start = time.monotonic()
    data = await session.read_raw(wait=0.3, idle=0.1)
    assert data == ""
    assert time.monotonic() - start < 2.0
    await session.close()


@pytest.mark.asyncio
async def test_idle_ttl_reaps_session():
    session, fake = await _make_session(ttl=0.2)
    await session.exec("uptime")  # establish the connection so reaping must disconnect it
    await asyncio.sleep(0.5)
    assert session.closed
    assert session.close_reason == "idle timeout"
    assert fake.disconnected


@pytest.mark.asyncio
async def test_activity_postpones_reaping():
    session, _ = await _make_session(ttl=0.3)
    for _ in range(3):
        await asyncio.sleep(0.15)
        await session.exec("ping")
    assert not session.closed
    await session.close()


@pytest.mark.asyncio
async def test_operations_serialized_by_lock():
    """Concurrent exec calls must not interleave on the same connection."""
    import time as _time

    slow = FakeConnection()

    def slow_exec(cmd, read_timeout=None, **kw):
        # Sync on purpose: exec() runs drivers in a worker thread
        _time.sleep(0.05)
        slow.writes.append(cmd)
        return "ok"

    slow.send_command = slow_exec
    session = ConsoleSession(("alice", "p1", "n1"), NODE_INFO, conn_factory=lambda: slow)
    await asyncio.gather(*(session.exec(f"c{i}") for i in range(5)))
    assert slow.writes == ["c0", "c1", "c2", "c3", "c4"]
    await session.close()


@pytest.mark.asyncio
async def test_manager_reuses_session_per_key():
    mgr = ConsoleSessionManager()
    fake = FakeConnection()
    session = ConsoleSession(("alice", "p1", "n1"), NODE_INFO, conn_factory=lambda: fake)
    mgr._sessions[("alice", "p1", "n1")] = session
    again = await mgr.get_or_open("alice", "p1", "n1", NODE_INFO)
    assert again is session
    # Different user gets a different session object for the same node
    other = await mgr.get_or_open("bob", "p1", "n1", NODE_INFO)
    assert other is not session
    await mgr.close_all()
    assert session.closed and other.closed


@pytest.mark.asyncio
async def test_manager_evicts_lru_at_capacity():
    mgr = ConsoleSessionManager(max_sessions=2)
    sessions = []
    for i, user in enumerate(("u1", "u2", "u3")):
        if i > 0:
            await asyncio.sleep(0.01)  # distinct activity timestamps
        sessions.append(await mgr.get_or_open(user, "p1", "n1", NODE_INFO))
    assert len(mgr._sessions) == 2
    assert sessions[0].closed and sessions[0].close_reason.startswith("evicted")
    assert not sessions[1].closed and not sessions[2].closed
    await mgr.close_all()


@pytest.mark.asyncio
async def test_manager_close_removes_session():
    mgr = ConsoleSessionManager()
    fake = FakeConnection()
    session = ConsoleSession(("alice", "p1", "n1"), NODE_INFO, conn_factory=lambda: fake)
    mgr._sessions[("alice", "p1", "n1")] = session
    await session.exec("uptime")  # establish the connection first
    assert await mgr.close("alice", "p1", "n1") is True
    assert session.closed and fake.disconnected
    assert await mgr.close("alice", "p1", "n1") is False
