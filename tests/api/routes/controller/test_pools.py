#!/usr/bin/env python
#
# Copyright (C) 2023 GNS3 Technologies Inc.
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

import uuid
import pytest
import pytest_asyncio

from fastapi import FastAPI, status
from httpx import AsyncClient

from sqlalchemy.ext.asyncio import AsyncSession
from gns3server.db.repositories.pools import ResourcePoolsRepository
from gns3server.controller import Controller
from gns3server.controller.project import Project
from gns3server.schemas.controller.pools import ResourceCreate, ResourcePoolCreate

pytestmark = pytest.mark.asyncio


class TestPoolRoutes:

    async def test_resource_pool(self, app: FastAPI, client: AsyncClient) -> None:

        new_group = {"name": "pool1"}
        response = await client.post(app.url_path_for("create_resource_pool"), json=new_group)
        assert response.status_code == status.HTTP_201_CREATED

    async def test_get_resource_pool(self, app: FastAPI, client: AsyncClient, db_session: AsyncSession) -> None:

        pools_repo = ResourcePoolsRepository(db_session)
        pool_in_db = await pools_repo.get_resource_pool_by_name("pool1")
        response = await client.get(app.url_path_for("get_resource_pool", resource_pool_id=pool_in_db.resource_pool_id))
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["resource_pool_id"] == str(pool_in_db.resource_pool_id)

    async def test_list_resource_pools(self, app: FastAPI, client: AsyncClient) -> None:

        response = await client.get(app.url_path_for("get_resource_pools"))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 1

    async def test_update_resource_pool(self, app: FastAPI, client: AsyncClient, db_session: AsyncSession) -> None:

        pools_repo = ResourcePoolsRepository(db_session)
        pool_in_db = await pools_repo.get_resource_pool_by_name("pool1")

        update_pool = {"name": "pool42"}
        response = await client.put(
            app.url_path_for("update_resource_pool", resource_pool_id=pool_in_db.resource_pool_id),
            json=update_pool
        )
        assert response.status_code == status.HTTP_200_OK
        updated_pool_in_db = await pools_repo.get_resource_pool(pool_in_db.resource_pool_id)
        assert updated_pool_in_db.name == "pool42"

    async def test_resource_group(
            self,
            app: FastAPI,
            client: AsyncClient,
            db_session: AsyncSession
    ) -> None:

        pools_repo = ResourcePoolsRepository(db_session)
        pool_in_db = await pools_repo.get_resource_pool_by_name("pool42")
        response = await client.delete(app.url_path_for("delete_resource_pool", resource_pool_id=pool_in_db.resource_pool_id))
        assert response.status_code == status.HTTP_204_NO_CONTENT


class TestResourcesPoolRoutes:

    @pytest_asyncio.fixture
    async def project(self, app: FastAPI, client: AsyncClient, controller: Controller) -> Project:
        project_id = str(uuid.uuid4())
        params = {"name": "test", "project_id": project_id}
        await client.post(app.url_path_for("create_project"), json=params)
        return controller.get_project(project_id)

    async def test_add_resource_to_pool(
            self,
            app: FastAPI,
            client: AsyncClient,
            db_session: AsyncSession,
            project: Project
    ) -> None:

        pools_repo = ResourcePoolsRepository(db_session)
        new_resource_pool = ResourcePoolCreate(
            name="pool1",
        )
        pool_in_db = await pools_repo.create_resource_pool(new_resource_pool)
        response = await client.put(
            app.url_path_for(
                "add_resource_to_pool",
                resource_pool_id=pool_in_db.resource_pool_id,
                resource_id=str(project.id)
            )
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        resources = await pools_repo.get_pool_resources(pool_in_db.resource_pool_id)
        assert len(resources) == 1
        assert str(resources[0].resource_id) == project.id

    async def test_add_to_resource_already_in_resource_pool(
            self,
            app: FastAPI,
            client: AsyncClient,
            db_session: AsyncSession,
            project: Project
    ) -> None:

        pools_repo = ResourcePoolsRepository(db_session)
        pool_in_db = await pools_repo.get_resource_pool_by_name("pool1")
        resource_create = ResourceCreate(resource_id=project.id, resource_type="project")
        resource = await pools_repo.create_resource(resource_create)
        await pools_repo.add_resource_to_pool(pool_in_db.resource_pool_id, resource)

        response = await client.put(
            app.url_path_for(
                "add_resource_to_pool",
                resource_pool_id=pool_in_db.resource_pool_id,
                resource_id=str(resource.resource_id)
            )
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_get_pool_resources(
            self,
            app: FastAPI,
            client: AsyncClient,
            db_session: AsyncSession
    ) -> None:

        pools_repo = ResourcePoolsRepository(db_session)
        pool_in_db = await pools_repo.get_resource_pool_by_name("pool1")
        response = await client.get(
            app.url_path_for(
                "get_pool_resources",
                resource_pool_id=pool_in_db.resource_pool_id)
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 2

    async def test_remove_resource_from_pool(
            self,
            app: FastAPI,
            client: AsyncClient,
            db_session: AsyncSession,
            project: Project
    ) -> None:

        pools_repo = ResourcePoolsRepository(db_session)
        pool_in_db = await pools_repo.get_resource_pool_by_name("pool1")
        resource_create = ResourceCreate(resource_id=project.id, resource_type="project")
        resource = await pools_repo.create_resource(resource_create)
        await pools_repo.add_resource_to_pool(pool_in_db.resource_pool_id, resource)

        resources = await pools_repo.get_pool_resources(pool_in_db.resource_pool_id)
        assert len(resources) == 3

        response = await client.delete(
            app.url_path_for(
                "remove_resource_from_pool",
                resource_pool_id=pool_in_db.resource_pool_id,
                resource_id=str(project.id)
            ),
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        resources = await pools_repo.get_pool_resources(pool_in_db.resource_pool_id)
        assert len(resources) == 2
