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
import signal
import os

from fastapi import FastAPI
from pydantic import ValidationError
from watchfiles import awatch, Change

from typing import List
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from alembic import command, config
from alembic.script import ScriptDirectory
from alembic.runtime.migration import MigrationContext
from alembic.util.exc import CommandError

from gns3server.db.repositories.computes import ComputesRepository
from gns3server.db.repositories.images import ImagesRepository
from gns3server.utils.images import discover_images, check_valid_image_header, read_image_info, default_images_directory, InvalidImageError
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
    engine = create_async_engine(db_url, connect_args={"check_same_thread": False}, future=True)
    alembic_cfg = config.Config()
    alembic_cfg.set_main_option("script_location", "gns3server:db_migrations")
    #alembic_cfg.set_main_option('sqlalchemy.url', db_url)
    try:
        async with engine.connect() as conn:
            current_rev, head_rev = await conn.run_sync(check_revision, alembic_cfg)
            log.info(f"Current database revision is {current_rev}")
            if current_rev is None:
                await conn.run_sync(Base.metadata.create_all)
                await conn.run_sync(run_stamp, alembic_cfg)
            elif current_rev != head_rev:
                # upgrade the database if needed
                await conn.run_sync(run_upgrade, alembic_cfg)
                await conn.commit()
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


def image_filter(change: Change, path: str) -> bool:

    if change == Change.added and os.path.isfile(path):
        if path.endswith(".tmp") or path.endswith(".md5sum") or path.startswith("."):
            return False
        if "/lib/" in path or "/lib64/" in path:
            # ignore custom IOU libraries
            return False
        header_magic_len = 7
        with open(path, "rb") as f:
            image_header = f.read(header_magic_len)  # read the first 7 bytes of the file
            if len(image_header) >= header_magic_len:
                try:
                    check_valid_image_header(image_header)
                except InvalidImageError as e:
                    log.debug(f"New image '{path}': {e}")
                    return False
            else:
                log.debug(f"New image '{path}': size is too small to be valid")
                return False
        return True
    # FIXME: should we support image deletion?
    # elif change == Change.deleted:
    #     return True
    return False


async def monitor_images_on_filesystem(app: FastAPI):

    directories_to_monitor = []
    for image_type in ("qemu", "ios", "iou"):
        image_dir = default_images_directory(image_type)
        if os.path.isdir(image_dir):
            log.debug(f"Monitoring for new images in '{image_dir}'")
            directories_to_monitor.append(image_dir)

    try:
        async for changes in awatch(
                *directories_to_monitor,
                watch_filter=image_filter,
                raise_interrupt=True
        ):
            async with AsyncSession(app.state._db_engine) as db_session:
                images_repository = ImagesRepository(db_session)
                for change in changes:
                    change_type, image_path = change
                    if change_type == Change.added:
                        try:
                            image = await read_image_info(image_path)
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
                    # if change_type == Change.deleted:
                    #     try:
                    #         if await images_repository.get_image(image_path):
                    #             success = await images_repository.delete_image(image_path)
                    #             if not success:
                    #                 log.warning(f"Could not delete image '{image_path}' from the database")
                    #             else:
                    #                 log.info(f"Image '{image_path}' has been deleted from the database")
                    #     except SQLAlchemyError as e:
                    #         log.warning(f"Error while deleting image '{image_path}' from the database: {e}")
    except KeyboardInterrupt:
        # send SIGTERM to the server PID so uvicorn can shutdown the process
        os.kill(os.getpid(), signal.SIGTERM)


async def discover_images_on_filesystem(app: FastAPI):

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
