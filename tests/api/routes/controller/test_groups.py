#!/usr/bin/env python
#
# Copyright (C) 2021 GNS3 Technologies Inc.
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

import pytest
import pytest_asyncio

from fastapi import FastAPI, status
from httpx import AsyncClient

from sqlalchemy.ext.asyncio import AsyncSession
from gns3server.db.repositories.users import UsersRepository
from gns3server.db.repositories.rbac import RbacRepository
from gns3server.schemas.controller.users import User
from gns3server.schemas.controller.rbac import Role
from gns3server import schemas

pytestmark = pytest.mark.asyncio


class TestGroupRoutes:

    async def test_create_group(self, app: FastAPI, client: AsyncClient) -> None:

        new_group = {"name": "group1"}
        response = await client.post(app.url_path_for("create_user_group"), json=new_group)
        assert response.status_code == status.HTTP_201_CREATED

    async def test_get_group(self, app: FastAPI, client: AsyncClient, db_session: AsyncSession) -> None:

        user_repo = UsersRepository(db_session)
        group_in_db = await user_repo.get_user_group_by_name("group1")
        response = await client.get(app.url_path_for("get_user_group", user_group_id=group_in_db.user_group_id))
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["user_group_id"] == str(group_in_db.user_group_id)

    async def test_list_groups(self, app: FastAPI, client: AsyncClient) -> None:

        response = await client.get(app.url_path_for("get_user_groups"))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 3  # 2 default groups + group1

    async def test_update_group(self, app: FastAPI, client: AsyncClient, db_session: AsyncSession) -> None:

        user_repo = UsersRepository(db_session)
        group_in_db = await user_repo.get_user_group_by_name("group1")

        update_group = {"name": "group42"}
        response = await client.put(
            app.url_path_for("update_user_group", user_group_id=group_in_db.user_group_id),
            json=update_group
        )
        assert response.status_code == status.HTTP_200_OK
        updated_group_in_db = await user_repo.get_user_group(group_in_db.user_group_id)
        assert updated_group_in_db.name == "group42"

    async def test_cannot_update_admin_group(
            self,
            app: FastAPI,
            client: AsyncClient,
            db_session: AsyncSession
    ) -> None:

        user_repo = UsersRepository(db_session)
        group_in_db = await user_repo.get_user_group_by_name("Administrators")
        update_group = {"name": "Hackers"}
        response = await client.put(
            app.url_path_for("update_user_group", user_group_id=group_in_db.user_group_id),
            json=update_group
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    async def test_delete_group(
            self,
            app: FastAPI,
            client: AsyncClient,
            db_session: AsyncSession
    ) -> None:

        user_repo = UsersRepository(db_session)
        group_in_db = await user_repo.get_user_group_by_name("group42")
        response = await client.delete(app.url_path_for("delete_user_group", user_group_id=group_in_db.user_group_id))
        assert response.status_code == status.HTTP_204_NO_CONTENT

    async def test_cannot_delete_admin_group(
            self,
            app: FastAPI,
            client: AsyncClient,
            db_session: AsyncSession
    ) -> None:

        user_repo = UsersRepository(db_session)
        group_in_db = await user_repo.get_user_group_by_name("Administrators")
        response = await client.delete(app.url_path_for("delete_user_group", user_group_id=group_in_db.user_group_id))
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestGroupMembersRoutes:

    async def test_add_member_to_group(
            self,
            app: FastAPI,
            client: AsyncClient,
            test_user: User,
            db_session: AsyncSession
    ) -> None:

        user_repo = UsersRepository(db_session)
        group_in_db = await user_repo.get_user_group_by_name("Users")
        response = await client.put(
            app.url_path_for(
                "add_member_to_group",
                user_group_id=group_in_db.user_group_id,
                user_id=str(test_user.user_id)
            )
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        members = await user_repo.get_user_group_members(group_in_db.user_group_id)
        assert len(members) == 1
        assert members[0].username == test_user.username

    async def test_get_user_group_members(
            self,
            app: FastAPI,
            client: AsyncClient,
            db_session: AsyncSession
    ) -> None:

        user_repo = UsersRepository(db_session)
        group_in_db = await user_repo.get_user_group_by_name("Users")
        response = await client.get(
            app.url_path_for(
                "get_user_group_members",
                user_group_id=group_in_db.user_group_id)
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 1

    async def test_remove_member_from_group(
            self,
            app: FastAPI,
            client: AsyncClient,
            test_user: User,
            db_session: AsyncSession
    ) -> None:

        user_repo = UsersRepository(db_session)
        group_in_db = await user_repo.get_user_group_by_name("Users")

        response = await client.delete(
            app.url_path_for(
                "remove_member_from_group",
                user_group_id=group_in_db.user_group_id,
                user_id=str(test_user.user_id)
            ),
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        members = await user_repo.get_user_group_members(group_in_db.user_group_id)
        assert len(members) == 0


@pytest_asyncio.fixture
async def test_role(db_session: AsyncSession) -> Role:

    new_role = schemas.RoleCreate(
        name="TestRole",
        description="This is my test role"
    )
    rbac_repo = RbacRepository(db_session)
    existing_role = await rbac_repo.get_role_by_name(new_role.name)
    if existing_role:
        return existing_role
    return await rbac_repo.create_role(new_role)


class TestGroupRolesRoutes:

    async def test_add_role_to_group(
            self,
            app: FastAPI,
            client: AsyncClient,
            test_role: Role,
            db_session: AsyncSession
    ) -> None:

        user_repo = UsersRepository(db_session)
        group_in_db = await user_repo.get_user_group_by_name("Users")
        response = await client.put(
            app.url_path_for(
                "add_role_to_group",
                user_group_id=group_in_db.user_group_id,
                role_id=str(test_role.role_id)
            )
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        roles = await user_repo.get_user_group_roles(group_in_db.user_group_id)
        assert len(roles) == 2  # 1 default role + 1 custom role
        for role in roles:
            if not role.is_builtin:
                assert role.name == test_role.name

    async def test_get_user_group_roles(
            self,
            app: FastAPI,
            client: AsyncClient,
            db_session: AsyncSession
    ) -> None:

        user_repo = UsersRepository(db_session)
        group_in_db = await user_repo.get_user_group_by_name("Users")
        response = await client.get(
            app.url_path_for(
                "get_user_group_roles",
                user_group_id=group_in_db.user_group_id)
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 2  # 1 default role + 1 custom role

    async def test_remove_role_from_group(
            self,
            app: FastAPI,
            client: AsyncClient,
            test_role: Role,
            db_session: AsyncSession
    ) -> None:

        user_repo = UsersRepository(db_session)
        group_in_db = await user_repo.get_user_group_by_name("Users")

        response = await client.delete(
            app.url_path_for(
                "remove_role_from_group",
                user_group_id=group_in_db.user_group_id,
                role_id=test_role.role_id
            ),
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        roles = await user_repo.get_user_group_roles(group_in_db.user_group_id)
        assert len(roles) == 1  # 1 default role
        assert roles[0].name != test_role.name
