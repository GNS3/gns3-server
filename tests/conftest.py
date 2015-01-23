# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 GNS3 Technologies Inc.
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
import socket
import asyncio
import tempfile
import shutil
from aiohttp import web

from gns3server.config import Config
from gns3server.web.route import Route
# TODO: get rid of *
from gns3server.handlers import *
from gns3server.modules import MODULES
from gns3server.modules.port_manager import PortManager
from gns3server.modules.project_manager import ProjectManager
from tests.api.base import Query


@pytest.fixture(scope="session")
def loop(request):
    """Return an event loop and destroy it at the end of test"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)  # Replace main loop to avoid conflict between tests

    def tear_down():
        loop.close()
        asyncio.set_event_loop(None)
    request.addfinalizer(tear_down)
    return loop


def _get_unused_port():
    """ Return an unused port on localhost. In rare occasion it can return
    an already used port (race condition)"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('localhost', 0))
    addr, port = s.getsockname()
    s.close()
    return port


@pytest.fixture(scope="session")
def server(request, loop, port_manager):
    """A GNS3 server"""

    port = _get_unused_port()
    host = "localhost"
    app = web.Application()
    for method, route, handler in Route.get_routes():
        app.router.add_route(method, route, handler)
    for module in MODULES:
        instance = module.instance()
        instance.port_manager = port_manager
    srv = loop.create_server(app.make_handler(), host, port)
    srv = loop.run_until_complete(srv)

    def tear_down():
        for module in MODULES:
            instance = module.instance()
            loop.run_until_complete(instance.unload())
        srv.close()
        srv.wait_closed()
    request.addfinalizer(tear_down)
    return Query(loop, host=host, port=port)


@pytest.fixture(scope="module")
def project():
    """A GNS3 lab"""

    return ProjectManager.instance().create_project(uuid="a1e920ca-338a-4e9f-b363-aa607b09dd80")


@pytest.fixture(scope="session")
def port_manager():
    """An instance of port manager"""

    return PortManager("127.0.0.1")


@pytest.fixture(scope="function")
def free_console_port(request, port_manager):
    """Get a free TCP port"""

    # In case of already use ports we will raise an exception
    port = port_manager.get_free_console_port()
    # We release the port immediately in order to allow
    # the test do whatever the test want
    port_manager.release_console_port(port)
    return port


@pytest.yield_fixture(autouse=True)
def run_around_tests():
    tmppath = tempfile.mkdtemp()

    config = Config.instance()
    server_section = config.get_section_config("Server")
    server_section["project_directory"] = tmppath
    config.set_section_config("Server", server_section)

    yield

    shutil.rmtree(tmppath)
