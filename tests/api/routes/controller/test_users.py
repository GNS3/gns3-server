#!/usr/bin/env python
#
# Copyright (C) 2020 GNS3 Technologies Inc.
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

from typing import Optional
from fastapi import FastAPI, HTTPException, status
from sqlalchemy import update
from httpx import AsyncClient
from jose import jwt

from sqlalchemy.ext.asyncio import AsyncSession
from gns3server.db.repositories.users import UsersRepository
from gns3server.db.repositories.rbac import RbacRepository
from gns3server.schemas.controller.rbac import Permission, HTTPMethods, PermissionAction
from gns3server.services import auth_service
from gns3server.config import Config
from gns3server.schemas.controller.users import User
from gns3server import schemas
import gns3server.db.models as models

pytestmark = pytest.mark.asyncio


class TestUserRoutes:

    async def test_route_exist(self, app: FastAPI, client: AsyncClient) -> None:

        new_user = {"username": "user1", "email": "user1@email.com", "password": "test_password"}
        response = await client.post(app.url_path_for("create_user"), json=new_user)
        assert response.status_code == status.HTTP_201_CREATED

    async def test_users_can_register_successfully(
            self,
            app: FastAPI,
            client: AsyncClient,
            db_session: AsyncSession
    ) -> None:

        user_repo = UsersRepository(db_session)
        params = {"username": "user2", "email": "user2@email.com", "password": "test_password"}

        # make sure the user doesn't exist in the database
        user_in_db = await user_repo.get_user_by_username(params["username"])
        assert user_in_db is None

        # register the user
        response = await client.post(app.url_path_for("create_user"), json=params)
        assert response.status_code == status.HTTP_201_CREATED

        # make sure the user does exists in the database now
        user_in_db = await user_repo.get_user_by_username(params["username"])
        assert user_in_db is not None
        assert user_in_db.email == params["email"]
        assert user_in_db.username == params["username"]

        # check that the user returned in the response is equal to the user in the database
        created_user = User(**response.json()).json()
        assert created_user == User.from_orm(user_in_db).json()

    @pytest.mark.parametrize(
        "attr, value, status_code",
        (
                ("email", "user2@email.com", status.HTTP_400_BAD_REQUEST),
                ("username", "user2", status.HTTP_400_BAD_REQUEST),
                ("email", "invalid_email@one@two.io", status.HTTP_422_UNPROCESSABLE_ENTITY),
                ("password", "short", status.HTTP_422_UNPROCESSABLE_ENTITY),
                ("username", "user2@#$%^<>", status.HTTP_422_UNPROCESSABLE_ENTITY),
                ("username", "ab", status.HTTP_422_UNPROCESSABLE_ENTITY),
        )
    )
    async def test_user_registration_fails_when_credentials_are_taken(
            self,
            app: FastAPI,
            client: AsyncClient,
            attr: str,
            value: str,
            status_code: int,
    ) -> None:

        new_user = {"email": "not_taken@email.com", "username": "not_taken_username", "password": "test_password"}
        new_user[attr] = value
        response = await client.post(app.url_path_for("create_user"), json=new_user)
        assert response.status_code == status_code

    @pytest.mark.parametrize(
        "attr, value, status_code",
        (
                ("email", "user@email.com", status.HTTP_200_OK),
                ("email", "user@email.com", status.HTTP_400_BAD_REQUEST),
                ("username", "user2", status.HTTP_400_BAD_REQUEST),
                ("email", "invalid_email@one@two.io", status.HTTP_422_UNPROCESSABLE_ENTITY),
                ("password", "short", status.HTTP_422_UNPROCESSABLE_ENTITY),
                ("username", "user2@#$%^<>", status.HTTP_422_UNPROCESSABLE_ENTITY),
                ("username", "ab", status.HTTP_422_UNPROCESSABLE_ENTITY),
                ("full_name", "John Doe", status.HTTP_200_OK),
                ("password", "password123", status.HTTP_200_OK),
                ("is_active", True, status.HTTP_200_OK),
        )
    )
    async def test_update_user(
            self,
            app: FastAPI,
            client: AsyncClient,
            db_session: AsyncSession,
            attr: str,
            value: str,
            status_code: int,
    ) -> None:

        user_repo = UsersRepository(db_session)
        user_in_db = await user_repo.get_user_by_username("user2")
        update_user = {}
        update_user[attr] = value
        response = await client.put(app.url_path_for("update_user", user_id=user_in_db.user_id), json=update_user)
        assert response.status_code == status_code

    async def test_users_saved_password_is_hashed(
        self,
        app: FastAPI,
        client: AsyncClient,
        db_session: AsyncSession
    ) -> None:

        user_repo = UsersRepository(db_session)
        new_user = {"username": "user3", "email": "user3@email.com", "password": "test_password"}

        # send post request to create user and ensure it is successful
        response = await client.post(app.url_path_for("create_user"), json=new_user)
        assert response.status_code == status.HTTP_201_CREATED

        # ensure that the users password is hashed in the db
        # and that we can verify it using our auth service
        user_in_db = await user_repo.get_user_by_username(new_user["username"])
        assert user_in_db is not None
        assert user_in_db.hashed_password != new_user["password"]
        assert auth_service.verify_password(new_user["password"], user_in_db.hashed_password)

    async def test_get_users(self, app: FastAPI, client: AsyncClient) -> None:

        response = await client.get(app.url_path_for("get_users"))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 4  # admin, user1, user2 and user3 should exist


class TestAuthTokens:

    async def test_can_create_token_successfully(
            self,
            app: FastAPI,
            client: AsyncClient,
            test_user: User,
            config: Config
    ) -> None:

        jwt_secret = config.settings.Controller.jwt_secret_key
        token = auth_service.create_access_token(test_user.username)
        payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
        username = payload.get("sub")
        assert username == test_user.username

    async def test_token_missing_user_is_invalid(self, app: FastAPI, client: AsyncClient, config: Config) -> None:

        jwt_secret = config.settings.Controller.jwt_secret_key
        token = auth_service.create_access_token(None)
        with pytest.raises(jwt.JWTError):
            jwt.decode(token, jwt_secret, algorithms=["HS256"])

    async def test_can_retrieve_username_from_token(
            self,
            app: FastAPI,
            client: AsyncClient,
            test_user: User
    ) -> None:

        token = auth_service.create_access_token(test_user.username)
        username = auth_service.get_username_from_token(token)
        assert username == test_user.username

    @pytest.mark.parametrize(
        "wrong_secret, wrong_token",
        (
                ("use correct secret", "asdf"),  # use wrong token
                ("use correct secret", ""),  # use wrong token
                ("ABC123", "use correct token"),  # use wrong secret
        ),
    )
    async def test_error_when_token_or_secret_is_wrong(
            self,
            app: FastAPI,
            client: AsyncClient,
            test_user: User,
            wrong_secret: str,
            wrong_token: Optional[str],
            config,
    ) -> None:

        token = auth_service.create_access_token(test_user.username)
        if wrong_secret == "use correct secret":
            wrong_secret = config.settings.Controller.jwt_secret_key
        if wrong_token == "use correct token":
            wrong_token = token
        with pytest.raises(HTTPException):
            auth_service.get_username_from_token(wrong_token, secret_key=wrong_secret)


class TestUserLogin:

    async def test_user_can_login_successfully_and_receives_valid_token(
            self,
            app: FastAPI,
            unauthorized_client: AsyncClient,
            test_user: User,
            config: Config
    ) -> None:

        jwt_secret = config.settings.Controller.jwt_secret_key
        unauthorized_client.headers["content-type"] = "application/x-www-form-urlencoded"
        login_data = {
            "username": test_user.username,
            "password": "user1_password",
        }
        response = await unauthorized_client.post(app.url_path_for("login"), data=login_data)
        assert response.status_code == status.HTTP_200_OK

        # check that token exists in response and has user encoded within it
        token = response.json().get("access_token")
        payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
        assert "sub" in payload
        username = payload.get("sub")
        assert username == test_user.username

        # check that token is proper type
        assert "token_type" in response.json()
        assert response.json().get("token_type") == "bearer"

    async def test_user_can_authenticate_using_json(
            self,
            app: FastAPI,
            unauthorized_client: AsyncClient,
            test_user: User,
            config: Config
    ) -> None:

        credentials = {
            "username": test_user.username,
            "password": "user1_password",
        }
        response = await unauthorized_client.post(app.url_path_for("authenticate"), json=credentials)
        assert response.status_code == status.HTTP_200_OK
        assert response.json().get("access_token")

    @pytest.mark.parametrize(
        "username, password, status_code",
        (
            ("wrong_username", "user1_password", status.HTTP_401_UNAUTHORIZED),
            ("user1", "wrong_password", status.HTTP_401_UNAUTHORIZED),
            ("user1", None, status.HTTP_422_UNPROCESSABLE_ENTITY),
        ),
    )
    async def test_user_with_wrong_creds_doesnt_receive_token(
        self,
        app: FastAPI,
        unauthorized_client: AsyncClient,
        test_user: User,
        username: str,
        password: str,
        status_code: int,
    ) -> None:

        unauthorized_client.headers["content-type"] = "application/x-www-form-urlencoded"
        login_data = {
            "username": username,
            "password": password,
        }
        response = await unauthorized_client.post(app.url_path_for("login"), data=login_data)
        assert response.status_code == status_code
        assert "access_token" not in response.json()

    async def test_user_can_use_token_as_url_param(
            self,
            app: FastAPI,
            unauthorized_client: AsyncClient,
            test_user: User,
            config: Config
    ) -> None:

        credentials = {
            "username": test_user.username,
            "password": "user1_password",
        }

        response = await unauthorized_client.post(app.url_path_for("authenticate"), json=credentials)
        assert response.status_code == status.HTTP_200_OK
        token = response.json().get("access_token")

        response = await unauthorized_client.get(app.url_path_for("get_projects"), params={"token": token})
        assert response.status_code == status.HTTP_200_OK


class TestUserMe:

    async def test_authenticated_user_can_retrieve_own_data(
            self,
            app: FastAPI,
            authorized_client: AsyncClient,
            test_user: User,
    ) -> None:

        response = await authorized_client.get(app.url_path_for("get_logged_in_user"))
        assert response.status_code == status.HTTP_200_OK
        user = User(**response.json())
        assert user.username == test_user.username
        assert user.email == test_user.email
        assert user.user_id == test_user.user_id

    async def test_user_cannot_access_own_data_if_not_authenticated(
            self, app: FastAPI,
            unauthorized_client: AsyncClient,
            test_user: User,
    ) -> None:

        response = await unauthorized_client.get(app.url_path_for("get_logged_in_user"))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_authenticated_user_can_update_own_data(
            self,
            app: FastAPI,
            authorized_client: AsyncClient,
            test_user: User,
    ) -> None:

        response = await authorized_client.get(app.url_path_for("get_logged_in_user"))
        assert response.status_code == status.HTTP_200_OK
        user = User(**response.json())
        assert user.username == test_user.username
        assert user.email == test_user.email
        assert user.user_id == test_user.user_id

    # logged in users can only change their email, full name and password
    @pytest.mark.parametrize(
        "attr, value, status_code",
        (
                ("email", "user42@email.com", status.HTTP_200_OK),
                ("email", "user42@email.com", status.HTTP_400_BAD_REQUEST),
                ("full_name", "John Doe", status.HTTP_200_OK),
                ("password", "password123", status.HTTP_200_OK),
        )
    )
    async def test_authenticated_user_can_update_own_data(
            self,
            app: FastAPI,
            authorized_client: AsyncClient,
            attr: str,
            value: str,
            status_code: int,
    ) -> None:

        update_user = {}
        update_user[attr] = value
        response = await authorized_client.put(
            app.url_path_for("update_logged_in_user"),
            json=update_user
        )
        assert response.status_code == status_code


class TestSuperAdmin:

    async def test_super_admin_exists(
            self,
            app: FastAPI,
            client: AsyncClient,
            db_session: AsyncSession
    ) -> None:

        user_repo = UsersRepository(db_session)
        admin_in_db = await user_repo.get_user_by_username("admin")
        assert admin_in_db is not None
        assert auth_service.verify_password("admin", admin_in_db.hashed_password)

    async def test_cannot_delete_super_admin(
            self,
            app: FastAPI,
            client: AsyncClient,
            db_session: AsyncSession
    ) -> None:

        user_repo = UsersRepository(db_session)
        admin_in_db = await user_repo.get_user_by_username("admin")
        response = await client.delete(app.url_path_for("delete_user", user_id=admin_in_db.user_id))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    async def test_admin_can_login_after_password_recovery(
            self,
            app: FastAPI,
            unauthorized_client: AsyncClient,
            db_session: AsyncSession
    ) -> None:

        # set the admin password to null in the database
        query = update(models.User).where(models.User.username == "admin").values(hashed_password=None)
        await db_session.execute(query)
        await db_session.commit()

        unauthorized_client.headers["content-type"] = "application/x-www-form-urlencoded"
        login_data = {
            "username": "admin",
            "password": "whatever",
        }
        response = await unauthorized_client.post(app.url_path_for("login"), data=login_data)
        assert response.status_code == status.HTTP_200_OK

    # async def test_super_admin_belongs_to_admin_group(
    #         self,
    #         app: FastAPI,
    #         client: AsyncClient,
    #         db_session: AsyncSession
    # ) -> None:
    #
    #     user_repo = UsersRepository(db_session)
    #     admin_in_db = await user_repo.get_user_by_username("admin")
    #     response = await client.get(app.url_path_for("get_user_memberships", user_id=admin_in_db.user_id))
    #     assert response.status_code == status.HTTP_200_OK
    #     assert len(response.json()) == 1


@pytest_asyncio.fixture
async def test_permission(db_session: AsyncSession) -> Permission:

    new_permission = schemas.PermissionCreate(
        methods=[HTTPMethods.get],
        path="/statistics",
        action=PermissionAction.allow
    )
    rbac_repo = RbacRepository(db_session)
    existing_permission = await rbac_repo.get_permission_by_path("/statistics")
    if existing_permission:
        return existing_permission
    return await rbac_repo.create_permission(new_permission)


class TestUserPermissionsRoutes:

    async def test_add_permission_to_user(
            self,
            app: FastAPI,
            client: AsyncClient,
            test_user: User,
            test_permission: Permission,
            db_session: AsyncSession
    ) -> None:

        response = await client.put(
            app.url_path_for(
                "add_permission_to_user",
                user_id=str(test_user.user_id),
                permission_id=str(test_permission.permission_id)
            )
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        rbac_repo = RbacRepository(db_session)
        permissions = await rbac_repo.get_user_permissions(test_user.user_id)
        assert len(permissions) == 1
        assert permissions[0].permission_id == test_permission.permission_id

    async def test_get_user_permissions(
            self,
            app: FastAPI,
            client: AsyncClient,
            test_user: User,
            db_session: AsyncSession
    ) -> None:

        response = await client.get(
            app.url_path_for(
                "get_user_permissions",
                user_id=str(test_user.user_id))
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 1

    async def test_remove_permission_from_user(
            self,
            app: FastAPI,
            client: AsyncClient,
            test_user: User,
            test_permission: Permission,
            db_session: AsyncSession
    ) -> None:

        response = await client.delete(
            app.url_path_for(
                "remove_permission_from_user",
                user_id=str(test_user.user_id),
                permission_id=str(test_permission.permission_id)
            ),
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        rbac_repo = RbacRepository(db_session)
        permissions = await rbac_repo.get_user_permissions(test_user.user_id)
        assert len(permissions) == 0
