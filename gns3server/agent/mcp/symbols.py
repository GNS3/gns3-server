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
MCP tool handlers for GNS3 symbol management.
"""

from typing import Any

import logging

from gns3server.services import access_ticket_service

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

def get_symbols_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    conn = _get_connector(gns3_ctx)
    symbols = conn.http_call("get", f"{conn.base_url}/symbols").json()
    return {"symbols": symbols, "count": len(symbols)}


def get_symbol_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    symbol_id = params.get("symbol_id")
    if not symbol_id:
        return {"error": "symbol_id is required"}
    path = f"/v3/symbols/{symbol_id}/raw"
    download_url = f"{gns3_ctx['server_url']}{path}"
    username = gns3_ctx.get("jwt_username")
    # short-lived ticket bound to this exact path — LLM clients retyping curl
    # commands corrupted the long Bearer JWT this used to embed
    ticket = access_ticket_service.mint(
        username, token_version=gns3_ctx.get("jwt_token_version", 0), path=path
    ) if username else None
    if ticket:
        download_url += f"?token={ticket}"
    result = {
        "symbol_id": symbol_id,
        "download_url": download_url,
        "note": "Symbol files are SVG images.",
    }
    if ticket:
        safe_name = symbol_id.replace(':', '').replace('/', '_')
        result["curl_command"] = f"curl -L -o '{safe_name}.svg' '{download_url}'"
        result["note"] += " The download URL includes a 10-minute ticket."
    return result


def get_symbol_dimensions_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    symbol_id = params.get("symbol_id")
    if not symbol_id:
        return {"error": "symbol_id is required"}
    conn = _get_connector(gns3_ctx)
    return conn.http_call("get", f"{conn.base_url}/symbols/{symbol_id}/dimensions").json()


def get_default_symbols_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    conn = _get_connector(gns3_ctx)
    symbols = conn.http_call("get", f"{conn.base_url}/symbols/default_symbols").json()
    return {"default_symbols": symbols}


def upload_symbol_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    symbol_id = params.get("symbol_id")
    content = params.get("content")
    if not symbol_id or content is None:
        return {"error": "symbol_id and content (SVG data) are required"}
    conn = _get_connector(gns3_ctx)
    url = f"{conn.base_url}/symbols/{symbol_id}/raw"
    conn.http_call("post", url, data=content, headers={"Content-Type": "image/svg+xml"})
    return {"message": f"Symbol {symbol_id} uploaded", "symbol_id": symbol_id}


def delete_symbol_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    symbol_id = params.get("symbol_id")
    if not symbol_id:
        return {"error": "symbol_id is required"}
    conn = _get_connector(gns3_ctx)
    conn.http_call("delete", f"{conn.base_url}/symbols/{symbol_id}")
    return {"message": f"Symbol {symbol_id} deleted", "symbol_id": symbol_id}
