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

import pytest
import pytest_asyncio
import uuid

from fastapi import FastAPI, status
from httpx import AsyncClient

from sqlalchemy.ext.asyncio import AsyncSession
from gns3server.db.repositories.users import UsersRepository
from gns3server.db.repositories.rbac import RbacRepository
from gns3server.controller import Controller
from gns3server.controller.project import Project
from gns3server.schemas.controller.users import User
from gns3server.schemas.controller.rbac import ACECreate

pytestmark = pytest.mark.asyncio


class TestACLRoutes:

    # @pytest_asyncio.fixture
    # async def project(
    #         self,
    #         app: FastAPI,
    #         authorized_client: AsyncClient,
    #         test_user: User,
    #         db_session: AsyncSession,
    #         controller: Controller
    # ) -> Project:
    #
    #     # add an ACE to allow user to create a project
    #     user_id = test_user.user_id
    #     rbac_repo = RbacRepository(db_session)
    #     role_in_db = await rbac_repo.get_role_by_name("User")
    #     role_id = role_in_db.role_id
    #     ace = ACECreate(
    #         path="/projects",
    #         type="user",
    #         user_id=user_id,
    #         role_id=role_id
    #     )
    #     await rbac_repo.create_ace(ace)
    #     project_uuid = str(uuid.uuid4())
    #     params = {"name": "test", "project_id": project_uuid}
    #     response = await authorized_client.post(app.url_path_for("create_project"), json=params)
    #     assert response.status_code == status.HTTP_201_CREATED
    #     return controller.get_project(project_uuid)

    #@pytest_asyncio.fixture
    # async def project(
    #         self,
    #         app: FastAPI,
    #         client: AsyncClient,
    #         controller: Controller
    # ) -> Project:
    #
    #     project_uuid = str(uuid.uuid4())
    #     params = {"name": "test", "project_id": project_uuid}
    #     response = await client.post(app.url_path_for("create_project"), json=params)
    #     assert response.status_code == status.HTTP_201_CREATED
    #     return controller.get_project(project_uuid)

    @pytest_asyncio.fixture
    async def group_id(self, db_session: AsyncSession) -> str:

        users_repo = UsersRepository(db_session)
        group_in_db = await users_repo.get_user_group_by_name("Users")
        group_id = str(group_in_db.user_group_id)
        return group_id

    @pytest_asyncio.fixture
    async def role_id(self, db_session: AsyncSession) -> str:

        rbac_repo = RbacRepository(db_session)
        role_in_db = await rbac_repo.get_role_by_name("User")
        role_id = str(role_in_db.role_id)
        return role_id

    async def test_create_ace(
            self,
            app: FastAPI,
            authorized_client: AsyncClient,
            db_session: AsyncSession,
            test_user: User,
            role_id: str
    ) -> None:

        # add an ACE on /projects to allow user to create a project
        path = f"/projects"
        new_ace = {
            "path": path,
            "type": "user",
            "user_id": str(test_user.user_id),
            "role_id": role_id
        }

        response = await authorized_client.post(app.url_path_for("create_ace"), json=new_ace)
        assert response.status_code == status.HTTP_201_CREATED

        rbac_repo = RbacRepository(db_session)
        assert await rbac_repo.check_user_has_privilege(test_user.user_id, path, "Project.Allocate") is True

        response = await authorized_client.post(app.url_path_for("create_project"), json={"name": "test"})
        assert response.status_code == status.HTTP_201_CREATED

    async def test_create_ace_not_existing_endpoint(
            self,
            app: FastAPI,
            client: AsyncClient,
            group_id: str,
            role_id: str
    ) -> None:

        new_ace = {
            "path": "/projects/invalid",
            "type": "group",
            "group_id": group_id,
            "role_id": role_id
        }
        response = await client.post(app.url_path_for("create_ace"), json=new_ace)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    # async def test_create_ace_not_existing_resource(
    #         self,
    #         app: FastAPI,
    #         client: AsyncClient,
    #         group_id: str,
    #         role_id: str
    # ) -> None:
    #
    #     new_ace = {
    #         "path": f"/projects/{str(uuid.uuid4())}",
    #         "group_id": group_id,
    #         "role_id": role_id
    #     }
    #     response = await client.post(app.url_path_for("create_ace"), json=new_ace)
    #     assert response.status_code == status.HTTP_403_FORBIDDEN

    async def test_get_ace(self, app: FastAPI, client: AsyncClient, db_session: AsyncSession) -> None:

        rbac_repo = RbacRepository(db_session)
        ace_in_db = await rbac_repo.get_ace_by_path(f"/projects")
        response = await client.get(app.url_path_for("get_ace", ace_id=ace_in_db.ace_id))
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["ace_id"] == str(ace_in_db.ace_id)

    async def test_list_aces(self, app: FastAPI, client: AsyncClient) -> None:

        response = await client.get(app.url_path_for("get_aces"))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 1

    async def test_update_ace(
            self, app: FastAPI,
            client: AsyncClient,
            db_session: AsyncSession,
            test_user: User,
            role_id: str
    ) -> None:

        rbac_repo = RbacRepository(db_session)
        ace_in_db = await rbac_repo.get_ace_by_path(f"/projects")

        update_ace = {
            "path": f"/appliances",
            "type": "user",
            "user_id": str(test_user.user_id),
            "role_id": role_id
        }
        response = await client.put(
            app.url_path_for("update_ace", ace_id=ace_in_db.ace_id),
            json=update_ace
        )
        assert response.status_code == status.HTTP_200_OK
        updated_ace_in_db = await rbac_repo.get_ace(ace_in_db.ace_id)
        assert updated_ace_in_db.path == f"/appliances"

    async def test_delete_ace(
            self,
            app: FastAPI,
            client: AsyncClient,
            db_session: AsyncSession,
    ) -> None:

        rbac_repo = RbacRepository(db_session)
        ace_in_db = await rbac_repo.get_ace_by_path(f"/appliances")
        response = await client.delete(app.url_path_for("delete_ace", ace_id=ace_in_db.ace_id))
        assert response.status_code == status.HTTP_204_NO_CONTENT

    # async def test_prune_permissions(self, app: FastAPI, client: AsyncClient, db_session: AsyncSession) -> None:
    #
    #     response = await client.post(app.url_path_for("prune_permissions"))
    #     assert response.status_code == status.HTTP_204_NO_CONTENT
    #
    #     rbac_repo = RbacRepository(db_session)
    #     permissions_in_db = await rbac_repo.get_permissions()
    #     assert len(permissions_in_db) == 10  # 6 default permissions + 4 custom permissions
