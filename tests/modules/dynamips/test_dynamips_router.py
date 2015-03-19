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
import asyncio
import configparser

from unittest.mock import patch
from gns3server.modules.dynamips.nodes.router import Router
from gns3server.modules.dynamips.dynamips_error import DynamipsError
from gns3server.modules.dynamips import Dynamips
from gns3server.config import Config


@pytest.fixture(scope="module")
def manager(port_manager):
    m = Dynamips.instance()
    m.port_manager = port_manager
    return m


@pytest.fixture(scope="function")
def router(project, manager):
    return Router("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", project, manager)


def test_router(project, manager):
    router = Router("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", project, manager)
    assert router.name == "test"
    assert router.id == "00010203-0405-0607-0809-0a0b0c0d0e0f"


def test_router_invalid_dynamips_path(project, manager, loop):

    config = Config.instance()
    config.set("Dynamips", "dynamips_path", "/bin/test_fake")
    config.set("Dynamips", "allocate_aux_console_ports", False)

    with pytest.raises(DynamipsError):
        router = Router("test", "00010203-0405-0607-0809-0a0b0c0d0e0e", project, manager)
        loop.run_until_complete(asyncio.async(router.create()))
        assert router.name == "test"
        assert router.id == "00010203-0405-0607-0809-0a0b0c0d0e0e"
