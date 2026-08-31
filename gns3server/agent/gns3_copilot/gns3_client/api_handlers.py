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
Shared GNS3 REST API handler layer.

Handlers receive ``(params: dict, gns3_ctx: dict)`` and call the GNS3 REST
API directly via ``Gns3Connector.http_call`` — no ORM-style wrapper objects.

This module is the single implementation shared by two consumers:

- the MCP service (``gns3server.agent.mcp``) re-exports these handlers as
  MCP tools, and
- gns3-copilot tools (``tools_v2``) call them directly.

``gns3_ctx`` carries the per-request connection info:

- ``server_url`` (str): GNS3 server base URL
- ``jwt_token`` (str): a JWT — API keys must be exchanged for a JWT by the
  entry point before calling handlers (see ``mcp._resolve_token``)
- ``jwt_username`` / ``jwt_token_version`` (optional): only needed by
  handlers that mint short-lived tokens for console/download URLs

Copilot-side callers build the context with :func:`build_gns3_ctx`, which
pulls the request-scoped user JWT from the context variables.
"""

from typing import Any
from concurrent.futures import ThreadPoolExecutor

import hashlib
import logging

from gns3server.services import access_ticket_service
from gns3server.services.access_tickets import DEFAULT_TICKET_TTL

from gns3server.agent.gns3_copilot.gns3_client.connector import Gns3Connector

log = logging.getLogger(__name__)

BATCH_MAX_WORKERS = 100

# ── Constants ──────────────────────────────────────────────────────────────

# Maximum bytes to return from get_node_file (safety net).
# Larger files are truncated with a truncated=True flag.
MAX_NODE_FILE_BYTES = 50 * 1024  # 50 KiB

VALID_NODE_FIELDS = {
    # NodeBase
    "compute_id", "name", "node_type", "node_id",
    "console", "console_type", "console_auto_start",
    "aux", "aux_type", "properties", "label", "symbol",
    "x", "y", "z", "locked",
    "port_name_format", "port_segment_size", "first_port_name",
    "custom_adapters", "tags",
    # Node
    "template_id", "project_id", "node_directory", "status",
    "command_line", "width", "height", "ports", "console_host",
}

VALID_LINK_FIELDS = {
    "link_id", "project_id", "link_type", "nodes", "suspend",
    "link_style", "filters", "show_filters_icon",
    "capturing", "capture_file_name", "capture_file_path",
    "capture_compute_id", "wireshark",
}

LINK_DEFAULT_FIELDS = ["link_id", "link_type", "nodes"]


# ── Helpers ────────────────────────────────────────────────────────────────

def _get_connector(gns3_ctx: dict[str, Any]):
    return Gns3Connector(
        url=gns3_ctx["server_url"],
        jwt_token=gns3_ctx["jwt_token"],
        api_version=3,
        verify=False,
    )


def build_gns3_ctx(
    jwt_token: str | None = None, url: str | None = None
) -> dict[str, Any] | None:
    """
    Build a handler ``gns3_ctx`` for in-process copilot callers.

    The JWT is taken from the request-scoped context variable when not
    passed explicitly (mirroring ``get_gns3_connector``); the URL uses the
    same Controller → Config → fallback detection order.

    Returns None when no JWT token is available.
    """
    from gns3server.agent.gns3_copilot.gns3_client.connector_factory import (
        _detect_url_for_api,
    )
    from gns3server.agent.gns3_copilot.gns3_client.context_helpers import (
        get_current_jwt_token,
    )

    token = jwt_token or get_current_jwt_token()
    if not token:
        return None
    return {
        "server_url": url or _detect_url_for_api(),
        "jwt_token": token,
        "jwt_username": None,
        "jwt_token_version": 0,
    }


def _filter_node_response(node: dict, fields: list[str] = None) -> dict:
    """Filter node response to only include requested fields."""
    if not fields:
        fields = ["node_id", "name", "node_type", "status", "console"]
    return {k: node[k] for k in fields if k in node}


def _filter_link_response(link: dict, fields: list[str] = None) -> dict:
    """Filter link response to only include requested fields."""
    if not fields:
        fields = LINK_DEFAULT_FIELDS
    return {k: link[k] for k in fields if k in link}


def _normalize_link_nodes(nodes) -> list[dict[str, Any]]:
    """
    Normalize link node entries, accepting both standard object format and
    compact array format to reduce token usage.

    Standard: [{"node_id": "uuid", "adapter_number": 0, "port_number": 0}]
    Compact:  ["uuid", 0, 0, "uuid", 0, 0]

    Returns the normalized list, or raises ValueError with a clear message
    on format errors so the AI can self-correct.
    """
    if not nodes:
        return nodes
    if not isinstance(nodes, list):
        raise ValueError(f"nodes must be a list, got {type(nodes).__name__}: {nodes}")
    # Standard object format: [{"node_id": "...", ...}]
    if isinstance(nodes[0], dict):
        return nodes
    # Compact array format: ["uuid", ad, pt, "uuid", ad, pt"]
    if all(not isinstance(n, dict) for n in nodes):
        if len(nodes) != 6:
            raise ValueError(
                f"Compact link format requires exactly 6 elements "
                f"[node_id, adapter, port, node_id, adapter, port], "
                f"but got {len(nodes)} elements: {nodes}"
            )
        if not isinstance(nodes[0], str) or not isinstance(nodes[3], str):
            raise ValueError(
                f"Compact link format expects node_id (string) at positions 0 and 3, "
                f"got types {type(nodes[0]).__name__} and {type(nodes[3]).__name__}: {nodes}"
            )
        return [
            {"node_id": nodes[0], "adapter_number": nodes[1], "port_number": nodes[2]},
            {"node_id": nodes[3], "adapter_number": nodes[4], "port_number": nodes[5]},
        ]
    raise ValueError(
        f"Unrecognized link nodes format. "
        f"Use standard [{{\"node_id\":\"..\",\"adapter_number\":0,\"port_number\":0}},...] "
        f"or compact [\"id\",0,0,\"id\",0,0], got: {nodes}"
    )


# ── Node handlers ──────────────────────────────────────────────────────────

def get_nodes_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    project_id = params.get("project_id")
    if not project_id:
        return {"error": "project_id is required"}
    conn = _get_connector(gns3_ctx)
    nodes = conn.http_call("get", f"{conn.base_url}/projects/{project_id}/nodes").json()
    fields = params.get("fields")
    if fields:
        if not isinstance(fields, list):
            return {"error": "fields must be a list of field names, e.g. [\"name\", \"status\"]"}
        invalid = [f for f in fields if f not in VALID_NODE_FIELDS]
        if invalid:
            return {
                "error": f"Unknown fields: {invalid}",
                "available_fields": sorted(VALID_NODE_FIELDS),
            }
        nodes = [{k: n[k] for k in fields if k in n} for n in nodes]
    return {"nodes": nodes, "count": len(nodes)}


def get_node_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    project_id = params.get("project_id")
    node_id = params.get("node_id")
    if not project_id or not node_id:
        return {"error": "project_id and node_id are required"}
    conn = _get_connector(gns3_ctx)
    node = conn.http_call("get", f"{conn.base_url}/projects/{project_id}/nodes/{node_id}").json()

    fields = params.get("fields")
    if fields:
        if not isinstance(fields, list):
            return {"error": "fields must be a list of field names, e.g. [\"name\", \"status\"]"}
        invalid = [f for f in fields if f not in VALID_NODE_FIELDS]
        if invalid:
            return {
                "error": f"Unknown fields: {invalid}",
                "available_fields": sorted(VALID_NODE_FIELDS),
            }
        return {k: node[k] for k in fields if k in node}

    return node


def _batch_lifecycle(project_id, node_ids, action, conn, action_label):
    """Helper to run a lifecycle action on multiple nodes in parallel."""
    def _act(nid):
        try:
            conn.http_call("post", f"{conn.base_url}/projects/{project_id}/nodes/{nid}/{action}")
            return {"node_id": nid, "status": "success", "message": f"Node {nid} {action_label}"}
        except Exception as e:
            return {"node_id": nid, "status": "error", "error": str(e)}
    with ThreadPoolExecutor(max_workers=min(len(node_ids), BATCH_MAX_WORKERS)) as pool:
        return list(pool.map(_act, node_ids))


def start_node_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    project_id = params.get("project_id")
    if not project_id:
        return {"error": "project_id is required"}
    node_ids = params.get("node_ids")
    if node_ids:
        if not isinstance(node_ids, list):
            return {"error": "node_ids must be a list"}
        conn = _get_connector(gns3_ctx)
        return _batch_lifecycle(project_id, node_ids, "start", conn, "started")
    node_id = params.get("node_id")
    if not node_id:
        return {"error": "node_id or node_ids is required"}
    conn = _get_connector(gns3_ctx)
    conn.http_call("post", f"{conn.base_url}/projects/{project_id}/nodes/{node_id}/start", json_data={})
    return {"message": f"Node {node_id} started", "node_id": node_id}


def stop_node_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    project_id = params.get("project_id")
    if not project_id:
        return {"error": "project_id is required"}
    node_ids = params.get("node_ids")
    if node_ids:
        if not isinstance(node_ids, list):
            return {"error": "node_ids must be a list"}
        conn = _get_connector(gns3_ctx)
        return _batch_lifecycle(project_id, node_ids, "stop", conn, "stopped")
    node_id = params.get("node_id")
    if not node_id:
        return {"error": "node_id or node_ids is required"}
    conn = _get_connector(gns3_ctx)
    conn.http_call("post", f"{conn.base_url}/projects/{project_id}/nodes/{node_id}/stop", json_data={})
    return {"message": f"Node {node_id} stopped", "node_id": node_id}


def suspend_node_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    project_id = params.get("project_id")
    if not project_id:
        return {"error": "project_id is required"}
    node_ids = params.get("node_ids")
    if node_ids:
        if not isinstance(node_ids, list):
            return {"error": "node_ids must be a list"}
        conn = _get_connector(gns3_ctx)
        return _batch_lifecycle(project_id, node_ids, "suspend", conn, "suspended")
    node_id = params.get("node_id")
    if not node_id:
        return {"error": "node_id or node_ids is required"}
    conn = _get_connector(gns3_ctx)
    conn.http_call("post", f"{conn.base_url}/projects/{project_id}/nodes/{node_id}/suspend")
    return {"message": f"Node {node_id} suspended", "node_id": node_id}


def create_node_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:

    project_id = params.get("project_id")
    if not project_id:
        return {"error": "project_id is required"}

    fields = params.get("fields")
    if fields is not None and not isinstance(fields, list):
        return {"error": "fields must be a list, e.g. [\"node_id\", \"name\"]"}

    nodes = params.get("nodes")
    # Batch mode: nodes=[{template_id?, x, y, name?, compute_id?}]
    # When top-level template_id is set, it applies to all nodes as a default
    if nodes is not None:
        if not isinstance(nodes, list) or not nodes:
            return {"error": "nodes must be a non-empty array"}
        default_tid = params.get("template_id")
        conn = _get_connector(gns3_ctx)
        def _create_one(node_data):
            tid = node_data.get("template_id", default_tid)
            if not tid:
                return {"template_id": tid, "status": "error", "error": "template_id is required"}
            try:
                url = f"{conn.base_url}/projects/{project_id}/templates/{tid}"
                body = {
                    "x": node_data.get("x", 0),
                    "y": node_data.get("y", 0),
                    "compute_id": node_data.get("compute_id", "local"),
                }
                node_name = node_data.get("name")
                if node_name:
                    body["name"] = node_name
                resp = conn.http_call("post", url, json_data=body).json()
                return {"template_id": tid, "status": "success", "node": _filter_node_response(resp, fields)}
            except Exception as e:
                return {"template_id": tid, "status": "error", "error": str(e)}
        if any(not node.get("name") for node in nodes):
            # The controller assigns default names (R-1, R-2, ...) and console
            # ports in request arrival order, and a parallel fan-out makes the
            # arrival order depend on thread scheduling. Batches that rely on
            # default naming are therefore created sequentially so those
            # server-side assignments follow the submission order; batches
            # where every node has an explicit name stay parallel.
            return [_create_one(node) for node in nodes]
        with ThreadPoolExecutor(max_workers=min(len(nodes), BATCH_MAX_WORKERS)) as pool:
            # pool.map keeps the submission order, so callers can correlate
            # results with the nodes they sent regardless of completion order
            return list(pool.map(_create_one, nodes))

    # Single mode
    template_id = params.get("template_id")
    if not template_id:
        return {"error": "template_id is required"}
    conn = _get_connector(gns3_ctx)
    data = {
        "x": params.get("x", 0),
        "y": params.get("y", 0),
        "compute_id": params.get("compute_id", "local"),
    }
    node_name = params.get("name")
    if node_name:
        data["name"] = node_name
    url = f"{conn.base_url}/projects/{project_id}/templates/{template_id}"
    resp = conn.http_call("post", url, json_data=data).json()
    return _filter_node_response(resp, fields)


def delete_node_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    project_id = params.get("project_id")
    if not project_id:
        return {"error": "project_id is required"}
    node_ids = params.get("node_ids")
    if node_ids:
        if not isinstance(node_ids, list):
            return {"error": "node_ids must be a list"}
        conn = _get_connector(gns3_ctx)
        def _del(nid):
            try:
                conn.http_call("delete", f"{conn.base_url}/projects/{project_id}/nodes/{nid}")
                return {"node_id": nid, "status": "success", "message": f"Node {nid} deleted"}
            except Exception as e:
                return {"node_id": nid, "status": "error", "error": str(e)}
        with ThreadPoolExecutor(max_workers=min(len(node_ids), BATCH_MAX_WORKERS)) as pool:
            return list(pool.map(_del, node_ids))
    node_id = params.get("node_id")
    if not node_id:
        return {"error": "node_id or node_ids is required"}
    conn = _get_connector(gns3_ctx)
    conn.http_call("delete", f"{conn.base_url}/projects/{project_id}/nodes/{node_id}")
    return {"message": f"Node {node_id} deleted", "node_id": node_id}


def update_node_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    project_id = params.get("project_id")
    node_id = params.get("node_id")
    if not project_id or not node_id:
        return {"error": "project_id and node_id are required"}
    conn = _get_connector(gns3_ctx)

    # Extract update parameters - handle nested kwargs structure from MCP clients
    if "kwargs" in params and isinstance(params["kwargs"], dict):
        update_data = params["kwargs"]
    else:
        update_data = {k: v for k, v in params.items() if k not in ("project_id", "node_id", "kwargs")}

    url = f"{conn.base_url}/projects/{project_id}/nodes/{node_id}"
    return conn.http_call("put", url, json_data=update_data).json()


def get_node_console_info_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    project_id = params.get("project_id")
    node_id = params.get("node_id")
    if not project_id or not node_id:
        return {"error": "project_id and node_id are required"}
    conn = _get_connector(gns3_ctx)
    node = conn.http_call("get", f"{conn.base_url}/projects/{project_id}/nodes/{node_id}").json()

    console_type = node.get("console_type", "unknown")
    # Short-lived console ticket (10 min, multi-use, bound to this node's
    # console endpoints). Deliberately a short random string instead of a JWT:
    # LLM clients retype this URL into shell commands and reliably corrupted
    # the ~200-char JWT previously embedded here (dropped header segment →
    # "Missing 'alg' value in header" on the server).
    username = gns3_ctx.get("jwt_username")
    ticket = access_ticket_service.mint(
        username,
        token_version=gns3_ctx.get("jwt_token_version", 0),
        project_id=project_id,
        node_id=node_id,
    ) if username else None
    raw_url = f"{gns3_ctx['server_url']}/v3/projects/{project_id}/nodes/{node_id}/console/ws"
    if ticket:
        raw_url += f"?token={ticket}"
    # Convert http scheme to ws for direct websocat usage
    ws_url = raw_url.replace("https://", "wss://").replace("http://", "ws://")

    result = {
        "node_id": node_id,
        "node_name": node.get("name"),
        "console_type": console_type,
        "ws_url": ws_url,
        "command": f"websocat -t --no-close {ws_url}",
    }
    if ticket:
        # Fingerprint of the minted token: compare it against what actually reached the
        # server (logged on WebSocket auth rejection) to detect copy corruption, and
        # re-request the URL once token_ttl_seconds has elapsed.
        result["token_sha256_prefix"] = hashlib.sha256(ticket.encode()).hexdigest()[:8]
        result["token_ttl_seconds"] = DEFAULT_TICKET_TTL
    if console_type in ("vnc",) and ticket:
        # Same node binding covers the vnc endpoint (identical path params)
        result["vnc_url"] = f"/v3/projects/{project_id}/nodes/{node_id}/console/vnc?token={ticket}"
    return result


# ── Node file handlers ────────────────────────────────────────────────────


def list_node_files_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    project_id = params.get("project_id")
    node_id = params.get("node_id")
    if not project_id or not node_id:
        return {"error": "project_id and node_id are required"}
    conn = _get_connector(gns3_ctx)
    url = f"{conn.base_url}/projects/{project_id}/nodes/{node_id}/files"
    query = {}
    if params.get("path"):
        query["path"] = params["path"]
    if params.get("recursive"):
        query["recursive"] = "true"
    files = conn.http_call("get", url, params=query if query else None).json()
    return {"files": files, "count": len(files)}


def get_node_file_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    project_id = params.get("project_id")
    node_id = params.get("node_id")
    file_path = params.get("file_path")
    if not project_id or not node_id or not file_path:
        return {"error": "project_id, node_id and file_path are required"}

    offset = params.get("offset", 0)
    limit = params.get("limit", 200)

    conn = _get_connector(gns3_ctx)
    url = f"{conn.base_url}/projects/{project_id}/nodes/{node_id}/files/{file_path}"
    raw = conn.http_call("get", url).text

    total_bytes = len(raw.encode("utf-8"))
    truncated = False
    if total_bytes > MAX_NODE_FILE_BYTES:
        raw = raw[:MAX_NODE_FILE_BYTES]
        truncated = True

    # keepends keeps the content byte-faithful: the trailing newline of the
    # last line and any \r\n endings survive the round trip
    lines = raw.splitlines(keepends=True)
    total_lines = len(lines)

    # Apply offset/limit
    selected = lines[offset: offset + limit] if offset < total_lines else []
    has_more = (offset + limit) < total_lines or truncated
    content = "".join(selected)

    return {
        "file_path": file_path,
        "content": content,
        "metadata": {
            "total_lines": total_lines,
            "total_bytes": total_bytes,
            "offset": offset,
            "limit": limit,
            "returned_lines": len(selected),
            "returned_bytes": len(content.encode("utf-8")),
            "truncated": truncated or has_more,
            "has_more": has_more,
        },
    }


def write_node_file_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    project_id = params.get("project_id")
    node_id = params.get("node_id")
    file_path = params.get("file_path")
    content = params.get("content")
    if not project_id or not node_id or not file_path or content is None:
        return {"error": "project_id, node_id, file_path and content are required"}
    conn = _get_connector(gns3_ctx)
    url = f"{conn.base_url}/projects/{project_id}/nodes/{node_id}/files/{file_path}"
    conn.http_call("post", url, data=content, headers={"Content-Type": "text/plain"})
    return {"message": f"File {file_path} written to node {node_id}", "file_path": file_path, "node_id": node_id}


def delete_node_file_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    project_id = params.get("project_id")
    node_id = params.get("node_id")
    file_path = params.get("file_path")
    if not project_id or not node_id or not file_path:
        return {"error": "project_id, node_id and file_path are required"}
    conn = _get_connector(gns3_ctx)
    url = f"{conn.base_url}/projects/{project_id}/nodes/{node_id}/files/{file_path}"
    conn.http_call("delete", url)
    return {"message": f"File {file_path} deleted from node {node_id}", "file_path": file_path, "node_id": node_id}


# ── Node bulk / advanced handlers ────────────────────────────────────────


def start_all_nodes_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    project_id = params.get("project_id")
    if not project_id:
        return {"error": "project_id is required"}
    conn = _get_connector(gns3_ctx)
    conn.http_call("post", f"{conn.base_url}/projects/{project_id}/nodes/start")
    return {"message": "All nodes started", "project_id": project_id}


def stop_all_nodes_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    project_id = params.get("project_id")
    if not project_id:
        return {"error": "project_id is required"}
    conn = _get_connector(gns3_ctx)
    conn.http_call("post", f"{conn.base_url}/projects/{project_id}/nodes/stop")
    return {"message": "All nodes stopped", "project_id": project_id}


def suspend_all_nodes_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    project_id = params.get("project_id")
    if not project_id:
        return {"error": "project_id is required"}
    conn = _get_connector(gns3_ctx)
    conn.http_call("post", f"{conn.base_url}/projects/{project_id}/nodes/suspend")
    return {"message": "All nodes suspended", "project_id": project_id}


def duplicate_node_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    project_id = params.get("project_id")
    node_id = params.get("node_id")
    if not project_id or not node_id:
        return {"error": "project_id and node_id are required"}
    conn = _get_connector(gns3_ctx)
    data = {k: v for k, v in params.items() if k not in ("project_id", "node_id") and v is not None}
    result = conn.http_call("post", f"{conn.base_url}/projects/{project_id}/nodes/{node_id}/duplicate", json_data=data).json()
    return {"message": f"Node {node_id} duplicated", "node": result}


def isolate_node_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    project_id = params.get("project_id")
    node_id = params.get("node_id")
    if not project_id or not node_id:
        return {"error": "project_id and node_id are required"}
    conn = _get_connector(gns3_ctx)
    conn.http_call("post", f"{conn.base_url}/projects/{project_id}/nodes/{node_id}/isolate")
    return {"message": f"Node {node_id} isolated (all links suspended)", "node_id": node_id}


def unisolate_node_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    project_id = params.get("project_id")
    node_id = params.get("node_id")
    if not project_id or not node_id:
        return {"error": "project_id and node_id are required"}
    conn = _get_connector(gns3_ctx)
    conn.http_call("post", f"{conn.base_url}/projects/{project_id}/nodes/{node_id}/unisolate")
    return {"message": f"Node {node_id} unisolated (links resumed)", "node_id": node_id}


def get_node_links_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    project_id = params.get("project_id")
    node_id = params.get("node_id")
    if not project_id or not node_id:
        return {"error": "project_id and node_id are required"}
    conn = _get_connector(gns3_ctx)
    links = conn.http_call("get", f"{conn.base_url}/projects/{project_id}/nodes/{node_id}/links").json()
    return {"links": links, "count": len(links)}


# ── Link handlers ──────────────────────────────────────────────────────────

def get_links_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    project_id = params.get("project_id")
    if not project_id:
        return {"error": "project_id is required"}
    conn = _get_connector(gns3_ctx)
    links = conn.http_call("get", f"{conn.base_url}/projects/{project_id}/links").json()
    fields = params.get("fields")
    if fields:
        if not isinstance(fields, list):
            return {"error": "fields must be a list, e.g. [\"link_id\", \"nodes\"]"}
        invalid = [f for f in fields if f not in VALID_LINK_FIELDS]
        if invalid:
            return {
                "error": f"Unknown fields: {invalid}",
                "available_fields": sorted(VALID_LINK_FIELDS),
            }
        links = [{k: link[k] for k in fields if k in link} for link in links]
    return {"links": links, "count": len(links)}


def get_link_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    project_id = params.get("project_id")
    link_id = params.get("link_id")
    if not project_id or not link_id:
        return {"error": "project_id and link_id are required"}
    conn = _get_connector(gns3_ctx)
    return conn.http_call("get", f"{conn.base_url}/projects/{project_id}/links/{link_id}").json()


def available_filters_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    """
    List the packet filter types available for a link (GNS3 API v3 only).

    Returns a list of filter descriptors (frequency_drop, packet_loss,
    delay, corrupt, bpf) with their parameters.
    """
    project_id = params.get("project_id")
    link_id = params.get("link_id")
    if not project_id or not link_id:
        return {"error": "project_id and link_id are required"}
    conn = _get_connector(gns3_ctx)
    url = f"{conn.base_url}/projects/{project_id}/links/{link_id}/available_filters"
    return conn.http_call("get", url).json()


def create_link_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    project_id = params.get("project_id")
    if not project_id:
        return {"error": "project_id is required"}

    fields = params.get("fields")
    if fields is not None and not isinstance(fields, list):
        return {"error": "fields must be a list, e.g. [\"link_id\", \"nodes\"]"}

    links = params.get("links")
    # Batch mode: links=[{nodes, link_type?, filters?, suspend?}]
    if links is not None:
        if not isinstance(links, list) or not links:
            return {"error": "links must be a non-empty array"}
        conn = _get_connector(gns3_ctx)
        def _create_one(link_data):
            raw_nodes = link_data.get("nodes")
            if not raw_nodes:
                return {"status": "error", "error": "nodes is required for each link"}
            try:
                body = {"nodes": _normalize_link_nodes(raw_nodes)}
                if link_data.get("link_type"):
                    body["link_type"] = link_data["link_type"]
                if link_data.get("filters"):
                    body["filters"] = link_data["filters"]
                if link_data.get("suspend"):
                    body["suspend"] = link_data["suspend"]
                url = f"{conn.base_url}/projects/{project_id}/links"
                resp = conn.http_call("post", url, json_data=body).json()
                return {"status": "success", "link": _filter_link_response(resp, fields)}
            except Exception as e:
                return {"status": "error", "error": str(e)}
        with ThreadPoolExecutor(max_workers=min(len(links), BATCH_MAX_WORKERS)) as pool:
            # pool.map keeps the submission order, so callers can correlate
            # results with the links they sent regardless of completion order
            return list(pool.map(_create_one, links))

    # Single mode
    nodes = params.get("nodes")
    if not nodes:
        return {"error": "nodes is required"}
    conn = _get_connector(gns3_ctx)
    data = {"nodes": _normalize_link_nodes(nodes)}
    if "link_type" in params:
        data["link_type"] = params["link_type"]
    if "filters" in params:
        data["filters"] = params["filters"]
    if "suspend" in params:
        data["suspend"] = params["suspend"]
    url = f"{conn.base_url}/projects/{project_id}/links"
    resp = conn.http_call("post", url, json_data=data).json()
    return _filter_link_response(resp, fields)


def delete_link_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    project_id = params.get("project_id")
    if not project_id:
        return {"error": "project_id is required"}
    link_ids = params.get("link_ids")
    if link_ids:
        if not isinstance(link_ids, list):
            return {"error": "link_ids must be a list"}
        conn = _get_connector(gns3_ctx)
        def _del(lid):
            try:
                conn.http_call("delete", f"{conn.base_url}/projects/{project_id}/links/{lid}")
                return {"link_id": lid, "status": "success", "message": f"Link {lid} deleted"}
            except Exception as e:
                return {"link_id": lid, "status": "error", "error": str(e)}
        with ThreadPoolExecutor(max_workers=min(len(link_ids), BATCH_MAX_WORKERS)) as pool:
            return list(pool.map(_del, link_ids))
    link_id = params.get("link_id")
    if not link_id:
        return {"error": "link_id or link_ids is required"}
    conn = _get_connector(gns3_ctx)
    conn.http_call("delete", f"{conn.base_url}/projects/{project_id}/links/{link_id}")
    return {"message": f"Link {link_id} deleted", "link_id": link_id}


def update_link_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    project_id = params.get("project_id")
    link_id = params.get("link_id")
    if not project_id or not link_id:
        return {"error": "project_id and link_id are required"}
    conn = _get_connector(gns3_ctx)

    # Extract update parameters - handle nested kwargs structure from MCP clients
    if "kwargs" in params and isinstance(params["kwargs"], dict):
        update_data = params["kwargs"]
    else:
        update_data = {k: v for k, v in params.items() if k not in ("project_id", "link_id", "kwargs")}

    url = f"{conn.base_url}/projects/{project_id}/links/{link_id}"
    return conn.http_call("put", url, json_data=update_data).json()


# ── Link capture / reset handlers ──────────────────────────────────────


def reset_link_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    project_id = params.get("project_id")
    if not project_id:
        return {"error": "project_id is required"}
    link_ids = params.get("link_ids")
    if link_ids:
        if not isinstance(link_ids, list):
            return {"error": "link_ids must be a list"}
        conn = _get_connector(gns3_ctx)
        def _rst(lid):
            try:
                url = f"{conn.base_url}/projects/{project_id}/links/{lid}/reset"
                r = conn.http_call("post", url).json()
                return {"link_id": lid, "status": "reset", "link": r}
            except Exception as e:
                return {"link_id": lid, "status": "error", "error": str(e)}
        with ThreadPoolExecutor(max_workers=min(len(link_ids), BATCH_MAX_WORKERS)) as pool:
            return list(pool.map(_rst, link_ids))
    link_id = params.get("link_id")
    if not link_id:
        return {"error": "link_id or link_ids is required"}
    conn = _get_connector(gns3_ctx)
    url = f"{conn.base_url}/projects/{project_id}/links/{link_id}/reset"
    result = conn.http_call("post", url).json()
    return {"message": f"Link {link_id} reset", "link": result}


def _batch_capture(project_id, link_ids, action, data_builder, conn):
    """Helper for batch capture start/stop."""
    def _act(lid):
        try:
            url = f"{conn.base_url}/projects/{project_id}/links/{lid}/capture/{action}"
            kwargs = data_builder(lid) if data_builder else {}
            conn.http_call("post", url, **kwargs)
            return {"link_id": lid, "status": "success"}
        except Exception as e:
            return {"link_id": lid, "status": "error", "error": str(e)}
    with ThreadPoolExecutor(max_workers=min(len(link_ids), BATCH_MAX_WORKERS)) as pool:
        return list(pool.map(_act, link_ids))


def start_capture_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    project_id = params.get("project_id")
    if not project_id:
        return {"error": "project_id is required"}
    link_ids = params.get("link_ids")
    if link_ids:
        if not isinstance(link_ids, list):
            return {"error": "link_ids must be a list"}
        conn = _get_connector(gns3_ctx)
        dlt = params.get("data_link_type", "DLT_EN10MB")
        ws = params.get("wireshark", False)
        fname = params.get("capture_file_name")
        def _build(lid):
            data = {"data_link_type": dlt, "wireshark": ws}
            if fname:
                data["capture_file_name"] = fname
            return {"json_data": data}
        return _batch_capture(project_id, link_ids, "start", _build, conn)
    link_id = params.get("link_id")
    if not link_id:
        return {"error": "link_id or link_ids is required"}
    conn = _get_connector(gns3_ctx)
    data = {
        "data_link_type": params.get("data_link_type", "DLT_EN10MB"),
        "wireshark": params.get("wireshark", False),
    }
    if params.get("capture_file_name"):
        data["capture_file_name"] = params["capture_file_name"]
    url = f"{conn.base_url}/projects/{project_id}/links/{link_id}/capture/start"
    result = conn.http_call("post", url, json_data=data).json()
    return {"message": f"Capture started on link {link_id}", "link": result}


def stop_capture_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    project_id = params.get("project_id")
    if not project_id:
        return {"error": "project_id is required"}
    link_ids = params.get("link_ids")
    if link_ids:
        if not isinstance(link_ids, list):
            return {"error": "link_ids must be a list"}
        conn = _get_connector(gns3_ctx)
        return _batch_capture(project_id, link_ids, "stop", None, conn)
    link_id = params.get("link_id")
    if not link_id:
        return {"error": "link_id or link_ids is required"}
    conn = _get_connector(gns3_ctx)
    url = f"{conn.base_url}/projects/{project_id}/links/{link_id}/capture/stop"
    conn.http_call("post", url)
    return {"message": f"Capture stopped on link {link_id}", "link_id": link_id}


def download_capture_file_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    project_id = params.get("project_id")
    if not project_id:
        return {"error": "project_id is required"}
    username = gns3_ctx.get("jwt_username")
    token_version = gns3_ctx.get("jwt_token_version", 0)

    def _download(link_id: str) -> dict[str, Any]:
        # short-lived ticket bound to this exact download path — LLM clients
        # retyping curl commands corrupted the long Bearer JWT this used to embed
        path = f"/v3/projects/{project_id}/links/{link_id}/capture/file"
        url = f"{gns3_ctx['server_url']}{path}"
        ticket = access_ticket_service.mint(username, token_version=token_version, path=path) if username else None
        if ticket:
            url += f"?token={ticket}"
        entry = {"link_id": link_id, "download_url": url}
        if ticket:
            entry["curl_command"] = f"curl -L -o capture_{link_id}.pcap '{url}'"
        return entry

    link_ids = params.get("link_ids")
    if link_ids:
        if not isinstance(link_ids, list):
            return {"error": "link_ids must be a list"}
        results = [_download(lid) for lid in link_ids]
        return {"downloads": results, "count": len(results), "note": "Files are in pcap format. URLs include a 10-minute ticket."}

    link_id = params.get("link_id")
    if not link_id:
        return {"error": "link_id or link_ids is required"}
    result = _download(link_id)
    result["note"] = "The file is in pcap format and can be analyzed with Wireshark or tcpdump."
    if "curl_command" in result:
        result["curl_command"] = f"curl -L -o capture.pcap '{result['download_url']}'"
        result["note"] += " The download URL includes a 10-minute ticket."
    return result


# ── Marker (traffic-insight) handlers ──────────────────────────────────


def link_marker_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    """
    Manage traffic-insight markers on a specific link.

    Actions:
      - create: POST /projects/{pid}/links/{lid}/markers
      - update: PUT  /projects/{pid}/links/{lid}/markers/{name}
      - delete: DELETE /projects/{pid}/links/{lid}/markers/{name}
    """
    project_id = params.get("project_id")
    link_id = params.get("link_id")
    action = params.get("action")
    if not all([project_id, link_id, action]):
        return {"error": "project_id, link_id and action are required"}
    if action not in ("create", "update", "delete"):
        return {"error": f"Unknown action: {action}. Supported: create, update, delete"}

    conn = _get_connector(gns3_ctx)
    base = f"{conn.base_url}/projects/{project_id}/links/{link_id}/markers"

    if action == "create":
        bpf = params.get("bpf")
        if not bpf:
            return {"error": "bpf is required for create action"}
        body: dict[str, Any] = {"bpf": bpf}
        for opt in ("name", "tag", "capture_node_id", "color", "highlight_duration", "data_link_type"):
            if params.get(opt) is not None:
                body[opt] = params[opt]
        # direction: "tx"/"rx" set a one-way filter; "both"/omitted = no filter.
        if params.get("direction") in ("tx", "rx"):
            body["direction"] = params["direction"]
        return conn.http_call("post", base, json_data=body).json()

    marker_name = params.get("marker_name")
    if not marker_name:
        return {"error": "marker_name is required for update/delete actions"}

    url = f"{base}/{marker_name}"

    if action == "update":
        body = {}
        for opt in ("bpf", "tag", "enabled", "color", "highlight_duration"):
            if params.get(opt) is not None:
                body[opt] = params[opt]
        # direction tri-state: omitted=preserve, "tx"/"rx"=set, "both"=clear (→ null).
        direction = params.get("direction")
        if direction == "both":
            body["direction"] = None
        elif direction in ("tx", "rx"):
            body["direction"] = direction
        if not body:
            return {"error": "At least one update field is required (bpf, tag, enabled, direction, color, highlight_duration)"}
        return conn.http_call("put", url, json_data=body).json()

    # action == "delete"
    conn.http_call("delete", url)
    return {"message": f"Marker '{marker_name}' deleted from link {link_id}", "link_id": link_id, "marker_name": marker_name}


def marker_definition_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    """
    Manage project-level marker definitions (auto-fanout to all links).

    Actions:
      - create: POST   /projects/{pid}/marker-definitions  → fans out global-{name} to every link
      - update: PUT    /projects/{pid}/marker-definitions/{name}
      - delete: DELETE /projects/{pid}/marker-definitions/{name}
      - list:   GET    /projects/{pid}/marker-definitions
    """
    project_id = params.get("project_id")
    action = params.get("action")
    if not all([project_id, action]):
        return {"error": "project_id and action are required"}
    if action not in ("create", "update", "delete", "list"):
        return {"error": f"Unknown action: {action}. Supported: create, update, delete, list"}

    conn = _get_connector(gns3_ctx)
    base = f"{conn.base_url}/projects/{project_id}/marker-definitions"

    if action == "list":
        return conn.http_call("get", base).json()

    if action == "create":
        bpf = params.get("bpf")
        if not bpf:
            return {"error": "bpf is required for create action"}
        body: dict[str, Any] = {"bpf": bpf}
        for opt in ("name", "tag", "color", "highlight_duration", "data_link_type"):
            if params.get(opt) is not None:
                body[opt] = params[opt]
        # No direction: a definition fans out to every link and auto-selects its
        # capture node on each, so tx/rx (which is relative to that node) has no
        # consistent meaning. Encode direction in the BPF instead.
        return conn.http_call("post", base, json_data=body).json()

    def_name = params.get("def_name")
    if not def_name:
        return {"error": "def_name is required for update/delete actions"}

    url = f"{base}/{def_name}"

    if action == "update":
        body = {}
        for opt in ("bpf", "tag", "color", "highlight_duration", "data_link_type"):
            if params.get(opt) is not None:
                body[opt] = params[opt]
        if not body:
            return {"error": "At least one update field is required (bpf, tag, color, highlight_duration, data_link_type)"}
        return conn.http_call("put", url, json_data=body).json()

    # action == "delete"
    conn.http_call("delete", url)
    return {"message": f"Marker definition '{def_name}' deleted", "project_id": project_id, "def_name": def_name}
