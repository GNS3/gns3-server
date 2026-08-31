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
MCP tool handlers for GNS3 image management.
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

def get_images_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    conn = _get_connector(gns3_ctx)
    images = conn.http_call("get", f"{conn.base_url}/images").json()
    return {"images": images, "count": len(images)}


def get_image_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    image_id = params.get("image_id")
    if not image_id:
        return {"error": "image_id is required"}
    conn = _get_connector(gns3_ctx)
    return conn.http_call("get", f"{conn.base_url}/images/{image_id}").json()


def delete_image_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    image_id = params.get("image_id")
    if not image_id:
        return {"error": "image_id is required"}
    conn = _get_connector(gns3_ctx)
    conn.http_call("delete", f"{conn.base_url}/images/{image_id}")
    return {"message": f"Image {image_id} deleted", "image_id": image_id}


def prune_images_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    conn = _get_connector(gns3_ctx)
    # Returns 204 No Content on success (empty body, no .json())
    conn.http_call("delete", f"{conn.base_url}/images/prune")
    return {"message": "Unused images pruned"}


def install_images_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    conn = _get_connector(gns3_ctx)
    response = conn.http_call("post", f"{conn.base_url}/images/install")
    if response.content:
        # the install endpoint reports which templates were created or skipped
        return response.json()
    # tolerate an empty body in case an older server still replies with 204
    return {"message": "Image installation completed"}
