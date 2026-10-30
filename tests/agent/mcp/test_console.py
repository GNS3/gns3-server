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
from gns3server.agent.mcp.console import _find_session
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
