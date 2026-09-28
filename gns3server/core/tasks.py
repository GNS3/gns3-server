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

from fastapi import FastAPI
from contextlib import asynccontextmanager

from gns3server.controller import Controller
from gns3server.config import Config
from gns3server.compute import MODULES
from gns3server.compute.port_manager import PortManager
from gns3server.compute.marker.marker_manager import MarkerManager
from gns3server.utils.http_client import HTTPClient
from gns3server.db.tasks import connect_to_db, get_computes, disconnect_from_db
from gns3server.services.image_reconciliation import get_image_reconciliation_service


import logging

log = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):

    await startup(app)
    try:
        yield
    finally:
        await shutdown(app)


async def startup(app: FastAPI) -> None:
    """
    Tasks to be performed when the server is starting.
    """

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

    get_image_reconciliation_service(app).start_background()

    for module in MODULES:
        log.debug(f"Loading module {module.__name__}")
        m = module.instance()
        m.port_manager = PortManager.instance()

    # Start the marker (traffic-insight) UDP sink. One listener per compute
    # process receives ubridge MARK signals; ubridges are told its host/port at
    # startup (see BaseNode._start_ubridge).
    server_settings = Config.instance().settings.Server
    await MarkerManager.instance().start(
        host=server_settings.marker_listen_host, port=server_settings.marker_listen_port
    )

    # Mark MCP server as ready to accept connections (if MCP is available)
    from gns3server.agent import MCP_AVAILABLE

    if MCP_AVAILABLE:
        from gns3server.agent.mcp import set_mcp_server_ready
        set_mcp_server_ready(True)
    log.info("GNS3 server startup completed")


async def shutdown(app: FastAPI) -> None:
    """
    Tasks to be performed when the server is exiting.
    """

    service = getattr(app.state, "image_reconciliation", None)
    if service is not None:
        await service.close()
        del app.state.image_reconciliation
    await HTTPClient.close_session()
    await MarkerManager.instance().stop()
    # Kill resident sharkd sessions (marker replay) and drop their /tmp
    # scratch copies before the process exits.
    from gns3server.controller import marker_replay

    await marker_replay.close_sessions()
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
