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
from gns3server.db.models import User

pytestmark = pytest.mark.asyncio


class TestPermissions:

    @pytest.mark.parametrize(
        "method, path, result",
        (
            ("GET", "/users", False),
            ("GET", "/projects", True),
            ("GET", "/projects/e451ad73-2519-4f83-87fe-a8e821792d44", False),
            ("POST", "/projects", True),
            ("GET", "/templates", True),
            ("GET", "/templates/62e92cf1-244a-4486-8dae-b95439b54da9", False),
            ("POST", "/templates", True),
            ("GET", "/computes", True),
            ("GET", "/computes/local", True),
            ("GET", "/symbols", True),
            ("GET", "/symbols/default_symbols", True),
        ),
    )
    async def test_default_permissions_user_group(
            self,
            app: FastAPI,
            authorized_client: AsyncClient,
            test_user: User,
            db_session: AsyncSession,
            method: str,
            path: str,
            result: bool
    ) -> None:

        rbac_repo = RbacRepository(db_session)
        authorized = await rbac_repo.check_user_is_authorized(test_user.user_id, method, path)
        assert authorized == result


class TestProjectsWithRbac:

    async def test_admin_create_project(self, app: FastAPI, client: AsyncClient):

        params = {"name": "Admin project"}
        response = await client.post(app.url_path_for("create_project"), json=params)
        assert response.status_code == status.HTTP_201_CREATED

    async def test_user_only_access_own_projects(
            self,
            app: FastAPI,
            authorized_client: AsyncClient,
            test_user: User,
            db_session: AsyncSession
    ) -> None:

        params = {"name": "User project"}
        response = await authorized_client.post(app.url_path_for("create_project"), json=params)
        assert response.status_code == status.HTTP_201_CREATED
        project_id = response.json()["project_id"]

        rbac_repo = RbacRepository(db_session)
        permissions_in_db = await rbac_repo.get_user_permissions(test_user.user_id)
        assert len(permissions_in_db) == 1
        assert permissions_in_db[0].path == f"/projects/{project_id}/*"

        response = await authorized_client.get(app.url_path_for("get_projects"))
        assert response.status_code == status.HTTP_200_OK
        projects = response.json()
        assert len(projects) == 1

    async def test_admin_access_all_projects(self, app: FastAPI, client: AsyncClient):

        response = await client.get(app.url_path_for("get_projects"))
        assert response.status_code == status.HTTP_200_OK
        projects = response.json()
        assert len(projects) == 2

    async def test_admin_user_give_permission_on_project(
            self,
            app: FastAPI,
            client: AsyncClient,
            test_user: User
    ):

        response = await client.get(app.url_path_for("get_projects"))
        assert response.status_code == status.HTTP_200_OK
        projects = response.json()
        project_id = None
        for project in projects:
            if project["name"] == "Admin project":
                project_id = project["project_id"]
                break

        new_permission = {
            "methods": ["GET"],
            "path": f"/projects/{project_id}",
            "action": "ALLOW"
        }
        response = await client.post(app.url_path_for("create_permission"), json=new_permission)
        assert response.status_code == status.HTTP_201_CREATED
        permission_id = response.json()["permission_id"]

        response = await client.put(
            app.url_path_for(
                "add_permission_to_user",
                user_id=test_user.user_id,
                permission_id=permission_id
            )
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

    async def test_user_access_admin_project(
            self,
            app: FastAPI,
            authorized_client: AsyncClient,
            test_user: User,
            db_session: AsyncSession
    ) -> None:

        response = await authorized_client.get(app.url_path_for("get_projects"))
        assert response.status_code == status.HTTP_200_OK
        projects = response.json()
        assert len(projects) == 2


class TestTemplatesWithRbac:

    async def test_admin_create_template(self, app: FastAPI, client: AsyncClient):

        new_template = {"base_script_file": "vpcs_base_config.txt",
                        "category": "guest",
                        "console_auto_start": False,
                        "console_type": "telnet",
                        "default_name_format": "PC{0}",
                        "name": "ADMIN_VPCS_TEMPLATE",
                        "compute_id": "local",
                        "symbol": ":/symbols/vpcs_guest.svg",
                        "template_type": "vpcs"}

        response = await client.post(app.url_path_for("create_template"), json=new_template)
        assert response.status_code == status.HTTP_201_CREATED

    async def test_user_only_access_own_templates(
            self, app: FastAPI,
            authorized_client: AsyncClient,
            test_user: User,
            db_session: AsyncSession
    ) -> None:

        new_template = {"base_script_file": "vpcs_base_config.txt",
                        "category": "guest",
                        "console_auto_start": False,
                        "console_type": "telnet",
                        "default_name_format": "PC{0}",
                        "name": "USER_VPCS_TEMPLATE",
                        "compute_id": "local",
                        "symbol": ":/symbols/vpcs_guest.svg",
                        "template_type": "vpcs"}

        response = await authorized_client.post(app.url_path_for("create_template"), json=new_template)
        assert response.status_code == status.HTTP_201_CREATED
        template_id = response.json()["template_id"]

        rbac_repo = RbacRepository(db_session)
        permissions_in_db = await rbac_repo.get_user_permissions(test_user.user_id)
        assert len(permissions_in_db) == 1
        assert permissions_in_db[0].path == f"/templates/{template_id}/*"

        response = await authorized_client.get(app.url_path_for("get_templates"))
        assert response.status_code == status.HTTP_200_OK
        templates = [template for template in response.json() if template["builtin"] is False]
        assert len(templates) == 1

    async def test_admin_access_all_templates(self, app: FastAPI, client: AsyncClient):

        response = await client.get(app.url_path_for("get_templates"))
        assert response.status_code == status.HTTP_200_OK
        templates = [template for template in response.json() if template["builtin"] is False]
        assert len(templates) == 2
