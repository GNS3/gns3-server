"""Startup media revision, including upgrade, downgrade and database startup."""

import logging

import pytest
import sqlalchemy as sa
from alembic import config
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from gns3server.db import tasks
from gns3server.db.models import Base
from gns3server.db.models.templates import QemuTemplate
from gns3server.db_migrations.versions import (
    a4d1f6b83c52_add_startup_media_profile_to_qemu_templates as media_migration,
)

RELEASED_REVISION = "b7d4c3f2a1e9"  # the last released revision before startup media


@pytest.fixture
def cfg():
    value = config.Config()
    value.set_main_option("script_location", "gns3server:db_migrations")
    return value


@pytest.fixture
def database(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'gns3_controller.db'}")
    yield engine
    engine.dispose()


def stamp_raw(connection, revision, *columns):
    extra = "".join(f", {name} VARCHAR" for name in columns)
    connection.execute(sa.text(f"CREATE TABLE qemu_templates (template_id VARCHAR PRIMARY KEY{extra})"))
    connection.execute(sa.text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)"))
    connection.execute(sa.text("INSERT INTO alembic_version VALUES (:rev)"), {"rev": revision})
    connection.commit()


def current(connection):
    return MigrationContext.configure(connection).get_current_revision()


HEAD = "a4d1f6b83c52"


def test_there_is_a_single_head_after_the_restore_revision(cfg):
    script = ScriptDirectory.from_config(cfg)
    assert script.get_heads() == [HEAD]
    assert script.get_revision(HEAD).down_revision == RELEASED_REVISION


def test_an_unknown_revision_is_reported_and_left_alone(database, cfg, caplog):
    with database.connect() as connection:
        stamp_raw(connection, "0123456789ab")
        with caplog.at_level(logging.ERROR):
            tasks.run_upgrade(connection, cfg)
        connection.commit()
        assert current(connection) == "0123456789ab"
    assert "0123456789ab" in caplog.text and "does not know" in caplog.text
    assert "Could not upgrade" not in caplog.text


def test_a_database_at_a_known_revision_still_upgrades(database, cfg):
    with database.connect() as connection:
        stamp_raw(connection, RELEASED_REVISION)
        tasks.run_upgrade(connection, cfg)
        assert current(connection) == HEAD


def columns(connection):
    return {column["name"] for column in sa.inspect(connection).get_columns("qemu_templates")}


def test_upgrading_twice_and_with_the_column_already_present_is_harmless(database, cfg):
    with database.connect() as connection:
        stamp_raw(connection, RELEASED_REVISION, "startup_media_profile")
        tasks.run_upgrade(connection, cfg)
        tasks.run_upgrade(connection, cfg)
        assert current(connection) == HEAD
        assert "startup_media_profile" in columns(connection)


def test_startup_media_migration_is_idempotent_and_reversible(database):
    with database.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE qemu_templates (id INTEGER PRIMARY KEY, name TEXT)")
        with Operations.context(MigrationContext.configure(connection)):
            media_migration.upgrade()
            media_migration.upgrade()
            names = [column["name"] for column in sa.inspect(connection).get_columns("qemu_templates")]
            assert names == ["id", "name", "startup_media_profile"]
            media_migration.downgrade()
        names = [column["name"] for column in sa.inspect(connection).get_columns("qemu_templates")]
        assert names == ["id", "name"]


@pytest.mark.asyncio
async def test_controller_startup_upgrades_and_stamps_an_unversioned_database(database, monkeypatch):
    from gns3server.services import auth_service

    monkeypatch.setattr(auth_service, "hash_password", lambda _: "test-hash")
    with database.connect() as connection:
        Base.metadata.create_all(connection)
        connection.execute(sa.text("ALTER TABLE qemu_templates DROP COLUMN startup_media_profile"))
        connection.commit()
        assert current(connection) is None
    monkeypatch.setenv("GNS3_DATABASE_URI", f"sqlite+aiosqlite:///{database.url.database}")
    app = FastAPI()
    await tasks.connect_to_db(app)
    try:
        async with AsyncSession(app.state._db_engine) as session:
            await session.execute(sa.select(QemuTemplate.startup_media_profile))
        with database.connect() as connection:
            assert current(connection) == HEAD
    finally:
        await tasks.disconnect_from_db(app)
