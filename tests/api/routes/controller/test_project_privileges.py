#
# Copyright (C) 2026 GNS3 Technologies Inc.
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
Tests for GET /projects/{project_id}/me/privileges: the per-project view of
the current user's effective privileges (unlike /access/users/me/privileges,
evaluated on the project resource path).
"""

import uuid

import pytest
import pytest_asyncio
from fastapi import FastAPI, status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from gns3server.controller import Controller
from gns3server.controller.project import Project
from gns3server.db.models import Role, User
from gns3server.db.repositories.pools import ResourcePoolsRepository
from gns3server.db.repositories.rbac import RbacRepository
from gns3server.schemas.controller.pools import ResourceCreate, ResourcePoolCreate
from gns3server.schemas.controller.rbac import ACECreate, RoleCreate
from gns3server.services import auth_service
from gns3server.services.authentication import DEFAULT_JWT_SECRET_KEY

pytestmark = pytest.mark.asyncio


class TestProjectPrivilegesRoute:
    """
    Every test creates its own project (unique id) and its own ACEs, so the
    file is order-independent under --random-order.
    """

    @pytest_asyncio.fixture
    async def project(self, app: FastAPI, client: AsyncClient, controller: Controller) -> Project:

        project_id = str(uuid.uuid4())
        params = {"name": f"privileges-{project_id[:8]}", "project_id": project_id}
        response = await client.post(app.url_path_for("create_project"), json=params)
        assert response.status_code == status.HTTP_201_CREATED
        return controller.get_project(project_id)

    @staticmethod
    def _user_headers(user: User) -> dict:
        token = auth_service.create_access_token(user.username, secret_key=DEFAULT_JWT_SECRET_KEY)
        return {"Authorization": f"Bearer {token}"}

    async def _create_user_ace(self, db_session: AsyncSession, path: str, user: User, role_name: str) -> None:

        rbac_repo = RbacRepository(db_session)
        role = await rbac_repo.get_role_by_name(role_name)
        await rbac_repo.create_ace(
            ACECreate(
                path=path,
                ace_type="user",
                propagate=True,
                user_id=str(user.user_id),
                role_id=str(role.role_id),
            )
        )

    @staticmethod
    async def _create_user_out_of_band(db_session: AsyncSession, username: str) -> User:
        """
        A user inserted directly (not via create_user) stays out of the "Users"
        group and holds no privileges beyond what the test grants.
        """

        db_user = User(username=username, hashed_password=auth_service.hash_password("password"))
        db_session.add(db_user)
        await db_session.commit()
        await db_session.refresh(db_user)  # the id must be a UUID, not the str default
        return db_user

    @staticmethod
    async def _create_audit_only_role(db_session: AsyncSession, name: str) -> Role:

        rbac_repo = RbacRepository(db_session)
        role = await rbac_repo.create_role(RoleCreate(name=name, description="Read-only role for tests"))
        for privilege_name in ("Project.Audit", "Node.Audit", "Link.Audit"):
            privilege = await rbac_repo.get_privilege_by_name(privilege_name)
            await rbac_repo.add_privilege_to_role(role.role_id, privilege)
        return role

    async def test_superadmin_gets_all_privileges(self, app: FastAPI, client: AsyncClient, project: Project) -> None:

        response = await client.get(app.url_path_for("get_logged_in_user_privileges_on_project", project_id=project.id))
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["is_superadmin"] is True
        assert "Project.Audit" in data["privileges"]
        assert "Project.Modify" in data["privileges"]
        assert "Node.PowerMgmt" in data["privileges"]

    async def test_unknown_project_returns_404(self, app: FastAPI, client: AsyncClient) -> None:

        response = await client.get(
            app.url_path_for("get_logged_in_user_privileges_on_project", project_id=str(uuid.uuid4()))
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_user_without_access_gets_403(
        self, app: FastAPI, client: AsyncClient, project: Project, db_session: AsyncSession
    ) -> None:

        user = await self._create_user_out_of_band(db_session, "no-project-access")
        response = await client.get(
            app.url_path_for("get_logged_in_user_privileges_on_project", project_id=project.id),
            headers=self._user_headers(user),
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    async def test_user_ace_grants_project_scoped_privileges(
        self,
        app: FastAPI,
        client: AsyncClient,
        project: Project,
        test_user: User,
        db_session: AsyncSession,
    ) -> None:

        # the "User" role carries the whole project-subtree family
        await self._create_user_ace(db_session, f"/projects/{project.id}", test_user, "User")

        response = await client.get(
            app.url_path_for("get_logged_in_user_privileges_on_project", project_id=project.id),
            headers=self._user_headers(test_user),
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["is_superadmin"] is False
        for privilege in (
            "Project.Audit",
            "Project.Modify",
            "Node.Modify",
            "Node.Console",
            "Node.PowerMgmt",
            "Link.Capture",
            "Snapshot.Restore",
        ):
            assert privilege in data["privileges"]
        # privileges outside the role must not appear, even path-scoped
        assert "User.Audit" not in data["privileges"]
        assert "Template.Modify" not in data["privileges"]

    async def test_audit_only_role_gets_audit_only(
        self,
        app: FastAPI,
        client: AsyncClient,
        project: Project,
        db_session: AsyncSession,
    ) -> None:

        user = await self._create_user_out_of_band(db_session, "audit-only-user")
        await self._create_audit_only_role(db_session, "audit-only")
        await self._create_user_ace(db_session, f"/projects/{project.id}", user, "audit-only")

        response = await client.get(
            app.url_path_for("get_logged_in_user_privileges_on_project", project_id=project.id),
            headers=self._user_headers(user),
        )
        assert response.status_code == status.HTTP_200_OK
        privileges = response.json()["privileges"]
        assert "Project.Audit" in privileges
        assert "Node.Audit" in privileges
        assert "Link.Audit" in privileges
        # audit-only users can look but not touch
        assert "Project.Modify" not in privileges
        assert "Node.Modify" not in privileges
        assert "Node.Console" not in privileges
        assert "Snapshot.Restore" not in privileges

    async def test_pool_membership_grants_privileges(
        self,
        app: FastAPI,
        client: AsyncClient,
        controller: Controller,
        project: Project,
        db_session: AsyncSession,
    ) -> None:

        user = await self._create_user_out_of_band(db_session, "pool-audit-user")
        await self._create_audit_only_role(db_session, "pool-audit")

        pools_repo = ResourcePoolsRepository(db_session)
        pool = await pools_repo.create_resource_pool(ResourcePoolCreate(name=f"pool-{uuid.uuid4().hex[:8]}"))
        resource = await pools_repo.create_resource(
            ResourceCreate(resource_id=uuid.UUID(project.id), resource_type="project", name=project.name)
        )
        await pools_repo.add_resource_to_pool(pool.resource_pool_id, resource)

        await self._create_user_ace(db_session, f"/pools/{pool.resource_pool_id}", user, "pool-audit")

        response = await client.get(
            app.url_path_for("get_logged_in_user_privileges_on_project", project_id=project.id),
            headers=self._user_headers(user),
        )
        assert response.status_code == status.HTTP_200_OK
        privileges = response.json()["privileges"]
        assert "Project.Audit" in privileges
        assert "Project.Modify" not in privileges
