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

import pytest
from fastapi import FastAPI, status
from httpx import AsyncClient
from ldap3 import ALL, MOCK_SYNC, Connection, Server
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from gns3server.config import Config
from gns3server.db.repositories.users import UsersRepository
from gns3server.services import auth_service, ldap_service
from gns3server.services.authentication import DEFAULT_JWT_SECRET_KEY

pytestmark = pytest.mark.asyncio

FORM_HEADERS = {"content-type": "application/x-www-form-urlencoded"}


@pytest.fixture
def mock_ldap_directory(config: Config):
    server = Server("mock_ldap_controller", get_info=ALL)
    conn = Connection(
        server, user="cn=admin,dc=example,dc=com", password="placeholder_password", client_strategy=MOCK_SYNC
    )
    conn.bind()

    # Service account
    conn.strategy.add_entry("cn=admin,dc=example,dc=com", {"userPassword": "placeholder_password", "cn": "admin"})

    # Directory users
    conn.strategy.add_entry(
        "uid=alice,ou=users,dc=example,dc=com",
        {
            "objectClass": ["person", "inetOrgPerson"],
            "uid": "alice",
            "cn": "Alice Wonderland",
            "mail": "alice@example.com",
            "userPassword": "mock_alice_secret",
            "memberOf": ["cn=GNS3-Admins,ou=groups,dc=example,dc=com"],
        },
    )

    conn.strategy.add_entry(
        "uid=bob,ou=users,dc=example,dc=com",
        {
            "objectClass": ["person", "inetOrgPerson"],
            "uid": "bob",
            "cn": "Bob Builder",
            "mail": "bob@example.com",
            "userPassword": "mock_bob_secret",
            "memberOf": ["cn=GNS3-Users,ou=groups,dc=example,dc=com"],
        },
    )

    # Configure LDAP in server settings
    orig_settings = config.settings.LDAP.model_copy()
    config.settings.LDAP.enabled = True
    config.settings.LDAP.uri = "ldap://mock_ldap_controller:389"
    config.settings.LDAP.bind_dn = "cn=admin,dc=example,dc=com"
    config.settings.LDAP.bind_password = SecretStr("placeholder_password")
    config.settings.LDAP.base_dn = "ou=users,dc=example,dc=com"
    config.settings.LDAP.group_mapping = {"GNS3-Admins": "Administrators", "GNS3-Users": "Users"}
    config.settings.LDAP.default_group = "Users"
    config.settings.LDAP.fallback_to_local = True

    # Point ldap_service to this mock server
    orig_server = ldap_service._server
    orig_strategy = ldap_service._client_strategy
    ldap_service._server = server
    ldap_service._client_strategy = MOCK_SYNC

    yield conn

    # Teardown
    ldap_service._server = orig_server
    ldap_service._client_strategy = orig_strategy
    config.settings.LDAP = orig_settings


class TestLdapAuthentication:
    async def test_ldap_login_form_and_jit_provisioning(
        self, app: FastAPI, unauthorized_client: AsyncClient, db_session: AsyncSession, mock_ldap_directory
    ) -> None:
        """
        Verify OAuth2 password form login via /v3/access/users/login creates user in SQLite and returns token.
        """
        users_repo = UsersRepository(db_session)
        assert await users_repo.get_user_by_username("alice") is None

        response = await unauthorized_client.post(
            app.url_path_for("login"), data={"username": "alice", "password": "mock_alice_secret"}, headers=FORM_HEADERS
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

        # Verify JIT provisioning in SQLite
        db_user = await users_repo.get_user_by_username("alice")
        assert db_user is not None
        assert db_user.username == "alice"
        assert db_user.email == "alice@example.com"
        assert db_user.full_name == "Alice Wonderland"
        assert db_user.auth_source == "ldap"
        assert db_user.hashed_password is None
        assert db_user.is_active is True

        # Verify group mapping
        memberships = await users_repo.get_user_memberships(db_user.user_id)
        assert any(grp.name == "Administrators" for grp in memberships)

    async def test_ldap_authenticate_json_endpoint(
        self, app: FastAPI, unauthorized_client: AsyncClient, db_session: AsyncSession, mock_ldap_directory
    ) -> None:
        """
        Verify JSON authentication via /v3/access/users/authenticate.
        """
        users_repo = UsersRepository(db_session)
        assert await users_repo.get_user_by_username("bob") is None

        response = await unauthorized_client.post(
            app.url_path_for("authenticate"), json={"username": "bob", "password": "mock_bob_secret"}
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data

        # Verify JIT provisioning in SQLite
        db_user = await users_repo.get_user_by_username("bob")
        assert db_user is not None
        assert db_user.auth_source == "ldap"
        memberships = await users_repo.get_user_memberships(db_user.user_id)
        assert any(grp.name == "Users" for grp in memberships)

    async def test_ldap_wrong_password_rejected(
        self, app: FastAPI, unauthorized_client: AsyncClient, mock_ldap_directory
    ) -> None:
        response = await unauthorized_client.post(
            app.url_path_for("login"), data={"username": "alice", "password": "wrong_password"}, headers=FORM_HEADERS
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_emergency_superadmin_fallback_works_when_ldap_enabled(
        self, app: FastAPI, unauthorized_client: AsyncClient, mock_ldap_directory
    ) -> None:
        """
        Local superadmin can always log in even when LDAP is enabled.
        """
        response = await unauthorized_client.post(
            app.url_path_for("login"), data={"username": "admin", "password": "admin"}, headers=FORM_HEADERS
        )
        assert response.status_code == status.HTTP_200_OK

    async def test_local_user_fallback_when_enabled(
        self, app: FastAPI, unauthorized_client: AsyncClient, client: AsyncClient, mock_ldap_directory
    ) -> None:
        """
        Local users not in LDAP can log in when fallback_to_local is True.
        """
        resp = await client.post(
            app.url_path_for("create_user"),
            json={"username": "local_user", "email": "local@example.com", "password": "mock_local_password"},
        )
        assert resp.status_code == status.HTTP_201_CREATED

        response = await unauthorized_client.post(
            app.url_path_for("login"),
            data={"username": "local_user", "password": "mock_local_password"},
            headers=FORM_HEADERS,
        )
        assert response.status_code == status.HTTP_200_OK

    async def test_local_user_fallback_rejected_when_disabled(
        self, app: FastAPI, unauthorized_client: AsyncClient, client: AsyncClient, config: Config, mock_ldap_directory
    ) -> None:
        """
        Local users not in LDAP cannot log in when fallback_to_local is False.
        """
        config.settings.LDAP.fallback_to_local = False

        resp = await client.post(
            app.url_path_for("create_user"),
            json={"username": "local_only_user", "email": "local_only@example.com", "password": "mock_local_password"},
        )
        assert resp.status_code == status.HTTP_201_CREATED

        response = await unauthorized_client.post(
            app.url_path_for("login"),
            data={"username": "local_only_user", "password": "mock_local_password"},
            headers=FORM_HEADERS,
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_ldap_user_cannot_change_password(
        self, app: FastAPI, client: AsyncClient, db_session: AsyncSession, mock_ldap_directory
    ) -> None:
        """
        Directory-authenticated users cannot change their password via /me or admin update.
        """
        users_repo = UsersRepository(db_session)
        user = await users_repo.authenticate_user("alice", "mock_alice_secret")
        assert user is not None
        assert user.auth_source == "ldap"

        token = auth_service.create_access_token(user.username, secret_key=DEFAULT_JWT_SECRET_KEY)

        # 1. Alice tries to change her password via PUT /me
        response = await client.put(
            app.url_path_for("update_logged_in_user"),
            headers={"Authorization": f"Bearer {token}"},
            json={"password": "mock_new_password"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Password cannot be changed for directory-authenticated users" in response.json()["message"]

        # 2. Administrator tries to change Alice's password via PUT /{user_id} when LDAP is enabled
        admin_response = await client.put(
            app.url_path_for("update_user", user_id=user.user_id),
            json={"password": "mock_new_password"},
        )
        assert admin_response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Password cannot be changed for directory-authenticated users" in admin_response.json()["message"]

        # 3. When LDAP is disabled, Administrator can reset password and user becomes local
        Config.instance().settings.LDAP.enabled = False
        try:
            admin_reset = await client.put(
                app.url_path_for("update_user", user_id=user.user_id),
                json={"password": "mock_new_password_123"},
            )
            assert admin_reset.status_code == status.HTTP_200_OK
            updated_alice = await users_repo.get_user(user.user_id)
            assert updated_alice.auth_source == "local"
        finally:
            Config.instance().settings.LDAP.enabled = True

    async def test_ldap_login_returns_canonical_username_in_token(
        self, app: FastAPI, unauthorized_client: AsyncClient, mock_ldap_directory
    ) -> None:
        """
        Verify that login response includes the canonical username.
        """
        response = await unauthorized_client.post(
            app.url_path_for("login"), data={"username": "alice", "password": "mock_alice_secret"}, headers=FORM_HEADERS
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data.get("username") == "alice"

    async def test_ldap_account_linking_by_email_prevents_duplicate_user(
        self,
        app: FastAPI,
        unauthorized_client: AsyncClient,
        db_session: AsyncSession,
        config: Config,
        mock_ldap_directory,
    ) -> None:
        """
        Verify that logging in with an email and later logging in with a short name links to the exact same user_id.
        """
        config.settings.LDAP.user_search_filter = (
            "(&(objectClass=person)(|(uid={username})(sAMAccountName={username})(mail={username})))"
        )
        users_repo = UsersRepository(db_session)

        # 1. Login with email
        resp1 = await unauthorized_client.post(
            app.url_path_for("login"),
            data={"username": "alice@example.com", "password": "mock_alice_secret"},
            headers=FORM_HEADERS,
        )
        assert resp1.status_code == status.HTTP_200_OK
        first_user = await users_repo.get_user_by_email("alice@example.com")
        assert first_user is not None
        first_user_id = first_user.user_id

        # 2. Login with short username
        resp2 = await unauthorized_client.post(
            app.url_path_for("login"), data={"username": "alice", "password": "mock_alice_secret"}, headers=FORM_HEADERS
        )
        assert resp2.status_code == status.HTTP_200_OK

        # 3. Verify user was linked, username updated to canonical, and no duplicate user exists
        linked_user = await users_repo.get_user(first_user_id)
        assert linked_user is not None
        assert linked_user.username == "alice"
        assert linked_user.email == "alice@example.com"

        # Ensure only 1 user exists for Alice in database
        all_alices = [u for u in await users_repo.get_users() if u.email == "alice@example.com"]
        assert len(all_alices) == 1

    async def test_ldap_superadmin_group_provisioning_and_revocation(
        self,
        app: FastAPI,
        unauthorized_client: AsyncClient,
        db_session: AsyncSession,
        config: Config,
        mock_ldap_directory,
    ) -> None:
        """
        Verify users in configured superadmin_groups receive is_superadmin=True,
        and users not in superadmin_groups receive is_superadmin=False.
        Also verify that removing the group revokes superadmin on next login.
        """
        config.settings.LDAP.superadmin_groups = ["GNS3-Admins"]
        users_repo = UsersRepository(db_session)

        # 1. Alice is in GNS3-Admins -> should be provisioned with is_superadmin=True
        resp_alice = await unauthorized_client.post(
            app.url_path_for("login"),
            data={"username": "alice", "password": "mock_alice_secret"},
            headers=FORM_HEADERS,
        )
        assert resp_alice.status_code == status.HTTP_200_OK
        alice_user = await users_repo.get_user_by_username("alice")
        assert alice_user is not None
        assert alice_user.is_superadmin is True

        # 2. Bob is in GNS3-Users -> should be provisioned with is_superadmin=False
        resp_bob = await unauthorized_client.post(
            app.url_path_for("login"),
            data={"username": "bob", "password": "mock_bob_secret"},
            headers=FORM_HEADERS,
        )
        assert resp_bob.status_code == status.HTTP_200_OK
        bob_user = await users_repo.get_user_by_username("bob")
        assert bob_user is not None
        assert bob_user.is_superadmin is False

        # 3. Remove GNS3-Admins from superadmin_groups -> Alice logs in again -> superadmin revoked
        config.settings.LDAP.superadmin_groups = []
        resp_alice2 = await unauthorized_client.post(
            app.url_path_for("login"),
            data={"username": "alice", "password": "mock_alice_secret"},
            headers=FORM_HEADERS,
        )
        assert resp_alice2.status_code == status.HTTP_200_OK
        alice_user_updated = await users_repo.get_user_by_username("alice")
        assert alice_user_updated is not None
        assert alice_user_updated.is_superadmin is False
