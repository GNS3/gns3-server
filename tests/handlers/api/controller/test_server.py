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

import os
import pytest

from unittest.mock import MagicMock
from gns3server.web.web_server import WebServer


@pytest.fixture
def web_server():

    WebServer._instance = MagicMock()
    yield WebServer._instance
    WebServer._instance = None


async def test_shutdown_local(controller_api, web_server, config):

    async def hello():
        return 0

    web_server.shutdown_server.return_value = hello()
    config.set("Server", "local", True)
    response = await controller_api.post('/shutdown')
    assert response.status == 201
    assert web_server.shutdown_server.called


async def test_shutdown_non_local(controller_api, web_server, config):

    WebServer._instance = MagicMock()
    config.set("Server", "local", False)
    response = await controller_api.post('/shutdown')
    assert response.status == 403
    assert not web_server.shutdown_server.called


async def test_debug(controller_api, config, tmpdir):

    config._main_config_file = str(tmpdir / "test.conf")
    config.set("Server", "local", True)
    response = await controller_api.post('/debug')
    assert response.status == 201
    debug_dir = os.path.join(config.config_dir, "debug")
    assert os.path.exists(debug_dir)
    assert os.path.exists(os.path.join(debug_dir, "controller.txt"))


async def test_debug_non_local(controller_api, config, tmpdir):

    config._main_config_file = str(tmpdir / "test.conf")
    config.set("Server", "local", False)
    response = await controller_api.post('/debug')
    assert response.status == 403


async def test_statistics_output(controller_api):

    response = await controller_api.get('/statistics')
    assert response.status == 200
