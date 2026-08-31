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
MCP tool handlers for GNS3 appliance management.
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

VALID_APPLIANCE_FIELDS = {
    "appliance_id", "name", "category", "description", "vendor_name",
    "vendor_url", "product_name", "product_url", "documentation_url",
    "status", "availability", "maintainer", "usage", "symbol",
    "images", "versions", "tags", "builtin",
    "first_port_name", "port_name_format", "port_segment_size",
    "linked_clone", "docker", "iou", "dynamips", "qemu",
}


def get_appliances_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    conn = _get_connector(gns3_ctx)
    appliances = conn.http_call("get", f"{conn.base_url}/appliances").json()
    fields = params.get("fields")
    if fields:
        if not isinstance(fields, list):
            return {"error": "fields must be a list, e.g. [\"name\", \"category\"]"}
        invalid = [f for f in fields if f not in VALID_APPLIANCE_FIELDS]
        if invalid:
            return {
                "error": f"Unknown fields: {invalid}",
                "available_fields": sorted(VALID_APPLIANCE_FIELDS),
            }
        appliances = [{k: a[k] for k in fields if k in a} for a in appliances]
    return {"appliances": appliances, "count": len(appliances)}


def get_appliance_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    appliance_id = params.get("appliance_id")
    if not appliance_id:
        return {"error": "appliance_id is required"}
    conn = _get_connector(gns3_ctx)
    return conn.http_call("get", f"{conn.base_url}/appliances/{appliance_id}").json()


def install_appliance_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    appliance_id = params.get("appliance_id")
    if not appliance_id:
        return {"error": "appliance_id is required"}
    conn = _get_connector(gns3_ctx)
    url = f"{conn.base_url}/appliances/{appliance_id}/install"
    request_params = {}
    version = params.get("version")
    if version:
        request_params["version"] = version
    response = conn.http_call("post", url, params=request_params)
    result = {"message": f"Appliance {appliance_id} installed"}
    if response.content:
        # the install endpoint returns the created template (201); tolerate an
        # empty body in case an older server still replies with 204
        template = response.json()
        result["template"] = {
            k: template[k] for k in ("template_id", "name", "version", "template_type") if k in template
        }
    return result
