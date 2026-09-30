#!/usr/bin/env python
#
# Copyright (C) 2020 GNS3 Technologies Inc.
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

import logging
import os
from typing import List, Optional

import sqlalchemy as sa
from alembic import command, config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from alembic.util.exc import CommandError
from fastapi import FastAPI
from pydantic import ValidationError
from sqlalchemy import event
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from gns3server import schemas
from gns3server.config import Config
from gns3server.db.repositories.computes import ComputesRepository
from gns3server.db.repositories.images import ImagesRepository
from gns3server.utils.images import read_image_info

from .models import Base

log = logging.getLogger(__name__)


def run_upgrade(connection, cfg):

    cfg.attributes["connection"] = connection
    try:
        command.upgrade(cfg, "head")
    except CommandError as e:
        log.error(f"Could not upgrade database: {e}")


def run_stamp(connection, cfg):

    cfg.attributes["connection"] = connection
    try:
        command.stamp(cfg, "head")
    except CommandError as e:
        log.error(f"Could not stamp database: {e}")


def check_revision(connection, cfg):

    script = ScriptDirectory.from_config(cfg)
    head_rev = script.get_revision("head").revision
    context = MigrationContext.configure(connection)
    current_rev = context.get_current_revision()
    return current_rev, head_rev


async def connect_to_db(app: FastAPI) -> None:

    db_path = os.path.join(Config.instance().config_dir, "gns3_controller.db")
    db_url = os.environ.get("GNS3_DATABASE_URI", f"sqlite+aiosqlite:///{db_path}")
    engine = create_async_engine(
        db_url, connect_args={"check_same_thread": False, "timeout": 20}, future=True, pool_size=512, max_overflow=1024
    )

    # Register PRAGMA on the sync engine to ensure it fires for async connections
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # Verify WAL mode is active
    async with engine.connect() as _verify_conn:

        def _check_wal(conn):
            cursor = conn.connection.cursor()
            cursor.execute("PRAGMA journal_mode")
            row = cursor.fetchone()
            cursor.close()
            return row[0] if row else "unknown"

        wal_mode = await _verify_conn.run_sync(_check_wal)
        log.info(f"SQLite journal mode: {wal_mode}")
        if wal_mode and wal_mode.upper() != "WAL":
            log.warning("WAL mode not active - concurrent writes may cause 'database is locked' errors")
    alembic_cfg = config.Config()
    alembic_cfg.set_main_option("script_location", "gns3server:db_migrations")
    # alembic_cfg.set_main_option('sqlalchemy.url', db_url)
    try:
        async with engine.connect() as conn:
            current_rev, head_rev = await conn.run_sync(check_revision, alembic_cfg)
            log.info(f"Current database revision is {current_rev}")
            if current_rev is None:
                # No version tracking found. Check if this is a truly new database
                # or an old database that needs migration.
                def check_db_state(connection):
                    # Check if llm_model_configs table exists
                    inspector = sa.inspect(connection)
                    tables = inspector.get_table_names()

                    if "users" not in tables:
                        return "new"  # Truly new database

                    # Check for new feature columns that indicate this is already migrated
                    columns = [col["name"] for col in inspector.get_columns("users")]
                    if "llm_model_configs" in tables:
                        # The llm_model_configs table already exists (created from code)
                        return "new_with_llm_configs"
                    else:
                        # Old database without llm_model_configs table, needs migration
                        return "old_needs_migration"

                db_state = await conn.run_sync(check_db_state)

                if db_state == "new":
                    # Truly new database: create all tables and stamp
                    await conn.run_sync(Base.metadata.create_all)
                    await conn.run_sync(run_stamp, alembic_cfg)
                    await conn.commit()
                    log.info("Created new database and stamped to head revision")
                elif db_state == "new_with_llm_configs":
                    # Database already has llm_model_configs table (from Base.metadata.create_all)
                    # Older unversioned metadata databases lack inventory fields.
                    # Ensure the additive schema before stamping the current head.
                    def upgrade_inventory(connection):
                        from alembic.operations import Operations

                        from gns3server.db_migrations.versions.d9e8a2b7c401_image_inventory_reconciliation import (
                            upgrade,
                        )

                        with Operations.context(MigrationContext.configure(connection)):
                            upgrade()

                    await conn.run_sync(upgrade_inventory)
                    await conn.run_sync(run_stamp, alembic_cfg)
                    await conn.commit()
                    log.info("Database has llm_model_configs table, stamped to head revision")
                else:
                    # Old database without llm_model_configs table: run migrations
                    log.info("Old database detected, running migrations to add llm_model_configs table...")
                    await conn.run_sync(run_upgrade, alembic_cfg)
                    await conn.commit()
                    log.info("Database migrations completed successfully")
            elif current_rev != head_rev:
                # upgrade the database if needed
                log.info(f"Upgrading database from revision {current_rev} to {head_rev}...")
                await conn.run_sync(run_upgrade, alembic_cfg)
                await conn.commit()
                log.info("Database upgrade completed successfully")
        app.state._db_engine = engine
    except SQLAlchemyError as e:
        log.fatal(f"Error while connecting to database '{db_url}: {e}")


async def disconnect_from_db(app: FastAPI) -> None:

    # dispose of the connection pool used by the database engine
    if app.state._db_engine:
        await app.state._db_engine.dispose()
        log.info("Disconnected from database")


async def get_computes(app: FastAPI) -> List[schemas.Compute]:

    computes = []
    async with AsyncSession(app.state._db_engine) as db_session:
        db_computes = await ComputesRepository(db_session).get_computes()
        for db_compute in db_computes:
            try:
                compute = schemas.Compute.model_validate(db_compute)
            except ValidationError as e:
                log.error(f"Could not load compute '{db_compute.compute_id}' from database: {e}")
                continue
            computes.append(compute)
    return computes


async def update_disk_checksums(updated_disks: List[str]) -> None:
    """Refresh complete metadata after a server-managed disk modification."""
    from gns3server.api.server import app
    from gns3server.utils.image_inventory import image_lock

    for path in updated_disks:
        async with image_lock(path):
            async with AsyncSession(app.state._db_engine, expire_on_commit=False) as db_session:
                repository = ImagesRepository(db_session)
                image = await repository.get_image(path)
                if image:
                    info = await read_image_info(path, str(image.image_type), allow_raw_image=True)
                    try:
                        os.unlink(path + ".md5sum")
                    except FileNotFoundError:
                        pass
                    except OSError as e:
                        log.warning("Could not invalidate checksum cache for '%s': %s", path, e)
                    await repository.save_verified_image(info)


async def get_user_llm_config_full(user_id: str, app: FastAPI) -> Optional[dict]:
    """
    Get user's full LLM configuration with decrypted API key for Copilot.

    This is a system-level function that bypasses API security restrictions.
    It retrieves the complete configuration including decrypted API keys,
    even for inherited group configurations.

    Args:
        user_id: User UUID
        app: FastAPI application instance

    Returns:
        Dictionary with LLM configuration (provider, model, api_key, etc.)
        or None if not found.
    """
    from uuid import UUID

    from gns3server.db.repositories.llm_model_configs import LLMModelConfigsRepository
    from gns3server.utils.encryption import decrypt, is_encrypted

    try:
        user_uuid = UUID(user_id)

        async with AsyncSession(app.state._db_engine, expire_on_commit=False) as session:
            repo = LLMModelConfigsRepository(session)

            # Get effective configs (own + inherited from groups)
            result = await repo.get_user_effective_configs(
                user_uuid,
                current_user_id=user_uuid,  # Viewing own config
                current_user_is_superadmin=False,
            )

            if not result or not result.get("default_config"):
                log.warning(f"No default LLM configuration found for user {user_id}")
                return None

            default_config = result["default_config"]
            config_id = default_config["config_id"]
            source = default_config["source"]  # "user" or "group"

            # Get full config from database
            if source == "user":
                full_config = await repo.get_user_config(config_id)
            else:
                full_config = await repo.get_group_config(config_id)

            if not full_config:
                log.error(f"Failed to retrieve full config from database: config_id={config_id}")
                return None

            # Decrypt API key
            config_data = full_config.config.copy()
            if "api_key" in config_data and config_data["api_key"]:
                try:
                    if is_encrypted(config_data["api_key"]):
                        config_data["api_key"] = decrypt(config_data["api_key"])
                        log.debug(f"Successfully decrypted API key for user {user_id}")
                except Exception as e:
                    log.error(f"Failed to decrypt API key: {e}")
                    config_data["api_key"] = None

            # Build configuration dict
            llm_config = {
                "config_id": str(full_config.config_id),
                "name": full_config.name,
                "model_type": str(full_config.model_type),
                "source": source,
                "group_name": default_config.get("group_name"),
                "user_id": str(full_config.user_id) if full_config.user_id else None,
                "group_id": str(full_config.group_id) if full_config.group_id else None,
                **config_data,  # provider, api_key, model, temperature, etc.
            }

            # Validate required fields
            if not llm_config.get("provider"):
                log.error(f"LLM config missing 'provider' field: {config_id}")
                return None

            if not llm_config.get("model"):
                log.error(f"LLM config missing 'model' field: {config_id}")
                return None

            log.info(
                f"Retrieved LLM config for user {user_id}: "
                f"provider={llm_config.get('provider')}, model={llm_config.get('model')}, source={source}"
            )

            return llm_config

    except Exception as e:
        log.error(f"Failed to retrieve LLM config for user {user_id}: {e}", exc_info=True)
        return None
