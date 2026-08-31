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
MCP tool handlers for GNS3 compute management.
"""

from typing import Any
import logging

log = logging.getLogger(__name__)


def _get_connector(gns3_ctx: dict[str, Any]):
    from gns3server.agent.gns3_copilot.gns3_client.connector import Gns3Connector
    return Gns3Connector(
        url=gns3_ctx["server_url"],
        jwt_token=gns3_ctx["jwt_token"],
        api_version=3,
        verify=False,
    )


def list_computes_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    conn = _get_connector(gns3_ctx)
    computes = conn.http_call("get", f"{conn.base_url}/computes").json()
    return {"computes": computes, "count": len(computes)}


def get_compute_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    compute_id = params.get("compute_id") or "local"
    conn = _get_connector(gns3_ctx)
    return conn.http_call("get", f"{conn.base_url}/computes/{compute_id}").json()


def get_compute_images_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    emulator = params.get("emulator")
    compute_id = params.get("compute_id") or "local"
    if not emulator:
        return {"error": "emulator is required (e.g. qemu, iou, docker)"}
    conn = _get_connector(gns3_ctx)
    images = conn.http_call("get", f"{conn.base_url}/computes/{compute_id}/{emulator}/images").json()
    return {"images": images, "count": len(images)}


COMPUTE_TOOLS = [
    {
        "name": "list_computes",
        "description": "List all compute nodes available to the server",
        "parameters": {"type": "object", "properties": {}},
        "handler": list_computes_handler,
    },
    {
        "name": "get_compute",
        "description": "Get detailed information about a compute node",
        "parameters": {
            "type": "object",
            "properties": {
                "compute_id": {"type": "string", "description": "Compute ID (default: local)"},
            },
        },
        "handler": get_compute_handler,
    },
    {
        "name": "get_compute_images",
        "description": "List available images for an emulator on a compute node",
        "parameters": {
            "type": "object",
            "properties": {
                "emulator": {"type": "string", "description": "Emulator type (e.g. qemu, iou, docker)"},
                "compute_id": {"type": "string", "description": "Compute ID (default: local)"},
            },
            "required": ["emulator"],
        },
        "handler": get_compute_images_handler,
    },
]
