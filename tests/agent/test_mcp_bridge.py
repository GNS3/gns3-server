# SPDX-License-Identifier: GPL-3.0-or-later
#
# GNS3-Copilot - AI-powered Network Lab Assistant for GNS3
#
# This file is part of GNS3-Copilot project.
#
# GNS3-Copilot is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your
# option) any later version.
#
# GNS3-Copilot is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
# for more details.
#
# You should have received a copy of the GNU General Public License
# along with GNS3-Copilot. If not, see <https://www.gnu.org/licenses/>.
#
# Copyright (C) 2025 Yue Guobin (岳国宾)
# Author: Yue Guobin (岳国宾)
#
# Project Home: https://github.com/yueguobin/gns3-copilot
#

"""
Tests for the copilot ← MCP tool bridge (tools_v2/mcp_bridge.py).

The bridge reuses the MCP server's tool registration as the single source
of truth for the copilot's LangChain tools. These tests pin the filter
(project-scoped allowlist, no administration tools), the drift guard on
requested names, the args-model generation, and the sync/async context
bridging.
"""

import asyncio
import json
from typing import Any

import pytest

from gns3server.agent.gns3_copilot.tools_v2 import mcp_bridge
from gns3server.agent.gns3_copilot.tools_v2.mcp_bridge import (
    MCP_ALLOWED_TOOLS,
    NATIVE_TOOL_NAMES,
    _run_coro_sync,
    _unwrap_mcp_content,
    adapted_mcp_tools,
)


def test_allowlist_excludes_administration_tools() -> None:
    """The copilot runs inside one project: management tools stay out."""
    banned = {
        "project_list",
        "project_create",
        "project_delete",
        "project_open",
        "project_close",
        "template_create",
        "template_update",
        "template_delete",
        "compute_list",
        "compute_get",
        "appliance_list",
        "appliance_install",
        "image_list",
        "image_delete",
        "image_prune",
        "server_version",
        "server_statistics",
    }
    assert banned & MCP_ALLOWED_TOOLS == set()


def test_every_allowed_tool_exists_on_the_mcp_server() -> None:
    """The allowlist must not reference tools the MCP server does not register."""
    from gns3server.agent.mcp import mcp

    registered = {tool.name for tool in mcp._tool_manager.list_tools()}
    assert MCP_ALLOWED_TOOLS <= registered


def test_adapted_pool_is_allowlist_minus_native_shadows() -> None:
    tools = adapted_mcp_tools()
    names = {tool.name for tool in tools}
    assert names == MCP_ALLOWED_TOOLS - NATIVE_TOOL_NAMES
    # link_create is served by the copilot-native wrapper (port-name
    # resolution) and must not be adapted.
    assert "link_create" not in names


def test_adapted_subset_preserves_order_and_drift_guard() -> None:
    tools = adapted_mcp_tools(names=["node_start", "node_stop"])
    assert [tool.name for tool in tools] == ["node_start", "node_stop"]

    with pytest.raises(RuntimeError, match="not available to the copilot"):
        adapted_mcp_tools(names=["node_start", "no_such_tool"])


def test_adapted_args_model_matches_mcp_schema() -> None:
    tool = next(t for t in adapted_mcp_tools() if t.name == "node_create")
    fields = tool.args_schema.model_fields
    # required parameter carried over from the MCP JSON schema
    assert "project_id" in fields
    assert fields["project_id"].is_required()
    # optional parameters keep their MCP defaults
    assert fields["compute_id"].default == "local"
    assert fields["x"].default == 0
    # **kwargs-style MCP tools surface a plain dict "kwargs" parameter
    node_update = next(t for t in adapted_mcp_tools() if t.name == "node_update")
    assert "kwargs" in node_update.args_schema.model_fields


def test_unwrap_mcp_content() -> None:
    assert _unwrap_mcp_content([{"type": "text", "text": json.dumps({"a": 1})}]) == {"a": 1}
    assert _unwrap_mcp_content([{"type": "text", "text": "plain text"}]) == "plain text"
    assert _unwrap_mcp_content({"already": "a dict"}) == {"already": "a dict"}
    assert _unwrap_mcp_content("bare string") == "bare string"


def test_run_coro_sync_without_running_loop() -> None:
    async def value() -> int:
        return 42

    assert _run_coro_sync(value()) == 42


def test_run_coro_sync_inside_running_loop() -> None:
    """Sync tool code executing on the event loop thread must still work."""

    async def value() -> int:
        return 7

    async def main() -> int:
        return _run_coro_sync(value())

    assert asyncio.run(main()) == 7


class _FakeMcpTool:
    """Minimal stand-in for an mcp.server.mcpserver Tool."""

    name = "fake_probe"
    description = "Fake tool for bridge tests."
    parameters: dict[str, Any] = {
        "properties": {"x": {"type": "integer", "description": "a number"}},
        "required": ["x"],
        "type": "object",
    }

    async def fn(self, x: int) -> list[dict[str, str]]:
        # Report the contextvars the bridge was supposed to set, proving
        # they survived the thread/loop hop into the handler context.
        from gns3server.agent.mcp import _jwt_token_var, _jwt_token_version_var, _jwt_username_var

        return [
            {
                "type": "text",
                "text": json.dumps(
                    {
                        "x": x,
                        "token": _jwt_token_var.get(),
                        "username": _jwt_username_var.get(),
                        "token_version": _jwt_token_version_var.get(),
                    }
                ),
            }
        ]


class _FakeTokenData:
    username = "tester"
    token_version = 3


def test_invoke_bridges_copilot_context_into_mcp_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    """The copilot's JWT must reach the MCP contextvars inside the handler."""
    monkeypatch.setattr(
        mcp_bridge, "build_gns3_ctx", lambda: {"jwt_token": "copilot-jwt", "server_url": "http://127.0.0.1:3080"}
    )
    monkeypatch.setattr(mcp_bridge.auth_service, "get_token_data", lambda token: _FakeTokenData())

    tool = mcp_bridge._adapt(_FakeMcpTool())
    result = tool.invoke({"x": 5})

    assert result == {"x": 5, "token": "copilot-jwt", "username": "tester", "token_version": 3}


def test_invoke_without_token_returns_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mcp_bridge, "build_gns3_ctx", lambda: None)

    tool = mcp_bridge._adapt(_FakeMcpTool())
    result = tool.invoke({"x": 5})

    assert "error" in result


class TestModeToolsets:
    """Pin the exact copilot mode toolset composition.

    The mode tables are the visible capability contract of the copilot:
    adapted MCP tools plus a few copilot-native ones. Any change here is a
    deliberate product decision and must update this test.
    """

    @staticmethod
    def _names(tools: list) -> set[str]:
        return {tool.name for tool in tools}

    @pytest.fixture(scope="class")
    def modes(self) -> dict[str, set[str]]:
        from gns3server.agent.gns3_copilot.agent.gns3_copilot import (
            LAB_AUTOMATION_ASSISTANT_MODE_TOOLS,
            TEACHING_ASSISTANT_MODE_TOOLS,
            TROUBLESHOOTING_INJECTION_MODE_TOOLS,
        )

        return {
            "teaching": self._names(TEACHING_ASSISTANT_MODE_TOOLS),
            "lab": self._names(LAB_AUTOMATION_ASSISTANT_MODE_TOOLS),
            "injection": self._names(TROUBLESHOOTING_INJECTION_MODE_TOOLS),
        }

    def test_teaching_assistant(self, modes: dict[str, set[str]]) -> None:
        assert modes["teaching"] == {
            "template_list",
            "template_get",
            "node_create",
            "node_update",
            "node_list",
            "node_get",
            "drawing_create_text",
            "drawing_create_rectangle",
            "drawing_create_ellipse",
            "node_start",
            "link_list",
            "link_marker",
            "device_show_run",
            "device_skill_get",
            # copilot-native
            "link_create",
            "wait_seconds",
            "packet_analysis",
            "packet_analysis_skills",
        }

    def test_lab_automation_assistant(self, modes: dict[str, set[str]]) -> None:
        assert modes["lab"] == {
            "template_list",
            "template_get",
            "node_create",
            "node_update",
            "node_list",
            "node_start",
            "node_stop",
            "node_suspend",
            "node_console_exec",
            "drawing_create_text",
            "drawing_create_rectangle",
            "drawing_create_ellipse",
            "device_show_run",
            "device_config_send",
            "vpcs_config_set",
            "device_skill_get",
            "snapshot_list",
            "snapshot_create",
            "snapshot_delete",
            "snapshot_restore",
            # copilot-native
            "link_create",
            "wait_seconds",
            "packet_analysis",
            "packet_analysis_skills",
        }

    def test_troubleshooting_injection(self, modes: dict[str, set[str]]) -> None:
        assert modes["injection"] == {
            "device_show_run",
            "device_config_send",
            "link_update",
            "link_available_filters",
            "link_capture_start",
            "link_capture_stop",
            "link_capture_download",
            "marker_definition",
            "injection_skill_get",
            # copilot-native
            "gns3_topology_reader",
        }

    def test_no_administration_tools_leak_into_any_mode(self, modes: dict[str, set[str]]) -> None:
        banned_prefixes = ("project_", "compute_", "appliance_", "image_", "server_")
        banned = {"template_create", "template_update", "template_delete"}
        for mode_name, names in modes.items():
            leaked = {n for n in names if n.startswith(banned_prefixes)} | (names & banned)
            assert not leaked, f"{mode_name} mode leaks administration tools: {leaked}"

    def test_every_mode_tool_is_resolvable(self, modes: dict[str, set[str]]) -> None:
        """Every tool name in every mode must be constructible (no typos)."""
        from gns3server.agent.gns3_copilot.agent.gns3_copilot import tools_by_name

        for mode_name, names in modes.items():
            missing = names - set(tools_by_name)
            assert not missing, f"{mode_name} mode references unknown tools: {missing}"
