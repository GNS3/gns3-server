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

from typing import Callable
from fastapi import FastAPI

from gns3server.controller import Controller
from gns3server.config import Config
from gns3server.compute import MODULES
from gns3server.compute.port_manager import PortManager
from gns3server.utils.http_client import HTTPClient
from gns3server.db.tasks import connect_to_db, get_computes, disconnect_from_db, discover_images_on_filesystem


import logging

log = logging.getLogger(__name__)


def create_startup_handler(app: FastAPI) -> Callable:
    """
    Tasks to be performed when the server is starting.
    """

    async def start_app() -> None:
        loop = asyncio.get_event_loop()
        logger = logging.getLogger("asyncio")
        logger.setLevel(logging.ERROR)

        if log.getEffectiveLevel() == logging.DEBUG:
            # On debug version we enable info that
            # coroutine is not called in a way await/await
            loop.set_debug(True)

        # connect to the database
        await connect_to_db(app)

        # retrieve the computes from the database
        computes = await get_computes(app)

        await Controller.instance().start(computes)

        # Because with a large image collection
        # without md5sum already computed we start the
        # computing with server start
        from gns3server.compute.qemu import Qemu

        if Config.instance().settings.Server.auto_discover_images is True:
            # Start the discovering new images on file system 5 seconds after the server has started
            # to give it a chance to process API requests
            loop.call_later(5, asyncio.create_task, discover_images_on_filesystem(app))

        for module in MODULES:
            log.debug(f"Loading module {module.__name__}")
            m = module.instance()
            m.port_manager = PortManager.instance()

    return start_app


def create_shutdown_handler(app: FastAPI) -> Callable:
    """
    Tasks to be performed when the server is exiting.
    """

    async def shutdown_handler() -> None:
        await HTTPClient.close_session()
        await Controller.instance().stop()

        for module in MODULES:
            log.debug(f"Unloading module {module.__name__}")
            m = module.instance()
            await m.unload()

        if PortManager.instance().tcp_ports:
            log.warning(f"TCP ports are still used {PortManager.instance().tcp_ports}")

        if PortManager.instance().udp_ports:
            log.warning(f"UDP ports are still used {PortManager.instance().udp_ports}")

        await disconnect_from_db(app)

    return shutdown_handler
