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
from gns3server.controller import Controller
from gns3server.db.repositories.rbac import RbacRepository
from gns3server.db.repositories.users import UsersRepository
from gns3server.db.repositories.pools import ResourcePoolsRepository
from gns3server.schemas.controller.rbac import ACECreate
from gns3server.schemas.controller.pools import ResourceCreate, ResourcePoolCreate
from gns3server.db.models import User

pytestmark = pytest.mark.asyncio

# @pytest_asyncio.fixture
# async def project_ace(db_session: AsyncSession):
#
#     group_id = (await UsersRepository(db_session).get_user_group_by_name("Users")).user_group_id
#     role_id = (await RbacRepository(db_session).get_role_by_name("User")).role_id
#     ace = ACECreate(
#         path="/projects",
#         ace_type="group",
#         propagate=False,
#         group_id=str(group_id),
#         role_id=str(role_id)
#     )
#     await RbacRepository(db_session).create_ace(ace)


class TestPrivileges:

    @pytest.mark.parametrize(
        "privilege, path, result",
        (
            ("User.Allocate", "/users", False),
            ("Project.Allocate", "/projects", False),
            ("Project.Allocate", "/projects", True),
            ("Project.Audit", "/projects/e451ad73-2519-4f83-87fe-a8e821792d44", True),
            ("Project.Audit", "/templates", False),
            ("Template.Audit", "/templates", True),
            ("Template.Allocate", "/templates", False),
            ("Compute.Audit", "/computes", True),
            ("Compute.Audit", "/computes/local", True),
            ("Symbol.Audit", "/symbols", True),
            ("Symbol.Audit", "/symbols/default_symbols", True),
        ),
    )
    async def test_default_privileges_user_group(
            self,
            test_user: User,
            db_session: AsyncSession,
            privilege: str,
            path: str,
            result: bool
    ) -> None:

        # add an ACE for path
        if result:
            group_id = (await UsersRepository(db_session).get_user_group_by_name("Users")).user_group_id
            role_id = (await RbacRepository(db_session).get_role_by_name("User")).role_id
            ace = ACECreate(
                path=path,
                ace_type="group",
                propagate=False,
                group_id=str(group_id),
                role_id=str(role_id)
            )
            await RbacRepository(db_session).create_ace(ace)

        authorized = await RbacRepository(db_session).check_user_has_privilege(test_user.user_id, path, privilege)
        assert authorized == result

    async def test_propagate(self, test_user: User, db_session: AsyncSession):

        privilege = "Project.Audit"
        path = "/projects/44929147-47bb-460a-90ae-c782c4dbb6ef"
        authorized = await RbacRepository(db_session).check_user_has_privilege(test_user.user_id, path, privilege)
        assert authorized is False

        ace = await RbacRepository(db_session).get_ace_by_path("/projects")
        ace.propagate = True
        await db_session.commit()

        authorized = await RbacRepository(db_session).check_user_has_privilege(test_user.user_id, path, privilege)
        assert authorized is True

    async def test_allowed(self, test_user: User, db_session: AsyncSession):

        ace = await RbacRepository(db_session).get_ace_by_path("/projects")
        ace.allowed = False
        ace.propagate = True
        await db_session.commit()

        privilege = "Project.Audit"
        path = "/projects/44929147-47bb-460a-90ae-c782c4dbb6ef"
        authorized = await RbacRepository(db_session).check_user_has_privilege(test_user.user_id, path, privilege)
        assert authorized is False

        # privileges on deeper levels replace those inherited from an upper level.
        group_id = (await UsersRepository(db_session).get_user_group_by_name("Users")).user_group_id
        role_id = (await RbacRepository(db_session).get_role_by_name("User")).role_id
        ace = ACECreate(
            path=path,
            ace_type="group",
            propagate=False,
            group_id=str(group_id),
            role_id=str(role_id)
        )
        await RbacRepository(db_session).create_ace(ace)

        authorized = await RbacRepository(db_session).check_user_has_privilege(test_user.user_id, path, privilege)
        assert authorized is True


class TestResourcePools:

    async def test_resource_pool(self, test_user: User, db_session: AsyncSession):

        project_id = uuid.uuid4()
        project_name = "project42"

        pools_repo = ResourcePoolsRepository(db_session)
        new_resource_pool = ResourcePoolCreate(name="pool1")
        pool_in_db = await pools_repo.create_resource_pool(new_resource_pool)

        resource_create = ResourceCreate(resource_id=project_id, resource_type="project", name=project_name)
        resource = await pools_repo.create_resource(resource_create)
        await pools_repo.add_resource_to_pool(pool_in_db.resource_pool_id, resource)

        group_id = (await UsersRepository(db_session).get_user_group_by_name("Users")).user_group_id
        role_id = (await RbacRepository(db_session).get_role_by_name("User")).role_id
        ace = ACECreate(
            path=f"/pools/{pool_in_db.resource_pool_id}",
            ace_type="group",
            propagate=False,
            group_id=str(group_id),
            role_id=str(role_id)
        )
        await RbacRepository(db_session).create_ace(ace)

        privilege = "Project.Audit"
        path = f"/projects/{project_id}"
        authorized = await RbacRepository(db_session).check_user_has_privilege(test_user.user_id, path, privilege)
        assert authorized is True

    async def test_list_projects_in_resource_pool(
            self,
            app: FastAPI,
            controller: Controller,
            authorized_client: AsyncClient,
            db_session: AsyncSession
    ) -> None:

        uuid1 = str(uuid.uuid4())
        uuid2 = str(uuid.uuid4())
        uuid3 = str(uuid.uuid4())
        await controller.add_project(project_id=uuid1, name="Project1")
        await controller.add_project(project_id=uuid2, name="Project2")
        await controller.add_project(project_id=uuid3, name="Project3")

        # user has no access to projects (no ACE on /projects or resource pools)
        response = await authorized_client.get(app.url_path_for("get_projects"))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 0

        pools_repo = ResourcePoolsRepository(db_session)
        new_resource_pool = ResourcePoolCreate(name="pool2")
        pool_in_db = await pools_repo.create_resource_pool(new_resource_pool)

        resource_create = ResourceCreate(resource_id=uuid2, resource_type="project", name="Project2")
        resource = await pools_repo.create_resource(resource_create)
        await pools_repo.add_resource_to_pool(pool_in_db.resource_pool_id, resource)

        group_id = (await UsersRepository(db_session).get_user_group_by_name("Users")).user_group_id
        role_id = (await RbacRepository(db_session).get_role_by_name("User")).role_id
        ace = ACECreate(
            path=f"/pools/{pool_in_db.resource_pool_id}",
            ace_type="group",
            propagate=False,
            group_id=str(group_id),
            role_id=str(role_id)
        )
        await RbacRepository(db_session).create_ace(ace)

        response = await authorized_client.get(app.url_path_for("get_project", project_id=uuid2))
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["name"] == "Project2"

        # user should only see one project because it is in the resource pool he has access to
        response = await authorized_client.get(app.url_path_for("get_projects"))
        assert response.status_code == status.HTTP_200_OK
        projects = response.json()
        assert len(projects) == 1
        assert projects[0]["project_id"] == uuid2

        ace = ACECreate(
            path=f"/projects",
            ace_type="group",
            propagate=True,
            group_id=str(group_id),
            role_id=str(role_id)
        )
        await RbacRepository(db_session).create_ace(ace)

        # now user should see all projects because he has access to /projects and the resource pool
        response = await authorized_client.get(app.url_path_for("get_projects"))
        assert response.status_code == status.HTTP_200_OK
        projects = response.json()
        assert len(projects) == 3

        await RbacRepository(db_session).delete_all_ace_starting_with_path(f"/pools/{pool_in_db.resource_pool_id}")
        response = await authorized_client.get(app.url_path_for("get_project", project_id=uuid2))
        assert response.status_code == status.HTTP_403_FORBIDDEN

        # now user should only see the projects that are not in a resource pool
        response = await authorized_client.get(app.url_path_for("get_projects"))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 2


# class TestProjectsWithRbac:
#
#     async def test_admin_create_project(self, app: FastAPI, client: AsyncClient):
#
#         params = {"name": "Admin project"}
#         response = await client.post(app.url_path_for("create_project"), json=params)
#         assert response.status_code == status.HTTP_201_CREATED
#
#     async def test_user_only_access_own_projects(
#             self,
#             app: FastAPI,
#             authorized_client: AsyncClient,
#             project_ace,
#             test_user: User,
#             db_session: AsyncSession
#     ) -> None:
#
#         params = {"name": "User project"}
#         response = await authorized_client.post(app.url_path_for("create_project"), json=params)
#         assert response.status_code == status.HTTP_201_CREATED
#         project_id = response.json()["project_id"]
#
#         rbac_repo = RbacRepository(db_session)
#         permissions_in_db = await rbac_repo.get_user_permissions(test_user.user_id)
#         assert len(permissions_in_db) == 1
#         assert permissions_in_db[0].path == f"/projects/{project_id}/*"
        #
        # response = await authorized_client.get(app.url_path_for("get_projects"))
        # assert response.status_code == status.HTTP_200_OK
        # projects = response.json()
        # assert len(projects) == 1

    # async def test_admin_access_all_projects(self, app: FastAPI, client: AsyncClient):
    #
    #     response = await client.get(app.url_path_for("get_projects"))
    #     assert response.status_code == status.HTTP_200_OK
    #     projects = response.json()
    #     assert len(projects) == 2
    #
    # async def test_admin_user_give_permission_on_project(
    #         self,
    #         app: FastAPI,
    #         client: AsyncClient,
    #         test_user: User
    # ):
    #
    #     response = await client.get(app.url_path_for("get_projects"))
    #     assert response.status_code == status.HTTP_200_OK
    #     projects = response.json()
    #     project_id = None
    #     for project in projects:
    #         if project["name"] == "Admin project":
    #             project_id = project["project_id"]
    #             break
    #
    #     new_permission = {
    #         "methods": ["GET"],
    #         "path": f"/projects/{project_id}",
    #         "action": "ALLOW"
    #     }
    #     response = await client.post(app.url_path_for("create_permission"), json=new_permission)
    #     assert response.status_code == status.HTTP_201_CREATED
    #     permission_id = response.json()["permission_id"]
    #
    #     response = await client.put(
    #         app.url_path_for(
    #             "add_permission_to_user",
    #             user_id=test_user.user_id,
    #             permission_id=permission_id
    #         )
    #     )
    #     assert response.status_code == status.HTTP_204_NO_CONTENT
    #
    # async def test_user_access_admin_project(
    #         self,
    #         app: FastAPI,
    #         authorized_client: AsyncClient,
    #         test_user: User,
    #         db_session: AsyncSession
    # ) -> None:
    #
    #     response = await authorized_client.get(app.url_path_for("get_projects"))
    #     assert response.status_code == status.HTTP_200_OK
    #     projects = response.json()
    #     assert len(projects) == 2
    #

# class TestTemplatesWithRbac:
#
#     async def test_admin_create_template(self, app: FastAPI, client: AsyncClient):
#
#         new_template = {"base_script_file": "vpcs_base_config.txt",
#                         "category": "guest",
#                         "console_auto_start": False,
#                         "console_type": "telnet",
#                         "default_name_format": "PC{0}",
#                         "name": "ADMIN_VPCS_TEMPLATE",
#                         "compute_id": "local",
#                         "symbol": ":/symbols/vpcs_guest.svg",
#                         "template_type": "vpcs"}
#
#         response = await client.post(app.url_path_for("create_template"), json=new_template)
#         assert response.status_code == status.HTTP_201_CREATED
#
#     async def test_user_only_access_own_templates(
#             self, app: FastAPI,
#             authorized_client: AsyncClient,
#             test_user: User,
#             db_session: AsyncSession
#     ) -> None:
#
#         new_template = {"base_script_file": "vpcs_base_config.txt",
#                         "category": "guest",
#                         "console_auto_start": False,
#                         "console_type": "telnet",
#                         "default_name_format": "PC{0}",
#                         "name": "USER_VPCS_TEMPLATE",
#                         "compute_id": "local",
#                         "symbol": ":/symbols/vpcs_guest.svg",
#                         "template_type": "vpcs"}
#
#         response = await authorized_client.post(app.url_path_for("create_template"), json=new_template)
#         assert response.status_code == status.HTTP_201_CREATED
#         template_id = response.json()["template_id"]
#
#         rbac_repo = RbacRepository(db_session)
#         permissions_in_db = await rbac_repo.get_user_permissions(test_user.user_id)
#         assert len(permissions_in_db) == 1
#         assert permissions_in_db[0].path == f"/templates/{template_id}/*"
#
#         response = await authorized_client.get(app.url_path_for("get_templates"))
#         assert response.status_code == status.HTTP_200_OK
#         templates = [template for template in response.json() if template["builtin"] is False]
#         assert len(templates) == 1
#
#     async def test_admin_access_all_templates(self, app: FastAPI, client: AsyncClient):
#
#         response = await client.get(app.url_path_for("get_templates"))
#         assert response.status_code == status.HTTP_200_OK
#         templates = [template for template in response.json() if template["builtin"] is False]
#         assert len(templates) == 2
