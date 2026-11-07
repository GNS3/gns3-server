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
Tests for the in-memory RBAC snapshot: every write through a repository
must be visible to the next permission check (write-through), and the
snapshot must survive a reset (database recreated).
"""

import uuid

import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from gns3server.db.models import User
from gns3server.db.rbac_state import RbacState
from gns3server.db.repositories.pools import ResourcePoolsRepository
from gns3server.db.repositories.rbac import RbacRepository
from gns3server.db.repositories.users import UsersRepository
from gns3server.schemas.controller.pools import ResourceCreate, ResourcePoolCreate
from gns3server.schemas.controller.rbac import ACECreate, RoleCreate
from gns3server.schemas.controller.users import UserGroupCreate
from gns3server.services import auth_service

pytestmark = pytest.mark.asyncio


class TestRbacStateWriteThrough:
    """
    Each test builds its own rows (unique paths and names) so the file is
    order-independent under --random-order.
    """

    @staticmethod
    async def _create_user_out_of_band(db_session: AsyncSession, username: str) -> User:
        """
        A user outside the "Users" group has no privileges from the default
        seeded ACE, so the only privilege source is what the test creates.
        """

        db_user = User(username=username, hashed_password=auth_service.hash_password("password"))
        db_session.add(db_user)
        await db_session.commit()
        await db_session.refresh(db_user)  # the id must be a UUID, not the str default
        return db_user

    async def test_group_membership_change_is_visible(self, db_session: AsyncSession) -> None:

        path = f"/projects/{uuid.uuid4()}"
        user = await self._create_user_out_of_band(db_session, "group-write-user")
        rbac_repo = RbacRepository(db_session)
        users_repo = UsersRepository(db_session)

        group = await users_repo.create_user_group(UserGroupCreate(name=f"group-{uuid.uuid4().hex[:8]}"))
        role = await rbac_repo.get_role_by_name("User")
        await rbac_repo.create_ace(
            ACECreate(
                path=path,
                ace_type="group",
                propagate=False,
                group_id=str(group.user_group_id),
                role_id=str(role.role_id),
            )
        )

        # the user is not a member of the group yet
        assert await rbac_repo.check_user_has_privilege(user.user_id, path, "Project.Audit") is False

        await users_repo.add_member_to_user_group(group.user_group_id, user)
        assert await rbac_repo.check_user_has_privilege(user.user_id, path, "Project.Audit") is True

        await users_repo.remove_member_from_user_group(group.user_group_id, user)
        assert await rbac_repo.check_user_has_privilege(user.user_id, path, "Project.Audit") is False

    async def test_role_privilege_change_is_visible(self, db_session: AsyncSession) -> None:

        path = f"/projects/{uuid.uuid4()}"
        user = await self._create_user_out_of_band(db_session, "role-write-user")
        rbac_repo = RbacRepository(db_session)

        # a role without any privilege, granted to the user itself
        role = await rbac_repo.create_role(RoleCreate(name=f"role-{uuid.uuid4().hex[:8]}"))
        await rbac_repo.create_ace(
            ACECreate(path=path, ace_type="user", propagate=False, user_id=str(user.user_id), role_id=str(role.role_id))
        )

        assert await rbac_repo.check_user_has_privilege(user.user_id, path, "Project.Audit") is False

        privilege = await rbac_repo.get_privilege_by_name("Project.Audit")
        await rbac_repo.add_privilege_to_role(role.role_id, privilege)
        assert await rbac_repo.check_user_has_privilege(user.user_id, path, "Project.Audit") is True

    async def test_pool_membership_change_is_visible(self, db_session: AsyncSession) -> None:

        project_id = str(uuid.uuid4())
        user = await self._create_user_out_of_band(db_session, "pool-write-user")
        rbac_repo = RbacRepository(db_session)
        pools_repo = ResourcePoolsRepository(db_session)

        pool = await pools_repo.create_resource_pool(ResourcePoolCreate(name=f"pool-{uuid.uuid4().hex[:8]}"))
        resource = await pools_repo.create_resource(
            ResourceCreate(resource_id=uuid.UUID(project_id), resource_type="project", name=f"project-{project_id[:8]}")
        )

        role = await rbac_repo.get_role_by_name("User")
        await rbac_repo.create_ace(
            ACECreate(
                path=f"/pools/{pool.resource_pool_id}",
                ace_type="user",
                propagate=False,
                user_id=str(user.user_id),
                role_id=str(role.role_id),
            )
        )

        # the resource is not in the pool yet
        assert (
            await rbac_repo.check_user_has_privilege(user.user_id, f"/projects/{project_id}", "Project.Audit") is False
        )

        await pools_repo.add_resource_to_pool(pool.resource_pool_id, resource)
        assert (
            await rbac_repo.check_user_has_privilege(user.user_id, f"/projects/{project_id}", "Project.Audit") is True
        )

    async def test_user_ace_denies_group_ace(self, test_user: User, db_session: AsyncSession) -> None:

        path = f"/projects/{uuid.uuid4()}"
        rbac_repo = RbacRepository(db_session)
        users_repo = UsersRepository(db_session)

        group_id = (await users_repo.get_user_group_by_name("Users")).user_group_id
        role = await rbac_repo.get_role_by_name("User")
        await rbac_repo.create_ace(
            ACECreate(path=path, ace_type="group", propagate=False, group_id=str(group_id), role_id=str(role.role_id))
        )
        assert await rbac_repo.check_user_has_privilege(test_user.user_id, path, "Project.Audit") is True

        # a deny ACE on the user itself replaces the group privileges
        await rbac_repo.create_ace(
            ACECreate(
                path=path,
                ace_type="user",
                propagate=False,
                allowed=False,
                user_id=str(test_user.user_id),
                role_id=str(role.role_id),
            )
        )
        assert await rbac_repo.check_user_has_privilege(test_user.user_id, path, "Project.Audit") is False


class TestRbacStateReload:
    async def test_dirty_flag_cycle(self, test_user: User, db_session: AsyncSession) -> None:

        state = RbacState.instance()
        state.reset()
        rbac_repo = RbacRepository(db_session)
        users_repo = UsersRepository(db_session)

        path = f"/projects/{uuid.uuid4()}"
        await rbac_repo.check_user_has_privilege(test_user.user_id, path, "Project.Audit")
        assert state._loaded is True
        assert state._dirty is False

        group_id = (await users_repo.get_user_group_by_name("Users")).user_group_id
        role = await rbac_repo.get_role_by_name("User")
        await rbac_repo.create_ace(
            ACECreate(path=path, ace_type="group", propagate=False, group_id=str(group_id), role_id=str(role.role_id))
        )
        assert state._dirty is True

        # the next check reloads the snapshot and clears the flag
        assert await rbac_repo.check_user_has_privilege(test_user.user_id, path, "Project.Audit") is True
        assert state._dirty is False

    async def test_reset_forces_reload_from_database(self, test_user: User, db_session: AsyncSession) -> None:

        rbac_repo = RbacRepository(db_session)
        users_repo = UsersRepository(db_session)

        path = f"/projects/{uuid.uuid4()}"
        group_id = (await users_repo.get_user_group_by_name("Users")).user_group_id
        role = await rbac_repo.get_role_by_name("User")
        await rbac_repo.create_ace(
            ACECreate(path=path, ace_type="group", propagate=False, group_id=str(group_id), role_id=str(role.role_id))
        )
        assert await rbac_repo.check_user_has_privilege(test_user.user_id, path, "Project.Audit") is True

        # a reset drops the in-memory data; the next check reloads from the
        # database and the ACE is still there
        RbacState.instance().reset()
        assert await rbac_repo.check_user_has_privilege(test_user.user_id, path, "Project.Audit") is True

    async def test_startup_helper_loads_snapshot(
        self, app: FastAPI, db_engine, test_user: User, db_session: AsyncSession
    ) -> None:

        from gns3server.db.tasks import load_rbac_state

        RbacState.instance().reset()
        app.state._db_engine = db_engine
        await load_rbac_state(app)
        assert RbacState.instance()._loaded is True
        assert RbacState.instance()._dirty is False
