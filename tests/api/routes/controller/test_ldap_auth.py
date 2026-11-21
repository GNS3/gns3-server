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

from typing import Optional

import pytest
import pytest_asyncio
from fastapi import FastAPI, status
from httpx import AsyncClient
from ldap3 import ALL, MOCK_SYNC, Connection, Server
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from gns3server.config import Config
from gns3server.db import models
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
    @pytest_asyncio.fixture
    async def users_group_id(self, db_session: AsyncSession) -> Optional[str]:
        grp = await UsersRepository(db_session).get_user_group_by_name("Users")
        return str(grp.user_group_id) if grp else None

    @staticmethod
    def _user_payload(base: dict, group_id: Optional[str] = None) -> dict:
        payload = dict(base)
        if group_id and "user_group_id" not in payload:
            payload["user_group_id"] = group_id
        return payload

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
        self,
        app: FastAPI,
        unauthorized_client: AsyncClient,
        client: AsyncClient,
        mock_ldap_directory,
        users_group_id: Optional[str],
    ) -> None:
        """
        Local users not in LDAP can log in when fallback_to_local is True.
        """
        resp = await client.post(
            app.url_path_for("create_user"),
            json=self._user_payload(
                {"username": "local_user", "email": "local@example.com", "password": "mock_local_password"},
                users_group_id,
            ),
        )
        assert resp.status_code == status.HTTP_201_CREATED

        response = await unauthorized_client.post(
            app.url_path_for("login"),
            data={"username": "local_user", "password": "mock_local_password"},
            headers=FORM_HEADERS,
        )
        assert response.status_code == status.HTTP_200_OK

    async def test_local_user_fallback_rejected_when_disabled(
        self,
        app: FastAPI,
        unauthorized_client: AsyncClient,
        client: AsyncClient,
        config: Config,
        mock_ldap_directory,
        users_group_id: Optional[str],
    ) -> None:
        """
        Local users not in LDAP cannot log in when fallback_to_local is False.
        """
        config.settings.LDAP.fallback_to_local = False

        resp = await client.post(
            app.url_path_for("create_user"),
            json=self._user_payload(
                {"username": "local_only_user", "email": "local_only@example.com", "password": "mock_local_password"},
                users_group_id,
            ),
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

    async def test_put_user_cannot_arbitrarily_change_auth_source(
        self, app: FastAPI, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """
        Verify that auth_source is not accepted in public UserUpdate payload
        and callers cannot arbitrarily change an account's auth_source.
        """
        users_repo = UsersRepository(db_session)
        user = await users_repo.get_user_by_username("admin")
        assert user.auth_source == "local"

        response = await client.put(
            app.url_path_for("update_user", user_id=user.user_id),
            json={"auth_source": "ldap", "full_name": "Admin Changed"},
        )
        assert response.status_code == status.HTTP_200_OK
        updated_user = await users_repo.get_user(user.user_id)
        assert updated_user.auth_source == "local"
        assert updated_user.full_name == "Admin Changed"

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

        # 3. Verify user was linked to the same account and no duplicate user exists
        linked_user = await users_repo.get_user(first_user_id)
        assert linked_user is not None
        assert linked_user.username == "alice"
        assert linked_user.email == "alice@example.com"
        assert resp2.json().get("username") == "alice"

        # Ensure only 1 user exists for Alice in database
        all_alices = [u for u in await users_repo.get_users() if u.email == "alice@example.com"]
        assert len(all_alices) == 1

    async def test_ldap_account_linking_preserves_existing_username_against_project_cutoff(
        self,
        app: FastAPI,
        unauthorized_client: AsyncClient,
        client: AsyncClient,
        db_session: AsyncSession,
        mock_ldap_directory,
    ) -> None:
        """
        Verify that when an existing LDAP account has a username that differs from LDAP's canonical name,
        the username is strictly preserved to prevent severing project ownership on disk (created_by string).
        """
        mock_ldap_directory.strategy.add_entry(
            "uid=frank_canonical,ou=users,dc=example,dc=com",
            {
                "objectClass": ["person", "inetOrgPerson"],
                "uid": "frank_canonical",
                "cn": "Frank Sinatra",
                "mail": "frank@example.com",
                "userPassword": "mock_frank_secret",
                "memberOf": ["cn=GNS3-Users,ou=groups,dc=example,dc=com"],
            },
        )

        users_repo = UsersRepository(db_session)

        # 1. Pre-create account with a legacy/existing username
        pre_user = models.User(
            username="frank_legacy",
            email="frank@example.com",
            full_name="Frank Sinatra",
            auth_source="ldap",
            is_active=True,
        )
        db_session.add(pre_user)
        await db_session.commit()
        await db_session.refresh(pre_user)
        assert pre_user.username == "frank_legacy"
        pre_user_id = pre_user.user_id

        # 2. Frank logs in with LDAP credentials where canonical name is 'frank_canonical'
        resp = await unauthorized_client.post(
            app.url_path_for("login"),
            data={"username": "frank_canonical", "password": "mock_frank_secret"},
            headers=FORM_HEADERS,
        )
        assert resp.status_code == status.HTTP_200_OK

        # 3. Verify that the account was linked, but the username was NOT renamed to frank_canonical
        db_user = await users_repo.get_user(pre_user_id)
        assert db_user is not None
        assert db_user.username == "frank_legacy"
        assert db_user.email == "frank@example.com"

    async def test_ldap_user_without_matching_groups_receives_fallback_users_group(
        self,
        app: FastAPI,
        unauthorized_client: AsyncClient,
        db_session: AsyncSession,
        mock_ldap_directory,
    ) -> None:
        """
        Verify that a directory user with no mapped groups is safely assigned the fallback
        default group ('Users') to prevent being an unprivileged ghost account in RBAC.
        """
        mock_ldap_directory.strategy.add_entry(
            "uid=edward,ou=users,dc=example,dc=com",
            {
                "objectClass": ["person", "inetOrgPerson"],
                "uid": "edward",
                "cn": "Edward Scissorhands",
                "mail": "edward@example.com",
                "userPassword": "mock_edward_secret",
                "memberOf": ["cn=Unmapped-AD-Group,ou=groups,dc=example,dc=com"],
            },
        )

        users_repo = UsersRepository(db_session)
        resp = await unauthorized_client.post(
            app.url_path_for("login"),
            data={"username": "edward", "password": "mock_edward_secret"},
            headers=FORM_HEADERS,
        )
        assert resp.status_code == status.HTTP_200_OK

        edward_user = await users_repo.get_user_by_username("edward")
        assert edward_user is not None
        memberships = await users_repo.get_user_memberships(edward_user.user_id)
        assert any(grp.name == "Users" for grp in memberships)

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

    async def test_existing_local_user_transitions_to_ldap_and_preserves_password_for_dr(
        self,
        app: FastAPI,
        unauthorized_client: AsyncClient,
        client: AsyncClient,
        db_session: AsyncSession,
        mock_ldap_directory,
        users_group_id: Optional[str],
    ) -> None:
        """
        Verify that an existing local user:
        1. Transitions auth_source to 'ldap' upon successful LDAP login.
        2. Preserves their hashed_password for Disaster Recovery.
        3. Can log in with their local password when LDAP is globally disabled.
        """
        mock_ldap_directory.strategy.add_entry(
            "uid=charlie,ou=users,dc=example,dc=com",
            {
                "objectClass": ["person", "inetOrgPerson"],
                "uid": "charlie",
                "cn": "Charlie Brown",
                "mail": "charlie@example.com",
                "userPassword": "mock_charlie_secret",
                "memberOf": ["cn=GNS3-Admins,ou=groups,dc=example,dc=com"],
            },
        )

        users_repo = UsersRepository(db_session)
        # 1. Pre-create local user 'charlie' with local password
        resp = await client.post(
            app.url_path_for("create_user"),
            json=self._user_payload(
                {"username": "charlie", "email": "charlie@local.dev", "password": "mock_local_charlie_password"},
                users_group_id,
            ),
        )
        assert resp.status_code == status.HTTP_201_CREATED
        local_user = await users_repo.get_user_by_username("charlie")
        assert local_user is not None
        assert local_user.auth_source == "local"
        assert local_user.hashed_password is not None
        saved_hashed_password = local_user.hashed_password

        # 2. Login with LDAP credentials
        ldap_login = await unauthorized_client.post(
            app.url_path_for("login"),
            data={"username": "charlie", "password": "mock_charlie_secret"},
            headers=FORM_HEADERS,
        )
        assert ldap_login.status_code == status.HTTP_200_OK

        # 3. Verify user transitioned to 'ldap' but preserved hashed_password
        transitioned_user = await users_repo.get_user_by_username("charlie")
        assert transitioned_user is not None
        assert transitioned_user.auth_source == "ldap"
        assert transitioned_user.hashed_password == saved_hashed_password

        # 4. While LDAP is enabled, local password cannot be used by directory account
        bad_local_login = await unauthorized_client.post(
            app.url_path_for("login"),
            data={"username": "charlie", "password": "mock_local_charlie_password"},
            headers=FORM_HEADERS,
        )
        assert bad_local_login.status_code == status.HTTP_401_UNAUTHORIZED

        # 5. Disaster Recovery: Admin disables LDAP globally -> local password works
        Config.instance().settings.LDAP.enabled = False
        try:
            dr_local_login = await unauthorized_client.post(
                app.url_path_for("login"),
                data={"username": "charlie", "password": "mock_local_charlie_password"},
                headers=FORM_HEADERS,
            )
            assert dr_local_login.status_code == status.HTTP_200_OK
        finally:
            Config.instance().settings.LDAP.enabled = True

    async def test_managed_only_group_sync_preserves_local_groups(
        self,
        app: FastAPI,
        unauthorized_client: AsyncClient,
        client: AsyncClient,
        db_session: AsyncSession,
        mock_ldap_directory,
        users_group_id: Optional[str],
    ) -> None:
        """
        Verify that directory-managed group sync only modifies groups mapped
        from LDAP/AD (or default group), leaving local-only groups untouched.
        """
        mock_ldap_directory.strategy.add_entry(
            "uid=david,ou=users,dc=example,dc=com",
            {
                "objectClass": ["person", "inetOrgPerson"],
                "uid": "david",
                "cn": "David Bowie",
                "mail": "david@example.com",
                "userPassword": "mock_david_secret",
                "memberOf": ["cn=GNS3-Users,ou=groups,dc=example,dc=com"],
            },
        )

        users_repo = UsersRepository(db_session)

        # 1. Create a custom local-only GNS3 group that is NOT in group_mapping
        group_resp = await client.post(
            app.url_path_for("create_user_group"),
            json={"name": "CCIE-Study-Cohort-1", "description": "Local study group"},
        )
        assert group_resp.status_code == status.HTTP_201_CREATED
        ccie_group = await users_repo.get_user_group_by_name("CCIE-Study-Cohort-1")
        assert ccie_group is not None

        # 2. Pre-create local user 'david' with membership in CCIE-Study-Cohort-1
        create_resp = await client.post(
            app.url_path_for("create_user"),
            json=self._user_payload(
                {"username": "david", "email": "david@local.dev", "password": "mock_david_password"},
                users_group_id,
            ),
        )
        assert create_resp.status_code == status.HTTP_201_CREATED
        david_user = await users_repo.get_user_by_username("david")
        assert david_user is not None

        # Assign david to CCIE-Study-Cohort-1 manually via API
        assign_resp = await client.put(
            app.url_path_for("add_member_to_group", user_group_id=ccie_group.user_group_id, user_id=david_user.user_id),
        )
        assert assign_resp.status_code == status.HTTP_204_NO_CONTENT

        # Verify initial membership has the local group
        initial_memberships = await users_repo.get_user_memberships(david_user.user_id)
        assert any(g.name == "CCIE-Study-Cohort-1" for g in initial_memberships)

        # 3. David logs in via LDAP (David has memberOf: GNS3-Users -> mapped to Users in mock_ldap_directory)
        login_resp = await unauthorized_client.post(
            app.url_path_for("login"),
            data={"username": "david", "password": "mock_david_secret"},
            headers=FORM_HEADERS,
        )
        assert login_resp.status_code == status.HTTP_200_OK

        # 4. Verify that David now has:
        # - The managed group 'Users' (added by JIT)
        # - AND RETAINS the local-only group 'CCIE-Study-Cohort-1' (NOT deleted by JIT)
        updated_memberships = await users_repo.get_user_memberships(david_user.user_id)
        group_names = {g.name for g in updated_memberships}
        assert "Users" in group_names
        assert "CCIE-Study-Cohort-1" in group_names

    async def test_adversarial_email_collision_cannot_hijack_local_account(
        self,
        app: FastAPI,
        unauthorized_client: AsyncClient,
        client: AsyncClient,
        db_session: AsyncSession,
        mock_ldap_directory,
        users_group_id: Optional[str],
    ) -> None:
        """
        Adversarial test: An untrusted directory user has a mail attribute that matches
        an existing local user's email. JIT sync must NOT adopt or mutate the local account.
        """
        users_repo = UsersRepository(db_session)

        # 1. Pre-create a legitimate local user with email 'victim@example.com'
        resp = await client.post(
            app.url_path_for("create_user"),
            json=self._user_payload(
                {"username": "victim_local", "email": "victim@example.com", "password": "mock_victim_password"},
                users_group_id,
            ),
        )
        assert resp.status_code == status.HTTP_201_CREATED
        local_victim = await users_repo.get_user_by_username("victim_local")
        assert local_victim is not None
        assert local_victim.auth_source == "local"
        original_victim_id = local_victim.user_id

        # 2. Malicious/colliding LDAP user 'attacker' is configured with mail=victim@example.com
        mock_ldap_directory.strategy.add_entry(
            "uid=attacker_ldap,ou=users,dc=example,dc=com",
            {
                "objectClass": ["person", "inetOrgPerson"],
                "uid": "attacker_ldap",
                "cn": "Attacker User",
                "mail": "victim@example.com",
                "userPassword": "mock_attacker_secret",
                "memberOf": ["cn=GNS3-Users,ou=groups,dc=example,dc=com"],
            },
        )

        # 3. Attacker authenticates via LDAP
        login_resp = await unauthorized_client.post(
            app.url_path_for("login"),
            data={"username": "attacker_ldap", "password": "mock_attacker_secret"},
            headers=FORM_HEADERS,
        )
        assert login_resp.status_code == status.HTTP_200_OK

        # 4. Verify local user remains intact and was NOT hijacked
        intact_victim = await users_repo.get_user(original_victim_id)
        assert intact_victim is not None
        assert intact_victim.username == "victim_local"
        assert intact_victim.auth_source == "local"
        assert intact_victim.email == "victim@example.com"

        # 5. Verify the attacker was created as a separate user without stealing the email
        attacker_user = await users_repo.get_user_by_username("attacker_ldap")
        assert attacker_user is not None
        assert attacker_user.user_id != original_victim_id
        assert attacker_user.email is None

    @pytest.mark.parametrize(
        "group_dn,expected_cn",
        [
            ("cn=Net+Eng/Admins,ou=groups,dc=example,dc=com", "Net+Eng/Admins"),
            ("CN=Security-Auditors,OU=Groups,DC=example,DC=com", "Security-Auditors"),
            ("cn=Admins with spaces,ou=groups,dc=example,dc=com", "Admins with spaces"),
        ],
    )
    async def test_adversarial_special_character_and_casing_group_parsing(
        self,
        group_dn: str,
        expected_cn: str,
    ) -> None:
        """
        Adversarial test: Ensure group DN parsing cleanly extracts common names containing
        special characters (plus signs, slashes, spaces) and mixed casing without failure.
        """
        from gns3server.services.ldap import _extract_cn

        extracted = _extract_cn(group_dn)
        assert extracted == expected_cn

    @pytest.mark.parametrize(
        "tampered_payload,field_name",
        [
            ({"is_superadmin": True}, "is_superadmin"),
            ({"auth_source": "ldap"}, "auth_source"),
        ],
    )
    async def test_adversarial_forged_payload_fields_on_user_creation(
        self,
        app: FastAPI,
        client: AsyncClient,
        db_session: AsyncSession,
        tampered_payload: dict,
        field_name: str,
        users_group_id: Optional[str],
    ) -> None:
        """
        Adversarial test: An API caller attempts to inject server-controlled fields
        (e.g. is_superadmin=True or auth_source='ldap') into POST /v3/access/users.
        The server must ignore the forged fields and apply secure defaults.
        """
        import uuid

        username = f"user_{uuid.uuid4().hex[:8]}"
        payload = self._user_payload(
            {
                "username": username,
                "email": f"{username}@example.com",
                "password": "mock_secure_password",
                **tampered_payload,
            },
            users_group_id,
        )

        resp = await client.post(app.url_path_for("create_user"), json=payload)
        assert resp.status_code == status.HTTP_201_CREATED

        users_repo = UsersRepository(db_session)
        created_user = await users_repo.get_user_by_username(username)
        assert created_user is not None
        if field_name == "is_superadmin":
            assert created_user.is_superadmin is False
        elif field_name == "auth_source":
            assert created_user.auth_source == "local"
