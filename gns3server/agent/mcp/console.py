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
MCP tool handlers for interactive console access — Linux shell consoles only.

Four tools on top of ConsoleSession (console_session.py):

  console_exec   — guarded command, run through the Linux shell driver
                   (exit-code marker completion), output + exact exit code
  console_send   — raw write (control keys such as \\x03 pass through)
  console_read   — drain console output collected since the last read
  console_close  — close the session explicitly

Transport follows the node's console_type, like the web console does: telnet,
docker_exec and unset use the gns3_linux_telnet driver; ssh uses
gns3_linux_ssh (the GNS3 SSH console proxy, no authentication layer). The
netmiko_device_type field only identifies the Linux family — a template that
says gns3_linux_telnet keeps working when its console_type is switched to ssh.

These tools deliberately do NOT serve network OS consoles: interactive config
mode (conf t → (config)# → (config-if)#) is a prompt state machine that the
batch tools already own (netmiko send_config_set enters/exits config mode
itself), and prompt-based completion misfires on mode-changing commands.
Network OS config and diagnostics go to device_config_send / device_show_run;
VPCS goes to vpcs_config_set. Any other device type is rejected with a
pointer to the right tool. No value at all is equally an error (no guessing —
a wrong driver fails in confusing ways).

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

# The driver's sentinel PS1 (mirrors linux_shell.PS1_SENTINEL; kept as a
# literal so this module stays importable without netmiko). It must never
# leak into console_read output — it is our own plumbing, not device data.
PS1_SENTINEL = "__MCP_PROMPT__"

# Netmiko device types these tools serve (both are the same Linux shell
# driver over different transports). The node field may name either one;
# console_type below picks the transport actually used.
LINUX_TELNET_DEVICE_TYPE = "gns3_linux_telnet"
LINUX_SSH_DEVICE_TYPE = "gns3_linux_ssh"
SHELL_DEVICE_TYPES = frozenset({LINUX_TELNET_DEVICE_TYPE, LINUX_SSH_DEVICE_TYPE})

# console_type → transport. telnet/docker_exec/unset are telnet-speaking
# (docker's docker_exec console is an AsyncioTelnetServer); ssh is the
# GNS3 AsyncioSSHServer proxy. The rest (vnc/spice/http/https) are not byte
# consoles at all and belong to node_console.
TELNET_CONSOLE_TYPES = (None, "telnet", "docker_exec")
SSH_CONSOLE_TYPES = ("ssh",)

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


def _reject_non_linux(device_type: str | None, node_name: str | None) -> dict[str, Any] | None:
    """In-band rejection for consoles these tools do not serve, or None to
    proceed. Anything that is not a Linux shell driver is pointed at the
    batch tool that owns it — the rejection is the routing hint."""
    if device_type in SHELL_DEVICE_TYPES:
        return None
    if device_type is None:
        return {
            "status": "failed",
            "error": "No device type found for this node. The console tools only serve Linux shells: set the "
            f"template/node 'netmiko_device_type' field to '{LINUX_TELNET_DEVICE_TYPE}' (telnet console) or "
            f"'{LINUX_SSH_DEVICE_TYPE}' (ssh console), or add a 'device_type:<type>' tag. "
            "List available types via the netmiko device-types endpoint.",
            "node": node_name,
        }
    if device_type == "gns3_vpcs_telnet":
        return {
            "status": "failed",
            "error": "The console tools only serve Linux shells; this node is a VPCS PC (gns3_vpcs_telnet). "
            "Use vpcs_config_set (batch, validated) for VPCS configuration.",
            "node": node_name,
        }
    return {
        "status": "failed",
        "error": f"The console tools only serve Linux shells (netmiko_device_type '{LINUX_TELNET_DEVICE_TYPE}' or "
        f"'{LINUX_SSH_DEVICE_TYPE}'); this node is '{device_type}' (a network OS). Use device_config_send to push "
        "configuration and device_show_run to inspect it — the batch drivers manage config mode themselves.",
        "node": node_name,
    }


def _console_device_type(node: dict[str, Any]) -> str:
    """Netmiko device type to connect with, chosen by the node's console_type.

    console_type is authoritative for the transport (it is what GNS3 used to
    build the console proxy); the netmiko_device_type field only identifies
    the Linux family, so switching a template from a telnet to an ssh console
    does not require editing the device type. Nodes with an unsupported
    console type never reach this helper — _resolve_target_sync rejects them.
    """
    if node.get("console_type") in SSH_CONSOLE_TYPES:
        return LINUX_SSH_DEVICE_TYPE
    return LINUX_TELNET_DEVICE_TYPE


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

    # console_type selects the console transport (telnet/docker_exec/unset →
    # telnet, ssh → SSH). Types without a byte console (vnc, spice, http,
    # https) belong to node_console.
    console_type = node.get("console_type")
    if console_type not in TELNET_CONSOLE_TYPES and console_type not in SSH_CONSOLE_TYPES:
        return {
            "status": "failed",
            "error": f"Console type '{console_type}' has no byte console these tools can drive "
            "(supported: telnet, ssh, docker_exec). For VNC/SPICE/HTTP consoles use the node_console tool instead.",
        }
    if node.get("status") != "started":
        return {
            "status": "failed",
            "error": f"Node '{node.get('name')}' is not started (status: {node.get('status')}). Start it first (node_start).",
        }
    if not node.get("console"):
        return {"status": "failed", "error": f"Node '{node.get('name')}' has no console port assigned."}

    device_type = _device_type_from_node(node)
    rejection = _reject_non_linux(device_type, node.get("name"))
    if rejection is not None:
        return rejection
    return node


async def _resolve_target(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    """Resolve in a worker thread; REST/transport failures become in-band
    errors instead of escaping as bare tool crashes (the controller can
    e.g. answer 403 "project is not opened")."""
    try:
        return await asyncio.to_thread(_resolve_target_sync, params, gns3_ctx)
    except Exception as e:
        log.debug("console target resolution failed", exc_info=True)
        return {"status": "failed", "error": f"Node lookup failed: {e}"}


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

    node = await _resolve_target(params, gns3_ctx)
    if "node_id" not in node:
        return node  # in-band error dict

    rejection = guard_command(command, "shell")
    if rejection is not None:
        rejection["node"] = node.get("name")
        return rejection

    manager = get_console_session_manager()
    session = await manager.get_or_open(
        gns3_ctx.get("jwt_username") or "unknown",
        node["project_id"],
        node["node_id"],
        _node_session_info(node, _console_device_type(node)),
        ttl=ttl,
    )
    try:
        result = await session.exec(command, read_timeout=read_timeout)
    except ConsoleSessionError as e:
        return {"status": "failed", "error": str(e), "node": node.get("name")}
    output, truncated = _truncate(result["output"], max_chars)
    if result.get("timed_out"):
        # The command is still running on the console — not a failure.
        return {
            "status": "timeout",
            "node": node.get("name"),
            "output": output,
            "exit_code": None,
            "truncated": truncated,
            "hint": f"Command not complete within {read_timeout:.0f}s and still running. Poll with console_read "
            "(a __MCP_DONE_<code>__ line marks completion, the code is the exit code) or interrupt with "
            "console_send text '\\x03'.",
        }
    return {
        "status": "ok",
        "node": node.get("name"),
        "output": output,
        "exit_code": result.get("exit_code"),
        "truncated": truncated,
    }


async def console_send_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    """Write raw text/keystrokes to a node console without waiting for output."""
    node = await _resolve_target(params, gns3_ctx)
    if "node_id" not in node:
        return node
    text = params.get("text") or ""

    # Plain command-looking text is screened too (control keys pass by design).
    rejection = guard_command(text, "shell")
    if rejection is not None:
        rejection["node"] = node.get("name")
        return rejection

    manager = get_console_session_manager()
    session = await manager.get_or_open(
        gns3_ctx.get("jwt_username") or "unknown",
        node["project_id"],
        node["node_id"],
        _node_session_info(node, _console_device_type(node)),
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
    node = await _resolve_target(params, gns3_ctx)
    if "node_id" not in node:
        return None, node
    session = await manager.get(user, node["project_id"], node["node_id"])
    if session is None:
        return None, {
            "status": "failed",
            "error": "No open console session for this node. Run console_exec or console_send first.",
        }
    return session, None


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
    # The sentinel PS1 is our own plumbing — never let it reach the caller.
    # The __MCP_DONE_<code>__ marker is deliberately KEPT: it is the
    # completion signal the caller polls for after an interrupt.
    clean = ANSI_ESCAPE_PATTERN.sub("", output).replace(PS1_SENTINEL, "")
    output, truncated = _truncate(clean, max_chars)
    return {"status": "ok", "node": session.node_info.get("name"), "output": output, "truncated": truncated}


async def console_close_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    """Close the console session for a node (releases the device's VTY line)."""
    manager = get_console_session_manager()
    user = gns3_ctx.get("jwt_username") or "unknown"
    closed = await manager.close(user, params.get("project_id"), params.get("node_id"))
    if not closed:
        node = await _resolve_target(params, gns3_ctx)
        if "node_id" in node:
            closed = await manager.close(user, node["project_id"], node["node_id"])
    return {"status": "ok", "closed": closed}
