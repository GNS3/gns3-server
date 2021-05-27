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

from fastapi import FastAPI, status
from httpx import AsyncClient

from sqlalchemy.ext.asyncio import AsyncSession
from gns3server.db.repositories.rbac import RbacRepository

pytestmark = pytest.mark.asyncio


class TestPermissionRoutes:

    async def test_create_permission(self, app: FastAPI, client: AsyncClient) -> None:

        new_permission = {
            "methods": ["GET"],
            "path": "/templates",
            "action": "ALLOW"
        }
        response = await client.post(app.url_path_for("create_permission"), json=new_permission)
        assert response.status_code == status.HTTP_201_CREATED

    async def test_get_permission(self, app: FastAPI, client: AsyncClient, db_session: AsyncSession) -> None:

        rbac_repo = RbacRepository(db_session)
        permission_in_db = await rbac_repo.get_permission_by_path("/templates")
        response = await client.get(app.url_path_for("get_permission", permission_id=permission_in_db.permission_id))
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["permission_id"] == str(permission_in_db.permission_id)

    async def test_list_permissions(self, app: FastAPI, client: AsyncClient) -> None:

        response = await client.get(app.url_path_for("get_permissions"))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 5  # 4 default permissions + 1 custom permission

    async def test_update_permission(self, app: FastAPI, client: AsyncClient, db_session: AsyncSession) -> None:

        rbac_repo = RbacRepository(db_session)
        permission_in_db = await rbac_repo.get_permission_by_path("/templates")

        update_permission = {
            "methods": ["GET"],
            "path": "/appliances",
            "action": "ALLOW"
        }
        response = await client.put(
            app.url_path_for("update_permission", permission_id=permission_in_db.permission_id),
            json=update_permission
        )
        assert response.status_code == status.HTTP_200_OK
        updated_permission_in_db = await rbac_repo.get_permission(permission_in_db.permission_id)
        assert updated_permission_in_db.path == "/appliances"

    async def test_delete_permission(
            self,
            app: FastAPI,
            client: AsyncClient,
            db_session: AsyncSession
    ) -> None:

        rbac_repo = RbacRepository(db_session)
        permission_in_db = await rbac_repo.get_permission_by_path("/appliances")
        response = await client.delete(app.url_path_for("delete_permission", permission_id=permission_in_db.permission_id))
        assert response.status_code == status.HTTP_204_NO_CONTENT
