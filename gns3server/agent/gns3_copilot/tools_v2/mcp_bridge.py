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
Bridge that reuses the MCP server's tools inside the copilot agent.

The copilot and the MCP server used to maintain two parallel wrapper
layers (LangChain BaseTool classes vs @mcp.tool() functions) over the
same handlers in ``gns3_client.api_handlers`` — descriptions and
parameters drifted apart (compute_id and link_type were missing on the
copilot side for months). This bridge makes the MCP registration the
single source of truth: tool names, descriptions and argument schemas
are taken from the MCP server and wrapped into LangChain tools.

Scope: the copilot runs INSIDE one project, so project management and
server administration tools are filtered out (see MCP_ALLOWED_TOOLS).
``NATIVE_TOOL_NAMES`` lists the opposite case — copilot-native wrappers
that are richer than their MCP counterpart (link_create resolves port
names) and therefore shadow the adapted version.

Context bridging: the MCP tool functions read their JWT from contextvars
set by the MCP transport's auth wrapper. The copilot carries its own
request-scoped token, so the bridge sets those contextvars inside the
coroutine right before invoking the tool function (asyncio.to_thread
propagates the calling context, verified in agent/mcp/__init__.py).
"""

import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field, create_model

from gns3server.agent.gns3_copilot.gns3_client.api_handlers import build_gns3_ctx
from gns3server.services import auth_service

logger = logging.getLogger(__name__)

# Project-scoped tools the copilot may use. Everything else the MCP server
# registers is server/project administration (project_*, template_create/
# update/delete, compute_*, appliance_*, image_*, server_*) and stays out
# because the copilot operates inside a single already-open project.
MCP_ALLOWED_TOOLS = frozenset(
    {
        # nodes
        "node_list",
        "node_get",
        "node_start",
        "node_stop",
        "node_suspend",
        "node_create",
        "node_delete",
        "node_update",
        "node_duplicate",
        "node_isolate",
        "node_unisolate",
        "node_links",
        "node_start_all",
        "node_stop_all",
        "node_suspend_all",
        "node_console_exec",
        # node files
        "node_file_list",
        "node_file_get",
        "node_file_write",
        "node_file_delete",
        # links
        "link_list",
        "link_get",
        "link_delete",
        "link_update",
        "link_available_filters",
        "link_reset",
        "link_capture_start",
        "link_capture_stop",
        "link_capture_download",
        "link_marker",
        "marker_definition",
        # drawings
        "drawing_list",
        "drawing_create_text",
        "drawing_create_rectangle",
        "drawing_create_ellipse",
        "drawing_get",
        "drawing_update",
        "drawing_delete",
        # snapshots
        "snapshot_list",
        "snapshot_create",
        "snapshot_delete",
        "snapshot_restore",
        # templates (read-only; create/update/delete are admin tasks)
        "template_list",
        "template_get",
        # device configuration
        "device_config_send",
        "device_show_run",
        "vpcs_config_set",
        # skills
        "device_skill_get",
        "injection_skill_get",
    }
)

# Copilot-native wrappers that shadow their MCP namesake because they add
# value the MCP tool lacks (link_create accepts port NAMES and resolves
# them to adapter/port numbers). These names are never adapted.
NATIVE_TOOL_NAMES = frozenset({"link_create"})

_JSON_SCHEMA_TYPE_MAP = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "array": list,
    "object": dict,
}

# Cache of adapted tools keyed by MCP tool name — the MCP registration is
# immutable after import, so the wrap happens once per process.
_adapted_cache: dict[str, BaseTool] = {}


def _build_args_model(mcp_tool: Any) -> type[BaseModel]:
    """Build a pydantic args model from the MCP tool's JSON schema."""
    schema = mcp_tool.parameters or {}
    properties = schema.get("properties", {})
    required = set(schema.get("required") or [])
    fields: dict[str, Any] = {}
    for param_name, param_spec in properties.items():
        param_type = _JSON_SCHEMA_TYPE_MAP.get(param_spec.get("type"))
        if param_type is None:
            param_type = Any
        description = param_spec.get("description")
        if param_name in required:
            fields[param_name] = (param_type, Field(..., description=description))
        elif "default" in param_spec:
            fields[param_name] = (param_type, Field(default=param_spec["default"], description=description))
        else:
            fields[param_name] = (param_type | None, Field(default=None, description=description))
    return create_model(f"{mcp_tool.name}_args", **fields)


def _run_coro_sync(coro: Any) -> Any:
    """Run a coroutine to completion from synchronous code.

    In a plain worker thread (no running loop) asyncio.run is enough.
    When called from inside a running event loop (sync tool executed on
    the loop thread), the coroutine runs on a fresh loop in a helper
    thread; the contextvars are set inside the coroutine itself, so the
    thread hop loses nothing.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def _unwrap_mcp_content(raw: Any) -> Any:
    """Unwrap MCP content blocks ([{"type": "text", "text": ...}]) to plain data."""
    if isinstance(raw, list) and raw and all(isinstance(block, dict) and block.get("type") == "text" for block in raw):
        texts = [block.get("text", "") for block in raw]
        if len(texts) == 1:
            try:
                return json.loads(texts[0])
            except (json.JSONDecodeError, TypeError):
                return texts[0]
        return texts
    return raw


def _invoke_mcp_tool(mcp_tool: Any, kwargs: dict[str, Any]) -> Any:
    """Invoke one MCP tool function with the copilot's credentials."""
    ctx = build_gns3_ctx()
    if ctx is None or not ctx.get("jwt_token"):
        return {"error": "No GNS3 authentication token available in this request context."}

    # Handlers that mint short-lived tickets (link_capture_download,
    # node_console_exec) need the username and token_version; decode them
    # from the copilot's own JWT. Handlers that do not need them tolerate
    # the fallbacks.
    username: str | None = None
    token_version = 0
    try:
        token_data = auth_service.get_token_data(ctx["jwt_token"])
        username = token_data.username
        token_version = token_data.token_version
    except Exception:
        logger.debug("Could not decode the copilot JWT for username/token_version")

    async def _call() -> Any:
        # Set inside the coroutine: whatever thread/loop ends up running
        # the handler thread inherits these via asyncio.to_thread's
        # context copy (see _gns3_ctx in agent/mcp/__init__.py).
        from gns3server.agent.mcp import _jwt_token_var, _jwt_token_version_var, _jwt_username_var

        _jwt_token_var.set(ctx["jwt_token"])
        _jwt_username_var.set(username)
        _jwt_token_version_var.set(token_version)
        return await mcp_tool.fn(**kwargs)

    try:
        raw = _run_coro_sync(_call())
    except Exception as e:
        logger.error("MCP tool %s failed via copilot bridge: %s", mcp_tool.name, e, exc_info=True)
        return {"error": f"{type(e).__name__}: {e!s}"}
    return _unwrap_mcp_content(raw)


def _adapt(mcp_tool: Any) -> BaseTool:
    """Wrap one MCP Tool into a LangChain StructuredTool."""

    def _run(**kwargs: Any) -> Any:
        return _invoke_mcp_tool(mcp_tool, kwargs)

    return StructuredTool.from_function(
        func=_run,
        name=mcp_tool.name,
        description=mcp_tool.description or "",
        args_schema=_build_args_model(mcp_tool),
    )


def adapted_mcp_tools(names: list[str] | None = None) -> list[BaseTool]:
    """Return LangChain tools adapted from the MCP server registration.

    Args:
        names: restrict to these MCP tool names (must also be allowed).
                None means every allowed tool except native-shadowed ones.
    """
    # Function-level import: gns3server.agent.mcp pulls the whole MCP
    # stack and imports back into gns3_copilot.gns3_client, so importing
    # it lazily keeps this module safe during package initialization.
    from gns3server.agent.mcp import mcp

    if not _adapted_cache:
        for mcp_tool in mcp._tool_manager.list_tools():
            if mcp_tool.name in MCP_ALLOWED_TOOLS and mcp_tool.name not in NATIVE_TOOL_NAMES:
                _adapted_cache[mcp_tool.name] = _adapt(mcp_tool)

    if names is None:
        return list(_adapted_cache.values())

    missing = [name for name in names if name not in _adapted_cache]
    if missing:
        # Fail loudly at agent construction: a typo or a renamed MCP tool
        # must never silently shrink the copilot toolset.
        raise RuntimeError(
            f"MCP tools not available to the copilot: {missing}. "
            f"Allowed pool has {len(_adapted_cache)} tools; check MCP_ALLOWED_TOOLS "
            "and the MCP registration."
        )
    return [_adapted_cache[name] for name in names]
