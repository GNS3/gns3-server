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
MCP tools for the current user's own account: the flattened privilege
view and the node quota usage. Both endpoints only need an authenticated
user, so these tools are the self-check the AI can always call.
"""

import logging
from typing import Any

log = logging.getLogger(__name__)


def _get_connector(gns3_ctx: dict[str, Any]):
    from gns3server.agent.gns3_copilot.gns3_client.connector import Gns3Connector

    return Gns3Connector(
        url=gns3_ctx["server_url"],
        jwt_token=gns3_ctx["jwt_token"],
        api_version=3,
        verify=False,
    )


def get_user_privileges_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    """Effective privileges of the current user, flattened across resource paths."""
    conn = _get_connector(gns3_ctx)
    return conn.http_call("get", f"{conn.base_url}/access/users/me/privileges").json()


def get_user_quotas_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    """Node quota limits of the current user and the current usage."""
    conn = _get_connector(gns3_ctx)
    return conn.http_call("get", f"{conn.base_url}/access/users/me/quotas").json()
