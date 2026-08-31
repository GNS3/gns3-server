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

"""
MCP (Model Context Protocol) service for GNS3 server.

Implements the standard MCP protocol over SSE transport using FastMCP:

  /v3/mcp/sse     — SSE stream
  /v3/mcp/messages/ — JSON-RPC messages

Tools are registered via @mcp.tool() decorators.
"""

import contextvars
import json
import asyncio
import logging
import socket
from uuid import UUID
import bcrypt
from typing import Any, Annotated
from urllib.parse import parse_qs

from fastapi import APIRouter
from fastapi.responses import Response

from pydantic import Field

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gns3server.config import Config
from gns3server.services.authentication import AuthService
import gns3server.db.models as models
from gns3server.services import auth_service
from gns3server.utils.request_utils import extract_client_info
from gns3server.db.repositories.api_keys import ApiKeysRepository
from gns3server.db.repositories.users import UsersRepository
from .projects import (
    list_projects_handler, get_project_handler, create_project_handler,
    delete_project_handler, open_project_handler, close_project_handler,
    get_project_stats_handler, update_project_handler, duplicate_project_handler,
    get_project_readme_handler, update_project_readme_handler,
    lock_project_handler, unlock_project_handler,
    get_locked_project_handler,
)
from .server import (
    get_version_handler, get_statistics_handler,
)
# Symbol tools are disabled for now: they require a vision-capable model to
# be genuinely useful (the tools shuttle SVG content, which a text-only LLM
# cannot inspect or produce). Revisit later.
# from .symbols import (
#     get_symbols_handler, get_symbol_handler,
#     get_symbol_dimensions_handler, get_default_symbols_handler,
#     upload_symbol_handler, delete_symbol_handler,
# )
from .appliances import (
    get_appliances_handler, get_appliance_handler,
    install_appliance_handler,
)
from .images import (
    get_images_handler, get_image_handler,
    delete_image_handler, prune_images_handler,
    install_images_handler,
)
from .device_config import (
    device_config_send_handler, device_show_run_handler,
    vpcs_config_set_handler,
)
from gns3server.agent.gns3_copilot.gns3_client.api_handlers import (
    get_nodes_handler, get_node_handler, start_node_handler,
    stop_node_handler, suspend_node_handler,
    create_node_handler, delete_node_handler, update_node_handler,
    get_node_console_info_handler,
    list_node_files_handler, get_node_file_handler,
    write_node_file_handler, delete_node_file_handler,
    start_all_nodes_handler, stop_all_nodes_handler,
    suspend_all_nodes_handler,
    duplicate_node_handler, isolate_node_handler,
    unisolate_node_handler, get_node_links_handler,
    get_links_handler, get_link_handler, available_filters_handler,
    create_link_handler,
    delete_link_handler, update_link_handler,
    reset_link_handler, start_capture_handler, stop_capture_handler,
    download_capture_file_handler,
    link_marker_handler, marker_definition_handler,
)
from .templates import (
    list_templates_handler, get_template_handler, create_template_handler,
    update_template_handler, delete_template_handler,
)
from .computes import (
    list_computes_handler, get_compute_handler, get_compute_images_handler,
)
from .snapshots import (
    get_snapshots_handler, create_snapshot_handler,
    delete_snapshot_handler, restore_snapshot_handler,
)
from .drawings import (
    get_drawings_handler, create_drawing_handler,
    get_drawing_handler, update_drawing_handler, delete_drawing_handler,
)

log = logging.getLogger(__name__)

# Suppress noisy telnet connection logs from device config tools.
logging.getLogger("telnetlib3").setLevel(logging.WARNING)

# FastAPI app reference — used to lazily access app.state._db_engine for API key validation.
# The db engine is initialized during the lifespan startup, which runs AFTER
# register_starlette_routes() is called, so we cannot capture it at registration time.
_app = None


# ── Server ready state ────────────────────────────────────────────────
# Tracks whether GNS3 server has completed initialization.
# MCP connections wait up to 5 seconds for startup to complete, then return
# 503 Service Unavailable if initialization is not complete to prevent
# "Received request before initialization was complete" errors.

_mcp_ready_event = asyncio.Event()


def set_mcp_server_ready(ready: bool = True) -> None:
    """
    Set MCP server ready state.

    Should be called after GNS3 startup completes (database, controller, etc.)
    to allow MCP connections to proceed.

    Args:
        ready: True to mark server as ready, False to mark as not ready
    """
    if ready:
        _mcp_ready_event.set()
        log.info("MCP server is now ready to accept connections")
    else:
        _mcp_ready_event.clear()


async def wait_for_mcp_ready() -> bool:
    """
    Wait until MCP server is ready before accepting connections.

    Returns:
        True if server is ready, False if timeout reached

    Returns immediately if already ready. Otherwise waits with a timeout
    and returns False if server does not become ready in time.
    """
    if _mcp_ready_event.is_set():
        return True

    log.debug("MCP server not ready yet, waiting for initialization to complete...")

    try:
        await asyncio.wait_for(_mcp_ready_event.wait(), timeout=5.0)
        log.debug("MCP server is now ready, proceeding with connection")
        return True
    except asyncio.TimeoutError:
        log.warning(
            "MCP server ready check timed out after 5 seconds - "
            "GNS3 server initialization may have issues"
        )
        return False


# ── Per‑connection JWT token  ─────────────────────────────────────────
# Set during SSE authentication, read by tool handlers running in the
# same asyncio task (contextvars propagate through asyncio.to_thread).

_jwt_token_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "mcp_jwt_token", default=None
)
# Username extracted during token validation — used by handlers to generate
# short-lived JWTs for download/console URLs without exposing the raw key.
_jwt_username_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "mcp_jwt_username", default=None
)
# token_version extracted during token validation — short-lived JWTs minted for
# download/console URLs must carry the same version, or the revocation check
# (token_data.token_version != user.token_version) rejects them as "revoked".
_jwt_token_version_var: contextvars.ContextVar[int] = contextvars.ContextVar(
    "mcp_jwt_token_version", default=0
)


# ── Token validation ──────────────────────────────────────────────────

async def _resolve_token(token: str) -> str | None:
    """Validate a token (JWT or API key) and return the effective JWT to use.

    For JWT tokens, returns the token as-is.
    For API keys, validates against the database and returns a fresh short-lived JWT.

    Returns None if the token is invalid.
    """
    # API keys (gns3_...) are never valid JWTs — skip the JWT attempt for them
    # so it doesn't log a spurious "JWT rejected" line on every API-key connection.
    if not token.startswith("gns3_"):
        try:
            token_data = auth_service.get_token_data(token)
            _jwt_username_var.set(token_data.username)
            _jwt_token_version_var.set(token_data.token_version)
            return token
        except Exception:
            pass

    # Try API key — format: gns3_<api_key_id>_<random_secret> → O(1) lookup
    if token.startswith("gns3_") and _app is not None:
        db_engine = getattr(_app.state, "_db_engine", None)
        if db_engine is not None:
            try:
                parts = token.split("_", 2)
                if len(parts) == 3:
                    key_id = UUID(parts[1])
                    secret = parts[2]
                    async with AsyncSession(db_engine, expire_on_commit=False) as db_session:
                        repo = ApiKeysRepository(db_session)
                        db_key = await repo.get_api_key(key_id)
                        if db_key and not db_key.revoked:
                            if await asyncio.to_thread(bcrypt.checkpw, secret.encode(), db_key.key_hash.encode()):
                                await repo.update_last_used(db_key.api_key_id)
                                user_repo = UsersRepository(db_session)
                                user = await user_repo.get_user(db_key.user_id)
                                if user:
                                    _jwt_username_var.set(user.username)
                                    _jwt_token_version_var.set(user.token_version)
                                    fresh_token = auth_service.create_access_token(user.username, token_version=user.token_version)
                                    return fresh_token
            except Exception:
                pass

    return None


# ── Server URL helper ─────────────────────────────────────────────────

def _server_url() -> str:
    cfg = Config.instance().settings
    host = cfg.Server.host
    if host in ("0.0.0.0", "::"):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.settimeout(0.1)
                s.connect(("8.8.8.8", 80))
                host = s.getsockname()[0]
        except OSError:
            host = "127.0.0.1"
    scheme = "https" if cfg.Server.enable_ssl else "http"
    return f"{scheme}://{host}:{cfg.Server.port}"


# ── FastMCP Server ────────────────────────────────────────────────────

def _create_mcp_server() -> FastMCP:
    """Create MCP server with security settings from configuration."""
    cfg = Config.instance().settings.Server

    # Always pass an explicit TransportSecuritySettings to prevent FastMCP
    # from auto-enabling protection when host is localhost (its default).
    if cfg.mcp_enable_dns_rebinding_protection:
        transport_security = TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=cfg.mcp_allowed_hosts or ["127.0.0.1:*", "localhost:*"],
            allowed_origins=cfg.mcp_allowed_origins or ["http://127.0.0.1:*", "http://localhost:*"],
        )
    else:
        transport_security = TransportSecuritySettings(
            enable_dns_rebinding_protection=False,
        )

    mcp = FastMCP("GNS3 MCP Server", transport_security=transport_security)
    return mcp


mcp = _create_mcp_server()


# ── Tool handlers ─────────────────────────────────────────────────────

def _run_handler_sync(handler, params: dict[str, Any]) -> list[dict[str, Any]]:
    """Run a synchronous Gns3Connector handler in a thread."""
    ctx = {
        "server_url": _server_url(),
        "jwt_token": _jwt_token_var.get(),
        "jwt_username": _jwt_username_var.get(),
        "jwt_token_version": _jwt_token_version_var.get(),
    }
    result = handler(params, ctx)
    return [{"type": "text", "text": json.dumps(result, ensure_ascii=False, default=str)}]


@mcp.tool()
async def project_list() -> list[dict[str, Any]]:
    """List all GNS3 projects accessible to the current user."""
    return await asyncio.to_thread(_run_handler_sync, list_projects_handler, {})


@mcp.tool()
async def project_get(
    project_id: Annotated[str, Field(description="UUID of the project")],
) -> list[dict[str, Any]]:
    """Get detailed information about a specific project."""
    return await asyncio.to_thread(_run_handler_sync, get_project_handler, {"project_id": project_id})


@mcp.tool()
async def project_create(
    name: Annotated[str, Field(description="Project name")],
) -> list[dict[str, Any]]:
    """Create a new GNS3 project. auto_close is set to False so the project stays open when clients disconnect."""
    params = {"name": name, "auto_close": False}
    return await asyncio.to_thread(_run_handler_sync, create_project_handler, params)


@mcp.tool()
async def project_delete(
    project_id: Annotated[str, Field(description="UUID of the project to delete")],
) -> list[dict[str, Any]]:
    """Delete a GNS3 project permanently."""
    return await asyncio.to_thread(_run_handler_sync, delete_project_handler, {"project_id": project_id})


@mcp.tool()
async def project_open(
    project_id: Annotated[str, Field(description="UUID of the project to open")],
) -> list[dict[str, Any]]:
    """Open a closed GNS3 project."""
    return await asyncio.to_thread(_run_handler_sync, open_project_handler, {"project_id": project_id})

@mcp.tool()
async def project_close(
    project_id: Annotated[str, Field(description="UUID of the project to close")],
) -> list[dict[str, Any]]:
    """Close an open GNS3 project."""
    return await asyncio.to_thread(_run_handler_sync, close_project_handler, {"project_id": project_id})

@mcp.tool()
async def project_stats(
    project_id: Annotated[str, Field(description="UUID of the project to get statistics for")],
) -> list[dict[str, Any]]:
    """Get statistics (nodes, links, snapshots, drawings) for a project."""
    return await asyncio.to_thread(_run_handler_sync, get_project_stats_handler, {"project_id": project_id})


@mcp.tool()
async def project_update(
    project_id: Annotated[str, Field(description="UUID of the project to update")],
    name: Annotated[str, Field(description="New project name")] = None,
    auto_close: Annotated[bool, Field(description="Close project when last client leaves")] = None,
    auto_open: Annotated[bool, Field(description="Project opens when GNS3 starts")] = None,
    auto_start: Annotated[bool, Field(description="Project starts when opened")] = None,
    scene_width: Annotated[int, Field(description="Width of the drawing area")] = None,
    scene_height: Annotated[int, Field(description="Height of the drawing area")] = None,
    zoom: Annotated[int, Field(description="Zoom of the drawing area")] = None,
    show_layers: Annotated[bool, Field(description="Show layers on the drawing area")] = None,
    snap_to_grid: Annotated[bool, Field(description="Snap to grid on the drawing area")] = None,
    show_grid: Annotated[bool, Field(description="Show the grid on the drawing area")] = None,
    grid_size: Annotated[int, Field(description="Grid size for the drawing area for nodes")] = None,
    drawing_grid_size: Annotated[int, Field(description="Grid size for the drawing area for drawings")] = None,
    show_interface_labels: Annotated[bool, Field(description="Show interface labels on the drawing area")] = None,
) -> list[dict[str, Any]]:
    """Update a project's properties (name, auto_close, auto_open, etc.)."""
    params = {"project_id": project_id}
    local_vars = {
        "name": name, "auto_close": auto_close, "auto_open": auto_open, "auto_start": auto_start,
        "scene_width": scene_width, "scene_height": scene_height, "zoom": zoom,
        "show_layers": show_layers, "snap_to_grid": snap_to_grid, "show_grid": show_grid,
        "grid_size": grid_size, "drawing_grid_size": drawing_grid_size, "show_interface_labels": show_interface_labels,
    }
    for key, val in local_vars.items():
        if val is not None:
            params[key] = val
    return await asyncio.to_thread(_run_handler_sync, update_project_handler, params)


@mcp.tool()
async def project_duplicate(
    project_id: Annotated[str, Field(description="UUID of the project to duplicate")],
    name: Annotated[str, Field(description="New project name")],
    reset_mac_addresses: Annotated[bool, Field(description="Reset MAC addresses for this project")] = False,
) -> list[dict[str, Any]]:
    """Duplicate a project."""
    params = {"project_id": project_id, "name": name}
    if reset_mac_addresses:
        params["reset_mac_addresses"] = reset_mac_addresses
    return await asyncio.to_thread(_run_handler_sync, duplicate_project_handler, params)


@mcp.tool()
async def project_readme_get(
    project_id: Annotated[str, Field(description="UUID of the project")],
) -> list[dict[str, Any]]:
    """Get the content of a project's README.md file — the project documentation (Markdown format)."""
    return await asyncio.to_thread(_run_handler_sync, get_project_readme_handler, {"project_id": project_id})


@mcp.tool()
async def project_readme_update(
    project_id: Annotated[str, Field(description="UUID of the project")],
    content: Annotated[str, Field(description="Content to write to README.md (Markdown format)")],
) -> list[dict[str, Any]]:
    """Update or create a project's README.md file — the project documentation (Markdown format)."""
    return await asyncio.to_thread(_run_handler_sync, update_project_readme_handler, {"project_id": project_id, "content": content})


# ── Node tools ────────────────────────────────────────────────────────

@mcp.tool()
async def node_list(
    project_id: Annotated[str, Field(description="UUID of the project")],
    fields: Annotated[list[str] | None, Field(description="Optional: return only these fields per node. e.g. [\"name\",\"status\"]. Available: name, status, node_type, console, console_type, console_host, node_id, project_id, compute_id, symbol, x, y, z, locked, ports, properties, command_line, node_directory, label, tags, template_id, width, height, aux, aux_type")] = None,
) -> list[dict[str, Any]]:
    """List all nodes in a project. Use fields=[] to return only what you need."""
    return await asyncio.to_thread(_run_handler_sync, get_nodes_handler, {"project_id": project_id, "fields": fields})


@mcp.tool()
async def node_get(
    project_id: Annotated[str, Field(description="UUID of the project")],
    node_id: Annotated[str, Field(description="UUID of the node")],
    fields: Annotated[list[str] | None, Field(description="Optional: return only these fields. e.g. [\"name\",\"status\"]. Available: name, status, node_type, console, console_type, console_host, node_id, project_id, compute_id, symbol, x, y, z, locked, ports, properties, command_line, node_directory, label, tags, template_id, width, height, aux, aux_type")] = None,
) -> list[dict[str, Any]]:
    """Get detailed information about a specific node. Use fields=[] to return only what you need."""
    return await asyncio.to_thread(_run_handler_sync, get_node_handler, {
        "project_id": project_id, "node_id": node_id, "fields": fields,
    })

@mcp.tool()
async def node_start(
    project_id: Annotated[str, Field(description="UUID of the project")],
    node_id: Annotated[str | None, Field(description="Node UUID (single mode)")] = None,
    node_ids: Annotated[list[str] | None, Field(description="Batch mode: [\"uuid1\",\"uuid2\"] — start multiple nodes in parallel")] = None,
) -> list[dict[str, Any]]:
    """Start one or more nodes. Provide node_id for single, or node_ids for batch."""
    params = {"project_id": project_id}
    if node_ids:
        params["node_ids"] = node_ids
    else:
        params["node_id"] = node_id
    return await asyncio.to_thread(_run_handler_sync, start_node_handler, params)

@mcp.tool()
async def node_stop(
    project_id: Annotated[str, Field(description="UUID of the project")],
    node_id: Annotated[str | None, Field(description="Node UUID (single mode)")] = None,
    node_ids: Annotated[list[str] | None, Field(description="Batch mode: [\"uuid1\",\"uuid2\"] — stop multiple nodes in parallel")] = None,
) -> list[dict[str, Any]]:
    """Stop one or more nodes. Provide node_id for single, or node_ids for batch."""
    params = {"project_id": project_id}
    if node_ids:
        params["node_ids"] = node_ids
    else:
        params["node_id"] = node_id
    return await asyncio.to_thread(_run_handler_sync, stop_node_handler, params)

@mcp.tool()
async def node_suspend(
    project_id: Annotated[str, Field(description="UUID of the project")],
    node_id: Annotated[str | None, Field(description="Node UUID (single mode)")] = None,
    node_ids: Annotated[list[str] | None, Field(description="Batch mode: [\"uuid1\",\"uuid2\"] — suspend multiple nodes in parallel")] = None,
) -> list[dict[str, Any]]:
    """Suspend one or more nodes. Provide node_id for single, or node_ids for batch."""
    params = {"project_id": project_id}
    if node_ids:
        params["node_ids"] = node_ids
    else:
        params["node_id"] = node_id
    return await asyncio.to_thread(_run_handler_sync, suspend_node_handler, params)


@mcp.tool()
async def node_create(
    project_id: Annotated[str, Field(description="UUID of the project")],
    template_id: Annotated[str | None, Field(description="Template UUID (required for single mode; used as default in batch mode)")] = None,
    x: Annotated[int, Field(description="X coordinate (canvas center origin, right positive)")] = 0,
    y: Annotated[int, Field(description="Y coordinate (canvas center origin, down positive)")] = 0,
    compute_id: Annotated[str, Field(description="Compute ID (default: local)")] = "local",
    nodes: Annotated[list | None, Field(description="Batch mode: [{name, template_id?, x?, y?, compute_id?}] — top-level template_id applies as default")] = None,
    fields: Annotated[list[str] | None, Field(description="Response fields to include (default: [node_id, name, node_type, status, console]). "
                                                           "Available: compute_id, name, node_type, node_id, console, console_type, "
                                                           "console_auto_start, aux, aux_type, properties, label, symbol, x, y, z, "
                                                           "locked, port_name_format, port_segment_size, first_port_name, "
                                                           "custom_adapters, tags, template_id, project_id, node_directory, "
                                                           "status, command_line, width, height, ports, console_host")] = None,
) -> list[dict[str, Any]]:
    """Create one or more nodes from templates.

    Single mode: provide template_id, x, y (optional compute_id)
    Batch mode:  provide nodes=[{name, template_id?, x?, y?, compute_id?}] — creates up to 100 in parallel.
                 Top-level template_id applies to all nodes; individual nodes can override.
                 Results are always returned in submission order; correlate nodes by node_id, not name.
                 When a node omits `name`, the server assigns a default name (R-1, R-2, ...) and console
                 port — such batches are created sequentially so those assignments follow submission order.
    """
    if nodes is not None:
        return await asyncio.to_thread(_run_handler_sync, create_node_handler, {
            "project_id": project_id, "nodes": nodes, "fields": fields,
            "template_id": template_id,
        })
    return await asyncio.to_thread(_run_handler_sync, create_node_handler, {
        "project_id": project_id, "template_id": template_id,
        "x": x, "y": y, "compute_id": compute_id, "fields": fields,
    })


@mcp.tool()
async def node_delete(
    project_id: Annotated[str, Field(description="UUID of the project")],
    node_id: Annotated[str | None, Field(description="Node UUID (single mode)")] = None,
    node_ids: Annotated[list[str] | None, Field(description="Batch mode: [\"uuid1\",\"uuid2\"] — delete multiple nodes in parallel")] = None,
) -> list[dict[str, Any]]:
    """Delete one or more nodes from a project. Provide node_id for single, or node_ids for batch."""
    params = {"project_id": project_id}
    if node_ids:
        params["node_ids"] = node_ids
    else:
        params["node_id"] = node_id
    return await asyncio.to_thread(_run_handler_sync, delete_node_handler, params)


@mcp.tool()
async def node_update(
    project_id: Annotated[str, Field(description="UUID of the project")],
    node_id: Annotated[str, Field(description="UUID of the node to update")],
    **kwargs: Any,
) -> list[dict[str, Any]]:
    """Update a node's properties (name, position, etc.)."""
    params = {"project_id": project_id, "node_id": node_id, **kwargs}
    return await asyncio.to_thread(_run_handler_sync, update_node_handler, params)


@mcp.tool()
async def node_console(
    project_id: Annotated[str, Field(description="UUID of the project containing the node")],
    node_id: Annotated[str, Field(description="UUID of the node to get console info for")],
) -> list[dict[str, Any]]:
    """Get WebSocket console connection info for a node.

    Returns the console type (telnet/ssh/vnc) and a ready-to-run websocat
    command with a short-lived access token (10 min) already embedded.

    IMPORTANT — copy the returned values EXACTLY:
      - Run the returned "command" string verbatim; it already contains the
        full URL with token. NEVER construct or edit the URL yourself, and
        NEVER copy the token by hand — a mistyped token is rejected.
      - The token expires after token_ttl_seconds (10 min): call this tool
        again to get a fresh one; do not reuse an old URL.

    Sending device commands after connecting:
      > timeout 10 websocat -t --no-close "ws://..." <<< $'\\r\\nenable\\r\\nshow version\\r\\nexit\\r\\n'

      - Use \\r\\n (not \\n) to match console protocol line endings
      - Use $'...' format for escape sequences in bash
      - --no-close keeps the WebSocket open after stdin (heredoc) hits EOF, so
        device output is not cut off before it arrives
      - Set a timeout to prevent hanging connections
    """
    return await asyncio.to_thread(_run_handler_sync, get_node_console_info_handler, {
        "project_id": project_id, "node_id": node_id,
    })


# ── Link tools ────────────────────────────────────────────────────────

@mcp.tool()
async def link_list(
    project_id: Annotated[str, Field(description="UUID of the project")],
    fields: Annotated[list[str] | None, Field(description="Optional: return only these fields. e.g. [\"link_id\",\"nodes\"]. Available: link_id, project_id, link_type, nodes, suspend, filters, capturing, capture_file_name, link_style")] = None,
) -> list[dict[str, Any]]:
    """List all links in a project. Use fields=[] to return only what you need."""
    return await asyncio.to_thread(_run_handler_sync, get_links_handler, {"project_id": project_id, "fields": fields})


@mcp.tool()
async def link_get(
    project_id: Annotated[str, Field(description="UUID of the project")],
    link_id: Annotated[str, Field(description="UUID of the link")],
) -> list[dict[str, Any]]:
    """Get detailed information about a specific link."""
    return await asyncio.to_thread(_run_handler_sync, get_link_handler, {"project_id": project_id, "link_id": link_id})


@mcp.tool()
async def link_create(
    project_id: Annotated[str, Field(description="UUID of the project")],
    nodes: Annotated[list | None, Field(description="Single mode: [{node_id, adapter_number, port_number}] or compact [id, ad, pt, id, ad, pt]")] = None,
    link_type: Annotated[str, Field(description="Link type - ethernet or serial")] = "ethernet",
    filters: Annotated[dict | None, Field(description="Optional packet filters")] = None,
    links: Annotated[list | None, Field(description="Batch mode: [{nodes, link_type?, filters?}] — nodes supports compact [id, ad, pt, id, ad, pt] format")] = None,
    fields: Annotated[list[str] | None, Field(description="Response fields to include (default: [link_id, link_type, nodes]). "
                                                           "Available: link_id, project_id, link_type, nodes, suspend, "
                                                           "link_style, filters, show_filters_icon, capturing, "
                                                           "capture_file_name, capture_file_path, capture_compute_id, wireshark")] = None,
) -> list[dict[str, Any]]:
    """Create one or more links between nodes.

    Single mode: provide nodes, link_type (optional filters)
    Batch mode:  provide links=[{nodes, link_type?, filters?}] — up to 100 in parallel
    """
    if links:
        return await asyncio.to_thread(_run_handler_sync, create_link_handler, {
            "project_id": project_id, "links": links, "fields": fields,
        })
    params = {"project_id": project_id, "nodes": nodes, "link_type": link_type, "fields": fields}
    if filters:
        params["filters"] = filters
    return await asyncio.to_thread(_run_handler_sync, create_link_handler, params)


@mcp.tool()
async def link_delete(
    project_id: Annotated[str, Field(description="UUID of the project")],
    link_id: Annotated[str | None, Field(description="Link UUID (single mode)")] = None,
    link_ids: Annotated[list[str] | None, Field(description="Batch mode: [\"uuid1\",\"uuid2\"] — delete multiple links in parallel")] = None,
) -> list[dict[str, Any]]:
    """Delete one or more links from a project."""
    params = {"project_id": project_id}
    if link_ids:
        params["link_ids"] = link_ids
    else:
        params["link_id"] = link_id
    return await asyncio.to_thread(_run_handler_sync, delete_link_handler, params)


@mcp.tool()
async def link_update(
    project_id: Annotated[str, Field(description="UUID of the project")],
    link_id: Annotated[str, Field(description="UUID of the link to update")],
    **kwargs: Any,
) -> list[dict[str, Any]]:
    """Update a link's properties (suspend, filters, etc.).

    Supported kwargs:
    - suspend: boolean - Suspend or resume the link
    - filters: dict - Packet filters (must use array format):
      * frequency_drop: [N] - Drop every Nth packet (N: -1 to 32767)
      * packet_loss: [rate] - Packet loss percentage (rate: 0 to 100)
      * delay: [ms, jitter] - Latency and jitter in milliseconds
      * corrupt: [rate] - Packet corruption percentage (rate: 0 to 100)
      * bpf: [expression] - Berkeley Packet Filter expression

    Example filters:
      {"filters": {"frequency_drop": [10]}}
      {"filters": {"delay": [100, 10]}}
      {"filters": {"packet_loss": [5]}}
      {"filters": {"delay": [50, 5], "packet_loss": [2]}}

    To clear all filters: {"filters": {}}

    Filters are applied **bidirectionally** — a packet crossing the link twice
    (e.g. ping round-trip) is filtered in both directions independently.
    For example, packet_loss: [50] gives ~75% observed loss (1 - 0.5²), not 50%.
    ARP frames also pass through filters; at high loss/corrupt rates, pre-set
    static ARP entries to avoid false "Destination Host Unreachable" errors.
    """
    params = {"project_id": project_id, "link_id": link_id, **kwargs}
    return await asyncio.to_thread(_run_handler_sync, update_link_handler, params)


@mcp.tool()
async def link_available_filters(
    project_id: Annotated[str, Field(description="UUID of the project")],
    link_id: Annotated[str, Field(description="UUID of the link")],
) -> list[dict[str, Any]]:
    """List the packet filter types available for a link (frequency_drop, packet_loss, delay, corrupt, bpf)
    with their parameters. Use before setting filters with link_update."""
    return await asyncio.to_thread(_run_handler_sync, available_filters_handler, {
        "project_id": project_id, "link_id": link_id,
    })


# ── Template tools ────────────────────────────────────────────

@mcp.tool()
async def template_list(
    fields: Annotated[list[str] | None, Field(description="Response fields to include (default: [template_id, name, template_type, category, default_name_format]). "
                                                           "Available: template_id, name, version, category, default_name_format, symbol, "
                                                           "template_type, compute_id, usage, tags, builtin, created_at, updated_at")] = None,
) -> list[dict[str, Any]]:
    """List all available templates on the server."""
    return await asyncio.to_thread(_run_handler_sync, list_templates_handler, {"fields": fields})


@mcp.tool()
async def template_get(
    template_id: Annotated[str | None, Field(description="Template UUID (optional if name is provided)")] = None,
    name: Annotated[str | None, Field(description="Template name (optional if template_id is provided)")] = None,
) -> list[dict[str, Any]]:
    """Get detailed information about a specific template."""
    return await asyncio.to_thread(_run_handler_sync, get_template_handler, {
        "template_id": template_id, "name": name,
    })


@mcp.tool()
async def template_create(
    name: Annotated[str, Field(description="Template name")],
    template_type: Annotated[str, Field(description="Template type (e.g. qemu, docker, dynamips)")],
    compute_id: Annotated[str, Field(description="Compute ID (default: local)")] = "local",
    image: Annotated[str | None, Field(description="Docker image name or Dynamips IOS image path (required for docker/dynamips)")] = None,
) -> list[dict[str, Any]]:
    """Create a new template.

    Template-type-specific required parameters:
      docker:  image is required (e.g. "ubuntu:latest")
      dynamips: image is required (path to .image file)
      iou:      needs 'path' (IOL image path) — set via template_update after creation
      qemu:     needs 'hda_disk_image' or 'qemu_path' — set via template_update after creation
    """
    params = {"name": name, "template_type": template_type, "compute_id": compute_id}
    if image:
        params["image"] = image
    return await asyncio.to_thread(_run_handler_sync, create_template_handler, params)


@mcp.tool()
async def template_update(
    template_id: Annotated[str | None, Field(description="Template UUID (optional if name is provided)")] = None,
    name: Annotated[str | None, Field(description="Template name (optional if template_id is provided)")] = None,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    """Update an existing template's properties."""
    params = {"template_id": template_id, "name": name, **kwargs}
    return await asyncio.to_thread(_run_handler_sync, update_template_handler, params)


@mcp.tool()
async def template_delete(
    template_id: Annotated[str | None, Field(description="Template UUID (optional if name is provided)")] = None,
    name: Annotated[str | None, Field(description="Template name (optional if template_id is provided)")] = None,
) -> list[dict[str, Any]]:
    """Delete a template."""
    return await asyncio.to_thread(_run_handler_sync, delete_template_handler, {
        "template_id": template_id, "name": name,
    })


# ── Compute tools ─────────────────────────────────────────────────────

@mcp.tool()
async def compute_list() -> list[dict[str, Any]]:
    """List all remotely registered compute nodes (returns only database entries, does NOT include the built-in local compute).

    For the local compute info, use server_statistics instead.
    """
    return await asyncio.to_thread(_run_handler_sync, list_computes_handler, {})


@mcp.tool()
async def compute_get(
    compute_id: Annotated[str, Field(description="Compute ID: 'local' (default) for the built-in local compute, or a compute UUID from compute_list")] = "local",
) -> list[dict[str, Any]]:
    """Get detailed information about a compute node.

    Accepts 'local' for the built-in local compute or a UUID from compute_list
    for a registered remote compute.
    """
    return await asyncio.to_thread(_run_handler_sync, get_compute_handler, {"compute_id": compute_id})


@mcp.tool()
async def compute_images(
    emulator: Annotated[str, Field(description="Emulator type (e.g. qemu, iou, docker)")],
    compute_id: Annotated[str, Field(description="Compute ID: 'local' (default) for the built-in local compute, or a compute UUID from compute_list")] = "local",
) -> list[dict[str, Any]]:
    """List available images for an emulator on a compute node.

    Accepts 'local' for the built-in local compute or a UUID from compute_list
    for a registered remote compute.
    """
    return await asyncio.to_thread(_run_handler_sync, get_compute_images_handler, {
        "emulator": emulator, "compute_id": compute_id,
    })


# ── Node file tools ────────────────────────────────────────────────────


@mcp.tool()
async def node_file_list(
    project_id: Annotated[str, Field(description="UUID of the project")],
    node_id: Annotated[str, Field(description="UUID of the node")],
    path: Annotated[str, Field(description="Subdirectory path within node directory (optional)")] = "",
    recursive: Annotated[bool, Field(description="Recursively list all files (optional, default: false)")] = False,
) -> list[dict[str, Any]]:
    """List files in a node directory with metadata (name, size, type, modified time).

    Use this first to check file sizes before reading files with get_node_file.
    Large config files should be read in chunks using offset/limit.
    """
    return await asyncio.to_thread(_run_handler_sync, list_node_files_handler, {
        "project_id": project_id, "node_id": node_id, "path": path, "recursive": recursive,
    })


@mcp.tool()
async def node_file_get(
    project_id: Annotated[str, Field(description="UUID of the project")],
    node_id: Annotated[str, Field(description="UUID of the node")],
    file_path: Annotated[str, Field(description="Path to the file within the node directory")],
    offset: Annotated[int, Field(description="Line offset to start reading from (optional, default: 0)")] = 0,
    limit: Annotated[int, Field(description="Maximum number of lines to return (optional, default: 200)")] = 200,
) -> list[dict[str, Any]]:
    """Read a text file from a node directory line-by-line with offset/limit support.

    Best practice:
      1. First call list_node_files to see the file size before deciding to read.
      2. Start with offset=0, limit=200 to preview the file.
      3. If metadata.has_more is true, read more by increasing offset.
      Large files (>50KB) are auto-truncated; check the metadata.truncated flag.
      For binary files, check the file type via list_node_files first.
    """
    return await asyncio.to_thread(_run_handler_sync, get_node_file_handler, {
        "project_id": project_id, "node_id": node_id, "file_path": file_path,
        "offset": offset, "limit": limit,
    })


@mcp.tool()
async def node_file_write(
    project_id: Annotated[str, Field(description="UUID of the project")],
    node_id: Annotated[str, Field(description="UUID of the node")],
    file_path: Annotated[str, Field(description="Path to the file within the node directory")],
    content: Annotated[str, Field(description="Content to write to the file")],
) -> list[dict[str, Any]]:
    """Write content to a file in a node directory. Creates the file if it doesn't exist. Overwrites existing content."""
    return await asyncio.to_thread(_run_handler_sync, write_node_file_handler, {
        "project_id": project_id, "node_id": node_id, "file_path": file_path, "content": content,
    })


@mcp.tool()
async def node_file_delete(
    project_id: Annotated[str, Field(description="UUID of the project")],
    node_id: Annotated[str, Field(description="UUID of the node")],
    file_path: Annotated[str, Field(description="Path to the file within the node directory")],
) -> list[dict[str, Any]]:
    """Delete a file from a node directory. Cannot be undone."""
    return await asyncio.to_thread(_run_handler_sync, delete_node_file_handler, {
        "project_id": project_id, "node_id": node_id, "file_path": file_path,
    })


# ── Node bulk / advanced tools ─────────────────────────────────────────


@mcp.tool()
async def node_start_all(
    project_id: Annotated[str, Field(description="UUID of the project")],
) -> list[dict[str, Any]]:
    """Start all nodes in a project."""
    return await asyncio.to_thread(_run_handler_sync, start_all_nodes_handler, {
        "project_id": project_id,
    })


@mcp.tool()
async def node_stop_all(
    project_id: Annotated[str, Field(description="UUID of the project")],
) -> list[dict[str, Any]]:
    """Stop all nodes in a project."""
    return await asyncio.to_thread(_run_handler_sync, stop_all_nodes_handler, {
        "project_id": project_id,
    })


@mcp.tool()
async def node_suspend_all(
    project_id: Annotated[str, Field(description="UUID of the project")],
) -> list[dict[str, Any]]:
    """Suspend all nodes in a project."""
    return await asyncio.to_thread(_run_handler_sync, suspend_all_nodes_handler, {
        "project_id": project_id,
    })


@mcp.tool()
async def node_duplicate(
    project_id: Annotated[str, Field(description="UUID of the project")],
    node_id: Annotated[str, Field(description="UUID of the node to duplicate")],
    x: Annotated[int, Field(description="X coordinate for the new node")] = 0,
    y: Annotated[int, Field(description="Y coordinate for the new node")] = 0,
    z: Annotated[int, Field(description="Z layer for the new node")] = 0,
) -> list[dict[str, Any]]:
    """Duplicate a node in a project, creating a copy at a new position."""
    return await asyncio.to_thread(_run_handler_sync, duplicate_node_handler, {
        "project_id": project_id, "node_id": node_id, "x": x, "y": y, "z": z,
    })


@mcp.tool()
async def node_isolate(
    project_id: Annotated[str, Field(description="UUID of the project")],
    node_id: Annotated[str, Field(description="UUID of the node to isolate")],
) -> list[dict[str, Any]]:
    """Isolate a node by suspending all its attached links (network isolation)."""
    return await asyncio.to_thread(_run_handler_sync, isolate_node_handler, {
        "project_id": project_id, "node_id": node_id,
    })


@mcp.tool()
async def node_unisolate(
    project_id: Annotated[str, Field(description="UUID of the project")],
    node_id: Annotated[str, Field(description="UUID of the node to unisolate")],
) -> list[dict[str, Any]]:
    """Un-isolate a node by resuming all its suspended links."""
    return await asyncio.to_thread(_run_handler_sync, unisolate_node_handler, {
        "project_id": project_id, "node_id": node_id,
    })


@mcp.tool()
async def node_links(
    project_id: Annotated[str, Field(description="UUID of the project")],
    node_id: Annotated[str, Field(description="UUID of the node")],
) -> list[dict[str, Any]]:
    """List all links connected to a specific node."""
    return await asyncio.to_thread(_run_handler_sync, get_node_links_handler, {
        "project_id": project_id, "node_id": node_id,
    })


# ── Link capture / reset tools ────────────────────────────────────────


@mcp.tool()
async def link_reset(
    project_id: Annotated[str, Field(description="UUID of the project")],
    link_id: Annotated[str | None, Field(description="Link UUID (single mode)")] = None,
    link_ids: Annotated[list[str] | None, Field(description="Batch mode: [\"uuid1\",\"uuid2\"] — reset multiple links in parallel")] = None,
) -> list[dict[str, Any]]:
    """Reset one or more links by tearing down and recreating the UDP connection.

    Use cases:
    - Clear accumulated packet errors/drops from the link's UDP connection
    - Force filter state (delay, packet loss, etc.) to restart fresh
    - Recover a stuck or abnormal link state

    This restarts the filter state machines (e.g. frequency_drop counters)
    while keeping the filter configuration intact. Filters are preserved but
    their internal application state resets.
    """
    params = {"project_id": project_id}
    if link_ids:
        params["link_ids"] = link_ids
    else:
        params["link_id"] = link_id
    return await asyncio.to_thread(_run_handler_sync, reset_link_handler, params)


@mcp.tool()
async def link_capture_start(
    project_id: Annotated[str, Field(description="UUID of the project")],
    link_id: Annotated[str | None, Field(description="Link UUID (single mode)")] = None,
    data_link_type: Annotated[str, Field(description="Data link type (default: DLT_EN10MB)")] = "DLT_EN10MB",
    capture_file_name: Annotated[str | None, Field(description="Capture file name (optional)")] = None,
    wireshark: Annotated[bool, Field(description="Open Wireshark automatically (default: false)")] = False,
    link_ids: Annotated[list[str] | None, Field(description="Batch mode: [\"uuid1\",\"uuid2\"] — start capture on multiple links in parallel")] = None,
) -> list[dict[str, Any]]:
    """Start packet capture on one or more links."""
    params = {"project_id": project_id, "data_link_type": data_link_type, "capture_file_name": capture_file_name, "wireshark": wireshark}
    if link_ids:
        params["link_ids"] = link_ids
    else:
        params["link_id"] = link_id
    return await asyncio.to_thread(_run_handler_sync, start_capture_handler, params)


@mcp.tool()
async def link_capture_stop(
    project_id: Annotated[str, Field(description="UUID of the project")],
    link_id: Annotated[str | None, Field(description="Link UUID (single mode)")] = None,
    link_ids: Annotated[list[str] | None, Field(description="Batch mode: [\"uuid1\",\"uuid2\"] — stop capture on multiple links in parallel")] = None,
) -> list[dict[str, Any]]:
    """Stop packet capture on one or more links."""
    params = {"project_id": project_id}
    if link_ids:
        params["link_ids"] = link_ids
    else:
        params["link_id"] = link_id
    return await asyncio.to_thread(_run_handler_sync, stop_capture_handler, params)


@mcp.tool()
async def link_capture_download(
    project_id: Annotated[str, Field(description="UUID of the project")],
    link_id: Annotated[str | None, Field(description="Link UUID (single mode)")] = None,
    link_ids: Annotated[list[str] | None, Field(description="Batch mode: [\"uuid1\",\"uuid2\"] — get download URLs for multiple captures")] = None,
) -> list[dict[str, Any]]:
    """Get download command(s) for PCAP capture file(s).

    Returns a ready-to-run curl command per link with a short-lived access
    ticket (10 min) already embedded in the URL.

    IMPORTANT — copy the returned values EXACTLY:
      - Run each returned "curl_command" verbatim; it already contains the
        full URL with ticket. NEVER construct or edit the URL yourself, and
        NEVER copy the ticket by hand — a mistyped ticket is rejected.
      - The ticket expires after 10 minutes: call this tool again to get a
        fresh one; do not reuse an old URL.
    """
    params = {"project_id": project_id}
    if link_ids:
        params["link_ids"] = link_ids
    else:
        params["link_id"] = link_id
    return await asyncio.to_thread(_run_handler_sync, download_capture_file_handler, params)


# ── Marker (traffic-insight) tools ─────────────────────────────────────


@mcp.tool()
async def link_marker(
    project_id: Annotated[str, Field(description="UUID of the project")],
    link_id: Annotated[str, Field(description="UUID of the link")],
    action: Annotated[str, Field(description="Action: create, update, or delete")],
    bpf: Annotated[str | None, Field(description="BPF expression, e.g. 'arp', 'icmp', 'tcp port 80' (required for create)")] = None,
    marker_name: Annotated[str | None, Field(description="Marker name (required for update/delete actions)")] = None,
    name: Annotated[str | None, Field(description="Custom marker name for create action (auto-generated if omitted)")] = None,
    tag: Annotated[int | None, Field(description="Numeric tag for packet correlation")] = None,
    enabled: Annotated[bool | None, Field(description="Enable or disable the marker (for update action)")] = None,
    direction: Annotated[str | None, Field(description="Direction filter: 'tx' (capture node sending only), 'rx' (receiving only), or 'both' (no filter — on update this clears a previously set direction). Omit to leave unchanged on update.")] = None,
    capture_node_id: Annotated[str | None, Field(description="UUID of the endpoint whose uBridge hosts the marker (the observer; tx/rx are from its perspective). Must be a link endpoint and marker-capable. Omit to auto-pick.")] = None,
    color: Annotated[str | None, Field(description="Hex color for UI highlight, e.g. '#ff5722'")] = None,
    highlight_duration: Annotated[int | None, Field(description="UI highlight duration in milliseconds")] = None,
    data_link_type: Annotated[str | None, Field(description="pcap link-layer type for serial links (create-only): DLT_C_HDLC / DLT_PPP_SERIAL / DLT_FRELAY / DLT_ATM_RFC1483, matching the encapsulation on the serial link. Omit = DLT_EN10MB (Ethernet). Ignored on update — changing it would invalidate the capture file.")] = None,
) -> list[dict[str, Any]]:
    """Manage traffic-insight markers on a link.

    A marker highlights packets matching a BPF expression as they cross the link.
    Set action='create' to add a marker, 'update' to modify it, 'delete' to remove.

    Create requires: project_id, link_id, action='create', bpf
    Update requires: project_id, link_id, action='update', marker_name, and at least one of (bpf, tag, enabled, direction, color, highlight_duration)
    Delete requires: project_id, link_id, action='delete', marker_name

    To read current markers, use link_get — the response includes a 'markers' dict.

    NOTE: Markers named 'global-*' are inherited from project-level marker definitions
    and cannot be modified or deleted via this tool.
    """
    params = {"project_id": project_id, "link_id": link_id, "action": action}
    for opt in ("bpf", "marker_name", "name", "tag", "enabled", "direction", "capture_node_id", "color", "highlight_duration", "data_link_type"):
        val = locals().get(opt)
        if val is not None:
            params[opt] = val
    return await asyncio.to_thread(_run_handler_sync, link_marker_handler, params)


@mcp.tool()
async def marker_definition(
    project_id: Annotated[str, Field(description="UUID of the project")],
    action: Annotated[str, Field(description="Action: create, update, delete, or list")],
    bpf: Annotated[str | None, Field(description="BPF expression, e.g. 'arp', 'ospf', 'tcp port 22' (required for create)")] = None,
    def_name: Annotated[str | None, Field(description="Definition name (required for update/delete actions)")] = None,
    name: Annotated[str | None, Field(description="Custom definition name for create action (auto-generated if omitted)")] = None,
    tag: Annotated[int | None, Field(description="Numeric tag for packet correlation")] = None,
    color: Annotated[str | None, Field(description="Hex color for UI highlight, e.g. '#ff5722'")] = None,
    highlight_duration: Annotated[int | None, Field(description="UI highlight duration in milliseconds")] = None,
    data_link_type: Annotated[str | None, Field(description="pcap link-layer type for serial links (DLT_C_HDLC / DLT_PPP_SERIAL / DLT_FRELAY / DLT_ATM_RFC1483). Omit = Ethernet-only (serial links skipped); setting it also covers serial links with that encapsulation")] = None,
) -> list[dict[str, Any]]:
    """Manage project-level marker definitions — traffic-insight rules that apply to ALL links.

    A marker definition is a global BPF rule. On create, it auto-fans out to every
    link in the project as 'global-{name}'. Updates sync to all inherited copies.
    On delete, 'global-{name}' is removed from every link.

    Create requires: project_id, action='create', bpf
    Update requires: project_id, action='update', def_name, and at least one of (bpf, tag, color, highlight_duration, data_link_type)
    Delete requires: project_id, action='delete', def_name
    List requires:  project_id, action='list'

    A definition has NO direction (tx/rx): it fans out to every link and auto-selects
    its capture node on each, so a fixed direction has no consistent meaning. Encode
    the direction you want in the BPF instead (e.g. 'icmp and icmp[icmptype]==8' for
    echo requests only). For a capture-node-relative direction on a single link, use
    the per-link `link_marker` tool.

    Common BPF examples: 'arp', 'icmp', 'ospf', 'tcp port 22', 'udp port 53'
    """
    params = {"project_id": project_id, "action": action}
    for opt in ("bpf", "def_name", "name", "tag", "color", "highlight_duration", "data_link_type"):
        val = locals().get(opt)
        if val is not None:
            params[opt] = val
    return await asyncio.to_thread(_run_handler_sync, marker_definition_handler, params)


# ── Snapshot tools ─────────────────────────────────────────────────────


@mcp.tool()
async def snapshot_list(
    project_id: Annotated[str, Field(description="UUID of the project")],
) -> list[dict[str, Any]]:
    """List all snapshots of a project."""
    return await asyncio.to_thread(_run_handler_sync, get_snapshots_handler, {
        "project_id": project_id,
    })


@mcp.tool()
async def snapshot_create(
    project_id: Annotated[str, Field(description="UUID of the project")],
    name: Annotated[str, Field(description="Name for the new snapshot")],
) -> list[dict[str, Any]]:
    """Create a new snapshot of a project.

    Prerequisite: All stoppable nodes (qemu, docker, dynamips, vpcs, iou, etc.)
    must be stopped first. Use node_stop_all before creating a snapshot.
    Cloud, NAT, and switch nodes are always-running and can be ignored.
    """
    return await asyncio.to_thread(_run_handler_sync, create_snapshot_handler, {
        "project_id": project_id, "name": name,
    })


@mcp.tool()
async def snapshot_delete(
    project_id: Annotated[str, Field(description="UUID of the project")],
    snapshot_id: Annotated[str, Field(description="UUID of the snapshot to delete")],
) -> list[dict[str, Any]]:
    """Delete a snapshot from a project. Cannot be undone."""
    return await asyncio.to_thread(_run_handler_sync, delete_snapshot_handler, {
        "project_id": project_id, "snapshot_id": snapshot_id,
    })


@mcp.tool()
async def snapshot_restore(
    project_id: Annotated[str, Field(description="UUID of the project")],
    snapshot_id: Annotated[str, Field(description="UUID of the snapshot to restore")],
) -> list[dict[str, Any]]:
    """Restore a project to a previous snapshot state. The project may be closed and reopened."""
    return await asyncio.to_thread(_run_handler_sync, restore_snapshot_handler, {
        "project_id": project_id, "snapshot_id": snapshot_id,
    })


# ── Drawing tools ──────────────────────────────────────────────────────


@mcp.tool()
async def drawing_list(
    project_id: Annotated[str, Field(description="UUID of the project")],
) -> list[dict[str, Any]]:
    """List all drawings (labels, shapes, images) on a project canvas."""
    return await asyncio.to_thread(_run_handler_sync, get_drawings_handler, {
        "project_id": project_id,
    })


@mcp.tool()
async def drawing_create(
    project_id: Annotated[str, Field(description="UUID of the project")],
    svg: Annotated[str, Field(description="SVG content for the drawing")],
    x: Annotated[int, Field(description="X coordinate (default: 0)")] = 0,
    y: Annotated[int, Field(description="Y coordinate (default: 0)")] = 0,
    z: Annotated[int, Field(description="Z layer (default: 0)")] = 0,
    locked: Annotated[bool, Field(description="Lock the drawing (default: false)")] = False,
    rotation: Annotated[int, Field(description="Rotation angle in degrees, -359 to 359 (default: 0)")] = 0,
) -> list[dict[str, Any]]:
    """Create a new drawing (label, shape, or image) on a project canvas.

    GNS3 SVG rendering notes:
    - <rect> MUST have a solid fill color (e.g. fill=\"#FF0000\") to render.
      fill=\"none\" or fill=\"transparent\" will be invisible in the GUI.
    - <ellipse> works correctly with or without fill.
    - <line> and <text> work normally.

    SVG examples:
      Text label:  <svg><text x=\"10\" y=\"20\" font-size=\"14\">R1</text></svg>
      Rectangle:   <svg><rect x=\"10\" y=\"10\" width=\"80\" height=\"50\" fill=\"#4A90D9\" stroke=\"black\"/></svg>
      Ellipse:     <svg><ellipse cx=\"50\" cy=\"50\" rx=\"40\" ry=\"20\" fill=\"red\" stroke=\"black\"/></svg>
      Line:        <svg><line x1=\"0\" y1=\"0\" x2=\"100\" y2=\"100\" stroke=\"black\" stroke-width=\"2\"/></svg>
      Dashed line: <svg><line x1=\"0\" y1=\"0\" x2=\"100\" y2=\"100\" stroke=\"black\" stroke-dasharray=\"5,5\"/></svg>
    """
    return await asyncio.to_thread(_run_handler_sync, create_drawing_handler, {
        "project_id": project_id, "svg": svg, "x": x, "y": y, "z": z,
        "locked": locked, "rotation": rotation,
    })


@mcp.tool()
async def drawing_get(
    project_id: Annotated[str, Field(description="UUID of the project")],
    drawing_id: Annotated[str, Field(description="UUID of the drawing")],
) -> list[dict[str, Any]]:
    """Get detailed information about a specific drawing."""
    return await asyncio.to_thread(_run_handler_sync, get_drawing_handler, {
        "project_id": project_id, "drawing_id": drawing_id,
    })


@mcp.tool()
async def drawing_update(
    project_id: Annotated[str, Field(description="UUID of the project")],
    drawing_id: Annotated[str, Field(description="UUID of the drawing")],
    svg: Annotated[str | None, Field(description="New SVG content")] = None,
    locked: Annotated[bool | None, Field(description="Lock or unlock the drawing")] = None,
    x: Annotated[int | None, Field(description="New X coordinate")] = None,
    y: Annotated[int | None, Field(description="New Y coordinate")] = None,
    z: Annotated[int | None, Field(description="New Z layer")] = None,
    rotation: Annotated[int | None, Field(description="Rotation angle in degrees, -359 to 359")] = None,
) -> list[dict[str, Any]]:
    """Update a drawing's properties (svg, position, lock state, rotation, etc.)."""
    params = {"project_id": project_id, "drawing_id": drawing_id}
    local_vars = {"svg": svg, "locked": locked, "x": x, "y": y, "z": z, "rotation": rotation}
    for key, val in local_vars.items():
        if val is not None:
            params[key] = val
    return await asyncio.to_thread(_run_handler_sync, update_drawing_handler, params)


@mcp.tool()
async def drawing_delete(
    project_id: Annotated[str, Field(description="UUID of the project")],
    drawing_id: Annotated[str, Field(description="UUID of the drawing to delete")],
) -> list[dict[str, Any]]:
    """Delete a drawing from a project canvas. Cannot be undone."""
    return await asyncio.to_thread(_run_handler_sync, delete_drawing_handler, {
        "project_id": project_id, "drawing_id": drawing_id,
    })


# ── Project lock tools ────────────────────────────────────────────────


@mcp.tool()
async def project_lock(
    project_id: Annotated[str, Field(description="UUID of the project")],
) -> list[dict[str, Any]]:
    """Lock all drawings and nodes in a project to prevent accidental changes."""
    return await asyncio.to_thread(_run_handler_sync, lock_project_handler, {
        "project_id": project_id,
    })


@mcp.tool()
async def project_unlock(
    project_id: Annotated[str, Field(description="UUID of the project")],
) -> list[dict[str, Any]]:
    """Unlock a project to allow editing of drawings and nodes."""
    return await asyncio.to_thread(_run_handler_sync, unlock_project_handler, {
        "project_id": project_id,
    })


@mcp.tool()
async def project_locked(
    project_id: Annotated[str, Field(description="UUID of the project")],
) -> list[dict[str, Any]]:
    """Check whether a project is locked (preventing edits to drawings and nodes)."""
    return await asyncio.to_thread(_run_handler_sync, get_locked_project_handler, {
        "project_id": project_id,
    })


# ── Server info tools ─────────────────────────────────────────────────


@mcp.tool()
async def server_version() -> list[dict[str, Any]]:
    """Get GNS3 server version information."""
    return await asyncio.to_thread(_run_handler_sync, get_version_handler, {})


@mcp.tool()
async def server_statistics() -> list[dict[str, Any]]:
    """Get GNS3 server statistics including computes, projects, nodes, and links."""
    return await asyncio.to_thread(_run_handler_sync, get_statistics_handler, {})


# ── Symbol tools ──────────────────────────────────────────────────────
#
# Disabled for now: symbol handling requires a vision-capable model (the
# tools shuttle SVG content, which a text-only LLM cannot inspect or
# produce). Revisit later.
#
# @mcp.tool()
# async def symbol_list() -> list[dict[str, Any]]:
#     """List all available symbols on the server."""
#     return await asyncio.to_thread(_run_handler_sync, get_symbols_handler, {})
#
#
# @mcp.tool()
# async def symbol_get(
#     symbol_id: Annotated[str, Field(description="Symbol ID (e.g. ':/symbols/router.svg')")],
# ) -> list[dict[str, Any]]:
#     """Get a download URL for a symbol file (SVG).
#
#     Returns a ready-to-run curl command with a short-lived access ticket
#     (10 min) embedded in the URL. Run the returned "curl_command" verbatim —
#     never reconstruct the URL or copy the ticket by hand. Re-call this tool
#     once the ticket has expired.
#     """
#     return await asyncio.to_thread(_run_handler_sync, get_symbol_handler, {
#         "symbol_id": symbol_id,
#     })
#
#
# @mcp.tool()
# async def symbol_dimensions(
#     symbol_id: Annotated[str, Field(description="Symbol ID to get dimensions for")],
# ) -> list[dict[str, Any]]:
#     """Get the dimensions (width, height) of a symbol."""
#     return await asyncio.to_thread(_run_handler_sync, get_symbol_dimensions_handler, {
#         "symbol_id": symbol_id,
#     })
#
#
# @mcp.tool()
# async def symbol_defaults() -> list[dict[str, Any]]:
#     """Get the default symbol mapping for each node type."""
#     return await asyncio.to_thread(_run_handler_sync, get_default_symbols_handler, {})
#
#
# @mcp.tool()
# async def symbol_upload(
#     symbol_id: Annotated[str, Field(description="Symbol ID to upload (e.g. ':/symbols/my_symbol.svg')")],
#     content: Annotated[str, Field(description="SVG content of the symbol")],
# ) -> list[dict[str, Any]]:
#     """Upload or update a custom symbol on the server. Provide the SVG content as a string."""
#     return await asyncio.to_thread(_run_handler_sync, upload_symbol_handler, {
#         "symbol_id": symbol_id, "content": content,
#     })
#
#
# @mcp.tool()
# async def symbol_delete(
#     symbol_id: Annotated[str, Field(description="Symbol ID to delete (e.g. ':/symbols/my_custom_symbol.svg'). Use symbol_list to get existing IDs.")],
# ) -> list[dict[str, Any]]:
#     """Delete a custom symbol from the server.
#
#     NOTE: Only custom (user-uploaded) symbols can be deleted.
#     Built-in symbols (starting with ':/symbols/') will be rejected with 403.
#     Use symbol_list to see which symbols are available and their IDs.
#     """
#     return await asyncio.to_thread(_run_handler_sync, delete_symbol_handler, {
#         "symbol_id": symbol_id,
#     })


# ── Appliance tools ───────────────────────────────────────────────────


@mcp.tool()
async def appliance_list(
    fields: Annotated[list[str] | None, Field(description="Optional: return only these fields. e.g. [\"name\",\"category\"]. Available: name, category, description, vendor_name, product_name, status, availability, images, versions, tags, symbol, usage, builtin")] = None,
) -> list[dict[str, Any]]:
    """List all available appliances (template library). Use fields=[] to return only what you need."""
    return await asyncio.to_thread(_run_handler_sync, get_appliances_handler, {"fields": fields} if fields else {})


@mcp.tool()
async def appliance_get(
    appliance_id: Annotated[str, Field(description="UUID of the appliance")],
) -> list[dict[str, Any]]:
    """Get detailed information about a specific appliance."""
    return await asyncio.to_thread(_run_handler_sync, get_appliance_handler, {
        "appliance_id": appliance_id,
    })


@mcp.tool()
async def appliance_install(
    appliance_id: Annotated[str, Field(description="UUID of the appliance to install")],
    version: Annotated[str | None, Field(description="Version to install (e.g. '2.7.0.356'). Required if the appliance has multiple versions. Use appliance_get to see available versions.")] = None,
) -> list[dict[str, Any]]:
    """Create a template from a GNS3 appliance definition and return the created template.

    NOTE: This does NOT download images. Images must be placed in the
    GNS3 images directory (e.g. ~/GNS3/images/) beforehand.
    The appliance definition is read from local .gns3a files bundled with the server.
    Use get_appliance first to see what images are required.
    """
    return await asyncio.to_thread(_run_handler_sync, install_appliance_handler, {
        "appliance_id": appliance_id,
        "version": version,
    })


# ── Image tools ───────────────────────────────────────────────────────


@mcp.tool()
async def image_list() -> list[dict[str, Any]]:
    """List all images available on the server across all emulators."""
    return await asyncio.to_thread(_run_handler_sync, get_images_handler, {})


@mcp.tool()
async def image_get(
    image_id: Annotated[str, Field(description="ID or filename of the image")],
) -> list[dict[str, Any]]:
    """Get detailed information about a specific image."""
    return await asyncio.to_thread(_run_handler_sync, get_image_handler, {
        "image_id": image_id,
    })


@mcp.tool()
async def image_delete(
    image_id: Annotated[str, Field(description="ID or filename of the image to delete")],
) -> list[dict[str, Any]]:
    """Delete an image from the server. Cannot be undone."""
    return await asyncio.to_thread(_run_handler_sync, delete_image_handler, {
        "image_id": image_id,
    })


@mcp.tool()
async def image_prune() -> list[dict[str, Any]]:
    """Remove images not referenced by any template.

    NOTE: Only images that are not used by any template will be removed.
    If all images are still referenced by templates, no images are deleted.
    Use image_list to see which images exist and check if they are in use.
    """
    return await asyncio.to_thread(_run_handler_sync, prune_images_handler, {})


@mcp.tool()
async def image_install() -> list[dict[str, Any]]:
    """Scan uploaded images and auto-create templates by matching image checksums against known appliance definitions.

    This is NOT for downloading images. Images must be uploaded first (via the GNS3 Web UI).
    If an uploaded image matches a known appliance, a template is automatically created.
    Returns {"created": [...], "skipped": [...]}: images already referenced by existing
    templates are skipped, and no template is auto-created when one with the same name
    already exists (regardless of version).
    """
    return await asyncio.to_thread(_run_handler_sync, install_images_handler, {})


# ── Device config tools ───────────────────────────────────────────────
# These tools connect to network device consoles via telnet/SSH using
# Nornir + Netmiko. Devices must be started and have a device_type tag.
#
# Workflow:
#   1. node_list(project_id) → identify device names
#   2. node_start_all(project_id) → ensure devices are running
#   3. device_config_send(project_id, device_configs=[...]) → push config
#   4. device_show_run(project_id, device_commands=[...]) → verify


@mcp.tool()
async def device_config_send(
    project_id: Annotated[str, Field(description="UUID of the project")],
    device_configs: Annotated[list, Field(
        description="List of device configs. Each entry: {\"device_name\": \"R1\", \"config_commands\": [\"int lo0\", \"ip add 1.1.1.1 255.255.255.255\"]}"
    )],
    template: Annotated[str | None, Field(description="Optional Jinja2 template. Use with vars in each device to reduce token usage for batch config. Example: \"interface lo{{ n }}\\nip address {{ ip }} 255.255.255.255\"")] = None,
) -> list[dict[str, Any]]:
    """Send configuration commands to network devices via console (telnet/SSH).

    Two modes:
      1. Direct commands: each device has config_commands=[...]
      2. Jinja2 template: provide template + vars per device — template is rendered for each
         Example: device_configs=[{\"device_name\": \"R1\", \"vars\": {\"n\": 0, \"ip\": \"1.1.1.1\"}}]

    Devices must be started first (use node_start or node_start_all).
    Device type is auto-detected from the 'device_type:<type>' tag on each node.
    Common device types: cisco_ios_telnet, cisco_xr_telnet, huawei_telnet, gns3_huawei_telnet_ce

    Error contract: every failure is reported in-band as an entry with
    status "failed" and an "error" message (per-device entries also carry
    device_name and commands).
    """
    params = {"project_id": project_id, "device_configs": device_configs}
    if template is not None:
        params["template"] = template
    return await asyncio.to_thread(_run_handler_sync, device_config_send_handler, params)


@mcp.tool()
async def device_show_run(
    project_id: Annotated[str, Field(description="UUID of the project")],
    device_configs: Annotated[list, Field(
        description="List of device commands. Each entry: {\"device_name\": \"R1\", \"commands\": [\"show ip int brief\", \"show running-config\"]}"
    )],
    template: Annotated[str | None, Field(description="Optional Jinja2 template. Use with vars per device. Example: \"show ip route {{ protocol }}\"")] = None,
) -> list[dict[str, Any]]:
    """Run read-only diagnostic (show) commands on network devices via console.

    Two modes:
      1. Direct commands: each device has commands=[...] (read-only show/display/ping/traceroute only)
      2. Jinja2 template: provide template + vars per device

    Use this to inspect device status, view configurations, or verify changes.
    For configuration changes use device_config_send instead.

    Prerequisites:
    - Devices must be started first (use node_start or node_start_all).
    - Each node must have a device_type:<type> tag set in GNS3
      (e.g. device_type:cisco_ios_telnet, device_type:gns3_huawei_telnet_ce).
      Nodes without this tag will fail with "device_type tag not found".
      Docker/Linux nodes are not supported (use node_console instead).

    Error contract: every failure is reported in-band as an entry with
    status "failed" and an "error" message (per-device entries also carry
    device_name and commands).
    """
    params = {"project_id": project_id, "device_configs": device_configs}
    if template is not None:
        params["template"] = template
    return await asyncio.to_thread(_run_handler_sync, device_show_run_handler, params)


@mcp.tool()
async def vpcs_config_set(
    project_id: Annotated[str, Field(description="UUID of the project")],
    device_configs: Annotated[list, Field(
        description="List of VPCS configs. Each entry: {\"device_name\": \"PC1\", \"commands\": [\"ip 10.0.0.1/24 10.0.0.254\", \"save\"]}"
    )],
) -> list[dict[str, Any]]:
    """Configure VPCS devices (set IP addresses, gateway, etc.).

    Only VPCS nodes are accepted: any other node type in device_configs fails
    with a per-device error instead of typing VPCS syntax into its CLI.
    Every failure is reported in-band as an entry with status "failed"
    and an "error" message.

    VPCS-specific configuration commands:
      - ip <address>/<mask> <gateway>   Set IP and gateway
      - save                            Save config to startup.vpc
      - ping <target>                   Test connectivity
    """
    return await asyncio.to_thread(_run_handler_sync, vpcs_config_set_handler, {
        "project_id": project_id, "device_configs": device_configs,
    })


# ── Auth‑wrapped SSE app ──────────────────────────────────────────────

def _make_auth_wrapper(inner_app):
    """Wrap the SSE app with JWT validation.

    Supports two ways to pass the token (checked in order):
      1. Authorization: Bearer <jwt> header
      2. ?token=<jwt> query parameter

    POST messages are passed through (authenticated by their session).
    """

    async def auth_wrapper(scope, receive, send):
        # Wait for GNS3 server to complete initialization before accepting MCP connections
        server_ready = await wait_for_mcp_ready()
        if not server_ready:
            # Server initialization timed out - return 503 Service Unavailable
            client_info = extract_client_info(scope, auth_service)
            log.warning(
                f"Rejecting MCP connection - GNS3 server initialization not complete. "
                f"Client: {client_info['host']}:{client_info['port']} ({client_info['user_info']}, Path: {client_info['path']})"
            )
            response = Response(
                "GNS3 server initialization not complete - please retry later",
                status_code=503
            )
            await response(scope, receive, send)
            return

        if scope["type"] == "http" and scope["method"] == "GET":
            token = None
            headers = dict(scope.get("headers", []))
            auth = headers.get(b"authorization", b"").decode()
            if auth.startswith("Bearer "):
                token = auth[7:]
            if not token:
                params = parse_qs(scope.get("query_string", b"").decode())
                tokens = params.get("token", [])
                if tokens:
                    token = tokens[0]
            if not token:
                response = Response("Missing or invalid token", status_code=401)
                await response(scope, receive, send)
                return
            resolved = await _resolve_token(token)
            if not resolved:
                response = Response("Missing or invalid token", status_code=401)
                await response(scope, receive, send)
                return
            _jwt_token_var.set(resolved)
        await inner_app(scope, receive, send)

    return auth_wrapper


# ── FastAPI router ────────────────────────────────────────────────────

router = APIRouter(prefix="/mcp", tags=["MCP"])


@router.get("/")
async def mcp_root():
    """MCP service metadata."""
    return {
        "name": "GNS3 MCP Server",
        "version": "1.0.0",
        "authentication": ["Authorization: Bearer <jwt>", "?token=<jwt>"],
        "transports": {
            "sse": "/v3/mcp/transport/sse",
        },
    }


def register_starlette_routes(app):
    """Mount MCP transports on the FastAPI app."""
    global _app
    _app = app
    sse_app = _make_auth_wrapper(mcp.sse_app(mount_path=""))
    app.mount("/v3/mcp/transport", sse_app, name="mcp-sse")
    log.info("MCP SSE server mounted at /v3/mcp/transport")

    # Log registered MCP tools for verification
    tool_names = list(mcp._tool_manager._tools.keys())
    log.info("MCP tools registered (%d): %s", len(tool_names), ", ".join(sorted(tool_names)))
