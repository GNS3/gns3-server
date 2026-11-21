#!/usr/bin/env python
#
# Copyright (C) 2026 GNS3 Technologies Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General License as published by
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
Tests for the per-user preferences document (self-access endpoints).

Each test resets the documents it touches so the file stays order-independent.
"""

import pytest
import pytest_asyncio
from fastapi import FastAPI, status
from httpx import AsyncClient

from gns3server.schemas.controller.users import User
from gns3server.services import auth_service
from gns3server.services.authentication import DEFAULT_JWT_SECRET_KEY

pytestmark = pytest.mark.asyncio


class TestUserPreferencesRoutes:
    @pytest_asyncio.fixture
    async def user1_headers(self, test_user: User) -> dict:

        access_token = auth_service.create_access_token(test_user.username, secret_key=DEFAULT_JWT_SECRET_KEY)
        return {"Authorization": f"Bearer {access_token}"}

    async def test_get_never_saved(self, app: FastAPI, client: AsyncClient) -> None:

        await client.delete(app.url_path_for("reset_logged_in_user_preferences"))
        response = await client.get(app.url_path_for("get_logged_in_user_preferences"))
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"preferences": {}, "updated_at": None}

    async def test_save_and_get(self, app: FastAPI, client: AsyncClient) -> None:

        await client.delete(app.url_path_for("reset_logged_in_user_preferences"))
        preferences = {"version": 1, "theme": "dark", "console": {"font_size": 12, "type": "telnet"}}
        response = await client.put(app.url_path_for("update_logged_in_user_preferences"), json=preferences)
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["preferences"] == preferences
        assert body["updated_at"] is not None

        response = await client.get(app.url_path_for("get_logged_in_user_preferences"))
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["preferences"] == preferences

    async def test_put_replaces_whole_document(self, app: FastAPI, client: AsyncClient) -> None:

        await client.put(app.url_path_for("update_logged_in_user_preferences"), json={"version": 1, "old": True})
        response = await client.put(app.url_path_for("update_logged_in_user_preferences"), json={"version": 2})
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["preferences"] == {"version": 2}

    async def test_put_rejects_oversized_document(self, app: FastAPI, client: AsyncClient) -> None:

        oversized = {"blob": "x" * (300 * 1024)}
        response = await client.put(app.url_path_for("update_logged_in_user_preferences"), json=oversized)
        assert response.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE

    async def test_put_rejects_non_object_document(self, app: FastAPI, client: AsyncClient) -> None:

        response = await client.put(app.url_path_for("update_logged_in_user_preferences"), json=[1, 2, 3])
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

        response = await client.put(app.url_path_for("update_logged_in_user_preferences"), json="not an object")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_delete(self, app: FastAPI, client: AsyncClient) -> None:

        await client.put(app.url_path_for("update_logged_in_user_preferences"), json={"theme": "light"})
        response = await client.delete(app.url_path_for("reset_logged_in_user_preferences"))
        assert response.status_code == status.HTTP_204_NO_CONTENT

        response = await client.get(app.url_path_for("get_logged_in_user_preferences"))
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"preferences": {}, "updated_at": None}

    async def test_delete_when_never_saved(self, app: FastAPI, client: AsyncClient) -> None:

        await client.delete(app.url_path_for("reset_logged_in_user_preferences"))
        response = await client.delete(app.url_path_for("reset_logged_in_user_preferences"))
        assert response.status_code == status.HTTP_204_NO_CONTENT

    async def test_documents_are_isolated_per_user(
        self, app: FastAPI, client: AsyncClient, user1_headers: dict
    ) -> None:

        await client.put(app.url_path_for("update_logged_in_user_preferences"), json={"who": "admin"})
        await client.delete(app.url_path_for("reset_logged_in_user_preferences"), headers=user1_headers)

        # user1 sees no trace of the admin document and writes its own
        response = await client.get(app.url_path_for("get_logged_in_user_preferences"), headers=user1_headers)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["preferences"] == {}

        response = await client.put(
            app.url_path_for("update_logged_in_user_preferences"), json={"who": "user1"}, headers=user1_headers
        )
        assert response.status_code == status.HTTP_200_OK

        # and the admin document is untouched
        response = await client.get(app.url_path_for("get_logged_in_user_preferences"))
        assert response.json()["preferences"] == {"who": "admin"}

    async def test_authentication_required(self, app: FastAPI, client: AsyncClient) -> None:

        headers = {"Authorization": "Bearer invalid_token"}
        response = await client.get(app.url_path_for("get_logged_in_user_preferences"), headers=headers)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

        response = await client.put(
            app.url_path_for("update_logged_in_user_preferences"), json={"a": 1}, headers=headers
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

        response = await client.delete(app.url_path_for("reset_logged_in_user_preferences"), headers=headers)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
