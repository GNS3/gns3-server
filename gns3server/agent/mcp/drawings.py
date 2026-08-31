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
MCP tool handlers for GNS3 drawing management.
"""

from typing import Any

import logging

log = logging.getLogger(__name__)


# ── Helper ─────────────────────────────────────────────────────────────────

def _get_connector(gns3_ctx: dict[str, Any]):
    from gns3server.agent.gns3_copilot.gns3_client.connector import Gns3Connector
    return Gns3Connector(
        url=gns3_ctx["server_url"],
        jwt_token=gns3_ctx["jwt_token"],
        api_version=3,
        verify=False,
    )


# ── Tool handlers ──────────────────────────────────────────────────────────

def get_drawings_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    project_id = params.get("project_id")
    if not project_id:
        return {"error": "project_id is required"}
    conn = _get_connector(gns3_ctx)
    drawings = conn.http_call("get", f"{conn.base_url}/projects/{project_id}/drawings").json()
    return {"drawings": drawings, "count": len(drawings)}


def create_drawing_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    project_id = params.get("project_id")
    svg = params.get("svg")
    if not project_id or not svg:
        return {"error": "project_id and svg are required"}
    conn = _get_connector(gns3_ctx)
    data = {
        "svg": svg,
        "x": params.get("x", 0),
        "y": params.get("y", 0),
        "z": params.get("z", 0),
        "locked": params.get("locked", False),
        "rotation": params.get("rotation", 0),
    }
    result = conn.http_call("post", f"{conn.base_url}/projects/{project_id}/drawings", json_data=data).json()
    return {"message": "Drawing created", "drawing": result}


def get_drawing_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    project_id = params.get("project_id")
    drawing_id = params.get("drawing_id")
    if not project_id or not drawing_id:
        return {"error": "project_id and drawing_id are required"}
    conn = _get_connector(gns3_ctx)
    return conn.http_call("get", f"{conn.base_url}/projects/{project_id}/drawings/{drawing_id}").json()


def update_drawing_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    project_id = params.get("project_id")
    drawing_id = params.get("drawing_id")
    if not project_id or not drawing_id:
        return {"error": "project_id and drawing_id are required"}
    conn = _get_connector(gns3_ctx)
    data = {k: v for k, v in params.items() if k not in ("project_id", "drawing_id") and v is not None}
    return conn.http_call("put", f"{conn.base_url}/projects/{project_id}/drawings/{drawing_id}", json_data=data).json()


def delete_drawing_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    project_id = params.get("project_id")
    drawing_id = params.get("drawing_id")
    if not project_id or not drawing_id:
        return {"error": "project_id and drawing_id are required"}
    conn = _get_connector(gns3_ctx)
    conn.http_call("delete", f"{conn.base_url}/projects/{project_id}/drawings/{drawing_id}")
    return {"message": f"Drawing {drawing_id} deleted", "drawing_id": drawing_id}
