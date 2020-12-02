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

from fastapi import FastAPI, status
from fastapi.encoders import jsonable_encoder
from httpx import AsyncClient

from gns3server.db.repositories.users import UsersRepository
from gns3server.schemas.users import User

pytestmark = pytest.mark.asyncio


# async def test_route_exist(app: FastAPI, client: AsyncClient) -> None:
#
#     params = {"username": "test_username", "email": "user@email.com", "password": "test_password"}
#     response = await client.post(app.url_path_for("create_user"), json=params)
#     assert response.status_code != status.HTTP_404_NOT_FOUND
#
#
# async def test_users_can_register_successfully(app: FastAPI, client: AsyncClient) -> None:
#
#     user_repo = UsersRepository()
#     params = {"username": "test_username2", "email": "user2@email.com", "password": "test_password2"}
#
#     # make sure the user doesn't exist in the database
#     user_in_db = await user_repo.get_user_by_username(params["username"])
#     assert user_in_db is None
#
#     # register the user
#     res = await client.post(app.url_path_for("create_user"), json=params)
#     assert res.status_code == status.HTTP_201_CREATED
#
#     # make sure the user does exists in the database now
#     user_in_db = await user_repo.get_user_by_username(params["username"])
#     assert user_in_db is not None
#     assert user_in_db.email == params["email"]
#     assert user_in_db.username == params["username"]
#
#     # check that the user returned in the response is equal to the user in the database
#     created_user = User(**res.json()).json()
#     print(created_user)
#     #print(user_in_db.__dict__)
#     test = jsonable_encoder(user_in_db.__dict__, exclude={"_sa_instance_state", "hashed_password"})
#     print(test)
#     assert created_user == test
