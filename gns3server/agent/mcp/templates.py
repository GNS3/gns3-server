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
MCP tool handlers for GNS3 template management.

Handlers receive (params, gns3_ctx) and call GNS3's REST API
via Gns3Connector (from gns3_copilot.gns3_client.connector).
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

VALID_TEMPLATE_FIELDS = {
    "template_id", "name", "version", "category", "default_name_format",
    "symbol", "template_type", "compute_id", "usage", "tags", "builtin",
    "created_at", "updated_at",
}

TEMPLATE_DEFAULT_FIELDS = ["template_id", "name", "template_type", "category", "default_name_format"]


def _filter_templates(templates, fields):
    """Filter each template to only include requested fields."""
    if not fields:
        fields = TEMPLATE_DEFAULT_FIELDS
    if isinstance(templates, dict):
        return {k: templates[k] for k in fields if k in templates}
    return [{k: t[k] for k in fields if k in t} for t in templates]


def list_templates_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    conn = _get_connector(gns3_ctx)
    templates = conn.http_call("get", f"{conn.base_url}/templates").json()
    fields = params.get("fields")
    if fields:
        if not isinstance(fields, list):
            return {"error": "fields must be a list, e.g. [\"template_id\", \"name\"]"}
        invalid = [f for f in fields if f not in VALID_TEMPLATE_FIELDS]
        if invalid:
            return {
                "error": f"Unknown fields: {invalid}",
                "available_fields": sorted(VALID_TEMPLATE_FIELDS),
            }
        templates = _filter_templates(templates, fields)
    return {"templates": templates, "count": len(templates)}


def get_template_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    template_id = params.get("template_id")
    name = params.get("name")

    if not template_id and not name:
        return {"error": "template_id or name is required"}

    conn = _get_connector(gns3_ctx)

    if template_id:
        template = conn.http_call("get", f"{conn.base_url}/templates/{template_id}").json()
    else:
        # Find template by name
        all_templates = conn.http_call("get", f"{conn.base_url}/templates").json()
        matches = [t for t in all_templates if t.get("name") == name]
        if not matches:
            return {"error": f"Template '{name}' not found"}
        template = matches[0]

    return template


def create_template_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    name = params.get("name")
    template_type = params.get("template_type")
    if not name or not template_type:
        return {"error": "name and template_type are required"}

    conn = _get_connector(gns3_ctx)
    data = {
        "name": name,
        "template_type": template_type,
        "compute_id": params.get("compute_id", "local"),
    }
    # Pass through optional template-type-specific fields (image, qemu_path, etc.)
    for key in ("image",):
        if key in params:
            data[key] = params[key]
    return conn.http_call("post", f"{conn.base_url}/templates", json_data=data).json()


def update_template_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    template_id = params.get("template_id")
    name = params.get("name")

    if not template_id and not name:
        return {"error": "template_id or name is required"}

    conn = _get_connector(gns3_ctx)

    # Resolve name to ID if needed
    if not template_id and name:
        all_templates = conn.http_call("get", f"{conn.base_url}/templates").json()
        matches = [t for t in all_templates if t.get("name") == name]
        if not matches:
            return {"error": f"Template '{name}' not found"}
        template_id = matches[0]["template_id"]

    update_data = {k: v for k, v in params.items() if k not in ("template_id", "name", "kwargs")}
    # Support nested kwargs from MCP clients
    if "kwargs" in params and isinstance(params["kwargs"], dict):
        update_data = params["kwargs"]

    return conn.http_call("put", f"{conn.base_url}/templates/{template_id}", json_data=update_data).json()


def delete_template_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    template_id = params.get("template_id")
    name = params.get("name")

    if not template_id and not name:
        return {"error": "template_id or name is required"}

    conn = _get_connector(gns3_ctx)

    if not template_id and name:
        all_templates = conn.http_call("get", f"{conn.base_url}/templates").json()
        matches = [t for t in all_templates if t.get("name") == name]
        if not matches:
            return {"error": f"Template '{name}' not found"}
        template_id = matches[0]["template_id"]

    conn.http_call("delete", f"{conn.base_url}/templates/{template_id}")
    return {"message": f"Template deleted"}


# ── Tool definitions ───────────────────────────────────────────────────────

TEMPLATE_TOOLS = [
    {
        "name": "list_templates",
        "description": "List all available templates on the server",
        "parameters": {
            "type": "object",
            "properties": {},
        },
        "handler": list_templates_handler,
    },
    {
        "name": "get_template",
        "description": "Get detailed information about a specific template",
        "parameters": {
            "type": "object",
            "properties": {
                "template_id": {"type": "string", "description": "Template UUID"},
                "name": {"type": "string", "description": "Template name"},
            },
        },
        "handler": get_template_handler,
    },
    {
        "name": "create_template",
        "description": "Create a new template",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Template name"},
                "template_type": {"type": "string", "description": "Template type (e.g. qemu, docker, dynamips)"},
                "compute_id": {"type": "string", "description": "Compute ID (optional, default: local)"},
            },
            "required": ["name", "template_type"],
        },
        "handler": create_template_handler,
    },
    {
        "name": "update_template",
        "description": "Update an existing template's properties",
        "parameters": {
            "type": "object",
            "properties": {
                "template_id": {"type": "string", "description": "Template UUID"},
                "name": {"type": "string", "description": "Template name"},
            },
        },
        "handler": update_template_handler,
    },
    {
        "name": "delete_template",
        "description": "Delete a template",
        "parameters": {
            "type": "object",
            "properties": {
                "template_id": {"type": "string", "description": "Template UUID"},
                "name": {"type": "string", "description": "Template name"},
            },
        },
        "handler": delete_template_handler,
    },
]
