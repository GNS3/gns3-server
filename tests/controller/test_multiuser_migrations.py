#
# Copyright (C) 2026 GNS3 Technologies Inc.
# Author: YueGuobin
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
The consolidated multi-user migration (b7d4c3f2a1e9) must seed the default
ACEs, the built-in privileges and roles, and create the new tables on
upgrade (versioned and unversioned databases alike), without touching
objects an administrator customized.
"""

import pytest
import sqlalchemy as sa
from alembic import command, config
from fastapi import FastAPI

from gns3server.db.models import Base
from gns3server.db.tasks import connect_to_db

BASE_REVISION = "e2a7c9d4b601"

LAB_MEMBER_PRIVILEGES = {
    "Project.Allocate",
    "Project.Audit",
    "Project.Marker",
    "Snapshot.Audit",
    "Snapshot.Restore",
    "Node.Audit",
    "Node.Console",
    "Node.PowerMgmt",
    "Link.Audit",
    "Link.Capture",
    "Link.Marker",
    "Drawing.Audit",
}


def _alembic_config():
    cfg = config.Config()
    cfg.set_main_option("script_location", "gns3server:db_migrations")
    return cfg


def test_default_aces_are_seeded_without_propagation_on_projects():
    engine = sa.create_engine("sqlite://")
    with engine.connect() as connection:
        Base.metadata.create_all(connection)
        assert connection.scalar(sa.text("SELECT COUNT(*) FROM acl")) == 8
        propagate = dict(connection.exec_driver_sql("SELECT path, propagate FROM acl").all())
        # the collection ACE must not grant access to the projects themselves
        assert propagate["/projects"] == 0
        assert propagate["/templates"] == 1
        connection.commit()
    engine.dispose()


def _administrator_has_notification_privilege(connection) -> int:

    return connection.execute(
        sa.text(
            "SELECT COUNT(*) FROM privilege_role_map m"
            " JOIN privileges p ON p.privilege_id = m.privilege_id"
            " JOIN roles r ON r.role_id = m.role_id"
            " WHERE p.name = 'Notification.Audit' AND r.name = 'Administrator'"
        )
    ).scalar_one()


def test_notification_privilege_is_seeded_for_administrator():
    engine = sa.create_engine("sqlite://")
    with engine.connect() as connection:
        Base.metadata.create_all(connection)
        # the stream privilege exists and the Administrator role (which
        # automatically receives every privilege on a new database) holds it
        assert connection.scalar(sa.text("SELECT COUNT(*) FROM privileges WHERE name = 'Notification.Audit'")) == 1
        assert _administrator_has_notification_privilege(connection) == 1
        connection.commit()
    engine.dispose()


async def _role_privileges(connection, role_name: str) -> set:
    rows = await connection.execute(
        sa.text(
            "SELECT p.name FROM privileges p"
            " JOIN privilege_role_map m ON m.privilege_id = p.privilege_id"
            " JOIN roles r ON r.role_id = m.role_id WHERE r.name = :name"
        ),
        {"name": role_name},
    )
    return {row[0] for row in rows}


@pytest.mark.parametrize("versioned", [False, True])
@pytest.mark.asyncio
async def test_default_projects_ace_is_restricted_on_upgrade(tmp_path, monkeypatch, versioned):
    path = tmp_path / "controller.db"
    engine = sa.create_engine(f"sqlite:///{path}")
    with engine.connect() as connection:
        Base.metadata.create_all(connection)
        # simulate a database seeded before the restriction: the /projects ACE
        # propagates to every project
        connection.exec_driver_sql("UPDATE acl SET propagate = 1 WHERE path = '/projects'")
        if versioned:
            cfg = _alembic_config()
            cfg.attributes["connection"] = connection
            command.stamp(cfg, BASE_REVISION)
        else:
            # unversioned database seeded before the default ACEs existed: the
            # startup path seeds them and must then apply the restriction
            connection.exec_driver_sql("DELETE FROM acl")
        connection.commit()
    engine.dispose()

    monkeypatch.setenv("GNS3_DATABASE_URI", f"sqlite+aiosqlite:///{path}")
    app = FastAPI()
    await connect_to_db(app)
    try:
        async with app.state._db_engine.connect() as connection:
            assert await connection.scalar(sa.text("SELECT COUNT(*) FROM acl")) == 8
            propagate = await connection.scalar(sa.text("SELECT propagate FROM acl WHERE path = '/projects'"))
            assert propagate == 0
    finally:
        await app.state._db_engine.dispose()


@pytest.mark.parametrize("versioned", [False, True])
@pytest.mark.asyncio
async def test_notification_privilege_is_added_on_upgrade(tmp_path, monkeypatch, versioned):
    path = tmp_path / "controller.db"
    engine = sa.create_engine(f"sqlite:///{path}")
    with engine.connect() as connection:
        Base.metadata.create_all(connection)
        # simulate a database from before the privilege existed
        connection.exec_driver_sql("DELETE FROM privileges WHERE name = 'Notification.Audit'")
        if versioned:
            cfg = _alembic_config()
            cfg.attributes["connection"] = connection
            command.stamp(cfg, BASE_REVISION)
        else:
            # unversioned database: the startup path seeds via the manual
            # upgrade chain — remove the seeded ACEs too so the chain runs
            connection.exec_driver_sql("DELETE FROM acl")
        connection.commit()
    engine.dispose()

    monkeypatch.setenv("GNS3_DATABASE_URI", f"sqlite+aiosqlite:///{path}")
    app = FastAPI()
    await connect_to_db(app)
    try:
        async with app.state._db_engine.connect() as connection:
            assert (
                await connection.scalar(sa.text("SELECT COUNT(*) FROM privileges WHERE name = 'Notification.Audit'"))
                == 1
            )
            assert await connection.run_sync(_administrator_has_notification_privilege) == 1
    finally:
        await app.state._db_engine.dispose()


@pytest.mark.parametrize("versioned", [False, True])
@pytest.mark.asyncio
async def test_user_preferences_table_is_added_on_upgrade(tmp_path, monkeypatch, versioned):
    path = tmp_path / "controller.db"
    engine = sa.create_engine(f"sqlite:///{path}")
    with engine.connect() as connection:
        Base.metadata.create_all(connection)
        # simulate a database from before the user preferences existed
        connection.exec_driver_sql("DROP TABLE user_preferences")
        if versioned:
            cfg = _alembic_config()
            cfg.attributes["connection"] = connection
            command.stamp(cfg, BASE_REVISION)
        # else: unversioned database with the table already created by the
        # code, upgraded through the manual startup chain
        connection.commit()
    engine.dispose()

    monkeypatch.setenv("GNS3_DATABASE_URI", f"sqlite+aiosqlite:///{path}")
    app = FastAPI()
    await connect_to_db(app)
    try:
        async with app.state._db_engine.connect() as connection:
            assert await connection.run_sync(lambda conn: sa.inspect(conn).has_table("user_preferences"))
            # the table is usable: the admin user can hold a preferences document
            admin_id = await connection.scalar(sa.text("SELECT user_id FROM users WHERE username = 'admin'"))
            await connection.execute(
                sa.text("INSERT INTO user_preferences (user_id, preferences) VALUES (:id, '{}')"),
                {"id": admin_id},
            )
            row = await connection.scalar(sa.text("SELECT preferences FROM user_preferences"))
            assert row == "{}"
            await connection.commit()
    finally:
        await app.state._db_engine.dispose()


@pytest.mark.asyncio
async def test_existing_user_preferences_table_survives_the_startup_chain(tmp_path, monkeypatch):
    # unversioned database already created from current code (create_all made
    # the table): the manual startup chain replays the migration and must
    # leave the existing document alone
    path = tmp_path / "controller.db"
    engine = sa.create_engine(f"sqlite:///{path}")
    with engine.connect() as connection:
        Base.metadata.create_all(connection)
        admin_id = connection.execute(sa.text("SELECT user_id FROM users WHERE username = 'admin'")).scalar_one()
        connection.execute(
            sa.text("INSERT INTO user_preferences (user_id) VALUES (:id)"),
            {"id": admin_id},
        )
        connection.commit()
    engine.dispose()

    monkeypatch.setenv("GNS3_DATABASE_URI", f"sqlite+aiosqlite:///{path}")
    app = FastAPI()
    await connect_to_db(app)
    try:
        async with app.state._db_engine.connect() as connection:
            count = await connection.scalar(sa.text("SELECT COUNT(*) FROM user_preferences"))
            assert count == 1
    finally:
        await app.state._db_engine.dispose()


@pytest.mark.parametrize("versioned", [False, True])
@pytest.mark.asyncio
async def test_lab_member_role_is_added_on_upgrade(tmp_path, monkeypatch, versioned):
    path = tmp_path / "controller.db"
    engine = sa.create_engine(f"sqlite:///{path}")
    with engine.connect() as connection:
        Base.metadata.create_all(connection)
        # simulate a database from before the role existed
        connection.execute(
            sa.text(
                "DELETE FROM privilege_role_map WHERE role_id = (SELECT role_id FROM roles WHERE name = 'Lab member')"
            )
        )
        connection.execute(sa.text("DELETE FROM roles WHERE name = 'Lab member'"))
        if versioned:
            cfg = _alembic_config()
            cfg.attributes["connection"] = connection
            command.stamp(cfg, BASE_REVISION)
        # else: unversioned database with the role already created by the
        # code, upgraded through the manual startup chain
        connection.commit()
    engine.dispose()

    monkeypatch.setenv("GNS3_DATABASE_URI", f"sqlite+aiosqlite:///{path}")
    app = FastAPI()
    await connect_to_db(app)
    try:
        async with app.state._db_engine.connect() as connection:
            is_builtin = await connection.scalar(sa.text("SELECT is_builtin FROM roles WHERE name = 'Lab member'"))
            assert is_builtin == 1
            assert await _role_privileges(connection, "Lab member") == LAB_MEMBER_PRIVILEGES
    finally:
        await app.state._db_engine.dispose()


@pytest.mark.asyncio
async def test_existing_lab_member_role_keeps_identity_and_gains_missing_privileges(tmp_path, monkeypatch):
    # unversioned database already created from current code, where an
    # administrator customized the role: it must not become builtin again and
    # the missing privileges are attached
    path = tmp_path / "controller.db"
    engine = sa.create_engine(f"sqlite:///{path}")
    with engine.connect() as connection:
        Base.metadata.create_all(connection)
        connection.execute(sa.text("UPDATE roles SET is_builtin = 0 WHERE name = 'Lab member'"))
        connection.execute(
            sa.text(
                "DELETE FROM privilege_role_map WHERE role_id ="
                " (SELECT role_id FROM roles WHERE name = 'Lab member')"
                " AND privilege_id NOT IN"
                " (SELECT privilege_id FROM privileges WHERE name = 'Project.Audit')"
            )
        )
        connection.commit()
    engine.dispose()

    monkeypatch.setenv("GNS3_DATABASE_URI", f"sqlite+aiosqlite:///{path}")
    app = FastAPI()
    await connect_to_db(app)
    try:
        async with app.state._db_engine.connect() as connection:
            is_builtin = await connection.scalar(sa.text("SELECT is_builtin FROM roles WHERE name = 'Lab member'"))
            assert is_builtin == 0
            assert await _role_privileges(connection, "Lab member") == LAB_MEMBER_PRIVILEGES
    finally:
        await app.state._db_engine.dispose()


@pytest.mark.parametrize("versioned", [False, True])
@pytest.mark.asyncio
async def test_user_quota_columns_are_added_on_upgrade(tmp_path, monkeypatch, versioned):
    path = tmp_path / "controller.db"
    engine = sa.create_engine(f"sqlite:///{path}")
    with engine.connect() as connection:
        Base.metadata.create_all(connection)
        # simulate a database from before the quota columns existed
        connection.exec_driver_sql("ALTER TABLE users DROP COLUMN max_nodes")
        connection.exec_driver_sql("ALTER TABLE users DROP COLUMN max_running_nodes")
        if versioned:
            cfg = _alembic_config()
            cfg.attributes["connection"] = connection
            command.stamp(cfg, BASE_REVISION)
        # else: unversioned database with the columns already created by the
        # code, upgraded through the manual startup chain
        connection.commit()
    engine.dispose()

    monkeypatch.setenv("GNS3_DATABASE_URI", f"sqlite+aiosqlite:///{path}")
    app = FastAPI()
    await connect_to_db(app)
    try:
        async with app.state._db_engine.connect() as connection:

            def _column_names(conn, table):
                return {column["name"] for column in sa.inspect(conn).get_columns(table)}

            assert await connection.run_sync(lambda conn: _column_names(conn, "users")) >= {
                "max_nodes",
                "max_running_nodes",
            }
            assert await connection.run_sync(lambda conn: _column_names(conn, "user_groups")) >= {
                "default_max_nodes",
                "default_max_running_nodes",
            }
    finally:
        await app.state._db_engine.dispose()


@pytest.mark.parametrize("versioned", [False, True])
@pytest.mark.asyncio
async def test_server_settings_privileges_are_backfilled_on_startup(tmp_path, monkeypatch, versioned):
    privileges = ("Server.Audit", "Server.Modify")
    path = tmp_path / "controller.db"
    engine = sa.create_engine(f"sqlite:///{path}")
    with engine.connect() as connection:
        Base.metadata.create_all(connection)
        # simulate a database created before the settings API seeded the privileges
        connection.exec_driver_sql(
            "DELETE FROM privilege_role_map WHERE privilege_id IN"
            " (SELECT privilege_id FROM privileges WHERE name IN ('Server.Audit', 'Server.Modify'))"
        )
        connection.exec_driver_sql("DELETE FROM privileges WHERE name IN ('Server.Audit', 'Server.Modify')")
        if versioned:
            cfg = _alembic_config()
            cfg.attributes["connection"] = connection
            command.stamp(cfg, BASE_REVISION)
        # else: unversioned database with the privileges already created by
        # the code, upgraded through the manual startup chain
        connection.commit()
    engine.dispose()

    monkeypatch.setenv("GNS3_DATABASE_URI", f"sqlite+aiosqlite:///{path}")
    app = FastAPI()
    await connect_to_db(app)
    try:
        async with app.state._db_engine.connect() as connection:
            for name in privileges:
                count = await connection.scalar(
                    sa.text("SELECT COUNT(*) FROM privileges WHERE name = :name"), {"name": name}
                )
                assert count == 1, f"{name} was not backfilled exactly once"
            attached = await connection.scalar(
                sa.text(
                    "SELECT COUNT(*) FROM privilege_role_map m"
                    " JOIN privileges p ON p.privilege_id = m.privilege_id"
                    " JOIN roles r ON r.role_id = m.role_id"
                    " WHERE p.name IN :names AND r.name = 'Administrator'"
                ).bindparams(sa.bindparam("names", expanding=True)),
                {"names": list(privileges)},
            )
            assert attached == 2, "the Administrator role does not hold both privileges"
    finally:
        await app.state._db_engine.dispose()


@pytest.mark.parametrize("versioned", [False, True])
@pytest.mark.asyncio
async def test_marker_privileges_are_backfilled_on_startup(tmp_path, monkeypatch, versioned):
    privileges = ("Link.Marker", "Project.Marker")
    role_names = ("Administrator", "User", "Lab member")
    path = tmp_path / "controller.db"
    engine = sa.create_engine(f"sqlite:///{path}")
    with engine.connect() as connection:
        Base.metadata.create_all(connection)
        # simulate a database created before the marker write endpoints had
        # their own privileges
        connection.exec_driver_sql(
            "DELETE FROM privilege_role_map WHERE privilege_id IN"
            " (SELECT privilege_id FROM privileges WHERE name IN ('Link.Marker', 'Project.Marker'))"
        )
        connection.exec_driver_sql("DELETE FROM privileges WHERE name IN ('Link.Marker', 'Project.Marker')")
        if versioned:
            cfg = _alembic_config()
            cfg.attributes["connection"] = connection
            command.stamp(cfg, BASE_REVISION)
        # else: unversioned database with the privileges already created by
        # the code, upgraded through the manual startup chain
        connection.commit()
    engine.dispose()

    monkeypatch.setenv("GNS3_DATABASE_URI", f"sqlite+aiosqlite:///{path}")
    app = FastAPI()
    await connect_to_db(app)
    try:
        async with app.state._db_engine.connect() as connection:
            for name in privileges:
                count = await connection.scalar(
                    sa.text("SELECT COUNT(*) FROM privileges WHERE name = :name"), {"name": name}
                )
                assert count == 1, f"{name} was not backfilled exactly once"
            for role in role_names:
                attached = await connection.scalar(
                    sa.text(
                        "SELECT COUNT(*) FROM privilege_role_map m"
                        " JOIN privileges p ON p.privilege_id = m.privilege_id"
                        " JOIN roles r ON r.role_id = m.role_id"
                        " WHERE p.name IN :names AND r.name = :role"
                    ).bindparams(sa.bindparam("names", expanding=True)),
                    {"names": list(privileges), "role": role},
                )
                assert attached == 2, f"the '{role}' role does not hold both marker privileges"
    finally:
        await app.state._db_engine.dispose()


@pytest.mark.parametrize("versioned", [False, True])
@pytest.mark.asyncio
async def test_mcp_tool_whitelist_table_is_added_on_upgrade(tmp_path, monkeypatch, versioned):
    path = tmp_path / "controller.db"
    engine = sa.create_engine(f"sqlite:///{path}")
    with engine.connect() as connection:
        Base.metadata.create_all(connection)
        # simulate a database from before the whitelist existed
        connection.exec_driver_sql("DROP TABLE mcp_tool_whitelist")
        if versioned:
            cfg = _alembic_config()
            cfg.attributes["connection"] = connection
            command.stamp(cfg, BASE_REVISION)
        # else: unversioned database with mcp_tool_whitelist already created
        # by the code, upgraded through the manual startup chain
        connection.commit()
    engine.dispose()

    monkeypatch.setenv("GNS3_DATABASE_URI", f"sqlite+aiosqlite:///{path}")
    app = FastAPI()
    await connect_to_db(app)
    try:
        async with app.state._db_engine.connect() as connection:
            assert await connection.run_sync(lambda conn: sa.inspect(conn).has_table("mcp_tool_whitelist"))
            # the table is usable: a group can hold whitelisted tool names
            group_id = await connection.scalar(sa.text("SELECT user_group_id FROM user_groups LIMIT 1"))
            await connection.execute(
                sa.text(
                    "INSERT INTO mcp_tool_whitelist (user_group_id, tool_name) VALUES (:group_id, 'server_version')"
                ),
                {"group_id": group_id},
            )
            count = await connection.scalar(sa.text("SELECT COUNT(*) FROM mcp_tool_whitelist"))
            assert count == 1
            await connection.commit()
    finally:
        await app.state._db_engine.dispose()


@pytest.mark.parametrize("versioned", [False, True])
@pytest.mark.asyncio
async def test_duplicate_export_privileges_are_added_on_upgrade(tmp_path, monkeypatch, versioned):
    # the Project.Duplicate and Project.Export privileges (f6d3a9c2e8b1) are
    # attached to Administrator and User, and deliberately NOT to Lab member:
    # a distributed copy must not be duplicated or exported
    privileges = ("Project.Duplicate", "Project.Export")
    path = tmp_path / "controller.db"
    engine = sa.create_engine(f"sqlite:///{path}")
    with engine.connect() as connection:
        Base.metadata.create_all(connection)
        # simulate a database from before the privileges existed
        connection.exec_driver_sql(
            "DELETE FROM privilege_role_map WHERE privilege_id IN"
            " (SELECT privilege_id FROM privileges WHERE name IN ('Project.Duplicate', 'Project.Export'))"
        )
        connection.exec_driver_sql("DELETE FROM privileges WHERE name IN ('Project.Duplicate', 'Project.Export')")
        if versioned:
            cfg = _alembic_config()
            cfg.attributes["connection"] = connection
            command.stamp(cfg, "b7d4c3f2a1e9")
        # else: unversioned database with the privileges already created by
        # the code, upgraded through the manual startup chain
        connection.commit()
    engine.dispose()

    monkeypatch.setenv("GNS3_DATABASE_URI", f"sqlite+aiosqlite:///{path}")
    app = FastAPI()
    await connect_to_db(app)
    try:
        async with app.state._db_engine.connect() as connection:
            for name in privileges:
                count = await connection.scalar(
                    sa.text("SELECT COUNT(*) FROM privileges WHERE name = :name"), {"name": name}
                )
                assert count == 1, f"{name} was not backfilled exactly once"
            for role, expected in (("Administrator", 2), ("User", 2), ("Lab member", 0)):
                attached = await connection.scalar(
                    sa.text(
                        "SELECT COUNT(*) FROM privilege_role_map m"
                        " JOIN privileges p ON p.privilege_id = m.privilege_id"
                        " JOIN roles r ON r.role_id = m.role_id"
                        " WHERE p.name IN :names AND r.name = :role"
                    ).bindparams(sa.bindparam("names", expanding=True)),
                    {"names": list(privileges), "role": role},
                )
                assert attached == expected, f"the '{role}' role holds {attached} of the two privileges"
    finally:
        await app.state._db_engine.dispose()


@pytest.mark.parametrize("versioned", [False, True])
@pytest.mark.asyncio
async def test_share_distribute_privileges_are_added_on_upgrade(tmp_path, monkeypatch, versioned):
    # the Project.Share and Project.Distribute privileges (c9e4f7a2b6d8) are
    # attached to Administrator and User, and deliberately NOT to Lab member:
    # a shared user or a copy recipient must not pass the lab on
    privileges = ("Project.Share", "Project.Distribute")
    path = tmp_path / "controller.db"
    engine = sa.create_engine(f"sqlite:///{path}")
    with engine.connect() as connection:
        Base.metadata.create_all(connection)
        # simulate a database from before the privileges existed
        connection.exec_driver_sql(
            "DELETE FROM privilege_role_map WHERE privilege_id IN"
            " (SELECT privilege_id FROM privileges WHERE name IN ('Project.Share', 'Project.Distribute'))"
        )
        connection.exec_driver_sql("DELETE FROM privileges WHERE name IN ('Project.Share', 'Project.Distribute')")
        if versioned:
            cfg = _alembic_config()
            cfg.attributes["connection"] = connection
            command.stamp(cfg, "f6d3a9c2e8b1")
        # else: unversioned database with the privileges already created by
        # the code, upgraded through the manual startup chain
        connection.commit()
    engine.dispose()

    monkeypatch.setenv("GNS3_DATABASE_URI", f"sqlite+aiosqlite:///{path}")
    app = FastAPI()
    await connect_to_db(app)
    try:
        async with app.state._db_engine.connect() as connection:
            for name in privileges:
                count = await connection.scalar(
                    sa.text("SELECT COUNT(*) FROM privileges WHERE name = :name"), {"name": name}
                )
                assert count == 1, f"{name} was not backfilled exactly once"
            for role, expected in (("Administrator", 2), ("User", 2), ("Lab member", 0)):
                attached = await connection.scalar(
                    sa.text(
                        "SELECT COUNT(*) FROM privilege_role_map m"
                        " JOIN privileges p ON p.privilege_id = m.privilege_id"
                        " JOIN roles r ON r.role_id = m.role_id"
                        " WHERE p.name IN :names AND r.name = :role"
                    ).bindparams(sa.bindparam("names", expanding=True)),
                    {"names": list(privileges), "role": role},
                )
                assert attached == expected, f"the '{role}' role holds {attached} of the two privileges"
    finally:
        await app.state._db_engine.dispose()
