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
Unit tests for the MCP console tool handlers (no I/O, REST monkeypatched).
"""

import pytest

import gns3server.agent.mcp.console as console
from gns3server.agent.mcp.console import (
    _console_device_type,
    _find_session,
    _node_session_info,
    _reject_non_linux,
    _resolve_target_sync,
    console_exec_handler,
    console_read_handler,
)
from gns3server.agent.mcp.console_session import ConsoleSession, ConsoleSessionManager

NODE = {
    "node_id": "n-uuid",
    "project_id": "p-uuid",
    "name": "linux-1",
    "status": "started",
    "console_type": "telnet",
    "console": 5001,
    "console_host": "127.0.0.1",
    "netmiko_device_type": "gns3_linux_telnet",
}


@pytest.fixture
def fresh_manager(monkeypatch):
    """Give each test an empty session manager (the module uses a singleton)."""
    manager = ConsoleSessionManager()
    monkeypatch.setattr(console, "get_console_session_manager", lambda: manager)
    return manager


@pytest.mark.asyncio
async def test_find_session_by_names_finds_uuid_keyed_session(fresh_manager, monkeypatch):
    """Regression: the slow path (names → resolve → UUID lookup) hit an
    UnboundLocalError when the session WAS found — the exact crash behind
    'Error executing tool console_read' in live testing."""
    session = ConsoleSession(("alice", "p-uuid", "n-uuid"), dict(NODE))
    fresh_manager._sessions[("alice", "p-uuid", "n-uuid")] = session
    monkeypatch.setattr(console, "_resolve_target_sync", lambda params, ctx: dict(NODE))

    found, error = await _find_session({"project_id": "my-proj", "node_id": "linux-1"}, {"jwt_username": "alice"})
    assert found is session
    assert error is None
    await fresh_manager.close_all()


@pytest.mark.asyncio
async def test_find_session_uuid_fast_path(fresh_manager):
    session = ConsoleSession(("alice", "p-uuid", "n-uuid"), dict(NODE))
    fresh_manager._sessions[("alice", "p-uuid", "n-uuid")] = session

    found, error = await _find_session({"project_id": "p-uuid", "node_id": "n-uuid"}, {"jwt_username": "alice"})
    assert found is session
    assert error is None
    await fresh_manager.close_all()


@pytest.mark.asyncio
async def test_find_session_without_session_is_in_band_error(fresh_manager, monkeypatch):
    monkeypatch.setattr(console, "_resolve_target_sync", lambda params, ctx: dict(NODE))

    found, error = await _find_session({"project_id": "my-proj", "node_id": "linux-1"}, {"jwt_username": "alice"})
    assert found is None
    assert error["status"] == "failed"
    assert "No open console session" in error["error"]


@pytest.mark.asyncio
async def test_find_session_node_error_passes_through(fresh_manager, monkeypatch):
    monkeypatch.setattr(console, "_resolve_target_sync", lambda params, ctx: {"status": "failed", "error": "nope"})

    found, error = await _find_session({"project_id": "x", "node_id": "y"}, {})
    assert found is None
    assert error == {"status": "failed", "error": "nope"}


class TestRejectNonLinux:
    """The console tools serve Linux shells only; everything else is routed."""

    def test_linux_shell_allowed(self):
        assert _reject_non_linux("gns3_linux_telnet", "n1") is None

    def test_network_os_rejected_with_batch_pointer(self):
        result = _reject_non_linux("cisco_ios_telnet", "R-1")
        assert result["status"] == "failed"
        assert "device_config_send" in result["error"] and "device_show_run" in result["error"]

    def test_vpcs_rejected_with_vpcs_pointer(self):
        result = _reject_non_linux("gns3_vpcs_telnet", "PC1")
        assert result["status"] == "failed"
        assert "vpcs_config_set" in result["error"]

    def test_missing_device_type_explains_the_field(self):
        result = _reject_non_linux(None, "n1")
        assert result["status"] == "failed"
        assert "gns3_linux_telnet" in result["error"]

    def test_linux_ssh_family_allowed(self):
        assert _reject_non_linux("gns3_linux_ssh", "n1") is None


class TestTransportSelection:
    """console_type picks the transport; the node field only marks the family."""

    def test_telnet_consoles(self):
        for console_type in (None, "telnet", "docker_exec"):
            node = {**NODE, "console_type": console_type}
            assert _console_device_type(node) == "gns3_linux_telnet", console_type

    def test_ssh_console(self):
        assert _console_device_type({**NODE, "console_type": "ssh"}) == "gns3_linux_ssh"

    def test_ssh_console_wins_over_telnet_family_field(self):
        """A template may keep netmiko_device_type gns3_linux_telnet while its
        console_type is switched to ssh — no template edit required."""
        node = {**NODE, "console_type": "ssh", "netmiko_device_type": "gns3_linux_telnet"}
        assert _console_device_type(node) == "gns3_linux_ssh"


class TestResolveConsoleTypeGate:
    """_resolve_target_sync accepts byte consoles only."""

    def _resolve(self, monkeypatch, console_type):
        import gns3server.agent.gns3_copilot.gns3_client.api_handlers as api_handlers

        monkeypatch.setattr(console, "resolve_locators", lambda params, run: (dict(params), None))
        monkeypatch.setattr(api_handlers, "get_node_handler", lambda p, c: {**NODE, "console_type": console_type})
        return _resolve_target_sync({"project_id": "p-uuid", "node_id": "n-uuid"}, {})

    def test_ssh_accepted(self, monkeypatch):
        assert self._resolve(monkeypatch, "ssh")["node_id"] == "n-uuid"

    def test_docker_exec_accepted(self, monkeypatch):
        assert self._resolve(monkeypatch, "docker_exec")["node_id"] == "n-uuid"

    def test_vnc_rejected_with_node_console_pointer(self, monkeypatch):
        result = self._resolve(monkeypatch, "vnc")
        assert result["status"] == "failed"
        assert "node_console" in result["error"]


class _FakeConn:
    """netmiko-shaped connection the session layer can drive."""

    def __init__(self):
        self.writes = []
        self.last_exit_code = 0
        self.last_timed_out = False
        self.outputs = []

    def send_command(self, command, read_timeout=None, **kwargs):
        self.writes.append(command)
        return self.outputs.pop(0) if self.outputs else ""

    def write_channel(self, data):
        self.writes.append(data)

    def read_channel(self):
        return self.outputs.pop(0) if self.outputs else ""

    def disconnect(self):
        pass


@pytest.mark.asyncio
async def test_exec_resolve_failure_is_in_band(fresh_manager, monkeypatch):
    """A REST failure during resolution (e.g. 403 project not opened) must
    not escape as a bare tool error."""
    monkeypatch.setattr(
        console, "_resolve_target_sync", lambda params, ctx: (_ for _ in ()).throw(RuntimeError("403 boom"))
    )
    result = await console_exec_handler({"project_id": "p", "node_id": "n", "command": "uptime"}, {})
    assert result["status"] == "failed"
    assert "403 boom" in result["error"]


@pytest.mark.asyncio
async def test_exec_timeout_status_with_partial_output(fresh_manager, monkeypatch):
    conn = _FakeConn()
    conn.send_command = lambda command, read_timeout=None, **kw: "partial output"
    conn.last_timed_out = True  # what the real driver reports on a timeout
    conn.last_exit_code = None
    session_info = _node_session_info(NODE, "gns3_linux_telnet")
    session = ConsoleSession(("alice", "p-uuid", "n-uuid"), session_info, conn_factory=lambda: conn)
    fresh_manager._sessions[("alice", "p-uuid", "n-uuid")] = session
    monkeypatch.setattr(console, "_resolve_target_sync", lambda params, ctx: dict(NODE))

    result = await console_exec_handler(
        {"project_id": "p", "node_id": "linux-1", "command": "sleep 30", "timeout": 5}, {"jwt_username": "alice"}
    )
    assert result["status"] == "timeout"
    assert result["output"] == "partial output"
    assert result["exit_code"] is None
    assert "console_read" in result["hint"]
    await fresh_manager.close_all()


@pytest.mark.asyncio
async def test_read_strips_sentinel_keeps_marker(fresh_manager, monkeypatch):
    conn = _FakeConn()
    conn.outputs = ["__MCP_PROMPT__ 64 bytes from 10.0.0.1\r\n__MCP_DONE_0__\r\n__MCP_PROMPT__ "]
    session_info = _node_session_info(NODE, "gns3_linux_telnet")
    session = ConsoleSession(("alice", "p-uuid", "n-uuid"), session_info, conn_factory=lambda: conn)
    fresh_manager._sessions[("alice", "p-uuid", "n-uuid")] = session
    monkeypatch.setattr(console, "_resolve_target_sync", lambda params, ctx: dict(NODE))

    result = await console_read_handler(
        {"project_id": "p", "node_id": "linux-1", "wait": 0.3}, {"jwt_username": "alice"}
    )
    assert result["status"] == "ok"
    assert "__MCP_PROMPT__" not in result["output"]
    assert "__MCP_DONE_0__" in result["output"]  # the completion signal survives
    await fresh_manager.close_all()
