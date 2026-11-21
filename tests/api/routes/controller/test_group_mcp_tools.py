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
#

"""
Tests for the per-group MCP tool whitelist endpoints and the snapshot
semantics behind them.
"""

import pytest
from fastapi import FastAPI, status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from gns3server.agent.mcp.tool_access import TOOL_SPECS
from gns3server.db.repositories.rbac import RbacRepository
from gns3server.db.repositories.users import UsersRepository
from gns3server.schemas.controller.users import User, UserGroupCreate

pytestmark = pytest.mark.asyncio


async def _get_group_id(db_session: AsyncSession, name: str) -> str:
    group = await UsersRepository(db_session).get_user_group_by_name(name)
    assert group is not None, f"group '{name}' not found"
    return str(group.user_group_id)


class TestGroupMCPToolsRoutes:
    async def test_get_unconfigured_group(self, app: FastAPI, client: AsyncClient, db_session: AsyncSession) -> None:

        group_id = await _get_group_id(db_session, "Users")
        response = await client.get(app.url_path_for("get_group_mcp_tools", user_group_id=group_id))
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        # unconfigured: no whitelist, privilege gating alone decides
        assert body["tools"] is None
        # candidates: tools with no privilege requirement are always there
        assert "server_version" in body["candidates"]
        # and candidates are a subset of every known tool
        assert set(body["candidates"]) <= set(TOOL_SPECS)
        # every candidate carries the description from the tool definition
        assert set(body["descriptions"]) == set(body["candidates"])
        assert body["descriptions"]["server_version"]

    async def test_bypass_when_no_regular_member(
        self, app: FastAPI, client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        """
        A group without a single non-superadmin member cannot be affected by
        a whitelist: bypass is True for an empty group and for a group whose
        members are all superadmins, and flips back when a regular user joins.
        """

        users_repo = UsersRepository(db_session)
        group = await users_repo.create_user_group(UserGroupCreate(name="mcp_bypass_group"))

        async def get_bypass() -> bool:
            response = await client.get(app.url_path_for("get_group_mcp_tools", user_group_id=str(group.user_group_id)))
            assert response.status_code == status.HTTP_200_OK
            return response.json()["bypass"]

        assert await get_bypass() is True  # empty group

        admin = await users_repo.get_user_by_username("admin")
        await users_repo.add_member_to_user_group(group.user_group_id, admin)
        assert await get_bypass() is True  # superadmin-only group

        await users_repo.add_member_to_user_group(group.user_group_id, test_user)
        assert await get_bypass() is False  # a regular member joined

    async def test_put_rejects_tool_outside_candidates(
        self, app: FastAPI, client: AsyncClient, db_session: AsyncSession
    ) -> None:

        group_id = await _get_group_id(db_session, "Users")
        response = await client.put(
            app.url_path_for("update_group_mcp_tools", user_group_id=group_id),
            json={"tools": ["server_version", "compute_create_nonsense"]},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_put_and_get_roundtrip(self, app: FastAPI, client: AsyncClient, db_session: AsyncSession) -> None:

        group_id = await _get_group_id(db_session, "Users")
        response = await client.put(
            app.url_path_for("update_group_mcp_tools", user_group_id=group_id),
            json={"tools": ["server_version"]},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["tools"] == ["server_version"]

        response = await client.get(app.url_path_for("get_group_mcp_tools", user_group_id=group_id))
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["tools"] == ["server_version"]

    async def test_delete_lifts_the_whitelist(
        self, app: FastAPI, client: AsyncClient, db_session: AsyncSession
    ) -> None:

        group_id = await _get_group_id(db_session, "Users")
        response = await client.delete(app.url_path_for("delete_group_mcp_tools", user_group_id=group_id))
        assert response.status_code == status.HTTP_204_NO_CONTENT

        response = await client.get(app.url_path_for("get_group_mcp_tools", user_group_id=group_id))
        assert response.json()["tools"] is None

    async def test_put_empty_list_hides_everything(
        self, app: FastAPI, client: AsyncClient, db_session: AsyncSession
    ) -> None:

        group_id = await _get_group_id(db_session, "Users")
        response = await client.put(
            app.url_path_for("update_group_mcp_tools", user_group_id=group_id), json={"tools": []}
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["tools"] == []

        rbac_repo = RbacRepository(db_session)
        assert await rbac_repo.get_group_mcp_tools(await _group_uuid(db_session, "Users")) == set()

        # restore the unconfigured state for the other tests
        response = await client.delete(app.url_path_for("delete_group_mcp_tools", user_group_id=group_id))
        assert response.status_code == status.HTTP_204_NO_CONTENT


async def _group_uuid(db_session: AsyncSession, name: str):
    group = await UsersRepository(db_session).get_user_group_by_name(name)
    return group.user_group_id


class TestUserWhitelistSemantics:
    """
    Snapshot-level semantics of the effective user whitelist.
    """

    async def test_whitelist_reaches_group_members(self, db_session: AsyncSession, test_user: User) -> None:

        rbac_repo = RbacRepository(db_session)
        users_group_id = await _group_uuid(db_session, "Users")

        # unconfigured: unrestricted
        assert await rbac_repo.get_user_mcp_tool_whitelist(test_user.user_id) is None

        await rbac_repo.set_group_mcp_tools(users_group_id, ["project_get", "server_version"])
        whitelist = await rbac_repo.get_user_mcp_tool_whitelist(test_user.user_id)
        assert whitelist == {"project_get", "server_version"}

        await rbac_repo.clear_group_mcp_tools(users_group_id)
        assert await rbac_repo.get_user_mcp_tool_whitelist(test_user.user_id) is None

    async def test_unconfigured_group_lifts_restriction(self, db_session: AsyncSession, test_user: User) -> None:
        """
        The whitelists union only applies when every group of the user is
        configured: one unconfigured group means no restriction.
        """

        users_repo = UsersRepository(db_session)
        rbac_repo = RbacRepository(db_session)

        users_group_id = await _group_uuid(db_session, "Users")
        other_group = await users_repo.create_user_group(UserGroupCreate(name="mcp_extra_group"))
        await users_repo.add_member_to_user_group(other_group.user_group_id, test_user)

        await rbac_repo.set_group_mcp_tools(users_group_id, ["server_version"])
        # the second group has no whitelist: still unrestricted
        assert await rbac_repo.get_user_mcp_tool_whitelist(test_user.user_id) is None

        await rbac_repo.set_group_mcp_tools(other_group.user_group_id, ["project_list"])
        # both configured now: union of both sets
        whitelist = await rbac_repo.get_user_mcp_tool_whitelist(test_user.user_id)
        assert whitelist == {"server_version", "project_list"}
