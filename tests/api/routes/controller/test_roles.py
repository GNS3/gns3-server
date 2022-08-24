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
from gns3server.db.repositories.rbac import RbacRepository
from gns3server.schemas.controller.rbac import Permission, HTTPMethods, PermissionAction
from gns3server import schemas

pytestmark = pytest.mark.asyncio


class TestRolesRoutes:

    async def test_create_role(self, app: FastAPI, client: AsyncClient) -> None:

        new_role = {"name": "role1"}
        response = await client.post(app.url_path_for("create_role"), json=new_role)
        assert response.status_code == status.HTTP_201_CREATED

    async def test_get_role(self, app: FastAPI, client: AsyncClient, db_session: AsyncSession) -> None:

        rbac_repo = RbacRepository(db_session)
        role_in_db = await rbac_repo.get_role_by_name("role1")
        response = await client.get(app.url_path_for("get_role", role_id=role_in_db.role_id))
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["role_id"] == str(role_in_db.role_id)

    async def test_list_roles(self, app: FastAPI, client: AsyncClient) -> None:

        response = await client.get(app.url_path_for("get_roles"))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 3  # 2 default roles + role1

    async def test_update_role(self, app: FastAPI, client: AsyncClient, db_session: AsyncSession) -> None:

        rbac_repo = RbacRepository(db_session)
        role_in_db = await rbac_repo.get_role_by_name("role1")

        update_role = {"name": "role42"}
        response = await client.put(
            app.url_path_for("update_role", role_id=role_in_db.role_id),
            json=update_role
        )
        assert response.status_code == status.HTTP_200_OK
        updated_role_in_db = await rbac_repo.get_role(role_in_db.role_id)
        assert updated_role_in_db.name == "role42"

    async def test_cannot_update_builtin_user_role(
            self,
            app: FastAPI,
            client: AsyncClient,
            db_session: AsyncSession
    ) -> None:

        rbac_repo = RbacRepository(db_session)
        role_in_db = await rbac_repo.get_role_by_name("User")
        update_role = {"name": "Hackers"}
        response = await client.put(
            app.url_path_for("update_role", role_id=role_in_db.role_id),
            json=update_role
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    async def test_delete_role(
            self,
            app: FastAPI,
            client: AsyncClient,
            db_session: AsyncSession
    ) -> None:

        rbac_repo = RbacRepository(db_session)
        role_in_db = await rbac_repo.get_role_by_name("role42")
        response = await client.delete(app.url_path_for("delete_role", role_id=role_in_db.role_id))
        assert response.status_code == status.HTTP_204_NO_CONTENT

    async def test_cannot_delete_builtin_administrator_role(
            self,
            app: FastAPI,
            client: AsyncClient,
            db_session: AsyncSession
    ) -> None:

        rbac_repo = RbacRepository(db_session)
        role_in_db = await rbac_repo.get_role_by_name("Administrator")
        response = await client.delete(app.url_path_for("delete_role", role_id=role_in_db.role_id))
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest_asyncio.fixture
async def test_permission(db_session: AsyncSession) -> Permission:

    new_permission = schemas.PermissionCreate(
        methods=[HTTPMethods.get],
        path="/statistics",
        action=PermissionAction.allow
    )
    rbac_repo = RbacRepository(db_session)
    existing_permission = await rbac_repo.get_permission_by_path("/statistics")
    if existing_permission:
        return existing_permission
    return await rbac_repo.create_permission(new_permission)


class TestRolesPermissionsRoutes:

    async def test_add_permission_to_role(
            self,
            app: FastAPI,
            client: AsyncClient,
            test_permission: Permission,
            db_session: AsyncSession
    ) -> None:

        rbac_repo = RbacRepository(db_session)
        role_in_db = await rbac_repo.get_role_by_name("User")

        response = await client.put(
            app.url_path_for(
                "add_permission_to_role",
                role_id=role_in_db.role_id,
                permission_id=str(test_permission.permission_id)
            )
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        permissions = await rbac_repo.get_role_permissions(role_in_db.role_id)
        assert len(permissions) == 6  # 5 default permissions + 1 custom permission

    async def test_get_role_permissions(
            self,
            app: FastAPI,
            client: AsyncClient,
            db_session: AsyncSession
    ) -> None:

        rbac_repo = RbacRepository(db_session)
        role_in_db = await rbac_repo.get_role_by_name("User")

        response = await client.get(
            app.url_path_for(
                "get_role_permissions",
                role_id=role_in_db.role_id)
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 6  # 5 default permissions + 1 custom permission

    async def test_remove_role_from_group(
            self,
            app: FastAPI,
            client: AsyncClient,
            test_permission: Permission,
            db_session: AsyncSession
    ) -> None:

        rbac_repo = RbacRepository(db_session)
        role_in_db = await rbac_repo.get_role_by_name("User")

        response = await client.delete(
            app.url_path_for(
                "remove_permission_from_role",
                role_id=role_in_db.role_id,
                permission_id=str(test_permission.permission_id)
            ),
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        permissions = await rbac_repo.get_role_permissions(role_in_db.role_id)
        assert len(permissions) == 5  # 5 default permissions
