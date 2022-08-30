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
import uuid

from fastapi import FastAPI, status
from httpx import AsyncClient

from sqlalchemy.ext.asyncio import AsyncSession
from gns3server.db.repositories.rbac import RbacRepository
from gns3server.controller import Controller
from gns3server.controller.project import Project

pytestmark = pytest.mark.asyncio


class TestPermissionRoutes:

    @pytest_asyncio.fixture
    async def project(self, app: FastAPI, client: AsyncClient, controller: Controller) -> Project:

        project_uuid = str(uuid.uuid4())
        params = {"name": "test", "project_id": project_uuid}
        await client.post(app.url_path_for("create_project"), json=params)
        return controller.get_project(project_uuid)

    async def test_create_permission(self, app: FastAPI, client: AsyncClient, project: Project) -> None:

        new_permission = {
            "methods": ["GET"],
            "path": f"/projects/{project.id}",
            "action": "ALLOW"
        }
        response = await client.post(app.url_path_for("create_permission"), json=new_permission)
        assert response.status_code == status.HTTP_201_CREATED

    async def test_create_wildcard_permission(self, app: FastAPI, client: AsyncClient, project: Project) -> None:

        new_permission = {
            "methods": ["POST"],
            "path": f"/projects/{project.id}/*",
            "action": "ALLOW"
        }

        response = await client.post(app.url_path_for("create_permission"), json=new_permission)
        assert response.status_code == status.HTTP_201_CREATED

    async def test_create_permission_not_existing_endpoint(self, app: FastAPI, client: AsyncClient) -> None:

        new_permission = {
            "methods": ["GET"],
            "path": "/projects/invalid",
            "action": "ALLOW"
        }
        response = await client.post(app.url_path_for("create_permission"), json=new_permission)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_create_permission_not_existing_object(self, app: FastAPI, client: AsyncClient) -> None:

        new_permission = {
            "methods": ["GET"],
            "path": f"/projects/{str(uuid.uuid4())}/*",
            "action": "ALLOW"
        }
        response = await client.post(app.url_path_for("create_permission"), json=new_permission)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    async def test_get_permission(self, app: FastAPI, client: AsyncClient, db_session: AsyncSession, project: Project) -> None:

        rbac_repo = RbacRepository(db_session)
        permission_in_db = await rbac_repo.get_permission_by_path(f"/projects/{project.id}/*")
        response = await client.get(app.url_path_for("get_permission", permission_id=permission_in_db.permission_id))
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["permission_id"] == str(permission_in_db.permission_id)

    async def test_list_permissions(self, app: FastAPI, client: AsyncClient) -> None:

        response = await client.get(app.url_path_for("get_permissions"))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 11  # 6 default permissions + 5 custom permissions

    async def test_update_permission(self, app: FastAPI, client: AsyncClient, db_session: AsyncSession, project: Project) -> None:

        rbac_repo = RbacRepository(db_session)
        permission_in_db = await rbac_repo.get_permission_by_path(f"/projects/{project.id}/*")

        update_permission = {
            "methods": ["GET"],
            "path": f"/projects/{project.id}/*",
            "action": "ALLOW"
        }
        response = await client.put(
            app.url_path_for("update_permission", permission_id=permission_in_db.permission_id),
            json=update_permission
        )
        assert response.status_code == status.HTTP_200_OK
        updated_permission_in_db = await rbac_repo.get_permission(permission_in_db.permission_id)
        assert updated_permission_in_db.path == f"/projects/{project.id}/*"

    async def test_delete_permission(
            self,
            app: FastAPI,
            client: AsyncClient,
            db_session: AsyncSession,
            project: Project,
    ) -> None:

        rbac_repo = RbacRepository(db_session)
        permission_in_db = await rbac_repo.get_permission_by_path(f"/projects/{project.id}/*")
        response = await client.delete(app.url_path_for("delete_permission", permission_id=permission_in_db.permission_id))
        assert response.status_code == status.HTTP_204_NO_CONTENT

    async def test_prune_permissions(self, app: FastAPI, client: AsyncClient, db_session: AsyncSession) -> None:

        response = await client.post(app.url_path_for("prune_permissions"))
        assert response.status_code == status.HTTP_204_NO_CONTENT

        rbac_repo = RbacRepository(db_session)
        permissions_in_db = await rbac_repo.get_permissions()
        assert len(permissions_in_db) == 10  # 6 default permissions + 4 custom permissions
