# -*- coding: utf-8 -*-
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
import uuid
import pytest

from gns3server.compute.dynamips.nodes.router import Router
from gns3server.compute.dynamips.dynamips_error import DynamipsError
from gns3server.compute.dynamips import Dynamips
from gns3server.config import Config


@pytest.fixture
async def manager(loop, port_manager):

    m = Dynamips.instance()
    m.port_manager = port_manager
    return m


@pytest.fixture(scope="function")
def router(compute_project, manager):

    return Router("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", compute_project, manager)


def test_router(compute_project, manager):

    router = Router("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", compute_project, manager)
    assert router.name == "test"
    assert router.id == "00010203-0405-0607-0809-0a0b0c0d0e0f"


def test_convert_project_before_2_0_0_b3(compute_project, manager):

    node_id = str(uuid.uuid4())
    wdir = compute_project.module_working_directory(manager.module_name.lower())
    os.makedirs(os.path.join(wdir, node_id))
    os.makedirs(os.path.join(wdir, "configs"))
    open(os.path.join(wdir, "configs", "i1_startup-config.cfg"), "w+").close()
    open(os.path.join(wdir, "configs", "i2_startup-config.cfg"), "w+").close()
    open(os.path.join(wdir, "c7200_i1_nvram"), "w+").close()
    open(os.path.join(wdir, "c7200_i2_nvram"), "w+").close()
    router = Router("test", node_id, compute_project, manager, dynamips_id=1)
    assert os.path.exists(os.path.join(wdir, node_id, "configs", "i1_startup-config.cfg"))
    assert not os.path.exists(os.path.join(wdir, node_id, "configs", "i2_startup-config.cfg"))
    assert os.path.exists(os.path.join(wdir, node_id, "c7200_i1_nvram"))
    assert not os.path.exists(os.path.join(wdir, node_id, "c7200_i2_nvram"))


async def test_router_invalid_dynamips_path(compute_project, manager):

    config = Config.instance()
    config.set("Dynamips", "dynamips_path", "/bin/test_fake")
    config.set("Dynamips", "allocate_aux_console_ports", False)

    with pytest.raises(DynamipsError):
        router = Router("test", "00010203-0405-0607-0809-0a0b0c0d0e0e", compute_project, manager)
        await router.create()
        assert router.name == "test"
        assert router.id == "00010203-0405-0607-0809-0a0b0c0d0e0e"
