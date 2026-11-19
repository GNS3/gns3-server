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

import asyncio
import json
import os
import time
import uuid
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from fastapi import FastAPI, status
from httpx import AsyncClient
from httpx_ws.transport import ASGIWebSocketTransport
from sqlalchemy.ext.asyncio import AsyncSession

from gns3server import schemas
from gns3server.api.routes.controller import projects as projects_routes
from gns3server.controller import Controller, qemu_overlay
from gns3server.controller import project as project_module
from gns3server.controller.controller_error import ControllerError
from gns3server.controller.distribution import DistributionRegistry
from gns3server.db.models import User
from gns3server.db.project_acl import ensure_all_project_aces, ensure_project_owner_ace, upsert_project_share_ace
from gns3server.db.repositories.distribution_records import DistributionRecordsRepository
from gns3server.db.repositories.pools import ResourcePoolsRepository
from gns3server.db.repositories.rbac import RbacRepository
from gns3server.db.repositories.users import UsersRepository
from gns3server.schemas.controller.pools import ResourceCreate, ResourcePoolCreate
from gns3server.schemas.controller.rbac import ACECreate, ACEUpdate
from gns3server.services import auth_service
from gns3server.utils import zipfile_zstd
from tests.utils import AsyncioMagicMock

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
            # privileges carried by the "User" role are granted by the default ACEs
            # seeded on each top-level resource path (nothing is granted outside them)
            ("User.Allocate", "/users", False),
            ("Project.Allocate", "/projects", True),
            # the /projects default ACE does not propagate: a project is only
            # accessible through its own (owner) ACE or a resource pool
            ("Project.Audit", "/projects/e451ad73-2519-4f83-87fe-a8e821792d44", False),
            ("Project.Audit", "/templates", True),
            ("Template.Audit", "/templates", True),
            ("Template.Allocate", "/templates", False),
            ("Compute.Audit", "/computes", True),
            ("Compute.Audit", "/computes/local", True),
            ("Symbol.Audit", "/symbols", True),
            ("Symbol.Audit", "/symbols/default_symbols", True),
            ("Appliance.Audit", "/appliances", True),
            ("Image.Audit", "/images", True),
            ("Snapshot.Allocate", "/projects/e451ad73-2519-4f83-87fe-a8e821792d44/snapshots", False),
            ("LLMConfig.Audit", "/access/users/e451ad73-2519-4f83-87fe-a8e821792d44/llm-model-configs", True),
            # a privilege carried by the "User" role is still denied on a path
            # without a matching seeded ACE (no blanket ACE on "/" anymore)
            ("Project.Audit", "/pools", False),
        ),
    )
    async def test_default_privileges_user_group(
        self, test_user: User, db_session: AsyncSession, privilege: str, path: str, result: bool
    ) -> None:

        # another test in this class may have changed the /projects ACE:
        # restore the seeded shape (non propagating, allowed) first
        await self._get_or_create_projects_ace(db_session, propagate=False)
        authorized = await RbacRepository(db_session).check_user_has_privilege(test_user.user_id, path, privilege)
        assert authorized == result

    async def _get_or_create_projects_ace(
        self, db_session: AsyncSession, *, propagate: bool, allowed: bool = True
    ) -> None:
        """
        The tests must not depend on the /projects ACE created by another test:
        reuse it when present, otherwise create it with the requested flags.
        """

        rbac_repo = RbacRepository(db_session)
        ace = await rbac_repo.get_ace_by_path("/projects")
        if ace is None:
            group_id = (await UsersRepository(db_session).get_user_group_by_name("Users")).user_group_id
            role_id = (await rbac_repo.get_role_by_name("User")).role_id
            await rbac_repo.create_ace(
                ACECreate(
                    path="/projects",
                    ace_type="group",
                    propagate=propagate,
                    allowed=allowed,
                    group_id=str(group_id),
                    role_id=str(role_id),
                )
            )
        else:
            await rbac_repo.update_ace(
                ace.ace_id,
                ACEUpdate(
                    ace_type=ace.ace_type,
                    path=ace.path,
                    role_id=ace.role_id,
                    propagate=propagate,
                    allowed=allowed,
                ),
            )

    async def test_propagate(self, db_session: AsyncSession):

        # a user outside the "Users" group has no default privileges
        user = User(username="propagate-user", hashed_password=auth_service.hash_password("password"))
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)  # the id must be a UUID, not the str default

        privilege = "Project.Audit"
        # a unique path so the shared "/projects" ACE used by other tests is not disturbed
        base_path = f"/projects/{uuid.uuid4()}"
        path = f"{base_path}/nodes"
        rbac_repo = RbacRepository(db_session)
        authorized = await rbac_repo.check_user_has_privilege(user.user_id, path, privilege)
        assert authorized is False

        role_id = (await rbac_repo.get_role_by_name("User")).role_id
        await rbac_repo.create_ace(
            ACECreate(path=base_path, ace_type="user", propagate=True, user_id=str(user.user_id), role_id=str(role_id))
        )

        authorized = await rbac_repo.check_user_has_privilege(user.user_id, path, privilege)
        assert authorized is True

    async def test_allowed(self, test_user: User, db_session: AsyncSession):

        await self._get_or_create_projects_ace(db_session, propagate=True, allowed=False)

        privilege = "Project.Audit"
        path = "/projects/44929147-47bb-460a-90ae-c782c4dbb6ef"
        authorized = await RbacRepository(db_session).check_user_has_privilege(test_user.user_id, path, privilege)
        assert authorized is False

        # privileges on deeper levels replace those inherited from an upper level.
        group_id = (await UsersRepository(db_session).get_user_group_by_name("Users")).user_group_id
        role_id = (await RbacRepository(db_session).get_role_by_name("User")).role_id
        ace = ACECreate(path=path, ace_type="group", propagate=False, group_id=str(group_id), role_id=str(role_id))
        await RbacRepository(db_session).create_ace(ace)

        authorized = await RbacRepository(db_session).check_user_has_privilege(test_user.user_id, path, privilege)
        assert authorized is True

    async def test_delete_all_ace_starting_with_path_is_committed(self, db_session: AsyncSession):
        """
        Production requests get a fresh session that is only closed at
        teardown, rolling back uncommitted work: the bulk ACE deletion must
        be committed to survive the end of the request.
        """

        rbac_repo = RbacRepository(db_session)
        group_id = (await UsersRepository(db_session).get_user_group_by_name("Users")).user_group_id
        role_id = (await rbac_repo.get_role_by_name("User")).role_id
        path = f"/projects/{uuid.uuid4()}"
        await rbac_repo.create_ace(
            ACECreate(path=path, ace_type="group", propagate=False, group_id=str(group_id), role_id=str(role_id))
        )

        await rbac_repo.delete_all_ace_starting_with_path(path)
        # simulate the production session teardown: close() rolls back the
        # open transaction and an uncommitted deletion would be lost
        await db_session.rollback()
        assert await rbac_repo.check_ace_exists(path) is False


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
            role_id=str(role_id),
        )
        await RbacRepository(db_session).create_ace(ace)

        privilege = "Project.Audit"
        path = f"/projects/{project_id}"
        authorized = await RbacRepository(db_session).check_user_has_privilege(test_user.user_id, path, privilege)
        assert authorized is True

    async def test_list_projects_in_resource_pool(
        self, app: FastAPI, controller: Controller, base_client: AsyncClient, db_session: AsyncSession
    ) -> None:

        # a user outside the "Users" group has no default privileges: access comes only from the ACEs below
        user = User(username="pool-list-user", hashed_password=auth_service.hash_password("password"))
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)  # the id must be a UUID, not the str default

        uuid1 = str(uuid.uuid4())
        uuid2 = str(uuid.uuid4())
        uuid3 = str(uuid.uuid4())
        await controller.add_project(project_id=uuid1, name="Project1", created_by=user.username)
        await controller.add_project(project_id=uuid2, name="Project2", created_by=user.username)
        await controller.add_project(project_id=uuid3, name="Project3", created_by=user.username)

        # Create resource pool and add uuid2 to it
        pools_repo = ResourcePoolsRepository(db_session)
        new_resource_pool = ResourcePoolCreate(name="pool2")
        pool_in_db = await pools_repo.create_resource_pool(new_resource_pool)

        resource_create = ResourceCreate(resource_id=uuid2, resource_type="project", name="Project2")
        resource = await pools_repo.create_resource(resource_create)
        await pools_repo.add_resource_to_pool(pool_in_db.resource_pool_id, resource)

        role_id = (await RbacRepository(db_session).get_role_by_name("User")).role_id

        # Give user access to resource pool only
        ace = ACECreate(
            path=f"/pools/{pool_in_db.resource_pool_id}",
            ace_type="user",
            propagate=False,
            user_id=str(user.user_id),
            role_id=str(role_id),
        )
        await RbacRepository(db_session).create_ace(ace)

        # Create a new client with test user authentication
        access_token = auth_service.create_access_token(user.username)
        async with AsyncClient(
            base_url="http://test-api",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {access_token}"},
            transport=ASGIWebSocketTransport(app=app),
        ) as user_client:
            # user should see only uuid2 (from resource pool)
            response = await user_client.get(app.url_path_for("get_projects"))
            assert response.status_code == status.HTTP_200_OK
            projects = response.json()
            assert len(projects) == 1
            assert projects[0]["project_id"] == uuid2

            response = await user_client.get(app.url_path_for("get_project", project_id=uuid2))
            assert response.status_code == status.HTTP_200_OK
            assert response.json()["name"] == "Project2"

            # Now give user access to /projects (in addition to resource pool)
            ace = ACECreate(
                path="/projects", ace_type="user", propagate=True, user_id=str(user.user_id), role_id=str(role_id)
            )
            await RbacRepository(db_session).create_ace(ace)

            # user should see all 3 projects: 3 from /projects ACE (uuid2 also in pool but deduplicated)
            response = await user_client.get(app.url_path_for("get_projects"))
            assert response.status_code == status.HTTP_200_OK
            projects = response.json()
            assert len(projects) == 3

            # Remove resource pool ACE
            await RbacRepository(db_session).delete_all_ace_starting_with_path(f"/pools/{pool_in_db.resource_pool_id}")

            # user should still see all 3 projects via /projects ACE (created_by check)
            response = await user_client.get(app.url_path_for("get_projects"))
            assert response.status_code == status.HTTP_200_OK
            assert len(response.json()) == 3

    async def test_list_projects_legacy_without_created_by(
        self, app: FastAPI, controller: Controller, base_client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        """
        Projects created before GNS3 3.1 have no created_by field. Without an
        owner ACE they are restricted to superadmins: the backfill must not
        create an ACE for them, and a non-superadmin only sees them once an
        explicit ACE is granted.
        """

        # Clean up any existing ACEs from previous tests
        await RbacRepository(db_session).delete_all_ace_starting_with_path("/projects")
        await RbacRepository(db_session).delete_all_ace_starting_with_path("/pools")

        legacy_id = str(uuid.uuid4())  # created with GNS3 < 3.1, no created_by
        owned_id = str(uuid.uuid4())
        other_id = str(uuid.uuid4())
        await controller.add_project(project_id=legacy_id, name="LegacyProject")
        await controller.add_project(project_id=owned_id, name="OwnedProject", created_by=test_user.username)
        await controller.add_project(project_id=other_id, name="OtherProject", created_by="admin")

        group_id = (await UsersRepository(db_session).get_user_group_by_name("Users")).user_group_id
        role_id = (await RbacRepository(db_session).get_role_by_name("User")).role_id
        # the seeded collection ACE, in its non propagating shape
        await RbacRepository(db_session).create_ace(
            ACECreate(path="/projects", ace_type="group", propagate=False, group_id=str(group_id), role_id=str(role_id))
        )

        created = await ensure_all_project_aces(
            db_session,
            [(legacy_id, None), (owned_id, test_user.username), (other_id, "admin")],
        )
        # owner ACEs for the owned project and the admin project, none for the
        # legacy project (no owner)
        assert created == 2
        assert await RbacRepository(db_session).get_ace_by_path(f"/projects/{legacy_id}") is None

        access_token = auth_service.create_access_token(test_user.username)
        async with AsyncClient(
            base_url="http://test-api",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {access_token}"},
            transport=ASGIWebSocketTransport(app=app),
        ) as user_client:
            response = await user_client.get(app.url_path_for("get_projects"))
            assert response.status_code == status.HTTP_200_OK
            projects = response.json()
            # only the user's own project: the legacy project (no owner) stays
            # restricted to superadmins, the admin project has its own owner
            assert {p["name"] for p in projects} == {"OwnedProject"}

            response = await user_client.get(app.url_path_for("get_project", project_id=legacy_id))
            assert response.status_code == status.HTTP_403_FORBIDDEN

            # an explicit ACE makes the legacy project visible
            await RbacRepository(db_session).create_ace(
                ACECreate(
                    path=f"/projects/{legacy_id}",
                    ace_type="user",
                    propagate=True,
                    user_id=str(test_user.user_id),
                    role_id=str(role_id),
                )
            )
            response = await user_client.get(app.url_path_for("get_projects"))
            assert response.status_code == status.HTTP_200_OK
            assert {p["name"] for p in response.json()} == {"LegacyProject", "OwnedProject"}

            response = await user_client.get(app.url_path_for("get_project", project_id=legacy_id))
            assert response.status_code == status.HTTP_200_OK


class TestProjectOwnership:
    """
    The default ACE on /projects does not propagate: a project is accessible
    through its owner ACE (created when the project is created) or through an
    explicit share (ACE or resource pool). Projects without an owner are
    restricted to superadmins.
    """

    @staticmethod
    async def _seed_collection_ace(db_session: AsyncSession) -> None:
        """
        Restore the seeded /projects ACE (non propagating, allowed) and drop
        the ACEs created by previous tests of the class.
        """

        rbac_repo = RbacRepository(db_session)
        await rbac_repo.delete_all_ace_starting_with_path("/projects")
        group_id = (await UsersRepository(db_session).get_user_group_by_name("Users")).user_group_id
        role_id = (await rbac_repo.get_role_by_name("User")).role_id
        await rbac_repo.create_ace(
            ACECreate(path="/projects", ace_type="group", propagate=False, group_id=str(group_id), role_id=str(role_id))
        )

    @staticmethod
    def _client_for(app: FastAPI, user: User) -> AsyncClient:
        access_token = auth_service.create_access_token(user.username)
        return AsyncClient(
            base_url="http://test-api",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {access_token}"},
            transport=ASGIWebSocketTransport(app=app),
        )

    @staticmethod
    async def _create_user_in_users_group(db_session: AsyncSession, username: str) -> User:
        group = await UsersRepository(db_session).get_user_group_by_name("Users")
        return await UsersRepository(db_session).create_user(
            schemas.UserCreate(
                username=username,
                email=f"{username}@email.com",
                password="password123",
                user_group_id=group.user_group_id,
            )
        )

    @staticmethod
    async def _create_role_with_privileges(db_session: AsyncSession, name: str, privilege_names) -> object:
        """
        Build a custom role carrying exactly the given privileges.
        """

        rbac_repo = RbacRepository(db_session)
        role = await rbac_repo.create_role(schemas.RoleCreate(name=name))
        assert role is not None
        for privilege_name in privilege_names:
            privilege = await rbac_repo.get_privilege_by_name(privilege_name)
            assert privilege is not None, f"Privilege '{privilege_name}' does not exist"
            role = await rbac_repo.add_privilege_to_role(role.role_id, privilege)
        assert role is not None
        return role

    async def test_create_project_creates_owner_ace(
        self, app: FastAPI, base_client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        await self._seed_collection_ace(db_session)
        async with self._client_for(app, test_user) as user_client:
            response = await user_client.post(
                app.url_path_for("create_project"), json={"name": f"owner-ace-{uuid.uuid4()}"}
            )
            assert response.status_code == status.HTTP_201_CREATED
            project_id = response.json()["project_id"]

            response = await user_client.get(app.url_path_for("get_project", project_id=project_id))
            assert response.status_code == status.HTTP_200_OK

        ace = await RbacRepository(db_session).get_ace_by_path(f"/projects/{project_id}")
        assert ace is not None
        assert str(ace.user_id) == str(test_user.user_id)
        assert ace.propagate is True

    async def test_owner_ace_is_idempotent(
        self, app: FastAPI, base_client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        await self._seed_collection_ace(db_session)
        project_id = str(uuid.uuid4())

        assert await ensure_project_owner_ace(db_session, project_id, test_user.username) is True
        assert await ensure_project_owner_ace(db_session, project_id, test_user.username) is False
        assert await RbacRepository(db_session).get_ace_by_path(f"/projects/{project_id}") is not None

    async def test_foreign_project_is_private(
        self, app: FastAPI, base_client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        await self._seed_collection_ace(db_session)
        async with self._client_for(app, test_user) as owner_client:
            response = await owner_client.post(
                app.url_path_for("create_project"), json={"name": f"private-{uuid.uuid4()}"}
            )
            assert response.status_code == status.HTTP_201_CREATED
            project_id = response.json()["project_id"]

        other_user = await self._create_user_in_users_group(db_session, f"other-{uuid.uuid4().hex[:8]}")
        async with self._client_for(app, other_user) as other_client:
            response = await other_client.get(app.url_path_for("get_projects"))
            assert response.status_code == status.HTTP_200_OK
            assert project_id not in {p["project_id"] for p in response.json()}

            response = await other_client.get(app.url_path_for("get_project", project_id=project_id))
            assert response.status_code == status.HTTP_403_FORBIDDEN

            response = await other_client.delete(app.url_path_for("delete_project", project_id=project_id))
            assert response.status_code == status.HTTP_403_FORBIDDEN

    async def test_explicit_ace_share_is_listed_and_accessible(
        self, app: FastAPI, base_client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        await self._seed_collection_ace(db_session)
        async with self._client_for(app, test_user) as owner_client:
            response = await owner_client.post(
                app.url_path_for("create_project"), json={"name": f"shared-{uuid.uuid4()}"}
            )
            assert response.status_code == status.HTTP_201_CREATED
            project_id = response.json()["project_id"]

        other_user = await self._create_user_in_users_group(db_session, f"shared-{uuid.uuid4().hex[:8]}")
        rbac_repo = RbacRepository(db_session)
        role_id = (await rbac_repo.get_role_by_name("User")).role_id
        await rbac_repo.create_ace(
            ACECreate(
                path=f"/projects/{project_id}",
                ace_type="user",
                propagate=True,
                user_id=str(other_user.user_id),
                role_id=str(role_id),
            )
        )

        async with self._client_for(app, other_user) as other_client:
            response = await other_client.get(app.url_path_for("get_projects"))
            assert response.status_code == status.HTTP_200_OK
            assert project_id in {p["project_id"] for p in response.json()}

            response = await other_client.get(app.url_path_for("get_project", project_id=project_id))
            assert response.status_code == status.HTTP_200_OK

    async def test_import_new_project_needs_collection_privilege(
        self, app: FastAPI, base_client: AsyncClient, db_session: AsyncSession, test_user: User, tmpdir
    ) -> None:
        await self._seed_collection_ace(db_session)
        with zipfile_zstd.ZipFile(str(tmpdir / "test.zip"), "w") as myzip:
            myzip.writestr(
                "project.gns3",
                b'{"project_id": "c6992992-ac72-47dc-833b-54aa334bcd05", "version": "2.0.0", "name": "rbac-import"}',
            )
            myzip.writestr("demo", b"hello")

        project_id = str(uuid.uuid4())
        async with self._client_for(app, test_user) as user_client:
            with open(str(tmpdir / "test.zip"), "rb") as f:
                response = await user_client.post(
                    app.url_path_for("import_project", project_id=project_id), content=f.read()
                )
        assert response.status_code == status.HTTP_201_CREATED

        # the importer becomes the owner of the imported project
        ace = await RbacRepository(db_session).get_ace_by_path(f"/projects/{project_id}")
        assert ace is not None
        assert str(ace.user_id) == str(test_user.user_id)

    async def test_import_without_privilege_is_denied(
        self, app: FastAPI, base_client: AsyncClient, db_session: AsyncSession, tmpdir
    ) -> None:
        await self._seed_collection_ace(db_session)
        user = User(
            username=f"no-import-{uuid.uuid4().hex[:8]}", hashed_password=auth_service.hash_password("password")
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        with zipfile_zstd.ZipFile(str(tmpdir / "test.zip"), "w") as myzip:
            myzip.writestr(
                "project.gns3",
                b'{"project_id": "c6992992-ac72-47dc-833b-54aa334bcd05", "version": "2.0.0", "name": "rbac-import"}',
            )

        project_id = str(uuid.uuid4())
        async with self._client_for(app, user) as user_client:
            with open(str(tmpdir / "test.zip"), "rb") as f:
                response = await user_client.post(
                    app.url_path_for("import_project", project_id=project_id), content=f.read()
                )
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestProjectDistribution:
    """
    Distributing a project (duplicate with target_user) creates a copy owned
    by the target user. The owner ACE of the copy carries a reduced role (the
    built-in "Lab member" role by default), so the recipient can use the lab
    but not modify its topology, while projects they create themselves keep
    their full role. The user-level owner ACE replaces group privileges, so a
    broad group grant cannot widen the copy. The copy is personal: it does not
    inherit the resource pools of the source, and it ships with a
    "template state" snapshot the recipient can restore on their own.
    """

    # These tests run on the class event loop, like the class-scoped database
    # fixtures. The distribution job runs in the background and shares the
    # class engine: with an in-memory database all sessions share one pooled
    # connection, and when a polling request and the job execute at the same
    # time the connection's execute mutex binds to the event loop of that
    # test. On the next test (a new event loop) a concurrent execute then
    # fails with "Lock is bound to a different event loop". One loop for the
    # whole class makes the job, the requests and the connection agree.
    pytestmark = pytest.mark.asyncio(loop_scope="class")

    LAB_MEMBER_PRIVILEGES = {
        "Project.Allocate",
        "Project.Audit",
        "Project.Marker",
        "Snapshot.Audit",
        "Snapshot.Restore",
        "Node.Audit",
        "Node.Console",
        "Node.PowerMgmt",
        "Link.Audit",
        "Link.Capture",
        "Link.Marker",
        "Drawing.Audit",
    }

    @staticmethod
    async def _wait_for_distribution(
        app: FastAPI, client: AsyncClient, project_id: str, distribution_id: str, timeout_seconds: float = 10.0
    ) -> dict:
        """
        Poll a distribution job until it completes and return its final state.
        """

        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            response = await client.get(
                app.url_path_for("get_project_distribution", project_id=project_id, distribution_id=distribution_id)
            )
            assert response.status_code == status.HTTP_200_OK
            job = response.json()
            if job["status"] == "completed":
                return job
            assert job["status"] == "running"
            await asyncio.sleep(0.05)
        raise AssertionError(f"Distribution '{distribution_id}' did not complete in {timeout_seconds} seconds")

    @staticmethod
    async def _wait_for_cancelled(
        app: FastAPI, client: AsyncClient, project_id: str, distribution_id: str, timeout_seconds: float = 10.0
    ) -> dict:
        """
        Poll a distribution job until it is cancelled and return its final state.
        """

        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            response = await client.get(
                app.url_path_for("get_project_distribution", project_id=project_id, distribution_id=distribution_id)
            )
            assert response.status_code == status.HTTP_200_OK
            job = response.json()
            if job["status"] == "cancelled":
                return job
            assert job["status"] in ("running", "cancelling")
            await asyncio.sleep(0.05)
        raise AssertionError(f"Distribution '{distribution_id}' was not cancelled in {timeout_seconds} seconds")

    @staticmethod
    async def _distribute(app: FastAPI, teacher: User, student_username: str) -> tuple[str, str]:
        """
        Create a project as the teacher and distribute it to the student.
        Returns (source_id, copy_id).
        """

        async with TestProjectOwnership._client_for(app, teacher) as teacher_client:
            response = await teacher_client.post(
                app.url_path_for("create_project"), json={"name": f"lab-{uuid.uuid4()}"}
            )
            assert response.status_code == status.HTTP_201_CREATED
            source_id = response.json()["project_id"]

            response = await teacher_client.post(
                app.url_path_for("distribute_project", project_id=source_id),
                json={"name": f"lab-copy-{uuid.uuid4()}", "target_user": student_username},
            )
            assert response.status_code == status.HTTP_202_ACCEPTED
            distribution_id = response.json()["distribution_id"]
            job = await TestProjectDistribution._wait_for_distribution(app, teacher_client, source_id, distribution_id)
            assert job["total"] == 1
            results = job["results"]
            assert len(results) == 1
            assert results[0]["error"] is None
            assert results[0]["username"] == student_username
            return source_id, results[0]["project"]["project_id"]

    async def test_distribute_project_to_user(
        self, app: FastAPI, base_client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        await TestProjectOwnership._seed_collection_ace(db_session)
        student = await TestProjectOwnership._create_user_in_users_group(db_session, f"student-{uuid.uuid4().hex[:8]}")
        source_id, copy_id = await self._distribute(app, test_user, student.username)

        # the owner ACE of the copy carries the built-in reduced role
        rbac_repo = RbacRepository(db_session)
        ace = await rbac_repo.get_ace_by_path(f"/projects/{copy_id}")
        assert ace is not None
        assert str(ace.user_id) == str(student.user_id)
        lab_member_role = await rbac_repo.get_role_by_name("Lab member")
        assert str(ace.role_id) == str(lab_member_role.role_id)

        async with TestProjectOwnership._client_for(app, student) as student_client:
            response = await student_client.get(app.url_path_for("get_projects"))
            assert response.status_code == status.HTTP_200_OK
            assert copy_id in {p["project_id"] for p in response.json()}

            response = await student_client.get(app.url_path_for("get_project", project_id=copy_id))
            assert response.status_code == status.HTTP_200_OK
            assert response.json()["created_by"] == student.username

            # the copy ships with a snapshot of the template state
            response = await student_client.get(app.url_path_for("get_snapshots", project_id=copy_id))
            assert response.status_code == status.HTTP_200_OK
            assert "template state" in {s["name"] for s in response.json()}

        # the copy is personal: the teacher has no access to it
        async with TestProjectOwnership._client_for(app, test_user) as teacher_client:
            response = await teacher_client.get(app.url_path_for("get_project", project_id=copy_id))
            assert response.status_code == status.HTTP_403_FORBIDDEN

    async def test_distribution_freezes_topology_for_recipient(
        self, app: FastAPI, base_client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        await TestProjectOwnership._seed_collection_ace(db_session)
        student = await TestProjectOwnership._create_user_in_users_group(db_session, f"student-{uuid.uuid4().hex[:8]}")
        source_id, copy_id = await self._distribute(app, test_user, student.username)

        async with TestProjectOwnership._client_for(app, student) as student_client:
            # frozen: the reduced role has no Project.Modify / Node.Allocate.
            # (Project.Allocate is part of the role: opening the project and
            # deleting one's own copy are allowed)
            response = await student_client.put(
                app.url_path_for("update_project", project_id=copy_id), json={"name": "hacked"}
            )
            assert response.status_code == status.HTTP_403_FORBIDDEN

            # usable: opening the project is how the recipient reaches the lab
            response = await student_client.post(app.url_path_for("open_project", project_id=copy_id))
            assert response.status_code == status.HTTP_200_OK

            response = await student_client.post(
                app.url_path_for("create_node", project_id=copy_id),
                json={"name": "extra", "node_type": "vpcs", "compute_id": "local", "properties": {}},
            )
            assert response.status_code == status.HTTP_403_FORBIDDEN

            # the effective privilege view shows exactly the reduced set
            response = await student_client.get(
                app.url_path_for("get_logged_in_user_privileges_on_project", project_id=copy_id)
            )
            assert response.status_code == status.HTTP_200_OK
            assert response.json()["is_superadmin"] is False
            assert set(response.json()["privileges"]) == self.LAB_MEMBER_PRIVILEGES

            # usable: the recipient can reset the lab on their own
            response = await student_client.get(app.url_path_for("get_snapshots", project_id=copy_id))
            snapshot_id = next(s["snapshot_id"] for s in response.json() if s["name"] == "template state")
            response = await student_client.post(
                app.url_path_for("restore_snapshot", project_id=copy_id, snapshot_id=snapshot_id)
            )
            assert response.status_code == status.HTTP_200_OK

        # distributing froze the template: the teacher cannot rename (or
        # otherwise modify) the source until every copy is deleted
        async with TestProjectOwnership._client_for(app, test_user) as teacher_client:
            response = await teacher_client.get(app.url_path_for("get_project", project_id=source_id))
            assert response.status_code == status.HTTP_200_OK
            assert response.json()["frozen"] is True

            response = await teacher_client.put(
                app.url_path_for("update_project", project_id=source_id), json={"name": "renamed-lab"}
            )
            assert response.status_code == status.HTTP_403_FORBIDDEN

            # unfreezing needs the copies gone: while the copy exists it is a 409
            response = await teacher_client.post(app.url_path_for("unfreeze_project", project_id=source_id))
            assert response.status_code == status.HTTP_409_CONFLICT

        # the recipient deletes their copy, then the teacher can unfreeze
        async with TestProjectOwnership._client_for(app, student) as student_client:
            response = await student_client.delete(app.url_path_for("delete_project", project_id=copy_id))
            assert response.status_code == status.HTTP_204_NO_CONTENT

        async with TestProjectOwnership._client_for(app, test_user) as teacher_client:
            response = await teacher_client.post(app.url_path_for("unfreeze_project", project_id=source_id))
            assert response.status_code == status.HTTP_200_OK
            assert response.json()["frozen"] is False

            # with the template unfrozen the full role is back
            response = await teacher_client.put(
                app.url_path_for("update_project", project_id=source_id), json={"name": "renamed-lab"}
            )
            assert response.status_code == status.HTTP_200_OK

    async def test_distribution_shield_against_group_grants(
        self, app: FastAPI, base_client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        await TestProjectOwnership._seed_collection_ace(db_session)

        # a broad group grant, as in a shared deployment: the Users group gets
        # the full "User" role on every project
        rbac_repo = RbacRepository(db_session)
        group_id = (await UsersRepository(db_session).get_user_group_by_name("Users")).user_group_id
        role_id = (await rbac_repo.get_role_by_name("User")).role_id
        await rbac_repo.create_ace(
            ACECreate(path="/projects", ace_type="group", propagate=True, group_id=str(group_id), role_id=str(role_id))
        )

        student = await TestProjectOwnership._create_user_in_users_group(db_session, f"student-{uuid.uuid4().hex[:8]}")
        _, copy_id = await self._distribute(app, test_user, student.username)

        # the user-level owner ACE replaces the group privileges: the copy
        # stays frozen even though the group could modify every other project
        async with TestProjectOwnership._client_for(app, student) as student_client:
            response = await student_client.put(
                app.url_path_for("update_project", project_id=copy_id), json={"name": "hacked"}
            )
            assert response.status_code == status.HTTP_403_FORBIDDEN

            response = await student_client.get(
                app.url_path_for("get_logged_in_user_privileges_on_project", project_id=copy_id)
            )
            assert set(response.json()["privileges"]) == self.LAB_MEMBER_PRIVILEGES

    async def test_distribution_to_missing_target_or_role(
        self, app: FastAPI, base_client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        await TestProjectOwnership._seed_collection_ace(db_session)
        student = await TestProjectOwnership._create_user_in_users_group(db_session, f"student-{uuid.uuid4().hex[:8]}")

        async with TestProjectOwnership._client_for(app, test_user) as teacher_client:
            response = await teacher_client.post(
                app.url_path_for("create_project"), json={"name": f"lab-{uuid.uuid4()}"}
            )
            source_id = response.json()["project_id"]

            response = await teacher_client.post(
                app.url_path_for("distribute_project", project_id=source_id),
                json={"name": "copy", "target_user": "missing-user"},
            )
            assert response.status_code == status.HTTP_404_NOT_FOUND

            response = await teacher_client.post(
                app.url_path_for("distribute_project", project_id=source_id),
                json={"name": "copy", "target_user": student.username, "owner_role": "No such role"},
            )
            assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_distribution_rejects_the_caller_as_target(
        self, app: FastAPI, base_client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        await TestProjectOwnership._seed_collection_ace(db_session)
        student = await TestProjectOwnership._create_user_in_users_group(db_session, f"student-{uuid.uuid4().hex[:8]}")

        async with TestProjectOwnership._client_for(app, test_user) as teacher_client:
            response = await teacher_client.post(
                app.url_path_for("create_project"), json={"name": f"lab-{uuid.uuid4()}"}
            )
            source_id = response.json()["project_id"]

            # a distribution hands the lab to other people: someone who wants
            # their own copy duplicates the project instead
            response = await teacher_client.post(
                app.url_path_for("distribute_project", project_id=source_id),
                json={"name": "copy", "target_user": test_user.username},
            )
            assert response.status_code == status.HTTP_409_CONFLICT

            response = await teacher_client.post(
                app.url_path_for("distribute_project", project_id=source_id),
                json={"name": "copy", "target_users": [student.username, test_user.username]},
            )
            assert response.status_code == status.HTTP_409_CONFLICT

            # a rejected distribution leaves nothing behind: no freeze, no job
            response = await teacher_client.get(app.url_path_for("get_project", project_id=source_id))
            assert response.json()["frozen"] is False
            response = await teacher_client.get(app.url_path_for("get_project_distributions", project_id=source_id))
            assert response.json() == []

    async def test_distribution_owner_role_wider_than_the_caller_is_rejected(
        self, app: FastAPI, base_client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        await TestProjectOwnership._seed_collection_ace(db_session)
        student = await TestProjectOwnership._create_user_in_users_group(db_session, f"student-{uuid.uuid4().hex[:8]}")

        async with TestProjectOwnership._client_for(app, test_user) as teacher_client:
            response = await teacher_client.post(
                app.url_path_for("create_project"), json={"name": f"lab-{uuid.uuid4()}"}
            )
            source_id = response.json()["project_id"]

            # the owner role of the copies cannot be wider than what the
            # caller holds on the project
            response = await teacher_client.post(
                app.url_path_for("distribute_project", project_id=source_id),
                json={"name": "copy", "target_user": student.username, "owner_role": "Administrator"},
            )
            assert response.status_code == status.HTTP_403_FORBIDDEN

            response = await teacher_client.get(app.url_path_for("get_project", project_id=source_id))
            assert response.json()["frozen"] is False
            response = await teacher_client.get(app.url_path_for("get_project_distributions", project_id=source_id))
            assert response.json() == []

    async def test_shared_lab_member_cannot_distribute(
        self, app: FastAPI, base_client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        await TestProjectOwnership._seed_collection_ace(db_session)
        student = await TestProjectOwnership._create_user_in_users_group(db_session, f"student-{uuid.uuid4().hex[:8]}")
        outsider = await TestProjectOwnership._create_user_in_users_group(db_session, f"peer-{uuid.uuid4().hex[:8]}")

        async with TestProjectOwnership._client_for(app, test_user) as teacher_client:
            response = await teacher_client.post(
                app.url_path_for("create_project"), json={"name": f"lab-{uuid.uuid4()}"}
            )
            source_id = response.json()["project_id"]
            response = await teacher_client.post(
                app.url_path_for("share_project", project_id=source_id),
                json={"target_user": student.username},
            )
            assert response.status_code == status.HTTP_201_CREATED

        # the shared user can see the project but cannot pass it on: the Lab
        # member role carries no Project.Distribute
        async with TestProjectOwnership._client_for(app, student) as student_client:
            response = await student_client.post(
                app.url_path_for("distribute_project", project_id=source_id),
                json={"name": "copy", "target_user": outsider.username},
            )
            assert response.status_code == status.HTTP_403_FORBIDDEN

    async def test_project_owner_can_read_and_clean_a_distribution_started_by_another_user(
        self, app: FastAPI, base_client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        await TestProjectOwnership._seed_collection_ace(db_session)
        student = await TestProjectOwnership._create_user_in_users_group(db_session, f"student-{uuid.uuid4().hex[:8]}")

        async with TestProjectOwnership._client_for(app, test_user) as teacher_client:
            response = await teacher_client.post(
                app.url_path_for("create_project"), json={"name": f"lab-{uuid.uuid4()}"}
            )
            source_id = response.json()["project_id"]

        # a superadmin distributes the teacher's project and may pick any
        # owner role (the width check does not apply to them)
        admin = await UsersRepository(db_session).get_user_by_username("admin")
        async with TestProjectOwnership._client_for(app, admin) as admin_client:
            response = await admin_client.post(
                app.url_path_for("distribute_project", project_id=source_id),
                json={"name": "copy", "target_user": student.username, "owner_role": "Administrator"},
            )
            assert response.status_code == status.HTTP_202_ACCEPTED
            distribution_id = response.json()["distribution_id"]
            job = await self._wait_for_distribution(app, admin_client, source_id, distribution_id)
            copy_id = job["results"][0]["project"]["project_id"]

        # the teacher did not start the distribution, but it is their project
        # it froze: they can read it and clean it up
        async with TestProjectOwnership._client_for(app, test_user) as teacher_client:
            response = await teacher_client.get(
                app.url_path_for("get_project_distribution", project_id=source_id, distribution_id=distribution_id)
            )
            assert response.status_code == status.HTTP_200_OK

            response = await teacher_client.get(app.url_path_for("get_project_distributions", project_id=source_id))
            assert {d["distribution_id"] for d in response.json()} == {distribution_id}

            response = await teacher_client.delete(
                app.url_path_for("delete_distribution_copies", project_id=source_id, distribution_id=distribution_id)
            )
            assert response.status_code == status.HTTP_200_OK
            assert all(result["project_exists"] is False for result in response.json()["results"])

            # with every copy gone the owner can unfreeze their project again
            response = await teacher_client.post(app.url_path_for("unfreeze_project", project_id=source_id))
            assert response.status_code == status.HTTP_200_OK

        # the copy is gone: only a superadmin can still probe its path (other
        # users lost their ACE with the deletion and are refused earlier)
        async with TestProjectOwnership._client_for(app, admin) as admin_client:
            response = await admin_client.get(app.url_path_for("get_project", project_id=copy_id))
            assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_recipient_can_delete_their_own_copy(
        self, app: FastAPI, base_client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        await TestProjectOwnership._seed_collection_ace(db_session)
        student = await TestProjectOwnership._create_user_in_users_group(db_session, f"student-{uuid.uuid4().hex[:8]}")
        _, copy_id = await self._distribute(app, test_user, student.username)

        # the copy belongs to its recipient: deleting it stays allowed (the
        # deletion guard is ownership-based, and the recipient is the owner)
        async with TestProjectOwnership._client_for(app, student) as student_client:
            response = await student_client.delete(app.url_path_for("delete_project", project_id=copy_id))
            assert response.status_code == status.HTTP_204_NO_CONTENT

    async def test_distribution_copy_does_not_inherit_resource_pools(
        self, app: FastAPI, base_client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        await TestProjectOwnership._seed_collection_ace(db_session)
        student = await TestProjectOwnership._create_user_in_users_group(db_session, f"student-{uuid.uuid4().hex[:8]}")
        source_id, copy_id = await self._distribute(app, test_user, student.username)

        # the source belongs to a pool
        pools_repo = ResourcePoolsRepository(db_session)
        pool = await pools_repo.create_resource_pool(ResourcePoolCreate(name=f"pool-{uuid.uuid4().hex[:8]}"))
        resource = await pools_repo.create_resource(
            ResourceCreate(resource_id=uuid.UUID(source_id), resource_type="project", name="lab")
        )
        await pools_repo.add_resource_to_pool(pool.resource_pool_id, resource)

        # a distributed copy is personal: no pool membership. A plain
        # duplicate keeps inheriting them.
        assert await pools_repo.get_resource_memberships(uuid.UUID(copy_id)) == []

        async with TestProjectOwnership._client_for(app, test_user) as teacher_client:
            response = await teacher_client.post(
                app.url_path_for("duplicate_project", project_id=source_id),
                json={"name": f"plain-copy-{uuid.uuid4()}"},
            )
            assert response.status_code == status.HTTP_201_CREATED
            plain_copy_id = response.json()["project_id"]
        memberships = await pools_repo.get_resource_memberships(uuid.UUID(plain_copy_id))
        assert {m.resource_pool_id for m in memberships} == {pool.resource_pool_id}

    async def test_node_level_freeze_on_distributed_copy(
        self, app: FastAPI, base_client: AsyncClient, db_session: AsyncSession, test_user: User, compute
    ) -> None:
        await TestProjectOwnership._seed_collection_ace(db_session)
        student = await TestProjectOwnership._create_user_in_users_group(db_session, f"student-{uuid.uuid4().hex[:8]}")
        _, copy_id = await self._distribute(app, test_user, student.username)

        # the node is part of the lab: the recipient opens the copy, then the
        # superadmin (who bypasses the privilege checks) adds the node so the
        # duplication itself stays on the fast path
        async with TestProjectOwnership._client_for(app, student) as student_client:
            response = await student_client.post(app.url_path_for("open_project", project_id=copy_id))
            assert response.status_code == status.HTTP_200_OK

        admin = await UsersRepository(db_session).get_user_by_username("admin")
        async with TestProjectOwnership._client_for(app, admin) as admin_client:
            compute_response = MagicMock()
            compute_response.json = {"console": 2048}
            compute.post = AsyncioMagicMock(return_value=compute_response)
            response = await admin_client.post(
                app.url_path_for("create_node", project_id=copy_id),
                json={
                    "name": "r1",
                    "node_type": "vpcs",
                    "compute_id": "example.com",
                    "properties": {},
                },
            )
            assert response.status_code == status.HTTP_201_CREATED
            node_id = response.json()["node_id"]

        compute.post = AsyncioMagicMock()
        async with TestProjectOwnership._client_for(app, student) as student_client:
            response = await student_client.get(app.url_path_for("get_node", project_id=copy_id, node_id=node_id))
            assert response.status_code == status.HTTP_200_OK

            # frozen: the reduced role has no Node.Modify
            response = await student_client.put(
                app.url_path_for("update_node", project_id=copy_id, node_id=node_id), json={"name": "hacked"}
            )
            assert response.status_code == status.HTTP_403_FORBIDDEN

            # usable: starting the node is a power operation, not a topology edit
            response = await student_client.post(
                app.url_path_for("start_node", project_id=copy_id, node_id=node_id), json={}
            )
            assert response.status_code == status.HTTP_200_OK

    @staticmethod
    async def _create_source_with_drawing(app: FastAPI, teacher: User) -> tuple[str, str]:
        """
        Create a project with one drawing. No nodes means no compute involved:
        the distribution stays on the fast directory-copy path.
        """

        async with TestProjectOwnership._client_for(app, teacher) as teacher_client:
            response = await teacher_client.post(
                app.url_path_for("create_project"), json={"name": f"lab-{uuid.uuid4()}"}
            )
            assert response.status_code == status.HTTP_201_CREATED
            source_id = response.json()["project_id"]

            response = await teacher_client.post(
                app.url_path_for("create_drawing", project_id=source_id),
                json={"svg": '<svg><rect width="200" height="100"></rect></svg>', "x": -128, "y": -10},
            )
            assert response.status_code == status.HTTP_201_CREATED
            return source_id, response.json()["drawing_id"]

    @staticmethod
    async def _distribute_from(
        app: FastAPI, teacher: User, source_id: str, student_username: str, **extra_fields
    ) -> str:
        """
        Distribute an existing project to one user and return the copy id.
        """

        async with TestProjectOwnership._client_for(app, teacher) as teacher_client:
            response = await teacher_client.post(
                app.url_path_for("distribute_project", project_id=source_id),
                json={"name": f"lab-copy-{uuid.uuid4()}", "target_user": student_username, **extra_fields},
            )
            assert response.status_code == status.HTTP_202_ACCEPTED
            distribution_id = response.json()["distribution_id"]
            job = await TestProjectDistribution._wait_for_distribution(app, teacher_client, source_id, distribution_id)
            assert job["total"] == 1
            results = job["results"]
            assert len(results) == 1
            assert results[0]["error"] is None
            return results[0]["project"]["project_id"]

    async def test_distributed_copy_locks_items_by_default(
        self, app: FastAPI, base_client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        await TestProjectOwnership._seed_collection_ace(db_session)
        student = await TestProjectOwnership._create_user_in_users_group(db_session, f"student-{uuid.uuid4().hex[:8]}")
        source_id, _ = await self._create_source_with_drawing(app, test_user)
        copy_id = await self._distribute_from(app, test_user, source_id, student.username)

        async with TestProjectOwnership._client_for(app, student) as student_client:
            # the copy ships locked: the client hides move and delete from the
            # start, instead of letting a drag end in a 403 and a ghost move
            response = await student_client.post(app.url_path_for("open_project", project_id=copy_id))
            assert response.status_code == status.HTTP_200_OK
            response = await student_client.get(app.url_path_for("get_drawings", project_id=copy_id))
            assert response.status_code == status.HTTP_200_OK
            drawings = response.json()
            assert len(drawings) == 1
            assert drawings[0]["locked"] is True

        # the source is untouched: the teacher keeps editing their lab
        async with TestProjectOwnership._client_for(app, test_user) as teacher_client:
            response = await teacher_client.post(app.url_path_for("open_project", project_id=source_id))
            assert response.status_code == status.HTTP_200_OK
            response = await teacher_client.get(app.url_path_for("get_drawings", project_id=source_id))
            assert response.status_code == status.HTTP_200_OK
            drawings = response.json()
            assert len(drawings) == 1
            assert drawings[0]["locked"] is False

    async def test_distributed_copy_unlocked_when_lock_topology_is_false(
        self, app: FastAPI, base_client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        await TestProjectOwnership._seed_collection_ace(db_session)
        student = await TestProjectOwnership._create_user_in_users_group(db_session, f"student-{uuid.uuid4().hex[:8]}")
        source_id, _ = await self._create_source_with_drawing(app, test_user)
        copy_id = await self._distribute_from(app, test_user, source_id, student.username, lock_topology=False)

        async with TestProjectOwnership._client_for(app, student) as student_client:
            response = await student_client.post(app.url_path_for("open_project", project_id=copy_id))
            assert response.status_code == status.HTTP_200_OK
            response = await student_client.get(app.url_path_for("get_drawings", project_id=copy_id))
            assert response.status_code == status.HTTP_200_OK
            drawings = response.json()
            assert len(drawings) == 1
            assert drawings[0]["locked"] is False

    async def test_distribution_keeps_source_locks_in_the_copy(
        self, app: FastAPI, base_client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        await TestProjectOwnership._seed_collection_ace(db_session)
        student = await TestProjectOwnership._create_user_in_users_group(db_session, f"student-{uuid.uuid4().hex[:8]}")
        source_id, _ = await self._create_source_with_drawing(app, test_user)

        # the teacher locks their source before distributing a modify-capable
        # role: the locks ride along with the copy
        async with TestProjectOwnership._client_for(app, test_user) as teacher_client:
            response = await teacher_client.post(app.url_path_for("open_project", project_id=source_id))
            assert response.status_code == status.HTTP_200_OK
            response = await teacher_client.post(app.url_path_for("lock_project", project_id=source_id))
            assert response.status_code == status.HTTP_204_NO_CONTENT

        copy_id = await self._distribute_from(app, test_user, source_id, student.username, lock_topology=False)

        async with TestProjectOwnership._client_for(app, student) as student_client:
            response = await student_client.post(app.url_path_for("open_project", project_id=copy_id))
            assert response.status_code == status.HTTP_200_OK
            response = await student_client.get(app.url_path_for("get_drawings", project_id=copy_id))
            assert response.status_code == status.HTTP_200_OK
            drawings = response.json()
            assert len(drawings) == 1
            assert drawings[0]["locked"] is True

    async def test_distribution_with_nodes_locks_and_restore_keeps_locked(
        self,
        app: FastAPI,
        base_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        compute,
    ) -> None:
        await TestProjectOwnership._seed_collection_ace(db_session)
        student = await TestProjectOwnership._create_user_in_users_group(db_session, f"student-{uuid.uuid4().hex[:8]}")

        # a node on a remote compute sends the copy through the export/import
        # fallback path: the lock must hold on both duplication paths
        compute_response = MagicMock()
        compute_response.json = {"console": 2048}
        compute.post = AsyncioMagicMock(return_value=compute_response)
        compute.delete = AsyncioMagicMock()
        # the export step lists the files the remote compute holds for the
        # project (a real compute answers a list, the bare mock answers None)
        compute.list_files = AsyncioMagicMock(return_value=[])
        async with TestProjectOwnership._client_for(app, test_user) as teacher_client:
            response = await teacher_client.post(
                app.url_path_for("create_project"), json={"name": f"lab-{uuid.uuid4()}"}
            )
            assert response.status_code == status.HTTP_201_CREATED
            source_id = response.json()["project_id"]
            response = await teacher_client.post(
                app.url_path_for("create_node", project_id=source_id),
                json={"name": "r1", "node_type": "vpcs", "compute_id": "example.com", "properties": {}},
            )
            assert response.status_code == status.HTTP_201_CREATED

        copy_id = await self._distribute_from(app, test_user, source_id, student.username)

        async with TestProjectOwnership._client_for(app, student) as student_client:
            response = await student_client.post(app.url_path_for("open_project", project_id=copy_id))
            assert response.status_code == status.HTTP_200_OK
            response = await student_client.get(app.url_path_for("get_nodes", project_id=copy_id))
            assert response.status_code == status.HTTP_200_OK
            nodes = response.json()
            assert len(nodes) == 1
            assert nodes[0]["locked"] is True

            # the lock is part of the template state: restoring the snapshot
            # (the way a recipient resets the lab) brings the items back
            # locked
            response = await student_client.get(app.url_path_for("get_snapshots", project_id=copy_id))
            snapshot_id = next(s["snapshot_id"] for s in response.json() if s["name"] == "template state")
            response = await student_client.post(
                app.url_path_for("restore_snapshot", project_id=copy_id, snapshot_id=snapshot_id)
            )
            assert response.status_code == status.HTTP_200_OK
            response = await student_client.get(app.url_path_for("get_nodes", project_id=copy_id))
            assert response.status_code == status.HTTP_200_OK
            nodes = response.json()
            assert len(nodes) == 1
            assert nodes[0]["locked"] is True

    async def test_remote_distribution_exports_the_project_once(
        self,
        app: FastAPI,
        base_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        compute,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        await TestProjectOwnership._seed_collection_ace(db_session)
        students = [
            await TestProjectOwnership._create_user_in_users_group(db_session, f"student-{uuid.uuid4().hex[:8]}")
            for _ in range(2)
        ]

        # count the exports of the job: the fallback path used to export the
        # project once per recipient
        real_export = project_module.export_project
        export_calls = []

        async def counting_export(*args, **kwargs):
            export_calls.append(1)
            return await real_export(*args, **kwargs)

        monkeypatch.setattr(project_module, "export_project", counting_export)

        # a node on a remote compute sends the copies through export/import
        compute_response = MagicMock()
        compute_response.json = {"console": 2048}
        compute.post = AsyncioMagicMock(return_value=compute_response)
        compute.delete = AsyncioMagicMock()
        compute.list_files = AsyncioMagicMock(return_value=[])
        async with TestProjectOwnership._client_for(app, test_user) as teacher_client:
            response = await teacher_client.post(
                app.url_path_for("create_project"), json={"name": f"lab-{uuid.uuid4()}"}
            )
            assert response.status_code == status.HTTP_201_CREATED
            source_id = response.json()["project_id"]
            response = await teacher_client.post(
                app.url_path_for("create_node", project_id=source_id),
                json={"name": "r1", "node_type": "vpcs", "compute_id": "example.com", "properties": {}},
            )
            assert response.status_code == status.HTTP_201_CREATED

            response = await teacher_client.post(
                app.url_path_for("distribute_project", project_id=source_id),
                json={"name": "lab1", "target_users": [student.username for student in students]},
            )
            assert response.status_code == status.HTTP_202_ACCEPTED
            distribution_id = response.json()["distribution_id"]
            job = await TestProjectDistribution._wait_for_distribution(app, teacher_client, source_id, distribution_id)

        assert job["total"] == 2
        assert [result["error"] for result in job["results"]] == [None, None]
        # one export for the job, not one per recipient
        assert len(export_calls) == 1

    async def test_distributing_a_closed_project_keeps_its_marker_definitions(
        self, app: FastAPI, base_client: AsyncClient, db_session: AsyncSession, test_user: User, controller
    ) -> None:
        await TestProjectOwnership._seed_collection_ace(db_session)
        student = await TestProjectOwnership._create_user_in_users_group(db_session, f"student-{uuid.uuid4().hex[:8]}")

        async with TestProjectOwnership._client_for(app, test_user) as teacher_client:
            response = await teacher_client.post(
                app.url_path_for("create_project"), json={"name": f"lab-{uuid.uuid4()}"}
            )
            source_id = response.json()["project_id"]
            response = await teacher_client.post(
                app.url_path_for("create_marker_definition", project_id=source_id),
                json={"name": "dns", "bpf": "udp port 53"},
            )
            assert response.status_code == status.HTTP_201_CREATED
            response = await teacher_client.post(app.url_path_for("close_project", project_id=source_id))
            assert response.status_code == status.HTTP_204_NO_CONTENT

            # freezing a closed project rewrites only its project fields: the
            # marker definitions live on disk and must survive the dump
            response = await teacher_client.post(
                app.url_path_for("distribute_project", project_id=source_id),
                json={"name": "lab1", "target_user": student.username},
            )
            assert response.status_code == status.HTTP_202_ACCEPTED
            distribution_id = response.json()["distribution_id"]
            job = await TestProjectDistribution._wait_for_distribution(app, teacher_client, source_id, distribution_id)
            assert job["results"][0]["error"] is None

        with open(controller.get_project(source_id).topology_file) as f:
            topology = json.load(f)
        assert "dns" in topology["marker_definitions"]

        # the copy was made from the closed template and carries the marker
        copy_id = job["results"][0]["project"]["project_id"]
        async with TestProjectOwnership._client_for(app, student) as student_client:
            response = await student_client.post(app.url_path_for("open_project", project_id=copy_id))
            assert response.status_code == status.HTTP_200_OK
            response = await student_client.get(app.url_path_for("get_marker_definitions", project_id=copy_id))
            assert response.status_code == status.HTTP_200_OK
            assert "dns" in response.json()

    async def test_distributing_a_closed_remote_project_is_not_an_error(
        self,
        app: FastAPI,
        base_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        compute,
    ) -> None:
        await TestProjectOwnership._seed_collection_ace(db_session)
        student = await TestProjectOwnership._create_user_in_users_group(db_session, f"student-{uuid.uuid4().hex[:8]}")

        compute_response = MagicMock()
        compute_response.json = {"console": 2048}
        compute.post = AsyncioMagicMock(return_value=compute_response)
        compute.delete = AsyncioMagicMock()
        compute.list_files = AsyncioMagicMock(return_value=[])
        async with TestProjectOwnership._client_for(app, test_user) as teacher_client:
            response = await teacher_client.post(
                app.url_path_for("create_project"), json={"name": f"lab-{uuid.uuid4()}"}
            )
            source_id = response.json()["project_id"]
            response = await teacher_client.post(
                app.url_path_for("create_node", project_id=source_id),
                json={"name": "r1", "node_type": "vpcs", "compute_id": "example.com", "properties": {}},
            )
            assert response.status_code == status.HTTP_201_CREATED
            response = await teacher_client.post(app.url_path_for("close_project", project_id=source_id))
            assert response.status_code == status.HTTP_204_NO_CONTENT

            # a closed project answers its computes from the topology file:
            # deciding the copy mode must not choke on them (it used to read
            # compute.id off plain dicts)
            response = await teacher_client.post(
                app.url_path_for("distribute_project", project_id=source_id),
                json={"name": "lab1", "target_user": student.username},
            )
            assert response.status_code == status.HTTP_202_ACCEPTED
            distribution_id = response.json()["distribution_id"]
            job = await TestProjectDistribution._wait_for_distribution(app, teacher_client, source_id, distribution_id)
            assert job["results"][0]["error"] is None

    async def test_distribute_project_to_group(
        self, app: FastAPI, base_client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        await TestProjectOwnership._seed_collection_ace(db_session)

        # a group with two members
        users_repo = UsersRepository(db_session)
        group = await users_repo.create_user_group(schemas.UserGroupCreate(name=f"lab-{uuid.uuid4().hex[:8]}"))
        members = []
        for name in ("alice", "bob"):
            member = await TestProjectOwnership._create_user_in_users_group(
                db_session, f"{name}-{uuid.uuid4().hex[:8]}"
            )
            await users_repo.add_member_to_user_group(group.user_group_id, member)
            members.append(member)

        async with TestProjectOwnership._client_for(app, test_user) as teacher_client:
            response = await teacher_client.post(
                app.url_path_for("create_project"), json={"name": f"lab-{uuid.uuid4()}"}
            )
            source_id = response.json()["project_id"]

            response = await teacher_client.post(
                app.url_path_for("distribute_project", project_id=source_id),
                json={"name": "lab1", "target_group": group.name},
            )
            assert response.status_code == status.HTTP_202_ACCEPTED
            distribution_id = response.json()["distribution_id"]
            job = await TestProjectDistribution._wait_for_distribution(app, teacher_client, source_id, distribution_id)
            assert job["total"] == 2
            results = job["results"]
            assert {result["username"] for result in results} == {member.username for member in members}
            copy_ids = {}
            for result in results:
                assert result["error"] is None
                assert result["project"]["created_by"] == result["username"]
                assert result["project"]["name"] == f"lab1-{result['username']}"
                copy_ids[result["username"]] = result["project"]["project_id"]

        # every member owns a private copy with the reduced role and the
        # template state snapshot
        rbac_repo = RbacRepository(db_session)
        lab_member_role = await rbac_repo.get_role_by_name("Lab member")
        for member in members:
            ace = await rbac_repo.get_ace_by_path(f"/projects/{copy_ids[member.username]}")
            assert str(ace.user_id) == str(member.user_id)
            assert str(ace.role_id) == str(lab_member_role.role_id)

            async with TestProjectOwnership._client_for(app, member) as member_client:
                response = await member_client.get(app.url_path_for("get_projects"))
                visible = {p["project_id"] for p in response.json()}
                assert copy_ids[member.username] in visible
                # the other member's copy stays private
                other = next(m for m in members if m.username != member.username)
                assert copy_ids[other.username] not in visible

                response = await member_client.get(
                    app.url_path_for("get_snapshots", project_id=copy_ids[member.username])
                )
                assert "template state" in {s["name"] for s in response.json()}

    async def test_group_distribution_reports_member_failures(
        self, app: FastAPI, base_client: AsyncClient, db_session: AsyncSession, test_user: User, controller
    ) -> None:
        await TestProjectOwnership._seed_collection_ace(db_session)

        users_repo = UsersRepository(db_session)
        group = await users_repo.create_user_group(schemas.UserGroupCreate(name=f"lab-{uuid.uuid4().hex[:8]}"))
        members = []
        for name in ("alice", "bob"):
            member = await TestProjectOwnership._create_user_in_users_group(
                db_session, f"{name}-{uuid.uuid4().hex[:8]}"
            )
            await users_repo.add_member_to_user_group(group.user_group_id, member)
            members.append(member)

        async with TestProjectOwnership._client_for(app, test_user) as teacher_client:
            response = await teacher_client.post(
                app.url_path_for("create_project"), json={"name": f"lab-{uuid.uuid4()}"}
            )
            source_id = response.json()["project_id"]
            source = controller.get_project(source_id)
            original_duplicate = source.duplicate
            calls = 0

            async def fail_on_second_call(**kwargs):
                nonlocal calls
                calls += 1
                if calls > 1:
                    raise ControllerError("boom")
                return await original_duplicate(**kwargs)

            source.duplicate = fail_on_second_call  # type: ignore[method-assign]
            try:
                response = await teacher_client.post(
                    app.url_path_for("distribute_project", project_id=source_id),
                    json={"name": "lab1", "target_group": group.name},
                )
                assert response.status_code == status.HTTP_202_ACCEPTED
                distribution_id = response.json()["distribution_id"]
                job = await TestProjectDistribution._wait_for_distribution(
                    app, teacher_client, source_id, distribution_id
                )
            finally:
                source.duplicate = original_duplicate  # type: ignore[method-assign]

        # one member got their copy, the failed one is reported with the error
        results = job["results"]
        assert len(results) == 2
        by_username = {result["username"]: result for result in results}
        failed = [result for result in results if result["error"] is not None]
        succeeded = [result for result in results if result["project"] is not None]
        assert len(failed) == 1 and len(succeeded) == 1
        assert failed[0]["error"]["message"] == "boom"
        assert succeeded[0]["project"]["created_by"] == succeeded[0]["username"]
        assert by_username[failed[0]["username"]]["project"] is None

    async def test_distribute_project_to_multiple_users(
        self, app: FastAPI, base_client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        await TestProjectOwnership._seed_collection_ace(db_session)
        student1 = await TestProjectOwnership._create_user_in_users_group(db_session, f"alice-{uuid.uuid4().hex[:8]}")
        student2 = await TestProjectOwnership._create_user_in_users_group(db_session, f"bob-{uuid.uuid4().hex[:8]}")

        async with TestProjectOwnership._client_for(app, test_user) as teacher_client:
            response = await teacher_client.post(
                app.url_path_for("create_project"), json={"name": f"lab-{uuid.uuid4()}"}
            )
            source_id = response.json()["project_id"]

            response = await teacher_client.post(
                app.url_path_for("distribute_project", project_id=source_id),
                json={"name": "lab1", "target_users": [student2.username, student1.username, student2.username]},
            )
            assert response.status_code == status.HTTP_202_ACCEPTED
            distribution_id = response.json()["distribution_id"]
            job = await TestProjectDistribution._wait_for_distribution(app, teacher_client, source_id, distribution_id)
            assert job["total"] == 2
            results = job["results"]
            # duplicates in the list are collapsed: one copy per user
            assert {result["username"] for result in results} == {student1.username, student2.username}
            for result in results:
                assert result["error"] is None
                assert result["project"]["created_by"] == result["username"]
                assert result["project"]["name"] == f"lab1-{result['username']}"

        rbac_repo = RbacRepository(db_session)
        lab_member_role = await rbac_repo.get_role_by_name("Lab member")
        for result in results:
            ace = await rbac_repo.get_ace_by_path(f"/projects/{result['project']['project_id']}")
            assert str(ace.role_id) == str(lab_member_role.role_id)

    async def test_multiple_users_distribution_fails_fast_on_unknown_user(
        self, app: FastAPI, base_client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        await TestProjectOwnership._seed_collection_ace(db_session)
        student = await TestProjectOwnership._create_user_in_users_group(db_session, f"alice-{uuid.uuid4().hex[:8]}")

        async with TestProjectOwnership._client_for(app, test_user) as teacher_client:
            response = await teacher_client.post(
                app.url_path_for("create_project"), json={"name": f"lab-{uuid.uuid4()}"}
            )
            source_id = response.json()["project_id"]

            response = await teacher_client.post(
                app.url_path_for("distribute_project", project_id=source_id),
                json={"name": "lab1", "target_users": [student.username, "missing-user"]},
            )
            assert response.status_code == status.HTTP_404_NOT_FOUND

        # nothing was distributed: a typo in the list must not half-succeed
        async with TestProjectOwnership._client_for(app, student) as student_client:
            response = await student_client.get(app.url_path_for("get_projects"))
            assert source_id not in {p["project_id"] for p in response.json()}
            assert all(not p["name"].startswith("lab1-") for p in response.json())

    async def test_distribution_job_visibility(
        self, app: FastAPI, base_client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        await TestProjectOwnership._seed_collection_ace(db_session)
        student = await TestProjectOwnership._create_user_in_users_group(db_session, f"student-{uuid.uuid4().hex[:8]}")

        async with TestProjectOwnership._client_for(app, test_user) as teacher_client:
            response = await teacher_client.post(
                app.url_path_for("create_project"), json={"name": f"lab-{uuid.uuid4()}"}
            )
            source_id = response.json()["project_id"]

            response = await teacher_client.post(
                app.url_path_for("distribute_project", project_id=source_id),
                json={"name": "lab1", "target_user": student.username},
            )
            assert response.status_code == status.HTTP_202_ACCEPTED
            distribution_id = response.json()["distribution_id"]
            job = await TestProjectDistribution._wait_for_distribution(app, teacher_client, source_id, distribution_id)
            assert job["created_by"] == test_user.username
            assert job["total"] == 1 and job["completed"] == 1

            # the job is listed with the project
            response = await teacher_client.get(app.url_path_for("get_project_distributions", project_id=source_id))
            assert response.status_code == status.HTTP_200_OK
            assert distribution_id in {job["distribution_id"] for job in response.json()}

            # an unknown distribution id is a 404
            response = await teacher_client.get(
                app.url_path_for("get_project_distribution", project_id=source_id, distribution_id=str(uuid.uuid4()))
            )
            assert response.status_code == status.HTTP_404_NOT_FOUND

        # a user without access to the source project cannot read the job
        async with TestProjectOwnership._client_for(app, student) as student_client:
            response = await student_client.get(
                app.url_path_for("get_project_distribution", project_id=source_id, distribution_id=distribution_id)
            )
            assert response.status_code == status.HTTP_403_FORBIDDEN

    async def test_cancel_distribution_stops_before_next_recipient(
        self,
        app: FastAPI,
        base_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        await TestProjectOwnership._seed_collection_ace(db_session)
        students = [
            await TestProjectOwnership._create_user_in_users_group(db_session, f"student-{uuid.uuid4().hex[:8]}")
            for _ in range(3)
        ]

        # hold the first copy in flight until the test lets it go, so the
        # cancel request lands while a copy is being made
        first_copy_started = asyncio.Event()
        release_first_copy = asyncio.Event()
        real_copy = projects_routes._distribute_project_copy
        copies_attempted = 0

        # pass-through signature: the wrapper only counts and holds calls, so
        # a new parameter on the wrapped function cannot break it again
        async def blocking_copy(*args, **kwargs):
            nonlocal copies_attempted
            copies_attempted += 1
            if copies_attempted == 1:
                first_copy_started.set()
                # bounded so a failed test cannot leave the job waiting forever
                await asyncio.wait_for(release_first_copy.wait(), timeout=30)
            return await real_copy(*args, **kwargs)

        monkeypatch.setattr(projects_routes, "_distribute_project_copy", blocking_copy)

        async with TestProjectOwnership._client_for(app, test_user) as teacher_client:
            response = await teacher_client.post(
                app.url_path_for("create_project"), json={"name": f"lab-{uuid.uuid4()}"}
            )
            assert response.status_code == status.HTTP_201_CREATED
            source_id = response.json()["project_id"]

            response = await teacher_client.post(
                app.url_path_for("distribute_project", project_id=source_id),
                json={"name": "lab1", "target_users": [student.username for student in students]},
            )
            assert response.status_code == status.HTTP_202_ACCEPTED
            distribution_id = response.json()["distribution_id"]

            # bounded: a broken copy call must fail the test, not hang it
            await asyncio.wait_for(first_copy_started.wait(), timeout=10)

            # the cancel request lands while the first copy is in flight: the
            # job switches to cancelling, and a repeated request changes
            # nothing (it is not an error)
            cancel_url = app.url_path_for(
                "cancel_project_distribution", project_id=source_id, distribution_id=distribution_id
            )
            response = await teacher_client.delete(cancel_url)
            assert response.status_code == status.HTTP_200_OK
            assert response.json()["status"] == "cancelling"
            response = await teacher_client.delete(cancel_url)
            assert response.status_code == status.HTTP_200_OK
            assert response.json()["status"] == "cancelling"

            # while the copy in flight is held, the job keeps reporting that
            # it is cancelling, not cancelled
            response = await teacher_client.get(
                app.url_path_for("get_project_distribution", project_id=source_id, distribution_id=distribution_id)
            )
            assert response.status_code == status.HTTP_200_OK
            assert response.json()["status"] == "cancelling"

            release_first_copy.set()
            job = await TestProjectDistribution._wait_for_cancelled(app, teacher_client, source_id, distribution_id)

        # the copy in flight completed and is a real project, the two
        # remaining recipients were never started
        assert job["total"] == 3
        assert job["completed"] == 1
        assert [result["username"] for result in job["results"]] == [students[0].username]
        assert job["results"][0]["error"] is None
        assert copies_attempted == 1
        copy_id = job["results"][0]["project"]["project_id"]
        async with TestProjectOwnership._client_for(app, students[0]) as student_client:
            response = await student_client.get(app.url_path_for("get_project", project_id=copy_id))
            assert response.status_code == status.HTTP_200_OK

    async def test_deleting_a_finished_distribution_removes_its_record(
        self, app: FastAPI, base_client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        await TestProjectOwnership._seed_collection_ace(db_session)
        student = await TestProjectOwnership._create_user_in_users_group(db_session, f"student-{uuid.uuid4().hex[:8]}")

        async with TestProjectOwnership._client_for(app, test_user) as teacher_client:
            response = await teacher_client.post(
                app.url_path_for("create_project"), json={"name": f"lab-{uuid.uuid4()}"}
            )
            source_id = response.json()["project_id"]
            response = await teacher_client.post(
                app.url_path_for("distribute_project", project_id=source_id),
                json={"name": "lab1", "target_user": student.username},
            )
            assert response.status_code == status.HTTP_202_ACCEPTED
            distribution_id = response.json()["distribution_id"]
            job = await TestProjectDistribution._wait_for_distribution(app, teacher_client, source_id, distribution_id)
            copy_id = job["results"][0]["project"]["project_id"]

            # the record is how the copies are found for a bulk cleanup: it
            # cannot be removed while a copy still exists
            response = await teacher_client.delete(
                app.url_path_for("cancel_project_distribution", project_id=source_id, distribution_id=distribution_id)
            )
            assert response.status_code == status.HTTP_409_CONFLICT
            assert student.username in response.json()["message"]

            # once the recipient deleted their copy the record can go, and
            # the distribution leaves the history
            async with TestProjectOwnership._client_for(app, student) as student_client:
                response = await student_client.delete(app.url_path_for("delete_project", project_id=copy_id))
                assert response.status_code == status.HTTP_204_NO_CONTENT

            response = await teacher_client.delete(
                app.url_path_for("cancel_project_distribution", project_id=source_id, distribution_id=distribution_id)
            )
            assert response.status_code == status.HTTP_204_NO_CONTENT

            response = await teacher_client.get(app.url_path_for("get_project_distributions", project_id=source_id))
            assert response.status_code == status.HTTP_200_OK
            assert response.json() == []

            response = await teacher_client.get(
                app.url_path_for("get_project_distribution", project_id=source_id, distribution_id=distribution_id)
            )
            assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_plain_duplicate_of_a_frozen_template_is_not_frozen(
        self, app: FastAPI, base_client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        await TestProjectOwnership._seed_collection_ace(db_session)
        student = await TestProjectOwnership._create_user_in_users_group(db_session, f"student-{uuid.uuid4().hex[:8]}")
        source_id, _ = await self._distribute(app, test_user, student.username)

        # the teacher can duplicate the frozen template: the duplicate is a
        # normal project, not a second frozen template
        async with TestProjectOwnership._client_for(app, test_user) as teacher_client:
            response = await teacher_client.post(
                app.url_path_for("duplicate_project", project_id=source_id),
                json={"name": f"variant-{uuid.uuid4()}"},
            )
            assert response.status_code == status.HTTP_201_CREATED
            duplicate = response.json()
            assert duplicate["frozen"] is False
            assert duplicate["distribution_master_id"] is None

            # and it is editable right away
            response = await teacher_client.put(
                app.url_path_for("update_project", project_id=duplicate["project_id"]),
                json={"name": "variant-renamed"},
            )
            assert response.status_code == status.HTTP_200_OK

    async def test_unfreeze_does_not_depend_on_distribution_records(
        self, app: FastAPI, base_client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        await TestProjectOwnership._seed_collection_ace(db_session)
        student = await TestProjectOwnership._create_user_in_users_group(db_session, f"student-{uuid.uuid4().hex[:8]}")

        async with TestProjectOwnership._client_for(app, test_user) as teacher_client:
            response = await teacher_client.post(
                app.url_path_for("create_project"), json={"name": f"lab-{uuid.uuid4()}"}
            )
            source_id = response.json()["project_id"]
            response = await teacher_client.post(
                app.url_path_for("distribute_project", project_id=source_id),
                json={"name": "lab1", "target_user": student.username},
            )
            distribution_id = response.json()["distribution_id"]
            job = await TestProjectDistribution._wait_for_distribution(app, teacher_client, source_id, distribution_id)
            copy_id = job["results"][0]["project"]["project_id"]

            # a record can vanish behind the API (a direct database cleanup,
            # or a crash before the write-through): the copy marker is the
            # authority, so the template stays locked
            await DistributionRecordsRepository(db_session).delete_record(UUID(distribution_id))
            response = await teacher_client.post(app.url_path_for("unfreeze_project", project_id=source_id))
            assert response.status_code == status.HTTP_409_CONFLICT
            assert student.username in response.json()["message"]

        # once the copy is gone, the marker scan finds nothing left
        async with TestProjectOwnership._client_for(app, student) as student_client:
            response = await student_client.delete(app.url_path_for("delete_project", project_id=copy_id))
            assert response.status_code == status.HTTP_204_NO_CONTENT

        async with TestProjectOwnership._client_for(app, test_user) as teacher_client:
            response = await teacher_client.post(app.url_path_for("unfreeze_project", project_id=source_id))
            assert response.status_code == status.HTTP_200_OK
            assert response.json()["frozen"] is False

    async def test_global_delete_of_a_record_with_live_copies_is_refused(
        self, app: FastAPI, base_client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        await TestProjectOwnership._seed_collection_ace(db_session)
        student = await TestProjectOwnership._create_user_in_users_group(db_session, f"student-{uuid.uuid4().hex[:8]}")

        async with TestProjectOwnership._client_for(app, test_user) as teacher_client:
            response = await teacher_client.post(
                app.url_path_for("create_project"), json={"name": f"lab-{uuid.uuid4()}"}
            )
            source_id = response.json()["project_id"]
            response = await teacher_client.post(
                app.url_path_for("distribute_project", project_id=source_id),
                json={"name": "lab1", "target_user": student.username},
            )
            distribution_id = response.json()["distribution_id"]
            job = await TestProjectDistribution._wait_for_distribution(app, teacher_client, source_id, distribution_id)
            copy_id = job["results"][0]["project"]["project_id"]

            # the global history endpoint is protected the same way as the
            # per-project one: the record locates the copies for a cleanup
            response = await teacher_client.delete(
                app.url_path_for("delete_distribution", distribution_id=distribution_id)
            )
            assert response.status_code == status.HTTP_409_CONFLICT
            assert student.username in response.json()["message"]

        async with TestProjectOwnership._client_for(app, student) as student_client:
            response = await student_client.delete(app.url_path_for("delete_project", project_id=copy_id))
            assert response.status_code == status.HTTP_204_NO_CONTENT

        async with TestProjectOwnership._client_for(app, test_user) as teacher_client:
            response = await teacher_client.delete(
                app.url_path_for("delete_distribution", distribution_id=distribution_id)
            )
            assert response.status_code == status.HTTP_204_NO_CONTENT

    async def test_distribution_history_flags_deleted_copies(
        self, app: FastAPI, base_client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        await TestProjectOwnership._seed_collection_ace(db_session)
        student = await TestProjectOwnership._create_user_in_users_group(db_session, f"student-{uuid.uuid4().hex[:8]}")
        source_id, copy_id = await self._distribute(app, test_user, student.username)

        async with TestProjectOwnership._client_for(app, test_user) as teacher_client:
            response = await teacher_client.get(app.url_path_for("get_project_distributions", project_id=source_id))
            entry = response.json()[0]
            assert entry["results"][0]["project_exists"] is True

        # the recipient deletes their copy: the history entry stays and now
        # flags the copy as gone (a directory removal has the same effect)
        async with TestProjectOwnership._client_for(app, student) as student_client:
            response = await student_client.delete(app.url_path_for("delete_project", project_id=copy_id))
            assert response.status_code == status.HTTP_204_NO_CONTENT

        async with TestProjectOwnership._client_for(app, test_user) as teacher_client:
            response = await teacher_client.get(app.url_path_for("get_project_distributions", project_id=source_id))
            entry = response.json()[0]
            assert entry["results"][0]["project_exists"] is False

    async def test_deleting_a_project_removes_its_distribution_history(
        self, app: FastAPI, base_client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        await TestProjectOwnership._seed_collection_ace(db_session)
        student = await TestProjectOwnership._create_user_in_users_group(db_session, f"student-{uuid.uuid4().hex[:8]}")
        source_id, copy_id = await self._distribute(app, test_user, student.username)

        records_repo = DistributionRecordsRepository(db_session)
        assert await records_repo.get_records_for_project(UUID(source_id))

        async with TestProjectOwnership._client_for(app, test_user) as teacher_client:
            # a distributed template cannot be deleted while a copy exists:
            # the copies' disks may be overlays of its files
            response = await teacher_client.delete(app.url_path_for("delete_project", project_id=source_id))
            assert response.status_code == status.HTTP_409_CONFLICT

        # the recipient deletes their copy, then the template can go
        async with TestProjectOwnership._client_for(app, student) as student_client:
            response = await student_client.delete(app.url_path_for("delete_project", project_id=copy_id))
            assert response.status_code == status.HTTP_204_NO_CONTENT

        async with TestProjectOwnership._client_for(app, test_user) as teacher_client:
            response = await teacher_client.delete(app.url_path_for("delete_project", project_id=source_id))
            assert response.status_code == status.HTTP_204_NO_CONTENT

        assert await records_repo.get_records_for_project(UUID(source_id)) == []

    async def test_global_distribution_history(
        self, app: FastAPI, base_client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        await TestProjectOwnership._seed_collection_ace(db_session)
        student = await TestProjectOwnership._create_user_in_users_group(db_session, f"student-{uuid.uuid4().hex[:8]}")
        source_id, _ = await self._distribute(app, test_user, student.username)

        async with TestProjectOwnership._client_for(app, test_user) as teacher_client:
            response = await teacher_client.get(app.url_path_for("get_project", project_id=source_id))
            source_name = response.json()["name"]

            # the cross-project listing returns the caller's own entries,
            # with the name of the distributed project
            response = await teacher_client.get(app.url_path_for("list_distributions"))
            assert response.status_code == status.HTTP_200_OK
            entries = response.json()
            assert all(entry["created_by"] == test_user.username for entry in entries)
            mine = [entry for entry in entries if entry["project_id"] == source_id]
            assert mine and mine[0]["project_name"] == source_name

        # another user does not see the teacher's entries
        async with TestProjectOwnership._client_for(app, student) as student_client:
            response = await student_client.get(app.url_path_for("list_distributions"))
            assert response.status_code == status.HTTP_200_OK
            assert source_id not in {entry["project_id"] for entry in response.json()}

        # a superadmin sees everyone's entries
        admin = await UsersRepository(db_session).get_user_by_username("admin")
        async with TestProjectOwnership._client_for(app, admin) as admin_client:
            response = await admin_client.get(app.url_path_for("list_distributions"))
            assert response.status_code == status.HTTP_200_OK
            assert source_id in {entry["project_id"] for entry in response.json()}

    async def test_global_delete_of_an_orphaned_record(
        self, app: FastAPI, base_client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        await TestProjectOwnership._seed_collection_ace(db_session)

        # a record whose project vanished without the API (its directory was
        # removed directly): unreachable from the per-project endpoints
        orphan_id = uuid.uuid4()
        records_repo = DistributionRecordsRepository(db_session)
        await records_repo.create_record(orphan_id, uuid.uuid4(), "lab1", test_user.username, 1)

        async with TestProjectOwnership._client_for(app, test_user) as teacher_client:
            response = await teacher_client.get(app.url_path_for("list_distributions"))
            entries = {entry["distribution_id"]: entry for entry in response.json()}
            assert entries[str(orphan_id)]["project_name"] is None

            response = await teacher_client.delete(app.url_path_for("delete_distribution", distribution_id=orphan_id))
            assert response.status_code == status.HTTP_204_NO_CONTENT

            response = await teacher_client.get(app.url_path_for("list_distributions"))
            assert str(orphan_id) not in {entry["distribution_id"] for entry in response.json()}

    async def test_cancel_distribution_of_another_user_is_rejected(
        self,
        app: FastAPI,
        base_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        await TestProjectOwnership._seed_collection_ace(db_session)
        student = await TestProjectOwnership._create_user_in_users_group(db_session, f"student-{uuid.uuid4().hex[:8]}")
        other_teacher = await TestProjectOwnership._create_user_in_users_group(
            db_session, f"teacher-{uuid.uuid4().hex[:8]}"
        )

        # hold the job open so the cancel requests reach a running job
        copy_started = asyncio.Event()
        release_copy = asyncio.Event()
        real_copy = projects_routes._distribute_project_copy

        # pass-through signature: see test_cancel_distribution_stops_before_next_recipient
        async def blocking_copy(*args, **kwargs):
            copy_started.set()
            await asyncio.wait_for(release_copy.wait(), timeout=30)
            return await real_copy(*args, **kwargs)

        monkeypatch.setattr(projects_routes, "_distribute_project_copy", blocking_copy)

        async with TestProjectOwnership._client_for(app, test_user) as teacher_client:
            response = await teacher_client.post(
                app.url_path_for("create_project"), json={"name": f"lab-{uuid.uuid4()}"}
            )
            source_id = response.json()["project_id"]
            response = await teacher_client.post(
                app.url_path_for("distribute_project", project_id=source_id),
                json={"name": "lab1", "target_user": student.username},
            )
            assert response.status_code == status.HTTP_202_ACCEPTED
            distribution_id = response.json()["distribution_id"]
            await asyncio.wait_for(copy_started.wait(), timeout=10)

            # an unknown distribution id is a 404
            response = await teacher_client.delete(
                app.url_path_for("cancel_project_distribution", project_id=source_id, distribution_id=str(uuid.uuid4()))
            )
            assert response.status_code == status.HTTP_404_NOT_FOUND

            # another user cannot cancel someone else's job
            async with TestProjectOwnership._client_for(app, other_teacher) as other_client:
                response = await other_client.delete(
                    app.url_path_for(
                        "cancel_project_distribution", project_id=source_id, distribution_id=distribution_id
                    )
                )
                assert response.status_code == status.HTTP_403_FORBIDDEN

            release_copy.set()
            await TestProjectDistribution._wait_for_distribution(app, teacher_client, source_id, distribution_id)

    async def test_group_distribution_validation(
        self, app: FastAPI, base_client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        await TestProjectOwnership._seed_collection_ace(db_session)

        async with TestProjectOwnership._client_for(app, test_user) as teacher_client:
            response = await teacher_client.post(
                app.url_path_for("create_project"), json={"name": f"lab-{uuid.uuid4()}"}
            )
            source_id = response.json()["project_id"]

            # a distribution targets one kind of recipient, never several
            response = await teacher_client.post(
                app.url_path_for("distribute_project", project_id=source_id),
                json={"name": "copy", "target_user": "user1", "target_group": "Users"},
            )
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

            response = await teacher_client.post(
                app.url_path_for("distribute_project", project_id=source_id),
                json={"name": "copy", "target_user": "user1", "target_users": ["user2"]},
            )
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

            response = await teacher_client.post(
                app.url_path_for("distribute_project", project_id=source_id),
                json={"name": "copy", "target_group": "missing-group"},
            )
            assert response.status_code == status.HTTP_404_NOT_FOUND

            # an empty list of users is rejected at validation time
            response = await teacher_client.post(
                app.url_path_for("distribute_project", project_id=source_id),
                json={"name": "copy", "target_users": []},
            )
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

            # a distribution without any target is rejected as well
            response = await teacher_client.post(
                app.url_path_for("distribute_project", project_id=source_id),
                json={"name": "copy"},
            )
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

            # the built-in "Users" group has the admin as member, but an empty
            # group must be rejected
            empty_group = await UsersRepository(db_session).create_user_group(
                schemas.UserGroupCreate(name=f"empty-{uuid.uuid4().hex[:8]}")
            )
            response = await teacher_client.post(
                app.url_path_for("distribute_project", project_id=source_id),
                json={"name": "copy", "target_group": empty_group.name},
            )
            assert response.status_code == status.HTTP_409_CONFLICT

    async def test_distribution_history_survives_a_controller_restart(
        self, app: FastAPI, base_client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        await TestProjectOwnership._seed_collection_ace(db_session)
        student = await TestProjectOwnership._create_user_in_users_group(db_session, f"student-{uuid.uuid4().hex[:8]}")
        source_id, _ = await self._distribute(app, test_user, student.username)

        async with TestProjectOwnership._client_for(app, test_user) as teacher_client:
            # what a controller restart does to the live registry: the jobs
            # are gone, the persisted records stay
            DistributionRegistry.instance()._jobs.clear()

            response = await teacher_client.get(app.url_path_for("get_project_distributions", project_id=source_id))
            assert response.status_code == status.HTTP_200_OK
            history = response.json()
            assert len(history) == 1
            entry = history[0]
            assert entry["status"] == "completed"
            assert entry["total"] == 1 and entry["completed"] == 1
            assert entry["created_by"] == test_user.username
            assert entry["created_at"] is not None
            assert entry["results"][0]["username"] == student.username
            assert entry["results"][0]["project"] is not None

            # one distribution also stays readable on its own endpoint
            response = await teacher_client.get(
                app.url_path_for(
                    "get_project_distribution", project_id=source_id, distribution_id=entry["distribution_id"]
                )
            )
            assert response.status_code == status.HTTP_200_OK
            assert response.json()["status"] == "completed"

    async def test_distribution_interrupted_by_a_restart_is_closed_out(
        self, app: FastAPI, base_client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        await TestProjectOwnership._seed_collection_ace(db_session)

        async with TestProjectOwnership._client_for(app, test_user) as teacher_client:
            response = await teacher_client.post(
                app.url_path_for("create_project"), json={"name": f"lab-{uuid.uuid4()}"}
            )
            source_id = response.json()["project_id"]

        # records left "running" and "cancelling" by a restart: their jobs
        # are not in the live registry and will never update the rows again
        records_repo = DistributionRecordsRepository(db_session)
        running_id = uuid.uuid4()
        cancelling_id = uuid.uuid4()
        await records_repo.create_record(running_id, UUID(source_id), "lab1", test_user.username, 2)
        await records_repo.create_record(cancelling_id, UUID(source_id), "lab2", test_user.username, 2)
        await records_repo.update_record(cancelling_id, "cancelling", None, True, [])

        async with TestProjectOwnership._client_for(app, test_user) as teacher_client:
            response = await teacher_client.get(app.url_path_for("get_project_distributions", project_id=source_id))
            assert response.status_code == status.HTTP_200_OK
            entries = {entry["distribution_id"]: entry for entry in response.json()}
            interrupted = entries[str(running_id)]
            assert interrupted["status"] == "failed"
            assert interrupted["error"] is not None
            cancelled = entries[str(cancelling_id)]
            assert cancelled["status"] == "cancelled"

    async def test_distribution_creates_thin_overlay_copies(
        self,
        app: FastAPI,
        base_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        controller,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        await TestProjectOwnership._seed_collection_ace(db_session)
        student = await TestProjectOwnership._create_user_in_users_group(db_session, f"student-{uuid.uuid4().hex[:8]}")

        # one QEMU node directory on the template: a disk image and a plain
        # config file, plus an old snapshot the copy must not inherit
        async with TestProjectOwnership._client_for(app, test_user) as teacher_client:
            response = await teacher_client.post(
                app.url_path_for("create_project"), json={"name": f"lab-{uuid.uuid4()}"}
            )
            source_id = response.json()["project_id"]
        source = controller.get_project(source_id)
        node_id = "5e2f2b7c-0000-0000-0000-000000000002"
        qemu_dir = os.path.join(source.path, "project-files", "qemu", node_id)
        os.makedirs(qemu_dir)
        with open(os.path.join(qemu_dir, "hda_disk.qcow2"), "w") as f:
            f.write("template disk")
        with open(os.path.join(qemu_dir, "config.txt"), "w") as f:
            f.write("hostname r1")
        snapshots_dir = os.path.join(source.path, "snapshots")
        os.makedirs(snapshots_dir)
        with open(os.path.join(snapshots_dir, "old-lab.gns3project"), "w") as f:
            f.write("an old snapshot zip")

        # stand-in disk plumbing: the overlay creation is unit-tested in
        # test_qemu_overlay.py, here only its placement matters
        created_overlays = []

        def fake_image_info(qemu_img, path):
            return {"format": "qcow2", "virtual-size": 42949632} if path.endswith(".qcow2") else None

        def fake_create_overlay(qemu_img, backing_file, overlay_file, info):
            created_overlays.append((backing_file, overlay_file))
            with open(overlay_file, "w") as f:
                f.write("thin overlay")

        monkeypatch.setattr(qemu_overlay, "find_qemu_img", lambda: "/fake/qemu-img")
        monkeypatch.setattr(qemu_overlay, "_image_info", fake_image_info)
        monkeypatch.setattr(qemu_overlay, "_create_overlay", fake_create_overlay)

        copy_id = await self._distribute_from(app, test_user, source_id, student.username)

        # the copy's disk is a thin overlay pointing at the template's disk
        assert len(created_overlays) == 1
        backing_file, overlay_file = created_overlays[0]
        assert backing_file == os.path.join(qemu_dir, "hda_disk.qcow2")
        assert overlay_file.startswith(os.path.join(controller.get_project(copy_id).path, "project-files", "qemu"))
        with open(overlay_file) as f:
            assert f.read() == "thin overlay"

        # the non-image files ride along verbatim
        copy = controller.get_project(copy_id)
        with open(os.path.join(copy.path, "project-files", "qemu", node_id, "config.txt")) as f:
            assert f.read() == "hostname r1"

        # the copy takes its own snapshot, it does not inherit the old ones
        assert not os.path.exists(os.path.join(copy.path, "snapshots", "old-lab.gns3project"))

        # the dependency is recorded on the copy, and the copy is not frozen
        assert copy.distribution_master_id == source_id
        assert copy.frozen is False
        async with TestProjectOwnership._client_for(app, student) as student_client:
            response = await student_client.get(app.url_path_for("get_project", project_id=copy_id))
            assert response.status_code == status.HTTP_200_OK
            assert response.json()["distribution_master_id"] == source_id
            assert response.json()["frozen"] is False

    async def test_distributed_copy_cannot_be_duplicated_exported_or_distributed(
        self, app: FastAPI, base_client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        await TestProjectOwnership._seed_collection_ace(db_session)
        student = await TestProjectOwnership._create_user_in_users_group(db_session, f"student-{uuid.uuid4().hex[:8]}")
        _, copy_id = await self._distribute(app, test_user, student.username)

        # the superadmin bypasses the privilege checks, so these exercise the
        # marker-based refusals, not the reduced role
        admin = await UsersRepository(db_session).get_user_by_username("admin")
        async with TestProjectOwnership._client_for(app, admin) as admin_client:
            response = await admin_client.post(
                app.url_path_for("duplicate_project", project_id=copy_id), json={"name": "derived"}
            )
            assert response.status_code == status.HTTP_409_CONFLICT

            response = await admin_client.get(app.url_path_for("export_project", project_id=copy_id))
            assert response.status_code == status.HTTP_409_CONFLICT

            response = await admin_client.post(
                app.url_path_for("distribute_project", project_id=copy_id),
                json={"name": "re-distributed", "target_user": "admin"},
            )
            assert response.status_code == status.HTTP_409_CONFLICT

    async def test_cleanup_endpoint_deletes_copies_and_enables_unfreeze(
        self, app: FastAPI, base_client: AsyncClient, db_session: AsyncSession, test_user: User, controller
    ) -> None:
        await TestProjectOwnership._seed_collection_ace(db_session)
        student1 = await TestProjectOwnership._create_user_in_users_group(db_session, f"alice-{uuid.uuid4().hex[:8]}")
        student2 = await TestProjectOwnership._create_user_in_users_group(db_session, f"bob-{uuid.uuid4().hex[:8]}")

        async with TestProjectOwnership._client_for(app, test_user) as teacher_client:
            response = await teacher_client.post(
                app.url_path_for("create_project"), json={"name": f"lab-{uuid.uuid4()}"}
            )
            source_id = response.json()["project_id"]
            response = await teacher_client.post(
                app.url_path_for("distribute_project", project_id=source_id),
                json={"name": "lab1", "target_users": [student1.username, student2.username]},
            )
            assert response.status_code == status.HTTP_202_ACCEPTED
            distribution_id = response.json()["distribution_id"]
            job = await TestProjectDistribution._wait_for_distribution(app, teacher_client, source_id, distribution_id)
            copy_ids = [result["project"]["project_id"] for result in job["results"]]
            copy_paths = [controller.get_project(copy_id).path for copy_id in copy_ids]

            # one recipient deletes their own copy on their side
            async with TestProjectOwnership._client_for(app, student1) as student_client:
                response = await student_client.delete(app.url_path_for("delete_project", project_id=copy_ids[0]))
                assert response.status_code == status.HTTP_204_NO_CONTENT

            # the cleanup takes the remaining copies and reports them gone
            response = await teacher_client.delete(
                app.url_path_for("delete_distribution_copies", project_id=source_id, distribution_id=distribution_id)
            )
            assert response.status_code == status.HTTP_200_OK
            assert all(result["project_exists"] is False for result in response.json()["results"])
            assert not os.path.exists(copy_paths[1])

            # with every copy gone the template can be unfrozen, then deleted
            response = await teacher_client.post(app.url_path_for("unfreeze_project", project_id=source_id))
            assert response.status_code == status.HTTP_200_OK
            response = await teacher_client.delete(app.url_path_for("delete_project", project_id=source_id))
            assert response.status_code == status.HTTP_204_NO_CONTENT

    async def test_unfreeze_a_project_that_is_not_frozen(
        self, app: FastAPI, base_client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        await TestProjectOwnership._seed_collection_ace(db_session)

        async with TestProjectOwnership._client_for(app, test_user) as teacher_client:
            response = await teacher_client.post(
                app.url_path_for("create_project"), json={"name": f"lab-{uuid.uuid4()}"}
            )
            source_id = response.json()["project_id"]
            response = await teacher_client.post(app.url_path_for("unfreeze_project", project_id=source_id))
            assert response.status_code == status.HTTP_409_CONFLICT


class TestProjectShare:
    """
    Sharing a project (the /share endpoint) gives the targets access to this
    very project through an ACE: no copy is created. Sharing is ruled by the
    Project.Share privilege (the built-in "Lab member" role does not carry
    it, so a shared user cannot pass the project on; a user granted a
    Share-capable role can share within what they hold). The default role is
    the built-in "Lab member" role (use the lab, frozen topology), and a
    share cannot grant a role wider than the sharer's own access to the
    project: the owner of a distributed (frozen) copy cannot unfreeze it by
    sharing. The owner is never a share target (it would replace the owner
    ACE and its role). Re-sharing with the same target replaces its role;
    removing a share removes the access.
    """

    @staticmethod
    async def _create_project(app: FastAPI, owner: User) -> str:
        """
        Create a project as the given user and return its id.
        """

        async with TestProjectOwnership._client_for(app, owner) as owner_client:
            response = await owner_client.post(
                app.url_path_for("create_project"), json={"name": f"shared-{uuid.uuid4()}"}
            )
            assert response.status_code == status.HTTP_201_CREATED
            return response.json()["project_id"]

    async def test_share_project_with_user(
        self, app: FastAPI, base_client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        await TestProjectOwnership._seed_collection_ace(db_session)
        student = await TestProjectOwnership._create_user_in_users_group(db_session, f"student-{uuid.uuid4().hex[:8]}")
        project_id = await self._create_project(app, test_user)

        async with TestProjectOwnership._client_for(app, test_user) as teacher_client:
            response = await teacher_client.post(
                app.url_path_for("share_project", project_id=project_id),
                json={"target_user": student.username},
            )
            assert response.status_code == status.HTTP_201_CREATED
            shares = response.json()
            assert len(shares) == 1
            assert shares[0]["username"] == student.username
            assert shares[0]["group_name"] is None
            assert shares[0]["role"] == "Lab member"

            # the share is listed; the owner ACE of the creator is not a share
            response = await teacher_client.get(app.url_path_for("get_project_shares", project_id=project_id))
            assert response.status_code == status.HTTP_200_OK
            assert {share["ace_id"] for share in response.json()} == {shares[0]["ace_id"]}

        async with TestProjectOwnership._client_for(app, student) as student_client:
            # no copy: this very project, still owned by the teacher
            response = await student_client.get(app.url_path_for("get_project", project_id=project_id))
            assert response.status_code == status.HTTP_200_OK
            assert response.json()["created_by"] == test_user.username

            response = await student_client.get(app.url_path_for("get_projects"))
            assert project_id in {p["project_id"] for p in response.json()}

            # usable (open the lab) but frozen, like a distributed copy
            response = await student_client.post(app.url_path_for("open_project", project_id=project_id))
            assert response.status_code == status.HTTP_200_OK

            response = await student_client.put(
                app.url_path_for("update_project", project_id=project_id), json={"name": "hacked"}
            )
            assert response.status_code == status.HTTP_403_FORBIDDEN

            response = await student_client.get(
                app.url_path_for("get_logged_in_user_privileges_on_project", project_id=project_id)
            )
            assert set(response.json()["privileges"]) == TestProjectDistribution.LAB_MEMBER_PRIVILEGES

        # removing the share removes the access
        async with TestProjectOwnership._client_for(app, test_user) as teacher_client:
            response = await teacher_client.delete(
                app.url_path_for("delete_project_share", project_id=project_id, ace_id=shares[0]["ace_id"])
            )
            assert response.status_code == status.HTTP_204_NO_CONTENT

        async with TestProjectOwnership._client_for(app, student) as student_client:
            response = await student_client.get(app.url_path_for("get_project", project_id=project_id))
            assert response.status_code == status.HTTP_403_FORBIDDEN

    async def test_share_with_full_role_allows_edits(
        self, app: FastAPI, base_client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        await TestProjectOwnership._seed_collection_ace(db_session)
        student = await TestProjectOwnership._create_user_in_users_group(db_session, f"student-{uuid.uuid4().hex[:8]}")
        project_id = await self._create_project(app, test_user)

        async with TestProjectOwnership._client_for(app, test_user) as teacher_client:
            response = await teacher_client.post(
                app.url_path_for("share_project", project_id=project_id),
                json={"target_user": student.username, "role": "User"},
            )
            assert response.status_code == status.HTTP_201_CREATED
            assert response.json()[0]["role"] == "User"

        # with the full role, the target edits the shared project like its owner
        async with TestProjectOwnership._client_for(app, student) as student_client:
            response = await student_client.put(
                app.url_path_for("update_project", project_id=project_id), json={"name": "renamed-together"}
            )
            assert response.status_code == status.HTTP_200_OK

    async def test_sharing_again_replaces_the_role(
        self, app: FastAPI, base_client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        await TestProjectOwnership._seed_collection_ace(db_session)
        student = await TestProjectOwnership._create_user_in_users_group(db_session, f"student-{uuid.uuid4().hex[:8]}")
        project_id = await self._create_project(app, test_user)

        async with TestProjectOwnership._client_for(app, test_user) as teacher_client:
            response = await teacher_client.post(
                app.url_path_for("share_project", project_id=project_id),
                json={"target_user": student.username, "role": "User"},
            )
            assert response.status_code == status.HTTP_201_CREATED
            first_share = response.json()[0]

            # sharing again with the same target must replace the role, not
            # stack a second ACE (a user-level ACE decides alone on its path)
            response = await teacher_client.post(
                app.url_path_for("share_project", project_id=project_id),
                json={"target_user": student.username},
            )
            assert response.status_code == status.HTTP_201_CREATED
            shares = response.json()
            assert len(shares) == 1
            assert shares[0]["ace_id"] == first_share["ace_id"]
            assert shares[0]["role"] == "Lab member"

            response = await teacher_client.get(app.url_path_for("get_project_shares", project_id=project_id))
            assert len(response.json()) == 1

        async with TestProjectOwnership._client_for(app, student) as student_client:
            response = await student_client.put(
                app.url_path_for("update_project", project_id=project_id), json={"name": "hacked"}
            )
            assert response.status_code == status.HTTP_403_FORBIDDEN

    async def test_share_target_cannot_delete_the_project(
        self, app: FastAPI, base_client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        await TestProjectOwnership._seed_collection_ace(db_session)
        student = await TestProjectOwnership._create_user_in_users_group(db_session, f"student-{uuid.uuid4().hex[:8]}")
        project_id = await self._create_project(app, test_user)

        async with TestProjectOwnership._client_for(app, test_user) as teacher_client:
            response = await teacher_client.post(
                app.url_path_for("share_project", project_id=project_id),
                json={"target_user": student.username},
            )
            assert response.status_code == status.HTTP_201_CREATED

        # the target carries Project.Allocate (it is required to open the
        # project) but must not be able to destroy the sharer's project
        async with TestProjectOwnership._client_for(app, student) as student_client:
            response = await student_client.delete(app.url_path_for("delete_project", project_id=project_id))
            assert response.status_code == status.HTTP_403_FORBIDDEN

        # the owner deletes their own project
        async with TestProjectOwnership._client_for(app, test_user) as teacher_client:
            response = await teacher_client.delete(app.url_path_for("delete_project", project_id=project_id))
            assert response.status_code == status.HTTP_204_NO_CONTENT

    async def test_share_with_multiple_users(
        self, app: FastAPI, base_client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        await TestProjectOwnership._seed_collection_ace(db_session)
        names = [f"student-{uuid.uuid4().hex[:8]}", f"student-{uuid.uuid4().hex[:8]}"]
        students = [await TestProjectOwnership._create_user_in_users_group(db_session, name) for name in names]
        project_id = await self._create_project(app, test_user)

        async with TestProjectOwnership._client_for(app, test_user) as teacher_client:
            response = await teacher_client.post(
                app.url_path_for("share_project", project_id=project_id),
                json={"target_users": [students[0].username, students[1].username, students[0].username]},
            )
            assert response.status_code == status.HTTP_201_CREATED
            # duplicates in the list are collapsed: one share per user
            assert {share["username"] for share in response.json()} == set(names)
            assert len(response.json()) == 2

        for student in students:
            async with TestProjectOwnership._client_for(app, student) as student_client:
                response = await student_client.get(app.url_path_for("get_project", project_id=project_id))
                assert response.status_code == status.HTTP_200_OK

    async def test_share_with_group(
        self, app: FastAPI, base_client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        await TestProjectOwnership._seed_collection_ace(db_session)

        users_repo = UsersRepository(db_session)
        group = await users_repo.create_user_group(schemas.UserGroupCreate(name=f"team-{uuid.uuid4().hex[:8]}"))
        members = []
        for name in ("alice", "bob"):
            member = await TestProjectOwnership._create_user_in_users_group(
                db_session, f"{name}-{uuid.uuid4().hex[:8]}"
            )
            await users_repo.add_member_to_user_group(group.user_group_id, member)
            members.append(member)

        project_id = await self._create_project(app, test_user)

        async with TestProjectOwnership._client_for(app, test_user) as teacher_client:
            response = await teacher_client.post(
                app.url_path_for("share_project", project_id=project_id),
                json={"target_group": group.name},
            )
            assert response.status_code == status.HTTP_201_CREATED
            shares = response.json()
            assert len(shares) == 1  # one group ACE for all the members
            assert shares[0]["group_name"] == group.name
            assert shares[0]["username"] is None

        # every member sees the project
        for member in members:
            async with TestProjectOwnership._client_for(app, member) as member_client:
                response = await member_client.get(app.url_path_for("get_project", project_id=project_id))
                assert response.status_code == status.HTTP_200_OK

        # removing the group share removes every member's access
        async with TestProjectOwnership._client_for(app, test_user) as teacher_client:
            response = await teacher_client.delete(
                app.url_path_for("delete_project_share", project_id=project_id, ace_id=shares[0]["ace_id"])
            )
            assert response.status_code == status.HTTP_204_NO_CONTENT

        async with TestProjectOwnership._client_for(app, members[0]) as member_client:
            response = await member_client.get(app.url_path_for("get_project", project_id=project_id))
            assert response.status_code == status.HTTP_403_FORBIDDEN

    async def test_share_validation(
        self, app: FastAPI, base_client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        await TestProjectOwnership._seed_collection_ace(db_session)
        student = await TestProjectOwnership._create_user_in_users_group(db_session, f"student-{uuid.uuid4().hex[:8]}")
        project_id = await self._create_project(app, test_user)

        async with TestProjectOwnership._client_for(app, test_user) as teacher_client:
            # a share targets one kind of recipient, never several
            response = await teacher_client.post(
                app.url_path_for("share_project", project_id=project_id),
                json={"target_user": "user1", "target_group": "Users"},
            )
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

            response = await teacher_client.post(
                app.url_path_for("share_project", project_id=project_id),
                json={"target_user": "user1", "target_users": ["user2"]},
            )
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

            # an empty list of users and a share without any target are rejected
            response = await teacher_client.post(
                app.url_path_for("share_project", project_id=project_id), json={"target_users": []}
            )
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

            response = await teacher_client.post(app.url_path_for("share_project", project_id=project_id), json={})
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

            # a missing user, group or role is rejected before anything is written
            response = await teacher_client.post(
                app.url_path_for("share_project", project_id=project_id), json={"target_user": "missing-user"}
            )
            assert response.status_code == status.HTTP_404_NOT_FOUND

            response = await teacher_client.post(
                app.url_path_for("share_project", project_id=project_id), json={"target_group": "missing-group"}
            )
            assert response.status_code == status.HTTP_404_NOT_FOUND

            response = await teacher_client.post(
                app.url_path_for("share_project", project_id=project_id),
                json={"target_user": student.username, "role": "No such role"},
            )
            assert response.status_code == status.HTTP_404_NOT_FOUND

            # an empty group must be rejected
            empty_group = await UsersRepository(db_session).create_user_group(
                schemas.UserGroupCreate(name=f"empty-{uuid.uuid4().hex[:8]}")
            )
            response = await teacher_client.post(
                app.url_path_for("share_project", project_id=project_id), json={"target_group": empty_group.name}
            )
            assert response.status_code == status.HTTP_409_CONFLICT

    async def test_share_owner_target_is_rejected(
        self, app: FastAPI, base_client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        """
        The owner already holds the owner ACE on the project: a share would
        replace it and its role, so the owner can never be a share target.
        """

        await TestProjectOwnership._seed_collection_ace(db_session)
        project_id = await self._create_project(app, test_user)

        async with TestProjectOwnership._client_for(app, test_user) as owner_client:
            response = await owner_client.post(
                app.url_path_for("share_project", project_id=project_id),
                json={"target_user": test_user.username},
            )
            assert response.status_code == status.HTTP_409_CONFLICT

            response = await owner_client.post(
                app.url_path_for("share_project", project_id=project_id),
                json={"target_users": [test_user.username]},
            )
            assert response.status_code == status.HTTP_409_CONFLICT

            # the owner ACE kept its role
            rbac_repo = RbacRepository(db_session)
            ace = await rbac_repo.get_ace_by_path(f"/projects/{project_id}")
            user_role = await rbac_repo.get_role_by_name("User")
            assert ace is not None
            assert str(ace.role_id) == str(user_role.role_id)

    async def test_delegate_with_share_privilege_can_share(
        self, app: FastAPI, base_client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        """
        Sharing is ruled by Project.Share, not by ownership alone: a user
        granted a Share-capable role on a project can share it, but only
        within the privileges they hold.
        """

        await TestProjectOwnership._seed_collection_ace(db_session)
        colleague = await TestProjectOwnership._create_user_in_users_group(db_session, f"peer-{uuid.uuid4().hex[:8]}")
        outsider = await TestProjectOwnership._create_user_in_users_group(db_session, f"peer-{uuid.uuid4().hex[:8]}")
        project_id = await self._create_project(app, test_user)

        sharer_role = await TestProjectOwnership._create_role_with_privileges(
            db_session,
            f"delegate-{uuid.uuid4().hex[:8]}",
            {"Project.Share", *TestProjectDistribution.LAB_MEMBER_PRIVILEGES},
        )
        await RbacRepository(db_session).create_ace(
            ACECreate(
                path=f"/projects/{project_id}",
                ace_type="user",
                propagate=True,
                user_id=str(colleague.user_id),
                role_id=str(sharer_role.role_id),
            )
        )

        async with TestProjectOwnership._client_for(app, colleague) as colleague_client:
            response = await colleague_client.post(
                app.url_path_for("share_project", project_id=project_id),
                json={"target_user": outsider.username},
            )
            assert response.status_code == status.HTTP_201_CREATED

            # but never a role wider than what they hold
            response = await colleague_client.post(
                app.url_path_for("share_project", project_id=project_id),
                json={"target_user": outsider.username, "role": "User"},
            )
            assert response.status_code == status.HTTP_403_FORBIDDEN

    async def test_only_owner_or_superadmin_can_manage_shares(
        self, app: FastAPI, base_client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        await TestProjectOwnership._seed_collection_ace(db_session)

        # a project owned by a student, shared with a colleague
        owner = await TestProjectOwnership._create_user_in_users_group(db_session, f"owner-{uuid.uuid4().hex[:8]}")
        colleague = await TestProjectOwnership._create_user_in_users_group(db_session, f"peer-{uuid.uuid4().hex[:8]}")
        outsider = await TestProjectOwnership._create_user_in_users_group(db_session, f"peer-{uuid.uuid4().hex[:8]}")
        project_id = await self._create_project(app, owner)

        async with TestProjectOwnership._client_for(app, owner) as owner_client:
            response = await owner_client.post(
                app.url_path_for("share_project", project_id=project_id),
                json={"target_user": colleague.username},
            )
            assert response.status_code == status.HTTP_201_CREATED
            share_ace_id = response.json()[0]["ace_id"]

        # the colleague has access (and Project.Audit), but is not the owner
        async with TestProjectOwnership._client_for(app, colleague) as colleague_client:
            response = await colleague_client.get(app.url_path_for("get_project", project_id=project_id))
            assert response.status_code == status.HTTP_200_OK

            response = await colleague_client.post(
                app.url_path_for("share_project", project_id=project_id),
                json={"target_user": outsider.username},
            )
            assert response.status_code == status.HTTP_403_FORBIDDEN

            response = await colleague_client.get(app.url_path_for("get_project_shares", project_id=project_id))
            assert response.status_code == status.HTTP_403_FORBIDDEN

            response = await colleague_client.delete(
                app.url_path_for("delete_project_share", project_id=project_id, ace_id=share_ace_id)
            )
            assert response.status_code == status.HTTP_403_FORBIDDEN

        # a superadmin can share someone else's project, with any role
        admin = await UsersRepository(db_session).get_user_by_username("admin")
        async with TestProjectOwnership._client_for(app, admin) as admin_client:
            response = await admin_client.post(
                app.url_path_for("share_project", project_id=project_id),
                json={"target_user": outsider.username, "role": "User"},
            )
            assert response.status_code == status.HTTP_201_CREATED

        async with TestProjectOwnership._client_for(app, outsider) as outsider_client:
            response = await outsider_client.get(app.url_path_for("get_project", project_id=project_id))
            assert response.status_code == status.HTTP_200_OK

    async def test_owner_ace_cannot_be_removed_as_a_share(
        self, app: FastAPI, base_client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        await TestProjectOwnership._seed_collection_ace(db_session)
        project_id = await self._create_project(app, test_user)

        # the ACE of the creator on the project path is the owner ACE
        rbac_repo = RbacRepository(db_session)
        aces = await rbac_repo.get_aces_for_path(f"/projects/{project_id}")
        owner_ace_id = next(ace.ace_id for ace in aces if ace.user is not None and ace.user.username == "user1")

        async with TestProjectOwnership._client_for(app, test_user) as owner_client:
            response = await owner_client.delete(
                app.url_path_for("delete_project_share", project_id=project_id, ace_id=owner_ace_id)
            )
            assert response.status_code == status.HTTP_404_NOT_FOUND

            # the owner ACE is intact
            response = await owner_client.get(app.url_path_for("get_project", project_id=project_id))
            assert response.status_code == status.HTTP_200_OK

    async def test_frozen_owner_cannot_share_a_wider_role(
        self, app: FastAPI, base_client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        await TestProjectOwnership._seed_collection_ace(db_session)
        student = await TestProjectOwnership._create_user_in_users_group(db_session, f"student-{uuid.uuid4().hex[:8]}")
        classmate = await TestProjectOwnership._create_user_in_users_group(db_session, f"peer-{uuid.uuid4().hex[:8]}")
        _, copy_id = await TestProjectDistribution._distribute(app, test_user, student.username)

        # the copy owner only carries the Lab member role: no Project.Share,
        # so they cannot pass the lab on to anyone
        async with TestProjectOwnership._client_for(app, student) as student_client:
            response = await student_client.post(
                app.url_path_for("share_project", project_id=copy_id),
                json={"target_user": classmate.username},
            )
            assert response.status_code == status.HTTP_403_FORBIDDEN

        # a sharer who does hold Project.Share still cannot grant a role wider
        # than what they have on the copy: the width rule survives the
        # privilege gate. The role of the copy owner is widened directly on
        # their owner ACE (the share endpoint refuses the owner as a target).
        sharer_role = await TestProjectOwnership._create_role_with_privileges(
            db_session,
            f"pair-sharer-{uuid.uuid4().hex[:8]}",
            {"Project.Share", *TestProjectDistribution.LAB_MEMBER_PRIVILEGES},
        )
        await upsert_project_share_ace(db_session, UUID(copy_id), sharer_role.role_id, user_id=student.user_id)

        async with TestProjectOwnership._client_for(app, student) as student_client:
            response = await student_client.post(
                app.url_path_for("share_project", project_id=copy_id),
                json={"target_user": classmate.username, "role": "User"},
            )
            assert response.status_code == status.HTTP_403_FORBIDDEN

            # sharing within what they hold is fine: a frozen pair share
            response = await student_client.post(
                app.url_path_for("share_project", project_id=copy_id),
                json={"target_user": classmate.username},
            )
            assert response.status_code == status.HTTP_201_CREATED

        async with TestProjectOwnership._client_for(app, classmate) as classmate_client:
            response = await classmate_client.get(app.url_path_for("get_project", project_id=copy_id))
            assert response.status_code == status.HTTP_200_OK

            response = await classmate_client.put(
                app.url_path_for("update_project", project_id=copy_id), json={"name": "hacked"}
            )
            assert response.status_code == status.HTTP_403_FORBIDDEN


class TestProjectShareCount:
    """
    The project list and the single project response carry a share_count for
    the project owner and superadmins only. It matches the number of rows the
    /shares endpoint lists: the owner ACE is not a share and a group share
    counts as one. Every other user gets no share_count at all.
    """

    @staticmethod
    def _share_count_in(projects_json, project_id: str):
        entry = next(p for p in projects_json if p["project_id"] == project_id)
        return entry.get("share_count")

    async def test_share_count_visible_to_owner_and_superadmin_only(
        self, app: FastAPI, base_client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        await TestProjectOwnership._seed_collection_ace(db_session)
        student = await TestProjectOwnership._create_user_in_users_group(db_session, f"student-{uuid.uuid4().hex[:8]}")
        project_id = await TestProjectShare._create_project(app, test_user)

        async with TestProjectOwnership._client_for(app, test_user) as teacher_client:
            response = await teacher_client.post(
                app.url_path_for("share_project", project_id=project_id),
                json={"target_user": student.username},
            )
            assert response.status_code == status.HTTP_201_CREATED
            share_ace_id = response.json()[0]["ace_id"]

            # the list and the single project agree with the /shares listing
            response = await teacher_client.get(app.url_path_for("get_projects"))
            assert self._share_count_in(response.json(), project_id) == 1

            response = await teacher_client.get(app.url_path_for("get_project", project_id=project_id))
            assert response.json()["share_count"] == 1

        # the shared user sees the project, but no share_count on it: the list
        # omits the field (exclude_unset) while the single project endpoint
        # always serializes every field, so it carries null instead
        async with TestProjectOwnership._client_for(app, student) as student_client:
            response = await student_client.get(app.url_path_for("get_projects"))
            assert project_id in {p["project_id"] for p in response.json()}
            assert self._share_count_in(response.json(), project_id) is None

            response = await student_client.get(app.url_path_for("get_project", project_id=project_id))
            assert response.status_code == status.HTTP_200_OK
            assert response.json()["share_count"] is None

        # a superadmin sees the share count of every project
        admin = await UsersRepository(db_session).get_user_by_username("admin")
        async with TestProjectOwnership._client_for(app, admin) as admin_client:
            response = await admin_client.get(app.url_path_for("get_projects"))
            assert self._share_count_in(response.json(), project_id) == 1

            response = await admin_client.get(app.url_path_for("get_project", project_id=project_id))
            assert response.json()["share_count"] == 1

        # removing the share drops the count back to zero
        async with TestProjectOwnership._client_for(app, test_user) as teacher_client:
            response = await teacher_client.delete(
                app.url_path_for("delete_project_share", project_id=project_id, ace_id=share_ace_id)
            )
            assert response.status_code == status.HTTP_204_NO_CONTENT

            response = await teacher_client.get(app.url_path_for("get_project", project_id=project_id))
            assert response.json()["share_count"] == 0

    async def test_share_count_zero_without_shares(
        self, app: FastAPI, base_client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        await TestProjectOwnership._seed_collection_ace(db_session)
        project_id = await TestProjectShare._create_project(app, test_user)

        # the owner ACE of the creator is not a share
        async with TestProjectOwnership._client_for(app, test_user) as owner_client:
            response = await owner_client.get(app.url_path_for("get_projects"))
            assert self._share_count_in(response.json(), project_id) == 0

    async def test_share_count_counts_a_group_as_one_and_never_stacks(
        self, app: FastAPI, base_client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        await TestProjectOwnership._seed_collection_ace(db_session)
        student = await TestProjectOwnership._create_user_in_users_group(db_session, f"student-{uuid.uuid4().hex[:8]}")

        users_repo = UsersRepository(db_session)
        group = await users_repo.create_user_group(schemas.UserGroupCreate(name=f"team-{uuid.uuid4().hex[:8]}"))
        member = await TestProjectOwnership._create_user_in_users_group(db_session, f"peer-{uuid.uuid4().hex[:8]}")
        await users_repo.add_member_to_user_group(group.user_group_id, member)

        project_id = await TestProjectShare._create_project(app, test_user)

        async with TestProjectOwnership._client_for(app, test_user) as teacher_client:
            # one group ACE covers all the members: one share
            response = await teacher_client.post(
                app.url_path_for("share_project", project_id=project_id),
                json={"target_group": group.name},
            )
            assert response.status_code == status.HTTP_201_CREATED
            group_share_ace_id = response.json()[0]["ace_id"]

            # sharing again with the group replaces the role, it does not stack
            response = await teacher_client.post(
                app.url_path_for("share_project", project_id=project_id),
                json={"target_group": group.name, "role": "User"},
            )
            assert response.status_code == status.HTTP_201_CREATED

            response = await teacher_client.get(app.url_path_for("get_project", project_id=project_id))
            assert response.json()["share_count"] == 1

            # a user share adds a second one, deleting the group share leaves one
            response = await teacher_client.post(
                app.url_path_for("share_project", project_id=project_id),
                json={"target_user": student.username},
            )
            assert response.status_code == status.HTTP_201_CREATED

            response = await teacher_client.get(app.url_path_for("get_project", project_id=project_id))
            assert response.json()["share_count"] == 2

            response = await teacher_client.delete(
                app.url_path_for("delete_project_share", project_id=project_id, ace_id=group_share_ace_id)
            )
            assert response.status_code == status.HTTP_204_NO_CONTENT

            response = await teacher_client.get(app.url_path_for("get_project", project_id=project_id))
            assert response.json()["share_count"] == 1


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
