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

import uuid

import pytest
from fastapi import FastAPI, status
from httpx import AsyncClient
from httpx_ws.transport import ASGIWebSocketTransport
from sqlalchemy.ext.asyncio import AsyncSession

from gns3server import schemas
from gns3server.controller import Controller
from gns3server.db.models import User
from gns3server.db.project_acl import ensure_all_project_aces, ensure_project_owner_ace
from gns3server.db.repositories.pools import ResourcePoolsRepository
from gns3server.db.repositories.rbac import RbacRepository
from gns3server.db.repositories.users import UsersRepository
from gns3server.schemas.controller.pools import ResourceCreate, ResourcePoolCreate
from gns3server.schemas.controller.rbac import ACECreate, ACEUpdate
from gns3server.services import auth_service
from gns3server.utils import zipfile_zstd

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
