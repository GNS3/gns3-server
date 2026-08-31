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
MCP tool handlers for GNS3 snapshot management.
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

def get_snapshots_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    project_id = params.get("project_id")
    if not project_id:
        return {"error": "project_id is required"}
    conn = _get_connector(gns3_ctx)
    snapshots = conn.http_call("get", f"{conn.base_url}/projects/{project_id}/snapshots").json()
    return {"snapshots": snapshots, "count": len(snapshots)}


def create_snapshot_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    project_id = params.get("project_id")
    name = params.get("name")
    if not project_id or not name:
        return {"error": "project_id and name are required"}
    conn = _get_connector(gns3_ctx)
    result = conn.http_call("post", f"{conn.base_url}/projects/{project_id}/snapshots", json_data={"name": name}).json()
    return {"message": f"Snapshot '{name}' created", "snapshot": result}


def delete_snapshot_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    project_id = params.get("project_id")
    snapshot_id = params.get("snapshot_id")
    if not project_id or not snapshot_id:
        return {"error": "project_id and snapshot_id are required"}
    conn = _get_connector(gns3_ctx)
    conn.http_call("delete", f"{conn.base_url}/projects/{project_id}/snapshots/{snapshot_id}")
    return {"message": f"Snapshot {snapshot_id} deleted", "snapshot_id": snapshot_id}


def restore_snapshot_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    project_id = params.get("project_id")
    snapshot_id = params.get("snapshot_id")
    if not project_id or not snapshot_id:
        return {"error": "project_id and snapshot_id are required"}
    conn = _get_connector(gns3_ctx)
    result = conn.http_call("post", f"{conn.base_url}/projects/{project_id}/snapshots/{snapshot_id}/restore").json()
    return {"message": f"Snapshot {snapshot_id} restored", "project": result}
