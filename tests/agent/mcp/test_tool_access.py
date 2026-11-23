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
Locks the MCP tool privilege specs to the live controller routes.

The specs in gns3server/agent/mcp/tool_access.py declare, per tool, the
privileges of every endpoint it calls. This test reflects over the real
controller router, extracts each endpoint's has_privilege() requirements
and asserts the declared set covers them. It also asserts every
registered tool has a spec entry, so a new tool cannot silently ship
without a privilege declaration.
"""

import pytest

from gns3server.agent.mcp import mcp
from gns3server.agent.mcp.tool_access import TOOL_SPECS, tool_visible
from gns3server.api.routes.controller import router as controller_router

PRIVILEGE_CHECKS = (
    "has_privilege.<locals>.get_user_and_check_privilege",
    "has_privilege_on_websocket.<locals>.get_user_and_check_privilege",
)


def _dependency_privileges(route) -> set[str]:
    """Privilege names required by a route's has_privilege dependencies."""

    privs = set()
    deps = list(getattr(route, "dependencies", []))
    dependant = getattr(route, "dependant", None)
    if dependant is not None:
        deps += list(dependant.dependencies)
    for dep in deps:
        fn = getattr(dep, "dependency", None)
        if fn is not None and getattr(fn, "__qualname__", "") in PRIVILEGE_CHECKS:
            for cell in fn.__closure__ or []:
                value = cell.cell_contents
                if isinstance(value, str) and "." in value:
                    privs.add(value)
    return privs


@pytest.fixture(scope="module")
def route_privileges() -> dict[tuple[str, str], set[str]]:
    """(method, path) -> required privileges, flattened from the controller router."""

    table: dict[tuple[str, str], set[str]] = {}
    for included in controller_router.routes:
        for candidate in included.effective_candidates():
            original = candidate.original_route
            path = candidate.path
            if not path:
                # websocket candidates carry no effective path: rebuild it
                # from the include prefix and the sub-router route path
                prefix = getattr(included.include_context, "prefix", "") or ""
                path = prefix + getattr(original, "path", "")
            if not path:
                continue
            methods = getattr(original, "methods", None) or {"WS"}
            privs = _dependency_privileges(original)
            for method in methods:
                entry = table.setdefault((method, path), set())
                entry |= privs
    return table


# Every endpoint each tool calls. Kept in the test (not in the product
# module) so the spec table stays a plain privilege declaration and this
# mapping is reviewed together with the routes it references.
TOOL_ENDPOINTS: dict[str, list[tuple[str, str]]] = {
    "project_list": [("GET", "/projects")],
    "project_get": [("GET", "/projects/{project_id}")],
    "project_create": [("POST", "/projects")],
    "project_update": [("PUT", "/projects/{project_id}")],
    "project_delete": [("DELETE", "/projects/{project_id}")],
    "project_open": [("POST", "/projects/{project_id}/open")],
    "project_close": [("POST", "/projects/{project_id}/close")],
    "project_duplicate": [("POST", "/projects/{project_id}/duplicate")],
    "project_stats": [("GET", "/projects/{project_id}/stats")],
    "project_readme_get": [("GET", "/projects/{project_id}/files/{file_path:path}")],
    "project_readme_update": [("POST", "/projects/{project_id}/files/{file_path:path}")],
    "project_lock": [("POST", "/projects/{project_id}/lock")],
    "project_unlock": [("POST", "/projects/{project_id}/unlock")],
    "project_locked": [("GET", "/projects/{project_id}/locked")],
    "project_privileges": [("GET", "/projects/{project_id}/me/privileges")],
    "project_distribute": [("POST", "/projects/{project_id}/distribute")],
    "project_distribution_list": [("GET", "/projects/{project_id}/distributions")],
    "project_distribution_cancel": [("DELETE", "/projects/{project_id}/distributions/{distribution_id}")],
    "distribution_list": [("GET", "/distributions")],
    "distribution_delete": [("DELETE", "/distributions/{distribution_id}")],
    "project_share": [("POST", "/projects/{project_id}/share")],
    "project_share_list": [("GET", "/projects/{project_id}/shares")],
    "project_share_delete": [("DELETE", "/projects/{project_id}/shares/{ace_id}")],
    "node_list": [("GET", "/projects/{project_id}/nodes")],
    "node_get": [("GET", "/projects/{project_id}/nodes/{node_id}")],
    "node_create": [
        ("POST", "/projects/{project_id}/nodes"),
        ("POST", "/projects/{project_id}/templates/{template_id}"),
    ],
    "node_update": [("PUT", "/projects/{project_id}/nodes/{node_id}")],
    "node_delete": [("DELETE", "/projects/{project_id}/nodes/{node_id}")],
    "node_start": [("POST", "/projects/{project_id}/nodes/{node_id}/start")],
    "node_stop": [("POST", "/projects/{project_id}/nodes/{node_id}/stop")],
    "node_suspend": [("POST", "/projects/{project_id}/nodes/{node_id}/suspend")],
    "node_start_all": [("POST", "/projects/{project_id}/nodes/start")],
    "node_stop_all": [("POST", "/projects/{project_id}/nodes/stop")],
    "node_suspend_all": [("POST", "/projects/{project_id}/nodes/suspend")],
    "node_duplicate": [("POST", "/projects/{project_id}/nodes/{node_id}/duplicate")],
    "node_isolate": [("POST", "/projects/{project_id}/nodes/{node_id}/isolate")],
    "node_unisolate": [("POST", "/projects/{project_id}/nodes/{node_id}/unisolate")],
    "node_links": [("GET", "/projects/{project_id}/nodes/{node_id}/links")],
    "node_file_list": [("GET", "/projects/{project_id}/nodes/{node_id}/files")],
    "node_file_get": [("GET", "/projects/{project_id}/nodes/{node_id}/files/{file_path:path}")],
    "node_file_write": [("POST", "/projects/{project_id}/nodes/{node_id}/files/{file_path:path}")],
    "node_file_delete": [("DELETE", "/projects/{project_id}/nodes/{node_id}/files/{file_path:path}")],
    "node_console_exec": [
        ("WS", "/projects/{project_id}/nodes/{node_id}/console/ws"),
        ("GET", "/projects/{project_id}/nodes/{node_id}"),
        ("POST", "/projects/{project_id}/nodes/{node_id}/files/{file_path:path}"),
    ],
    "link_list": [("GET", "/projects/{project_id}/links")],
    "link_get": [("GET", "/projects/{project_id}/links/{link_id}")],
    "link_create": [("POST", "/projects/{project_id}/links")],
    "link_update": [("PUT", "/projects/{project_id}/links/{link_id}")],
    "link_delete": [("DELETE", "/projects/{project_id}/links/{link_id}")],
    "link_reset": [("POST", "/projects/{project_id}/links/{link_id}/reset")],
    "link_available_filters": [("GET", "/projects/{project_id}/links/{link_id}/available_filters")],
    "link_capture_start": [("POST", "/projects/{project_id}/links/{link_id}/capture/start")],
    "link_capture_stop": [("POST", "/projects/{project_id}/links/{link_id}/capture/stop")],
    "link_capture_download": [("GET", "/projects/{project_id}/links/{link_id}/capture/file")],
    "link_marker": [
        ("POST", "/projects/{project_id}/links/{link_id}/markers"),
        ("PUT", "/projects/{project_id}/links/{link_id}/markers/{marker_name}"),
        ("DELETE", "/projects/{project_id}/links/{link_id}/markers/{marker_name}"),
    ],
    "marker_definition": [
        ("GET", "/projects/{project_id}/marker-definitions"),
        ("POST", "/projects/{project_id}/marker-definitions"),
        ("PUT", "/projects/{project_id}/marker-definitions/{def_name}"),
        ("DELETE", "/projects/{project_id}/marker-definitions/{def_name}"),
    ],
    "snapshot_list": [("GET", "/projects/{project_id}/snapshots")],
    "snapshot_create": [("POST", "/projects/{project_id}/snapshots")],
    "snapshot_delete": [("DELETE", "/projects/{project_id}/snapshots/{snapshot_id}")],
    "snapshot_restore": [("POST", "/projects/{project_id}/snapshots/{snapshot_id}/restore")],
    "drawing_list": [("GET", "/projects/{project_id}/drawings")],
    "drawing_get": [("GET", "/projects/{project_id}/drawings/{drawing_id}")],
    "drawing_create_text": [("POST", "/projects/{project_id}/drawings")],
    "drawing_create_rectangle": [("POST", "/projects/{project_id}/drawings")],
    "drawing_create_ellipse": [("POST", "/projects/{project_id}/drawings")],
    "drawing_update": [("PUT", "/projects/{project_id}/drawings/{drawing_id}")],
    "drawing_delete": [("DELETE", "/projects/{project_id}/drawings/{drawing_id}")],
    "template_list": [("GET", "/templates")],
    "template_get": [("GET", "/templates/{template_id}"), ("GET", "/templates")],
    "template_create": [("POST", "/templates")],
    "template_update": [("PUT", "/templates/{template_id}"), ("GET", "/templates")],
    "template_delete": [("DELETE", "/templates/{template_id}"), ("GET", "/templates")],
    "appliance_list": [("GET", "/appliances")],
    "appliance_get": [("GET", "/appliances/{appliance_id}")],
    "appliance_install": [("POST", "/appliances/{appliance_id}/install")],
    "compute_list": [("GET", "/computes")],
    "compute_get": [("GET", "/computes/{compute_id}")],
    "compute_images": [("GET", "/computes/{compute_id}/{emulator}/{endpoint_path:path}")],
    "image_list": [("GET", "/images")],
    "image_get": [("GET", "/images/{image_path:path}")],
    "image_install": [("POST", "/images/install")],
    "image_delete": [("DELETE", "/images/{image_path:path}")],
    "image_prune": [("DELETE", "/images/prune")],
    "server_version": [("GET", "/version")],
    "server_statistics": [("GET", "/statistics")],
    "user_privileges": [("GET", "/access/users/me/privileges")],
    "user_quotas": [("GET", "/access/users/me/quotas")],
    # netmiko reaches the console TCP port directly (no RBAC there); the
    # topology read that resolves devices goes through the nodes endpoint
    "device_config_send": [("GET", "/projects/{project_id}/nodes")],
    "device_show_run": [("GET", "/projects/{project_id}/nodes")],
    "vpcs_config_set": [("GET", "/projects/{project_id}/nodes")],
    # local skill documentation, no endpoint
    "device_skill_get": [],
    "injection_skill_get": [],
}


def test_every_endpoint_in_tool_endpoints_exists(route_privileges) -> None:
    missing = [
        (tool, method, path)
        for tool, endpoints in TOOL_ENDPOINTS.items()
        for method, path in endpoints
        if (method, path) not in route_privileges
    ]
    assert not missing, f"TOOL_ENDPOINTS references unknown routes: {missing}"


def test_tool_specs_cover_endpoint_privileges(route_privileges) -> None:
    failures = []
    for tool, endpoints in TOOL_ENDPOINTS.items():
        declared = TOOL_SPECS.get(tool)
        if declared is None:
            failures.append(f"{tool}: no spec entry in TOOL_SPECS")
            continue
        for method, path in endpoints:
            required = route_privileges[(method, path)]
            if not required <= declared:
                failures.append(f"{tool}: spec {sorted(declared)} does not cover {method} {path} -> {sorted(required)}")
    assert not failures, "\n".join(failures)


def test_every_registered_tool_has_a_spec() -> None:
    registered = {tool.name for tool in mcp._tool_manager.list_tools()}
    without_spec = sorted(name for name in registered if name not in TOOL_SPECS)
    assert not without_spec, f"tools without a privilege spec: {without_spec}"
    dead = sorted(name for name in TOOL_SPECS if name not in registered)
    assert not dead, f"spec entries for tools that do not exist: {dead}"


def test_tool_visible_semantics() -> None:
    assert tool_visible("project_get", frozenset({"Project.Audit"}), is_superadmin=False)
    # path-agnostic: a scoped ACE grant (flattened view) is enough
    assert tool_visible("project_get", frozenset({"Project.Modify", "Project.Audit"}), is_superadmin=False)
    assert not tool_visible("project_get", frozenset({"Project.Modify"}), is_superadmin=False)
    assert tool_visible("project_get", frozenset(), is_superadmin=True)
    # tools without a requirement are always visible
    assert tool_visible("server_version", frozenset(), is_superadmin=False)


@pytest.mark.asyncio
async def test_visible_tool_names_for_a_user(monkeypatch) -> None:
    """The names the copilot may bind: privileges plus the group whitelist."""

    from gns3server.agent.mcp import tool_access

    async def fake_resolve(username):
        # Node.Audit only; the whitelist also lists node_start, which the
        # user has no privilege for
        return frozenset({"Node.Audit"}), False, frozenset({"node_list", "node_get", "node_start"})

    monkeypatch.setattr(tool_access, "resolve_user_privileges", fake_resolve)

    names = await tool_access.visible_tool_names_for("alice")
    assert names is not None
    assert "node_list" in names
    assert "node_get" in names
    assert "node_start" not in names  # no Node.PowerMgmt
    assert "project_get" not in names  # outside the group whitelist


@pytest.mark.asyncio
async def test_visible_tool_names_are_unrestricted_for_a_superadmin(monkeypatch) -> None:
    from gns3server.agent.mcp import tool_access

    async def fake_resolve(username):
        return frozenset(), True, None

    monkeypatch.setattr(tool_access, "resolve_user_privileges", fake_resolve)
    assert await tool_access.visible_tool_names_for("admin") is None

    # no resolvable identity: the callers fail open, like the gated server
    async def fake_unavailable(username):
        return None

    monkeypatch.setattr(tool_access, "resolve_user_privileges", fake_unavailable)
    assert await tool_access.visible_tool_names_for("nobody") is None


@pytest.mark.asyncio
async def test_gated_server_applies_group_whitelist(monkeypatch) -> None:
    from gns3server.agent.mcp import tool_access

    async def fake_resolve(username):
        # privileges allow project tools, whitelist only allows project_get
        return frozenset({"Project.Audit"}), False, frozenset({"project_get", "project_list"})

    monkeypatch.setattr(tool_access, "resolve_user_privileges", fake_resolve)
    monkeypatch.setattr(tool_access, "_current_username", lambda: "alice")

    names = {tool.name for tool in await mcp.list_tools()}
    assert "project_get" in names  # privileged and whitelisted
    assert "project_stats" not in names  # privileged but not whitelisted
    assert "node_list" not in names  # whitelisted out too (and no privilege anyway)

    from mcp.server.mcpserver.exceptions import ToolError

    with pytest.raises(ToolError):
        await mcp.call_tool("project_stats", {})


@pytest.mark.asyncio
async def test_gated_server_filters_list_and_call(monkeypatch) -> None:
    from gns3server.agent.mcp import tool_access

    async def fake_resolve(username):
        return frozenset({"Project.Audit"}), False, None

    monkeypatch.setattr(tool_access, "resolve_user_privileges", fake_resolve)
    monkeypatch.setattr(tool_access, "_current_username", lambda: "alice")

    server = mcp  # the real gated server with all tools registered
    listing = await server.list_tools()
    names = {tool.name for tool in listing}
    assert "project_get" in names
    assert "node_list" not in names  # needs Node.Audit
    assert "project_create" not in names  # needs Project.Allocate

    from mcp.server.mcpserver.exceptions import ToolError

    with pytest.raises(ToolError):
        await server.call_tool("node_list", {})


@pytest.mark.asyncio
async def test_gated_server_fails_open_without_identity(monkeypatch) -> None:
    from gns3server.agent.mcp import tool_access

    monkeypatch.setattr(tool_access, "_current_username", lambda: None)
    listing = await mcp.list_tools()
    names = {tool.name for tool in listing}
    assert "node_list" in names  # no identity: fail open, endpoints decide
