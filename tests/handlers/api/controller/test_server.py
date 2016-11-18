#!/usr/bin/env python
#
# Copyright (C) 2016 GNS3 Technologies Inc.
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
import asyncio

from unittest.mock import MagicMock, patch
from gns3server.web.web_server import WebServer


@pytest.yield_fixture
def web_server():
    WebServer._instance = MagicMock()
    yield WebServer._instance
    WebServer._instance = None


def test_shutdown_local(http_controller, web_server, config):
    @asyncio.coroutine
    def hello():
        return 0

    web_server.shutdown_server.return_value = hello()
    config.set("Server", "local", True)
    response = http_controller.post('/shutdown', example=True)
    assert response.status == 201
    assert web_server.shutdown_server.called


def test_shutdown_non_local(http_controller, web_server, config):
    """
    Disallow shutdown of a non local GNS3 server
    """
    WebServer._instance = MagicMock()
    config.set("Server", "local", False)
    response = http_controller.post('/shutdown')
    assert response.status == 403
    assert not web_server.shutdown_server.called


def test_debug(http_controller, config, tmpdir):
    config._main_config_file = str(tmpdir / "test.conf")

    config.set("Server", "local", True)
    response = http_controller.post('/debug')
    assert response.status == 201
    debug_dir = os.path.join(config.config_dir, "debug")
    assert os.path.exists(debug_dir)
    assert os.path.exists(os.path.join(debug_dir, "controller.txt"))


def test_debug_non_local(http_controller, config, tmpdir):
    config._main_config_file = str(tmpdir / "test.conf")

    config.set("Server", "local", False)
    response = http_controller.post('/debug')
    assert response.status == 403
