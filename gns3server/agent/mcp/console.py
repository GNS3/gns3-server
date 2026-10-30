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
MCP tool handlers for interactive console access.

Four tools on top of ConsoleSession (console_session.py):

  console_exec   — guarded command, run through the node's netmiko driver
                   (prompt-based for network OS, exit-code marker for
                   gns3_linux_telnet), output returned when the command done
  console_send   — raw write (control keys such as \\x03 pass through)
  console_read   — drain console output collected since the last read
  console_close  — close the session explicitly

Family dispatch is a single netmiko_device_type lookup — the same field the
batch config tools resolve (node/template field first, device_type:<x> tag as
fallback). gns3_linux_telnet means the Linux shell driver; any other driver
value means a network OS; no value at all is an error (no guessing — a wrong
driver fails in confusing ways).

Commands are screened against a small high-confidence table of
screen-interactive commands (top, less, tail -f, ...). Rejections carry the
non-interactive alternative so the caller can retry immediately — the error
message is the teaching moment. Control-key writes bypass the screen.
"""

import asyncio
import logging
import re
from typing import Any

from gns3server.agent.mcp.console_guard import guard_command
from gns3server.agent.mcp.console_session import ConsoleSessionError, get_console_session_manager
from gns3server.agent.mcp.locators import resolve_locators

log = logging.getLogger(__name__)

# Shared ANSI escape stripper (same pattern as the custom netmiko drivers).
ANSI_ESCAPE_PATTERN = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")

# The Linux shell driver — the only marker-based family.
SHELL_DEVICE_TYPE = "gns3_linux_telnet"

DEFAULT_READ_TIMEOUT = 30.0
MAX_OUTPUT_CHARS = 20000


# ── Node / family resolution ──────────────────────────────────────────────


def _device_type_from_node(node: dict[str, Any]) -> str | None:
    """Same precedence as the batch config tools: the netmiko_device_type
    field (node → template → appliance, propagated by the controller) wins;
    a device_type:<type> tag is the fallback. Node types with exactly one
    possible driver (VPCS) get that driver as a default — unlike docker,
    where xrd/IOL containers make any default a guess."""
    device_type = node.get("netmiko_device_type")
    if device_type:
        return device_type
    for tag in node.get("tags") or []:
        if tag.startswith("device_type:"):
            return tag.split(":", 1)[1].strip()
    if node.get("node_type") == "vpcs":
        return "gns3_vpcs_telnet"
    return None


def _resolve_target_sync(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    """Fetch the node (names resolved to UUIDs) and validate it for console use.

    Returns the node dict, or an in-band error dict.
    """

    def run(handler, handler_params):
        return handler(handler_params, gns3_ctx)

    from gns3server.agent.gns3_copilot.gns3_client.api_handlers import get_node_handler

    resolved, resolution_error = resolve_locators(params, run)
    if resolved is None:
        return resolution_error
    node = get_node_handler(resolved, gns3_ctx)
    if not isinstance(node, dict) or "node_id" not in node:
        return {
            "status": "failed",
            "error": f"Node not found: {node!r}" if not isinstance(node, dict) else "Node not found",
        }

    # console_type None on docker nodes = the (telnet-style) exec console;
    # an assigned port is the real signal. Only clearly non-telnet consoles
    # (vnc/http) are rejected.
    if node.get("console_type") not in (None, "telnet"):
        return {
            "status": "failed",
            "error": f"Console type '{node.get('console_type')}' is not supported by console tools (telnet only). "
            f"For VNC consoles use the node_console tool instead.",
        }
    if node.get("status") != "started":
        return {
            "status": "failed",
            "error": f"Node '{node.get('name')}' is not started (status: {node.get('status')}). Start it first (node_start).",
        }
    if not node.get("console"):
        return {"status": "failed", "error": f"Node '{node.get('name')}' has no console port assigned."}

    device_type = _device_type_from_node(node)
    if not device_type:
        return {
            "status": "failed",
            "error": "No device type found for this node. Set the template/node 'netmiko_device_type' field "
            f"(e.g. '{SHELL_DEVICE_TYPE}' for Linux shells, 'cisco_ios_telnet' for IOS, 'gns3_vpcs_telnet' for VPCS), "
            "or add a 'device_type:<type>' tag. List available types via the netmiko device-types endpoint.",
            "node": node.get("name"),
        }
    return node


def _node_session_info(node: dict[str, Any], device_type: str) -> dict[str, Any]:
    return {
        "device_type": device_type,
        "console_host": node.get("console_host"),
        "console": node.get("console"),
        "name": node.get("name"),
        "default_username": node.get("default_username"),
        "default_password": node.get("default_password"),
    }


def _truncate(output: str, max_chars: int) -> tuple[str, bool]:
    if len(output) <= max_chars:
        return output, False
    return output[:max_chars], True


# ── Tool handlers ─────────────────────────────────────────────────────────


async def console_exec_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    """Run one command on a node console and return its output."""
    command = params.get("command") or ""
    read_timeout = float(params.get("timeout") or DEFAULT_READ_TIMEOUT)
    ttl = float(params.get("ttl") or 60.0)
    max_chars = int(params.get("max_chars") or MAX_OUTPUT_CHARS)

    node = await asyncio.to_thread(_resolve_target_sync, params, gns3_ctx)
    if "node_id" not in node:
        return node  # in-band error dict

    device_type = _device_type_from_node(node)
    family = "shell" if device_type == SHELL_DEVICE_TYPE else "netos"
    rejection = guard_command(command, family)
    if rejection is not None:
        rejection["node"] = node.get("name")
        return rejection

    manager = get_console_session_manager()
    session = await manager.get_or_open(
        gns3_ctx.get("jwt_username") or "unknown",
        node["project_id"],
        node["node_id"],
        _node_session_info(node, device_type),
        ttl=ttl,
    )
    try:
        result = await session.exec(command, read_timeout=read_timeout)
    except ConsoleSessionError as e:
        return {"status": "failed", "error": str(e), "node": node.get("name")}
    output, truncated = _truncate(result["output"], max_chars)
    return {
        "status": "ok",
        "node": node.get("name"),
        "output": output,
        "exit_code": result.get("exit_code"),
        "truncated": truncated,
        "family": family,
    }


async def console_send_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    """Write raw text/keystrokes to a node console without waiting for output."""
    node = await asyncio.to_thread(_resolve_target_sync, params, gns3_ctx)
    if "node_id" not in node:
        return node
    text = params.get("text") or ""

    device_type = _device_type_from_node(node)
    family = "shell" if device_type == SHELL_DEVICE_TYPE else "netos"
    # Plain command-looking text is screened too (control keys pass by design).
    rejection = guard_command(text, family)
    if rejection is not None:
        rejection["node"] = node.get("name")
        return rejection

    manager = get_console_session_manager()
    session = await manager.get_or_open(
        gns3_ctx.get("jwt_username") or "unknown",
        node["project_id"],
        node["node_id"],
        _node_session_info(node, device_type),
    )
    try:
        await session.send_raw(text)
    except ConsoleSessionError as e:
        return {"status": "failed", "error": str(e), "node": node.get("name")}
    return {"status": "ok", "node": node.get("name"), "sent": text}


async def _find_session(params: dict[str, Any], gns3_ctx: dict[str, Any]):
    """Locate the caller's session for a node, accepting name or UUID ids.

    Tries the ids as given first (fast path for UUIDs); on a miss resolves
    names via the REST API and retries. Returns (session, error_dict).
    """
    manager = get_console_session_manager()
    user = gns3_ctx.get("jwt_username") or "unknown"
    session = await manager.get(user, params.get("project_id"), params.get("node_id"))
    if session is not None:
        return session, None
    node = await asyncio.to_thread(_resolve_target_sync, params, gns3_ctx)
    if "node_id" not in node:
        return None, node
    session = await manager.get(user, node["project_id"], node["node_id"])
    if session is None:
        session, error = (
            None,
            {
                "status": "failed",
                "error": "No open console session for this node. Run console_exec or console_send first.",
            },
        )
    return session, error


async def console_read_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    """Read console output that arrived since the last read (bounded wait)."""
    wait = float(params.get("wait") or 5.0)
    max_chars = int(params.get("max_chars") or MAX_OUTPUT_CHARS)

    session, error = await _find_session(params, gns3_ctx)
    if session is None:
        return error
    try:
        output = await session.read_raw(wait=wait, max_chars=max_chars)
    except ConsoleSessionError as e:
        return {"status": "failed", "error": str(e), "node": session.node_info.get("name")}
    output, truncated = _truncate(ANSI_ESCAPE_PATTERN.sub("", output), max_chars)
    return {"status": "ok", "node": session.node_info.get("name"), "output": output, "truncated": truncated}


async def console_close_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    """Close the console session for a node (releases the device's VTY line)."""
    manager = get_console_session_manager()
    user = gns3_ctx.get("jwt_username") or "unknown"
    closed = await manager.close(user, params.get("project_id"), params.get("node_id"))
    if not closed:
        node = await asyncio.to_thread(_resolve_target_sync, params, gns3_ctx)
        if "node_id" in node:
            closed = await manager.close(user, node["project_id"], node["node_id"])
    return {"status": "ok", "closed": closed}
