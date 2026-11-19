#
# Copyright (C) 2026 GNS3 Technologies Inc.
# Author: YueGuobin
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
Privilege-based tool visibility for the MCP server.

Each MCP tool declares the controller privileges its underlying REST
endpoints require (union over every endpoint the tool touches, including
fallback calls). ``tools/list`` only returns tools the current user could
call somewhere, and ``tools/call`` re-checks before dispatching. Instance
level decisions (which exact project a user may open) stay with the REST
endpoints themselves: this layer only answers "does the user hold the
privilege at any scope" using the flattened view from
``RbacRepository.get_user_privileges`` — the same semantics as
``GET /access/users/me/privileges``.

The declared sets are locked to the live routes by
``tests/agent/mcp/test_tool_access.py``: it reflects over the controller
router, extracts each endpoint's ``has_privilege(...)`` requirements and
asserts every spec covers them. Adding a privilege to an endpoint breaks
that test until the spec here is updated.
"""

import logging
import time
from typing import Any, FrozenSet, Optional
from uuid import UUID

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger(__name__)

# Cache the flattened privilege set per user for a short while: the RBAC
# snapshot itself is in-memory, but the lookup still needs a DB session.
# A short TTL keeps revocations effective without a round-trip per call.
# The third tuple element is the group whitelist: the union of the MCP
# tool whitelists of the user's groups (None = unrestricted).
_PRIVILEGE_CACHE_TTL_S = 5.0
_privilege_cache: dict[str, tuple[float, FrozenSet[str], bool, Optional[FrozenSet[str]]]] = {}


# A tool with no entry here is visible to every authenticated user.
# Entries must list every privilege required by any endpoint the tool
# calls (see the consistency test for the authoritative extraction).
TOOL_SPECS: dict[str, FrozenSet[str]] = {
    # projects
    "project_list": frozenset(),
    "project_get": frozenset({"Project.Audit"}),
    "project_create": frozenset({"Project.Allocate"}),
    "project_update": frozenset({"Project.Modify"}),
    "project_delete": frozenset({"Project.Allocate"}),
    "project_open": frozenset({"Project.Allocate"}),
    "project_close": frozenset({"Project.Allocate"}),
    "project_duplicate": frozenset({"Project.Duplicate"}),
    "project_stats": frozenset({"Project.Audit"}),
    "project_readme_get": frozenset({"Project.Audit"}),
    "project_readme_update": frozenset({"Project.Modify"}),
    "project_lock": frozenset({"Project.Modify"}),
    "project_unlock": frozenset({"Project.Modify"}),
    "project_locked": frozenset({"Project.Audit"}),
    "project_privileges": frozenset({"Project.Audit"}),
    # distribution and sharing (owner-side workflows: distributing freezes the
    # source project, sharing authorizes other users on it)
    "project_distribute": frozenset({"Project.Distribute"}),
    "project_distribution_list": frozenset({"Project.Audit"}),
    "project_distribution_cancel": frozenset({"Project.Audit"}),
    "distribution_list": frozenset({"Project.Audit"}),
    "distribution_delete": frozenset({"Project.Audit"}),
    "project_share": frozenset({"Project.Share"}),
    "project_share_list": frozenset({"Project.Share"}),
    "project_share_delete": frozenset({"Project.Share"}),
    # account self-check endpoints only need an authenticated user
    "user_privileges": frozenset(),
    "user_quotas": frozenset(),
    # nodes
    "node_list": frozenset({"Node.Audit"}),
    "node_get": frozenset({"Node.Audit"}),
    "node_create": frozenset({"Node.Allocate"}),
    "node_update": frozenset({"Node.Modify"}),
    "node_delete": frozenset({"Node.Allocate"}),
    "node_start": frozenset({"Node.PowerMgmt"}),
    "node_stop": frozenset({"Node.PowerMgmt"}),
    "node_suspend": frozenset({"Node.PowerMgmt"}),
    "node_start_all": frozenset({"Node.PowerMgmt"}),
    "node_stop_all": frozenset({"Node.PowerMgmt"}),
    "node_suspend_all": frozenset({"Node.PowerMgmt"}),
    "node_duplicate": frozenset({"Node.Allocate"}),
    "node_isolate": frozenset({"Link.Modify"}),
    "node_unisolate": frozenset({"Link.Modify"}),
    "node_links": frozenset({"Link.Audit"}),
    "node_file_list": frozenset({"Node.Audit"}),
    "node_file_get": frozenset({"Node.Audit"}),
    "node_file_write": frozenset({"Node.Modify"}),
    "node_file_delete": frozenset({"Node.Modify"}),
    "node_console_exec": frozenset({"Node.Console", "Node.Audit", "Node.Modify"}),
    # links
    "link_list": frozenset({"Link.Audit"}),
    "link_get": frozenset({"Link.Audit"}),
    "link_create": frozenset({"Link.Allocate"}),
    "link_update": frozenset({"Link.Modify"}),
    "link_delete": frozenset({"Link.Allocate"}),
    "link_reset": frozenset({"Link.Modify"}),
    "link_available_filters": frozenset({"Link.Audit"}),
    "link_capture_start": frozenset({"Link.Capture"}),
    "link_capture_stop": frozenset({"Link.Capture"}),
    "link_capture_download": frozenset({"Link.Capture"}),
    "link_marker": frozenset({"Link.Marker"}),
    "marker_definition": frozenset({"Project.Marker", "Project.Audit"}),
    # snapshots
    "snapshot_list": frozenset({"Snapshot.Audit"}),
    "snapshot_create": frozenset({"Snapshot.Allocate"}),
    "snapshot_delete": frozenset({"Snapshot.Allocate"}),
    "snapshot_restore": frozenset({"Snapshot.Restore"}),
    # drawings
    "drawing_list": frozenset({"Drawing.Audit"}),
    "drawing_get": frozenset({"Drawing.Audit"}),
    "drawing_create_text": frozenset({"Drawing.Allocate"}),
    "drawing_create_rectangle": frozenset({"Drawing.Allocate"}),
    "drawing_create_ellipse": frozenset({"Drawing.Allocate"}),
    "drawing_update": frozenset({"Drawing.Modify"}),
    "drawing_delete": frozenset({"Drawing.Allocate"}),
    # templates and appliances
    "template_list": frozenset({"Template.Audit"}),
    "template_get": frozenset({"Template.Audit"}),
    "template_create": frozenset({"Template.Allocate"}),
    "template_update": frozenset({"Template.Modify", "Template.Audit"}),
    "template_delete": frozenset({"Template.Allocate", "Template.Audit"}),
    "appliance_list": frozenset({"Appliance.Audit"}),
    "appliance_get": frozenset({"Appliance.Audit"}),
    "appliance_install": frozenset({"Appliance.Allocate"}),
    # computes, images, server info
    "compute_list": frozenset({"Compute.Audit"}),
    "compute_get": frozenset({"Compute.Audit"}),
    "compute_images": frozenset(),
    "image_list": frozenset({"Image.Audit"}),
    "image_get": frozenset({"Image.Audit"}),
    "image_install": frozenset({"Image.Allocate"}),
    "image_delete": frozenset({"Image.Allocate"}),
    "image_prune": frozenset({"Image.Allocate"}),
    "server_version": frozenset(),
    "server_statistics": frozenset({"Server.Audit"}),
    # device configuration: netmiko over the console port, topology read over the API
    "device_config_send": frozenset({"Node.Audit"}),
    "device_show_run": frozenset({"Node.Audit"}),
    "vpcs_config_set": frozenset({"Node.Audit"}),
    # local skill documentation, no endpoint
    "device_skill_get": frozenset(),
    "injection_skill_get": frozenset(),
}


def tool_required_privileges(name: str) -> FrozenSet[str]:
    """Privileges required to see and call a tool (empty = open to all)."""

    return TOOL_SPECS.get(name, frozenset())


def all_tool_descriptions() -> dict[str, str]:
    """
    Description of every registered MCP tool, straight from the tool
    definitions (the docstrings of the @mcp.tool functions). Consumers that
    present tool lists to humans (e.g. the group whitelist admin UI) read
    this instead of keeping their own copy.
    """

    from . import mcp  # late import: the package owns the server instance

    return {tool.name: tool.description or "" for tool in mcp._tool_manager.list_tools()}


def tool_visible(name: str, privileges: FrozenSet[str], is_superadmin: bool) -> bool:
    """Decide visibility from a flattened, path-agnostic privilege set."""

    if is_superadmin:
        return True
    required = tool_required_privileges(name)
    return required <= privileges


def tool_allowed_for_user(
    name: str, privileges: FrozenSet[str], is_superadmin: bool, whitelist: Optional[FrozenSet[str]]
) -> bool:
    """One visibility decision shared by the gated server and the copilot.

    The group whitelist narrows the privilege rule: a tool outside every
    whitelist of the user's groups is hidden like a missing privilege.
    """

    if is_superadmin:
        return True
    if whitelist is not None and name not in whitelist:
        return False
    return tool_visible(name, privileges, is_superadmin)


async def visible_tool_names_for(username: str) -> Optional[FrozenSet[str]]:
    """Names of the MCP tools the user may see, or None when unrestricted.

    None means every tool stays available: a superadmin, or a failed
    lookup (the same fail-open rule as PrivilegeGatedMCPServer). In-process
    consumers that build their own tool list (the copilot bridge) bind only
    these names to the LLM.
    """

    resolved = await resolve_user_privileges(username)
    if resolved is None:
        return None
    privileges, is_superadmin, whitelist = resolved
    if is_superadmin:
        return None

    from . import mcp  # late import: the package owns the server instance

    return frozenset(
        tool.name
        for tool in mcp._tool_manager.list_tools()
        if tool_allowed_for_user(tool.name, privileges, is_superadmin, whitelist)
    )


async def resolve_user_privileges(username: str) -> tuple[FrozenSet[str], bool, Optional[FrozenSet[str]]] | None:
    """Flattened privilege set, superadmin flag and group whitelist for a user.

    The whitelist is the union of the MCP tool whitelists of the groups the
    user belongs to (see the /access/groups/{id}/mcp_tools endpoints); None
    means unrestricted (no group has a configured whitelist). Cached for a
    short TTL.

    Returns None when the user or the database is unavailable; callers
    should fail open (show the tool) and let the REST endpoints decide —
    visibility filtering is an experience layer, not the authority.
    """

    cached = _privilege_cache.get(username)
    now = time.monotonic()
    if cached is not None and cached[0] > now:
        return cached[1], cached[2], cached[3]

    from . import _app  # late import: the module owning the starlette app

    db_engine = getattr(_app.state, "_db_engine", None) if _app is not None else None
    if db_engine is None:
        return None

    from gns3server.db.repositories.rbac import RbacRepository
    from gns3server.db.repositories.users import UsersRepository

    try:
        async with AsyncSession(db_engine, expire_on_commit=False) as db_session:
            users_repo = UsersRepository(db_session)
            user = await users_repo.get_user_by_username(username)
            if user is None:
                return None
            if user.is_superadmin:
                result: tuple[FrozenSet[str], bool, Optional[FrozenSet[str]]] = (frozenset(), True, None)
            else:
                rbac_repo = RbacRepository(db_session)
                user_id = UUID(str(user.user_id))
                names = await rbac_repo.get_user_privileges(user_id)
                whitelist = await rbac_repo.get_user_mcp_tool_whitelist(user_id)
                result = (frozenset(names), False, frozenset(whitelist) if whitelist is not None else None)
    except Exception as e:
        log.warning("Could not resolve MCP privileges for user %s (%s); failing open", username, e)
        return None

    _privilege_cache[username] = (now + _PRIVILEGE_CACHE_TTL_S, result[0], result[1], result[2])
    return result


def _current_username() -> str | None:
    from . import _jwt_username_var

    return _jwt_username_var.get()


class PrivilegeGatedMCPServer(MCPServer):
    """An MCPServer that hides tools the current user lacks privileges for.

    The username arrives via the auth wrapper contextvar set on every
    request (including the initialize request whose context the session
    task inherits). ``list_tools`` filters; ``call_tool`` re-checks so a
    client that cached an older list cannot reach a hidden tool.
    """

    async def _user_can(self, name: str) -> bool:
        username = _current_username()
        if username is None:
            return True  # no identity to check against: fail open, endpoints decide
        resolved = await resolve_user_privileges(username)
        if resolved is None:
            return True
        privileges, is_superadmin, whitelist = resolved
        return tool_allowed_for_user(name, privileges, is_superadmin, whitelist)

    async def list_tools(self) -> list[Any]:
        tools = await super().list_tools()
        visible = []
        for tool in tools:
            if await self._user_can(tool.name):
                visible.append(tool)
            else:
                log.debug("Hiding MCP tool %s from user %s", tool.name, _current_username())
        return visible

    async def call_tool(self, name: str, arguments: dict[str, Any], context: Any = None) -> Any:
        if not await self._user_can(name):
            log.info("Denied MCP tool %s for user %s", name, _current_username())
            # Indistinguishable from an unknown tool: hidden means nonexistent.
            raise ToolError(f"Unknown tool: {name}")
        return await super().call_tool(name, arguments, context)
