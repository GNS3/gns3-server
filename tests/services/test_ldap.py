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
from ldap3 import ALL, MOCK_SYNC, Connection, Server
from pydantic import SecretStr

from gns3server.schemas.config import LDAPSettings
from gns3server.services.ldap import LDAPService, _extract_cn

pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_ldap_server():
    server = Server("mock_ldap_server", get_info=ALL)
    admin_conn = Connection(
        server,
        user="cn=admin,dc=example,dc=com",
        password="placeholder_password",
        client_strategy=MOCK_SYNC,
    )
    admin_conn.bind()

    # Add service account
    admin_conn.strategy.add_entry(
        "cn=admin,dc=example,dc=com",
        {"userPassword": "placeholder_password", "cn": "admin"},
    )

    # Add test user: alice (in GNS3-Admins group via memberOf)
    admin_conn.strategy.add_entry(
        "uid=alice,ou=users,dc=example,dc=com",
        {
            "objectClass": ["person", "inetOrgPerson"],
            "uid": "alice",
            "cn": "Alice Wonderland",
            "mail": "alice@example.com",
            "userPassword": "mock_alice_password",
            "memberOf": ["cn=GNS3-Admins,ou=groups,dc=example,dc=com"],
        },
    )

    # Add test user: bob (no memberOf attribute)
    admin_conn.strategy.add_entry(
        "uid=bob,ou=users,dc=example,dc=com",
        {
            "objectClass": ["person", "inetOrgPerson"],
            "uid": "bob",
            "cn": "Bob Builder",
            "mail": "bob@example.com",
            "userPassword": "mock_bob_password",
        },
    )

    # Add group entries for directory search
    admin_conn.strategy.add_entry(
        "cn=GNS3-Users,ou=groups,dc=example,dc=com",
        {
            "objectClass": ["groupOfNames"],
            "cn": "GNS3-Users",
            "member": ["uid=bob,ou=users,dc=example,dc=com"],
        },
    )

    return server


@pytest.fixture
def default_settings():
    return LDAPSettings(
        enabled=True,
        uri="ldap://mock_ldap_server:389",
        bind_dn="cn=admin,dc=example,dc=com",
        bind_password=SecretStr("placeholder_password"),
        base_dn="ou=users,dc=example,dc=com",
        user_search_filter="(&(objectClass=person)(|(uid={username})(sAMAccountName={username})))",
        group_mapping={"GNS3-Admins": "Administrators", "GNS3-Users": "Users"},
        default_group="Users",
    )


async def test_extract_cn():
    assert _extract_cn("CN=GNS3-Admins,OU=Groups,DC=example,DC=com") == "GNS3-Admins"
    assert _extract_cn("cn=Domain Admins,ou=groups,dc=corp,dc=local") == "Domain Admins"
    assert _extract_cn("PlainGroupName") == "PlainGroupName"
    assert _extract_cn("  cn=SpacedName , ou=org  ") == "SpacedName"


async def test_ldap_disabled_returns_none(mock_ldap_server, default_settings):
    default_settings.enabled = False
    service = LDAPService(server=mock_ldap_server, client_strategy=MOCK_SYNC)

    profile = await service.authenticate("alice", "mock_alice_password", default_settings)
    assert profile is None


async def test_ldap_empty_credentials(mock_ldap_server, default_settings):
    service = LDAPService(server=mock_ldap_server, client_strategy=MOCK_SYNC)

    assert await service.authenticate("", "password", default_settings) is None
    assert await service.authenticate("alice", "", default_settings) is None
    assert await service.authenticate("", "", default_settings) is None


async def test_ldap_successful_authentication(mock_ldap_server, default_settings):
    service = LDAPService(server=mock_ldap_server, client_strategy=MOCK_SYNC)

    profile = await service.authenticate("alice", "mock_alice_password", default_settings)
    assert profile is not None
    assert profile.username == "alice"
    assert profile.email == "alice@example.com"
    assert profile.full_name == "Alice Wonderland"
    assert profile.groups == ["Administrators"]


async def test_ldap_wrong_password_fails(mock_ldap_server, default_settings):
    service = LDAPService(server=mock_ldap_server, client_strategy=MOCK_SYNC)

    profile = await service.authenticate("alice", "wrong_password", default_settings)
    assert profile is None


async def test_ldap_nonexistent_user_fails(mock_ldap_server, default_settings):
    service = LDAPService(server=mock_ldap_server, client_strategy=MOCK_SYNC)

    profile = await service.authenticate("charlie", "any_password", default_settings)
    assert profile is None


async def test_ldap_injection_attack_escaped(mock_ldap_server, default_settings):
    service = LDAPService(server=mock_ldap_server, client_strategy=MOCK_SYNC)

    # Injection attempts to bypass the filter
    profile = await service.authenticate("alice*)(uid=*", "wrong_password", default_settings)
    assert profile is None

    profile2 = await service.authenticate("*", "any_password", default_settings)
    assert profile2 is None


async def test_ldap_group_mapping_fallback_to_default_group(mock_ldap_server, default_settings):
    default_settings.group_mapping = {}  # No mapping configured
    default_settings.default_group = "Users"
    service = LDAPService(server=mock_ldap_server, client_strategy=MOCK_SYNC)

    profile = await service.authenticate("alice", "mock_alice_password", default_settings)
    assert profile is not None
    assert profile.groups == ["Users"]


async def test_ldap_group_search_resolution(mock_ldap_server, default_settings):
    # Bob has no memberOf on his user object, but group cn=GNS3-Users has member=uid=bob
    default_settings.group_search_base = "ou=groups,dc=example,dc=com"
    default_settings.group_search_filter = "(&(objectClass=groupOfNames)(member={user_dn}))"
    service = LDAPService(server=mock_ldap_server, client_strategy=MOCK_SYNC)

    profile = await service.authenticate("bob", "mock_bob_password", default_settings)
    assert profile is not None
    assert profile.username == "bob"
    assert profile.email == "bob@example.com"
    assert profile.groups == ["Users"]


async def test_ldap_merge_direct_and_searched_groups(mock_ldap_server, default_settings):
    admin_conn = Connection(mock_ldap_server, client_strategy=MOCK_SYNC)
    admin_conn.bind()
    admin_conn.strategy.add_entry(
        "cn=GNS3-Staff,ou=groups,dc=example,dc=com",
        {
            "objectClass": ["groupOfNames"],
            "cn": "GNS3-Staff",
            "member": ["uid=alice,ou=users,dc=example,dc=com"],
        },
    )

    default_settings.group_mapping = {
        "GNS3-Admins": "Administrators",
        "GNS3-Staff": "StaffGroup",
    }
    default_settings.group_search_base = "ou=groups,dc=example,dc=com"
    default_settings.group_search_filter = "(&(objectClass=groupOfNames)(member={user_dn}))"

    service = LDAPService(server=mock_ldap_server, client_strategy=MOCK_SYNC)
    profile = await service.authenticate("alice", "mock_alice_password", default_settings)

    assert profile is not None
    assert "Administrators" in profile.groups
    assert "StaffGroup" in profile.groups


async def test_ldap_service_account_bind_failure(mock_ldap_server, default_settings):
    default_settings.bind_password = SecretStr("mock_incorrect_password")
    service = LDAPService(server=mock_ldap_server, client_strategy=MOCK_SYNC)

    profile = await service.authenticate("alice", "mock_alice_password", default_settings)
    assert profile is None


async def test_ldap_test_connection_success(mock_ldap_server, default_settings):
    service = LDAPService(server=mock_ldap_server, client_strategy=MOCK_SYNC)

    result = await service.test_connection(default_settings)
    assert result["status"] == "success"
    assert result["bind_successful"] is True
    assert result["user_search_successful"] is True
    assert result["users_found"] >= 2
    assert result["latency_ms"] >= 0


async def test_ldap_test_connection_bind_failure(mock_ldap_server, default_settings):
    default_settings.bind_password = SecretStr("wrong_password")
    service = LDAPService(server=mock_ldap_server, client_strategy=MOCK_SYNC)

    result = await service.test_connection(default_settings)
    assert result["status"] == "error"
    assert result["bind_successful"] is False
    assert result["user_search_successful"] is False
    assert "Failed to bind" in result["message"]


async def test_ldap_start_tls_failure_aborts_bind():
    """Verify that if start_tls returns False or fails, _bind_connection aborts without binding."""
    from unittest.mock import MagicMock

    service = LDAPService()
    mock_conn = MagicMock()
    mock_conn.start_tls.return_value = False

    success = service._bind_connection(mock_conn, start_tls=True, uri="ldap://dc.example.com:389")
    assert success is False
    assert not mock_conn.bind.called


async def test_extract_cn_rfc4514_escapes():
    """Verify RFC 4514 escaped characters and hex octets in RDNs are correctly decoded."""
    assert _extract_cn(r"CN=Smith\, John,OU=Users,DC=example,DC=com") == "Smith, John"
    assert _extract_cn(r"CN=Engineering\+Admins,OU=Groups,DC=example,DC=com") == "Engineering+Admins"
    assert _extract_cn(r"CN=L\<D\>A\=P\;Group\"\\\#,DC=example,DC=com") == 'L<D>A=P;Group"\\#'
    assert _extract_cn(r"CN=Hex\2BGroup,DC=example,DC=com") == "Hex+Group"
    assert _extract_cn(r"CN=Space\ Group\ ,DC=example,DC=com") == "Space Group "
    assert _extract_cn("GNS3-Admins") == "GNS3-Admins"
    assert _extract_cn("") == ""


async def test_ldap_connection_disables_check_names():
    """Verify that ldap3.Connection is initialized with check_names=False to allow cross-directory fallback attributes."""
    service = LDAPService(client_strategy=MOCK_SYNC)
    server = Server("mock_server")
    conn = service._create_connection(server, "cn=admin", "password", timeout=5)
    assert conn.check_names is False
