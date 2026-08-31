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
MCP tools for GNS3 project management.

Tool handlers receive (params, gns3_ctx) and call GNS3's REST API
via Gns3Connector (from gns3_copilot.gns3_client.connector).
"""

from typing import Any

import logging

log = logging.getLogger(__name__)


# ── Helper ─────────────────────────────────────────────────────────────────

def _get_connector(gns3_ctx: dict[str, Any]):
    """Create a Gns3Connector from the GNS3 context dict."""
    from gns3server.agent.gns3_copilot.gns3_client.connector import Gns3Connector
    return Gns3Connector(
        url=gns3_ctx["server_url"],
        jwt_token=gns3_ctx["jwt_token"],
        api_version=3,
        verify=False,
    )


# ── Tool handlers ──────────────────────────────────────────────────────────

def list_projects_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    conn = _get_connector(gns3_ctx)
    projects = conn.http_call("get", f"{conn.base_url}/projects").json()
    return {"projects": projects, "count": len(projects)}


def get_project_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    project_id = params.get("project_id")
    if not project_id:
        return {"error": "project_id is required"}
    conn = _get_connector(gns3_ctx)
    project = conn.http_call("get", f"{conn.base_url}/projects/{project_id}").json()
    if project is None:
        return {"error": f"Project '{project_id}' not found"}
    return project


def create_project_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    name = params.get("name")
    if not name:
        return {"error": "name is required"}
    conn = _get_connector(gns3_ctx)
    json_data: dict[str, Any] = {"name": name}
    if params.get("auto_close") is not None:
        json_data["auto_close"] = params["auto_close"]
    return conn.http_call("post", f"{conn.base_url}/projects", json_data=json_data).json()


def delete_project_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    project_id = params.get("project_id")
    if not project_id:
        return {"error": "project_id is required"}
    conn = _get_connector(gns3_ctx)
    conn.http_call("delete", f"{conn.base_url}/projects/{project_id}")
    return {"message": f"Project '{project_id}' deleted", "project_id": project_id}


def open_project_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    project_id = params.get("project_id")
    if not project_id:
        return {"error": "project_id is required"}
    conn = _get_connector(gns3_ctx)
    url = f"{conn.base_url}/projects/{project_id}/open"
    return conn.http_call("post", url).json()


def close_project_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    project_id = params.get("project_id")
    if not project_id:
        return {"error": "project_id is required"}
    conn = _get_connector(gns3_ctx)
    url = f"{conn.base_url}/projects/{project_id}/close"
    conn.http_call("post", url)
    return {"message": f"Project '{project_id}' closed", "project_id": project_id}


def get_project_stats_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    project_id = params.get("project_id")
    if not project_id:
        return {"error": "project_id is required"}
    conn = _get_connector(gns3_ctx)
    url = f"{conn.base_url}/projects/{project_id}/stats"
    return conn.http_call("get", url).json()


def update_project_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    project_id = params.get("project_id")
    if not project_id:
        return {"error": "project_id is required"}
    conn = _get_connector(gns3_ctx)
    kwargs = {k: v for k, v in params.items() if k != "project_id" and v is not None}
    return conn.http_call("put", f"{conn.base_url}/projects/{project_id}", json_data=kwargs).json()


def duplicate_project_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    project_id = params.get("project_id")
    if not project_id:
        return {"error": "project_id is required"}
    name = params.get("name")
    if not name:
        return {"error": "name is required"}
    conn = _get_connector(gns3_ctx)
    kwargs = {k: v for k, v in params.items() if k not in ("project_id",) and v is not None}
    return conn.http_call("post", f"{conn.base_url}/projects/{project_id}/duplicate", json_data=kwargs).json()


def get_project_readme_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    project_id = params.get("project_id")
    if not project_id:
        return {"error": "project_id is required"}
    conn = _get_connector(gns3_ctx)
    try:
        url = f"{conn.base_url}/projects/{project_id}/files/README.txt"
        content = conn.http_call("get", url).text
        return {"project_id": project_id, "file": "README.txt", "content": content}
    except Exception as e:
        if "404" in str(e):
            return {"project_id": project_id, "file": "README.txt", "content": None, "message": "README.txt does not exist yet"}
        raise


def update_project_readme_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    project_id = params.get("project_id")
    if not project_id:
        return {"error": "project_id is required"}
    content = params.get("content")
    if content is None:
        return {"error": "content is required"}
    conn = _get_connector(gns3_ctx)
    url = f"{conn.base_url}/projects/{project_id}/files/README.txt"
    conn.http_call("post", url, data=content, headers={"Content-Type": "text/plain"})
    return {"message": "README.txt updated", "project_id": project_id}


def lock_project_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    project_id = params.get("project_id")
    if not project_id:
        return {"error": "project_id is required"}
    conn = _get_connector(gns3_ctx)
    conn.http_call("post", f"{conn.base_url}/projects/{project_id}/lock")
    return {"message": f"Project {project_id} locked", "project_id": project_id}


def unlock_project_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    project_id = params.get("project_id")
    if not project_id:
        return {"error": "project_id is required"}
    conn = _get_connector(gns3_ctx)
    conn.http_call("post", f"{conn.base_url}/projects/{project_id}/unlock")
    return {"message": f"Project {project_id} unlocked", "project_id": project_id}


def get_locked_project_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    project_id = params.get("project_id")
    if not project_id:
        return {"error": "project_id is required"}
    conn = _get_connector(gns3_ctx)
    locked = conn.http_call("get", f"{conn.base_url}/projects/{project_id}/locked").json()
    return {"project_id": project_id, "locked": locked}


# ── Tool definitions (consumed by mcp/__init__.py) ─────────────────────────

PROJECT_TOOLS = [
    {
        "name": "list_projects",
        "description": "List all GNS3 projects accessible to the current user",
        "parameters": {"type": "object", "properties": {}},
        "handler": list_projects_handler,
    },
    {
        "name": "get_project",
        "description": "Get detailed information about a specific project",
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Project UUID"},
            },
            "required": ["project_id"],
        },
        "handler": get_project_handler,
    },
    {
        "name": "create_project",
        "description": "Create a new GNS3 project",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Project name"},
                "description": {"type": "string", "description": "Optional project description"},
            },
            "required": ["name"],
        },
        "handler": create_project_handler,
    },
    {
        "name": "delete_project",
        "description": "Delete a GNS3 project permanently",
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "UUID of the project to delete"},
            },
            "required": ["project_id"],
        },
        "handler": delete_project_handler,
    },
    {
        "name": "open_project",
        "description": "Open a closed GNS3 project",
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Project UUID"},
            },
            "required": ["project_id"],
        },
        "handler": open_project_handler,
    },
    {
        "name": "close_project",
        "description": "Close an open GNS3 project",
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Project UUID"},
            },
            "required": ["project_id"],
        },
        "handler": close_project_handler,
    },
    {
        "name": "get_project_stats",
        "description": "Get statistics (nodes, links, snapshots, drawings) for a project",
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Project UUID"},
            },
            "required": ["project_id"],
        },
        "handler": get_project_stats_handler,
    },
    {
        "name": "update_project",
        "description": "Update a project's properties (name, auto_close, auto_open, etc.)",
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Project UUID"},
                "name": {"type": "string", "description": "New project name"},
                "auto_close": {"type": "boolean", "description": "Close project when last client leaves"},
                "auto_open": {"type": "boolean", "description": "Project opens when GNS3 starts"},
                "auto_start": {"type": "boolean", "description": "Project starts when opened"},
                "scene_width": {"type": "integer", "description": "Width of the drawing area"},
                "scene_height": {"type": "integer", "description": "Height of the drawing area"},
                "zoom": {"type": "integer", "description": "Zoom of the drawing area"},
                "show_layers": {"type": "boolean", "description": "Show layers on the drawing area"},
                "snap_to_grid": {"type": "boolean", "description": "Snap to grid on the drawing area"},
                "show_grid": {"type": "boolean", "description": "Show the grid on the drawing area"},
                "grid_size": {"type": "integer", "description": "Grid size for the drawing area for nodes"},
                "drawing_grid_size": {"type": "integer", "description": "Grid size for the drawing area for drawings"},
                "show_interface_labels": {"type": "boolean", "description": "Show interface labels on the drawing area"},
            },
            "required": ["project_id"],
        },
        "handler": update_project_handler,
    },
    {
        "name": "duplicate_project",
        "description": "Duplicate a project",
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "UUID of the project to duplicate"},
                "name": {"type": "string", "description": "New project name"},
                "reset_mac_addresses": {"type": "boolean", "description": "Reset MAC addresses for this project"},
            },
            "required": ["project_id", "name"],
        },
        "handler": duplicate_project_handler,
    },
    {
        "name": "get_project_readme",
        "description": "Get the content of a project's README.md file (project documentation, Markdown format)",
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Project UUID"},
            },
            "required": ["project_id"],
        },
        "handler": get_project_readme_handler,
    },
    {
        "name": "update_project_readme",
        "description": "Update or create a project's README.md file (project documentation, Markdown format)",
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Project UUID"},
                "content": {"type": "string", "description": "Content to write to README.md (Markdown format)"},
            },
            "required": ["project_id", "content"],
        },
        "handler": update_project_readme_handler,
    },
]
