import pytest
import sqlalchemy as sa
from alembic import command, config
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from fastapi import FastAPI

from gns3server.db.models import Base
from gns3server.db.tasks import connect_to_db
from gns3server.db_migrations.versions import e2a7c9d4b601_add_cdrom_interfaces as migration


def _head_revision() -> str:
    cfg = config.Config()
    cfg.set_main_option("script_location", "gns3server:db_migrations")
    return ScriptDirectory.from_config(cfg).get_revision("head").revision


def test_cdrom_migration_defaults_idempotence_and_downgrade():
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE qemu_templates (id INTEGER PRIMARY KEY)")
        connection.exec_driver_sql("INSERT INTO qemu_templates (id) VALUES (1)")
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            migration.upgrade()
            assert connection.exec_driver_sql("SELECT cdrom_interface, cdrom2_interface FROM qemu_templates").one() == (
                "ide",
                "ide",
            )
            migration.downgrade()
        assert [column["name"] for column in sa.inspect(connection).get_columns("qemu_templates")] == ["id"]
    engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("versioned", [False, True])
async def test_database_startup_adds_cdrom_interfaces(tmp_path, monkeypatch, versioned):
    path = tmp_path / "controller.db"
    engine = sa.create_engine(f"sqlite:///{path}")
    with engine.connect() as connection:
        Base.metadata.create_all(connection)
        connection.exec_driver_sql("ALTER TABLE qemu_templates DROP COLUMN cdrom_interface")
        connection.exec_driver_sql("ALTER TABLE qemu_templates DROP COLUMN cdrom2_interface")
        # simulate a database created before the default ACEs were seeded
        connection.exec_driver_sql("DELETE FROM acl")
        if versioned:
            cfg = config.Config()
            cfg.set_main_option("script_location", "gns3server:db_migrations")
            cfg.attributes["connection"] = connection
            command.stamp(cfg, migration.down_revision)
        connection.commit()
    engine.dispose()
    monkeypatch.setenv("GNS3_DATABASE_URI", f"sqlite+aiosqlite:///{path}")
    app = FastAPI()
    await connect_to_db(app)
    try:
        async with app.state._db_engine.connect() as connection:
            columns = await connection.run_sync(lambda conn: sa.inspect(conn).get_columns("qemu_templates"))
            assert {"cdrom_interface", "cdrom2_interface"} <= {column["name"] for column in columns}
            revision = await connection.scalar(sa.text("SELECT version_num FROM alembic_version"))
            assert revision == _head_revision()
            # the default ACEs are restored on both startup paths
            # (migration chain, or stamp for unversioned databases)
            assert await connection.scalar(sa.text("SELECT COUNT(*) FROM acl")) == 7
    finally:
        await app.state._db_engine.dispose()
