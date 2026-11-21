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

"""
Quota configuration routes and the quota snapshot resolution.

Every test builds its own rows and reloads the snapshot explicitly: the
in-memory quota state has no bound engine in tests, so the write-through
hook cannot fire.
"""

import uuid

import pytest
import pytest_asyncio
from fastapi import FastAPI, status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from gns3server.db.repositories.users import UsersRepository
from gns3server.db.user_quota_state import UserQuotaState
from gns3server.schemas.controller.users import UserCreate, UserGroupCreate, UserGroupUpdate, UserUpdate
from gns3server.services import auth_service
from gns3server.services.authentication import DEFAULT_JWT_SECRET_KEY

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def reset_quota_state():

    UserQuotaState._reset()
    yield
    UserQuotaState._reset()


@pytest_asyncio.fixture
async def quota_user(db_session: AsyncSession):
    """
    A fresh user in its own fresh group: quota rows are class-scoped, so
    every test must own its users instead of mutating a shared one.
    """

    repo = UsersRepository(db_session)
    suffix = uuid.uuid4().hex[:8]
    group = await repo.create_user_group(UserGroupCreate(name=f"quota-group-{suffix}"))
    user = await repo.create_user(
        UserCreate(username=f"quota-{suffix}", password="quota_password", user_group_id=group.user_group_id)
    )
    return user, group


class TestUserQuotaRoutes:
    @pytest_asyncio.fixture
    async def users_group_id(self, db_session: AsyncSession) -> str:

        return str((await UsersRepository(db_session).get_user_group_by_name("Users")).user_group_id)

    async def test_update_user_quotas(self, app: FastAPI, client: AsyncClient, test_user, users_group_id: str) -> None:
        """
        The quota fields ride the regular user update route.
        """

        response = await client.put(
            app.url_path_for("update_user", user_id=str(test_user.user_id)),
            json={"max_nodes": 100, "max_running_nodes": 20},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["max_nodes"] == 100
        assert response.json()["max_running_nodes"] == 20

    async def test_update_user_quotas_validation(
        self, app: FastAPI, client: AsyncClient, test_user, users_group_id: str
    ) -> None:
        """
        -1 (explicitly unlimited) is valid, anything below is a 422.
        """

        response = await client.put(
            app.url_path_for("update_user", user_id=str(test_user.user_id)),
            json={"max_nodes": -1},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["max_nodes"] == -1

        response = await client.put(
            app.url_path_for("update_user", user_id=str(test_user.user_id)),
            json={"max_nodes": -2},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_create_user_keeps_the_quota_fields(
        self, app: FastAPI, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """
        An admin sets the quotas when creating the user: the values must be
        stored, not silently dropped.
        """

        repo = UsersRepository(db_session)
        group = await repo.create_user_group(UserGroupCreate(name=f"quota-create-{uuid.uuid4().hex[:8]}"))
        response = await client.post(
            app.url_path_for("create_user"),
            json={
                "username": f"quota-new-{uuid.uuid4().hex[:8]}",
                "password": "quota_password",
                "user_group_id": str(group.user_group_id),
                "max_nodes": 5,
                "max_running_nodes": 2,
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["max_nodes"] == 5
        assert response.json()["max_running_nodes"] == 2

    async def test_create_group_keeps_the_default_quota_fields(self, app: FastAPI, client: AsyncClient) -> None:
        """
        The group defaults sent at creation time must be stored as well.
        """

        response = await client.post(
            app.url_path_for("create_user_group"),
            json={
                "name": f"quota-defaults-{uuid.uuid4().hex[:8]}",
                "default_max_nodes": 10,
                "default_max_running_nodes": 3,
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["default_max_nodes"] == 10
        assert response.json()["default_max_running_nodes"] == 3

    async def test_update_group_default_quotas(
        self, app: FastAPI, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """
        The group defaults ride the regular group update route.
        """

        repo = UsersRepository(db_session)
        group = await repo.create_user_group(UserGroupCreate(name="quota-test-group"))
        response = await client.put(
            app.url_path_for("update_user_group", user_group_id=str(group.user_group_id)),
            json={"default_max_nodes": 50, "default_max_running_nodes": 10},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["default_max_nodes"] == 50
        assert response.json()["default_max_running_nodes"] == 10

    async def test_builtin_group_quotas_editable_but_not_name(
        self, app: FastAPI, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """
        A built-in group (the default "Users" group) cannot be renamed,
        but its quota defaults stay editable — that is where an
        administrator sets the limit for the users created by default.
        """

        repo = UsersRepository(db_session)
        users_group = await repo.get_user_group_by_name("Users")
        assert users_group.is_builtin

        response = await client.put(
            app.url_path_for("update_user_group", user_group_id=str(users_group.user_group_id)),
            json={"default_max_nodes": 100, "default_max_running_nodes": 20},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["name"] == "Users"
        assert response.json()["default_max_nodes"] == 100

        # renaming a built-in group is refused, alone or alongside quotas,
        # and an explicit null name counts as touching the name
        for payload in ({"name": "renamed"}, {"name": "renamed", "default_max_nodes": 5}, {"name": None}):
            response = await client.put(
                app.url_path_for("update_user_group", user_group_id=str(users_group.user_group_id)),
                json=payload,
            )
            assert response.status_code == status.HTTP_403_FORBIDDEN, payload

    async def test_me_quotas_superadmin(self, app: FastAPI, client: AsyncClient) -> None:
        """
        A superadmin is never limited: both limits come back null.
        """

        response = await client.get(app.url_path_for("get_logged_in_user_quotas"))
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["max_nodes"] is None
        assert body["max_running_nodes"] is None
        assert body["current_nodes"] == 0
        assert body["current_running_nodes"] == 0

    async def test_me_quotas_reflect_user_override(
        self, app: FastAPI, client: AsyncClient, db_session: AsyncSession, quota_user
    ) -> None:
        """
        A user-level value wins over the group default and shows up on
        /me/quotas for that user.
        """

        user, group = quota_user
        repo = UsersRepository(db_session)
        await repo.update_user_group(
            group.user_group_id, UserGroupUpdate(default_max_nodes=50, default_max_running_nodes=10)
        )
        await repo.update_user(user.user_id, UserUpdate(max_nodes=5, max_running_nodes=2))
        await UserQuotaState.instance().reload(db_session)

        token = auth_service.create_access_token(user.username, secret_key=DEFAULT_JWT_SECRET_KEY)
        response = await client.get(
            app.url_path_for("get_logged_in_user_quotas"), headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["max_nodes"] == 5  # the user override, not the group 50
        assert body["max_running_nodes"] == 2
        assert body["current_nodes"] == 0

    async def test_me_quotas_inherit_group_default(
        self, app: FastAPI, client: AsyncClient, db_session: AsyncSession, quota_user
    ) -> None:
        """
        Without a user override the group default applies.
        """

        user, group = quota_user
        repo = UsersRepository(db_session)
        await repo.update_user_group(
            group.user_group_id, UserGroupUpdate(default_max_nodes=7, default_max_running_nodes=3)
        )
        await UserQuotaState.instance().reload(db_session)

        token = auth_service.create_access_token(user.username, secret_key=DEFAULT_JWT_SECRET_KEY)
        response = await client.get(
            app.url_path_for("get_logged_in_user_quotas"), headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["max_nodes"] == 7
        assert response.json()["max_running_nodes"] == 3

    async def test_quota_resolution(self, app: FastAPI, db_session: AsyncSession, quota_user) -> None:
        """
        Snapshot resolution: user value wins (-1 means unlimited), several
        groups combine to the widest default, superadmins are not stored.
        """

        user, group = quota_user
        repo = UsersRepository(db_session)
        wide_group = await repo.create_user_group(UserGroupCreate(name=f"quota-wide-{uuid.uuid4().hex[:8]}"))

        # a second membership with a wider default wins
        await repo.add_member_to_user_group(wide_group.user_group_id, user)
        await repo.update_user_group(
            group.user_group_id, UserGroupUpdate(default_max_nodes=7, default_max_running_nodes=2)
        )
        await repo.update_user_group(
            wide_group.user_group_id, UserGroupUpdate(default_max_nodes=100, default_max_running_nodes=4)
        )
        state = UserQuotaState.instance()
        await state.reload(db_session)
        limits = state.get(user.username)
        assert limits is not None
        assert limits.max_nodes == 100  # widest group default
        assert limits.max_running_nodes == 4

        # an unset (or -1) group default is unlimited and wins over any number
        await repo.update_user_group(group.user_group_id, UserGroupUpdate(default_max_running_nodes=-1))
        await state.reload(db_session)
        assert state.get(user.username).max_running_nodes is None

        # an unlimited group default makes everything unlimited
        await repo.update_user_group(wide_group.user_group_id, UserGroupUpdate(default_max_nodes=-1))
        await state.reload(db_session)
        assert state.get(user.username).max_nodes is None

        # the user override beats every group
        await repo.update_user(user.user_id, UserUpdate(max_nodes=5))
        await state.reload(db_session)
        assert state.get(user.username).max_nodes == 5

        # superadmins are never stored: not limited
        assert state.get("admin") is None

    async def test_me_quotas_requires_authentication(self, app: FastAPI, client: AsyncClient) -> None:
        """
        Per-request header keeps the 401 assertion order-independent.
        """

        response = await client.get(
            app.url_path_for("get_logged_in_user_quotas"), headers={"Authorization": "Bearer wrong_token"}
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
