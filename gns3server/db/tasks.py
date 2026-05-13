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

import asyncio
import time
import os

from fastapi import FastAPI
from pydantic import ValidationError
from typing import List, Optional
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from alembic import command, config
from alembic.script import ScriptDirectory
from alembic.runtime.migration import MigrationContext
from alembic.util.exc import CommandError
from watchdog.observers import Observer
from watchdog.events import FileSystemEvent, PatternMatchingEventHandler

from gns3server.db.repositories.computes import ComputesRepository
from gns3server.db.repositories.images import ImagesRepository
from gns3server.utils.images import md5sum, discover_images, read_image_info, InvalidImageError
from gns3server.utils.asyncio import wait_run_in_executor
from gns3server import schemas

from .models import Base
from gns3server.config import Config

import logging

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
    engine = create_async_engine(db_url, connect_args={"check_same_thread": False, "timeout": 20}, future=True, pool_size=512, max_overflow=1024)
    alembic_cfg = config.Config()
    alembic_cfg.set_main_option("script_location", "gns3server:db_migrations")
    #alembic_cfg.set_main_option('sqlalchemy.url', db_url)
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

                    if 'users' not in tables:
                        return 'new'  # Truly new database

                    # Check for new feature columns that indicate this is already migrated
                    columns = [col['name'] for col in inspector.get_columns('users')]
                    if 'llm_model_configs' in tables:
                        # The llm_model_configs table already exists (created from code)
                        return 'new_with_llm_configs'
                    else:
                        # Old database without llm_model_configs table, needs migration
                        return 'old_needs_migration'

                db_state = await conn.run_sync(check_db_state)

                if db_state == 'new':
                    # Truly new database: create all tables and stamp
                    await conn.run_sync(Base.metadata.create_all)
                    await conn.run_sync(run_stamp, alembic_cfg)
                    await conn.commit()
                    log.info("Created new database and stamped to head revision")
                elif db_state == 'new_with_llm_configs':
                    # Database already has llm_model_configs table (from Base.metadata.create_all)
                    # Just stamp the version
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
    if getattr(app.state, "_db_engine"):
        await app.state._db_engine.dispose()
        log.info(f"Disconnected from database")


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):

    # Enable SQL foreign key support for SQLite
    # https://docs.sqlalchemy.org/en/14/dialects/sqlite.html#foreign-key-support
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


async def get_computes(app: FastAPI) -> List[dict]:

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


async def discover_images_on_filesystem(app: FastAPI) -> None:

    async with AsyncSession(app.state._db_engine) as db_session:
        images_repository = ImagesRepository(db_session)
        db_images = await images_repository.get_images()
        existing_image_paths = []
        for db_image in db_images:
            try:
                image = schemas.Image.model_validate(db_image)
                existing_image_paths.append(image.path)
            except ValidationError as e:
                log.error(f"Could not load image '{db_image.filename}' from database: {e}")
                continue
        for image_type in ("qemu", "ios", "iou"):
            discovered_images = await discover_images(image_type, existing_image_paths)
            for image in discovered_images:
                log.info(f"Adding discovered image '{image['path']}' to the database")
                try:
                    await images_repository.add_image(**image)
                except SQLAlchemyError as e:
                    log.warning(f"Error while adding image '{image['path']}' to the database: {e}")

    # monitor if images have been manually added
    asyncio.create_task(monitor_images_on_filesystem(app))


async def update_disk_checksums(updated_disks: List[str]) -> None:
    """
    Update the checksum of a list of disks in the database.

    :param updated_disks: list of updated disks
    """

    from gns3server.api.server import app
    async with AsyncSession(app.state._db_engine) as db_session:
        images_repository = ImagesRepository(db_session)
        for path in updated_disks:
            image = await images_repository.get_image(path)
            if image:
                log.info(f"Updating image '{path}' in the database")
                checksum = await wait_run_in_executor(md5sum, path, cache_to_md5file=False)
                if image.checksum != checksum:
                    await images_repository.update_image(path, checksum, "md5")

class EventHandler(PatternMatchingEventHandler):
    """
    Watchdog event handler.
    """

    def __init__(self, queue: asyncio.Queue, loop: asyncio.BaseEventLoop, **kwargs):

        self._loop = loop
        self._queue = queue

        # ignore temporary files, md5sum files, hidden files and directories
        super().__init__(ignore_patterns=["*.tmp", "*.md5sum", ".*"], ignore_directories = True, **kwargs)

    def on_closed(self, event: FileSystemEvent) -> None:
        # monitor for closed files (e.g. when a file has finished to be copied)
        if "/lib/" in event.src_path or "/lib64/" in event.src_path:
            return  # ignore custom IOU libraries
        self._loop.call_soon_threadsafe(self._queue.put_nowait, event)

class EventIterator(object):
    """
    Watchdog Event iterator.
    """

    def __init__(self, queue: asyncio.Queue):
        self.queue = queue

    def __aiter__(self):
        return self

    async def __anext__(self):

        item = await self.queue.get()
        if item is None:
            raise StopAsyncIteration
        return item

async def monitor_images_on_filesystem(app: FastAPI):

    def watchdog(
            path: str,
            queue: asyncio.Queue,
            loop: asyncio.BaseEventLoop,
            app: FastAPI, recursive: bool = False
    ) -> None:
        """
        Thread to monitor a directory for new images.
        """

        handler = EventHandler(queue, loop)
        observer = Observer()
        observer.schedule(handler, str(path), recursive=recursive)
        observer.start()
        log.info(f"Monitoring for new images in '{path}'")
        while True:
            time.sleep(1)
            # stop when the app is exiting
            if app.state.exiting:
                observer.stop()
                observer.join(10)
                log.info(f"Stopping monitoring for new images in '{path}'")
                loop.call_soon_threadsafe(queue.put_nowait, None)
                break

    queue = asyncio.Queue()
    loop = asyncio.get_event_loop()
    server_config = Config.instance().settings.Server
    image_dir = os.path.expanduser(server_config.images_path)
    asyncio.get_event_loop().run_in_executor(None, watchdog,image_dir, queue, loop, app, True)

    async for filesystem_event in EventIterator(queue):
        # read the file system event from the queue
        image_path = filesystem_event.src_path
        expected_image_type = None
        if "IOU" in image_path:
            expected_image_type = "iou"
        elif "QEMU" in image_path:
            expected_image_type = "qemu"
        elif "IOS" in image_path:
            expected_image_type = "ios"
        async with AsyncSession(app.state._db_engine) as db_session:
            images_repository = ImagesRepository(db_session)
            try:
                image = await read_image_info(image_path, expected_image_type)
            except InvalidImageError as e:
                log.warning(str(e))
                continue
            try:
                if await images_repository.get_image(image_path):
                    continue
                await images_repository.add_image(**image)
                log.info(f"Discovered image '{image_path}' has been added to the database")
            except SQLAlchemyError as e:
                log.warning(f"Error while adding image '{image_path}' to the database: {e}")


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
        user_uuid = UUID(user_id) if isinstance(user_id, str) else user_id

        async with AsyncSession(app.state._db_engine, expire_on_commit=False) as session:
            repo = LLMModelConfigsRepository(session)

            # Get effective configs (own + inherited from groups)
            result = await repo.get_user_effective_configs(
                user_uuid,
                current_user_id=user_uuid,  # Viewing own config
                current_user_is_superadmin=False
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
                **config_data  # provider, api_key, model, temperature, etc.
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

