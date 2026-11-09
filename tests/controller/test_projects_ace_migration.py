import pytest
import sqlalchemy as sa
from alembic import command, config
from fastapi import FastAPI

from gns3server.db.models import Base
from gns3server.db.tasks import connect_to_db


def _alembic_config():
    cfg = config.Config()
    cfg.set_main_option("script_location", "gns3server:db_migrations")
    return cfg


def test_default_aces_are_seeded_without_propagation_on_projects():
    engine = sa.create_engine("sqlite://")
    with engine.connect() as connection:
        Base.metadata.create_all(connection)
        assert connection.scalar(sa.text("SELECT COUNT(*) FROM acl")) == 7
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
            command.stamp(cfg, "c5e9a3f7d821")
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
            assert await connection.scalar(sa.text("SELECT COUNT(*) FROM acl")) == 7
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
            command.stamp(cfg, "c5e9a3f7d821")
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
