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
import sqlalchemy as sa
from alembic import command, config
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from fastapi import FastAPI

from gns3server.db.models import Base
from gns3server.db.tasks import connect_to_db
from gns3server.db_migrations.versions import ab9aec245c08_add_auth_source_to_users_table as migration


def test_auth_source_migration_defaults_idempotence_and_downgrade():
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE users (user_id VARCHAR PRIMARY KEY, username VARCHAR)")
        connection.exec_driver_sql("INSERT INTO users (user_id, username) VALUES ('1', 'admin')")
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            migration.upgrade()
            assert connection.exec_driver_sql("SELECT auth_source FROM users").scalar() == "local"
            migration.downgrade()
        assert [column["name"] for column in sa.inspect(connection).get_columns("users")] == ["user_id", "username"]
    engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("versioned", [False, True])
async def test_database_startup_adds_auth_source(tmp_path, monkeypatch, versioned):
    path = tmp_path / "controller.db"
    engine = sa.create_engine(f"sqlite:///{path}")
    with engine.connect() as connection:
        Base.metadata.create_all(connection)
        connection.exec_driver_sql("ALTER TABLE users DROP COLUMN auth_source")
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
            columns = await connection.run_sync(lambda conn: sa.inspect(conn).get_columns("users"))
            assert "auth_source" in {column["name"] for column in columns}
            revision = await connection.scalar(sa.text("SELECT version_num FROM alembic_version"))
            assert revision == migration.revision
    finally:
        await app.state._db_engine.dispose()
