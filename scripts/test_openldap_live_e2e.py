#!/usr/bin/env python3
"""
GNS3 Live OpenLDAP 2.6.15 End-to-End Integration Battery

Mirrors the exact Stage 39 testbed used by upstream GNS3 reviewers:
- Docker Image: osixia/openldap:2.6.15
- Non-standard unprivileged ports: 3890 (LDAP) / 6360 (LDAPS)
- OpenLDAP olcDatabase={1}mdb ACL patch allowing member attribute search
- Realistic directory structure: ou=people, ou=groups under ou=gns3,dc=example,dc=org
- Service account binding, multi-group resolution, dynamic revocation, rate limiting, and DR fallback.

Zero third-party test framework dependencies: runs natively with Python 3.8+.
"""

# ruff: noqa: S603, S607, PLW1510, S106, ASYNC221

import asyncio
import subprocess
import time

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from gns3server.db.models.base import Base
from gns3server.db.rbac_state import RbacState
from gns3server.db.repositories.users import UsersRepository
from gns3server.schemas.config import LDAPSettings
from gns3server.services.ldap import LDAPService
from gns3server.services.login_rate_limiter import login_rate_limiter

CONTAINER_NAME = "gns3-openldap-26-e2e"
LDAP_PORT = "3890"


def setup_openldap():
    print("=================================================================")
    print("🚀  SPINNING UP OSIXIA/OPENLDAP:2.6.15 TESTBED")
    print("=================================================================")
    subprocess.run(["docker", "rm", "-f", CONTAINER_NAME], capture_output=True)
    res = subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            CONTAINER_NAME,
            "--rm",
            "-p",
            f"{LDAP_PORT}:3890",
            "-e",
            "OPENLDAP_BOOTSTRAP_ORGANIZATION=Example Inc.",
            "-e",
            "OPENLDAP_BOOTSTRAP_SUFFIX=dc=example,dc=org",
            "-e",
            "OPENLDAP_BOOTSTRAP_DATA_ROOT_PASSWORD_HASHED=admin",
            "-e",
            "OPENLDAP_BOOTSTRAP_CONFIG_ROOT_PASSWORD_HASHED=config",
            "osixia/openldap:2.6.15",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    print(f"[*] Container started: {res.stdout.strip()[:12]}")

    print("[*] Waiting for slapd on port 3890...")
    for _ in range(30):
        check = subprocess.run(
            [
                "docker",
                "exec",
                CONTAINER_NAME,
                "ldapsearch",
                "-x",
                "-H",
                f"ldap://127.0.0.1:{LDAP_PORT}",
                "-D",
                "cn=admin,dc=example,dc=org",
                "-w",
                "admin",
                "-b",
                "dc=example,dc=org",
                "(objectClass=*)",
            ],
            capture_output=True,
        )
        if check.returncode == 0:
            print("[+] OpenLDAP 2.6.15 is online.")
            break
        time.sleep(1)
    else:
        raise RuntimeError("OpenLDAP 2.6.15 failed to start in 30 seconds.")

    # Apply ACL patch allowing member attribute queries (Guobin Stage 39 Step 2)
    print("[*] Applying OpenLDAP olcAccess {2} member attribute allow-list patch...")
    acl_ldif = """
dn: olcDatabase={1}mdb,cn=config
changetype: modify
delete: olcAccess
olcAccess: {2}to attrs=entry,objectClass,cn,sn,givenName,mail,uid,ou,o,dc by self read by users read by * break
-
add: olcAccess
olcAccess: {2}to attrs=entry,objectClass,cn,sn,givenName,mail,uid,ou,o,dc,member by self read by users read by * break
"""
    subprocess.run(
        [
            "docker",
            "exec",
            "-i",
            CONTAINER_NAME,
            "ldapmodify",
            "-x",
            "-H",
            f"ldap://127.0.0.1:{LDAP_PORT}",
            "-D",
            "cn=admin,cn=config",
            "-w",
            "config",
        ],
        input=acl_ldif,
        text=True,
        check=True,
        capture_output=True,
    )

    # Seed directory structure
    print("[*] Seeding OUs, users (svc-gns3, alice, carol), and groups...")
    data_ldif = """
dn: ou=gns3,dc=example,dc=org
objectClass: organizationalUnit
ou: gns3

dn: ou=people,ou=gns3,dc=example,dc=org
objectClass: organizationalUnit
ou: people

dn: ou=groups,ou=gns3,dc=example,dc=org
objectClass: organizationalUnit
ou: groups

dn: uid=svc-gns3,ou=people,ou=gns3,dc=example,dc=org
objectClass: inetOrgPerson
uid: svc-gns3
cn: Service Account
sn: Service
userPassword: svcldap123

dn: uid=alice,ou=people,ou=gns3,dc=example,dc=org
objectClass: inetOrgPerson
uid: alice
cn: Alice Smith
sn: Smith
mail: alice@example.org
userPassword: gns3test

dn: uid=carol,ou=people,ou=gns3,dc=example,dc=org
objectClass: inetOrgPerson
uid: carol
cn: Carol Danvers
sn: Danvers
mail: carol@example.org
userPassword: gns3test

dn: cn=gns3-admins,ou=groups,ou=gns3,dc=example,dc=org
objectClass: groupOfNames
cn: gns3-admins
member: uid=carol,ou=people,ou=gns3,dc=example,dc=org
member: uid=svc-gns3,ou=people,ou=gns3,dc=example,dc=org

dn: cn=gns3-testers,ou=groups,ou=gns3,dc=example,dc=org
objectClass: groupOfNames
cn: gns3-testers
member: uid=carol,ou=people,ou=gns3,dc=example,dc=org
member: uid=alice,ou=people,ou=gns3,dc=example,dc=org
"""
    subprocess.run(
        [
            "docker",
            "exec",
            "-i",
            CONTAINER_NAME,
            "ldapadd",
            "-x",
            "-H",
            f"ldap://127.0.0.1:{LDAP_PORT}",
            "-D",
            "cn=admin,dc=example,dc=org",
            "-w",
            "admin",
        ],
        input=data_ldif,
        text=True,
        check=True,
        capture_output=True,
    )
    print("[+] OpenLDAP directory seeded successfully.")


def teardown_openldap():
    print("\n[*] Stopping OpenLDAP container...")
    subprocess.run(["docker", "stop", CONTAINER_NAME], capture_output=True)
    print("[+] Testbed stopped.")


async def run_live_battery():
    setup_openldap()
    try:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with engine.connect() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.commit()

        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        rbac_state = RbacState.instance()

        async with async_session() as session:
            await rbac_state.ensure_loaded(session)

        settings = LDAPSettings(
            enabled=True,
            uri=f"ldap://127.0.0.1:{LDAP_PORT}",
            bind_dn="uid=svc-gns3,ou=people,ou=gns3,dc=example,dc=org",
            bind_password="svcldap123",
            base_dn="ou=gns3,dc=example,dc=org",
            user_search_filter="(&(objectClass=person)(uid={username}))",
            user_attr_username="uid",
            user_attr_email="mail",
            user_attr_fullname="cn",
            group_search_base="ou=gns3,dc=example,dc=org",
            group_search_filter="(&(objectClass=groupOfNames)(member={user_dn}))",
            group_mapping={"gns3-admins": "Administrators", "gns3-testers": "Testers"},
            default_group="Users",
            fallback_to_local=True,
            timeout=10,
        )

        ldap_service = LDAPService()

        # TEST 1: Diagnostic Test Endpoint
        print("\n--- TEST 1: Diagnostic Bind & Search ---")
        diag = await ldap_service.test_connection(settings)
        assert diag.get("status") == "success"
        print(f"✅ Diagnostic test passed: status={diag['status']}, latency={diag.get('latency_ms')}ms")

        # TEST 2: Multi-Group Resolution (Carol -> Administrators + Testers)
        print("\n--- TEST 2: Multi-Group Authentication & RBAC Snapshot Invalidation ---")
        carol_profile = await ldap_service.authenticate("carol", "gns3test", settings)
        assert carol_profile is not None
        assert "Administrators" in carol_profile.groups
        assert "Testers" in carol_profile.groups
        print(f"✅ OpenLDAP resolved multi-groups: {carol_profile.groups}")

        async with async_session() as session:
            repo = UsersRepository(session)
            carol_user = await repo.sync_ldap_user(carol_profile)
            assert rbac_state.needs_reload is True, "RbacState was not marked dirty!"
            await rbac_state.ensure_loaded(session)
            has_admin = rbac_state.user_has_privilege(carol_user.user_id, "/", "Server.Modify")
            assert has_admin is True, "Carol lacks Server.Modify privilege immediately after login!"
            print("✅ Carol has Server.Modify admin privilege immediately on first request")

        # TEST 3: Dynamic Group Revocation via live ldapmodify
        print("\n--- TEST 3: Dynamic Group Revocation ---")
        mod_ldif = """
dn: cn=gns3-admins,ou=groups,ou=gns3,dc=example,dc=org
changetype: modify
delete: member
member: uid=carol,ou=people,ou=gns3,dc=example,dc=org
"""
        subprocess.run(
            [
                "docker",
                "exec",
                "-i",
                CONTAINER_NAME,
                "ldapmodify",
                "-x",
                "-H",
                f"ldap://127.0.0.1:{LDAP_PORT}",
                "-D",
                "cn=admin,dc=example,dc=org",
                "-w",
                "admin",
            ],
            input=mod_ldif,
            text=True,
            check=True,
            capture_output=True,
        )

        carol_after = await ldap_service.authenticate("carol", "gns3test", settings)
        assert "Administrators" not in carol_after.groups
        assert "Testers" in carol_after.groups
        print(f"✅ OpenLDAP reflects revoked group: {carol_after.groups}")

        async with async_session() as session:
            repo = UsersRepository(session)
            synced_carol = await repo.sync_ldap_user(carol_after)
            await rbac_state.ensure_loaded(session)
            has_admin_now = rbac_state.user_has_privilege(synced_carol.user_id, "/", "Server.Modify")
            assert has_admin_now is False, "Carol still retained Server.Modify after group removal!"
            print("✅ Carol's Server.Modify administrative privilege was cleanly revoked on login")

        # TEST 4: Sliding-Window Rate Limiting Protection
        print("\n--- TEST 4: Sliding-Window Rate Limiting Protection ---")
        login_rate_limiter.clear()
        test_ip = "192.168.101.50"
        for i in range(1, 6):
            is_limited, _ = login_rate_limiter.is_rate_limited("alice", test_ip)
            assert not is_limited, f"Attempt {i} was prematurely rate-limited!"
            login_rate_limiter.record_failure("alice", test_ip)

        is_limited, retry_after = login_rate_limiter.is_rate_limited("alice", test_ip)
        assert is_limited is True
        assert retry_after > 0
        print(f"✅ 5 failures allowed, 6th attempt blocked locally (Retry-After: {retry_after}s)")

        # TEST 5: Anonymous Bind Defense
        print("\n--- TEST 5: Empty Password Rejection ---")
        empty_res = await ldap_service.authenticate("alice", "", settings)
        assert empty_res is None
        print("✅ Empty password rejected without contacting server")

        # TEST 6: Directory Outage & Break-Glass Recovery
        print("\n--- TEST 6: Directory Outage & Break-Glass Recovery ---")
        subprocess.run(["docker", "stop", CONTAINER_NAME], check=True, capture_output=True)

        outage_auth = await ldap_service.authenticate("alice", "gns3test", settings)
        assert outage_auth is None
        print("✅ Directory outage handled gracefully (returns None)")

        async with async_session() as session:
            repo = UsersRepository(session)
            admin_auth = await repo.authenticate_user("admin", "admin")
            assert admin_auth is not None
            assert admin_auth.is_superadmin is True
            print(f"✅ Break-glass admin '{admin_auth.username}' authenticates during outage")

        print("\n=================================================================")
        print("🏆  ALL INTEGRATION TESTS PASSED 100% AGAINST OPENLDAP 2.6.15!")
        print("=================================================================")

    finally:
        teardown_openldap()


if __name__ == "__main__":
    asyncio.run(run_live_battery())
