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


import pytest
import tempfile
import sys
import uuid
import os

from gns3server.compute.dynamips import Dynamips
from gns3server.compute.dynamips.dynamips_error import DynamipsError
from unittest.mock import patch
from tests.utils import asyncio_patch, AsyncioMagicMock


@pytest.fixture
async def manager(loop, port_manager):

    m = Dynamips.instance()
    m.port_manager = port_manager
    return m


def test_vm_invalid_dynamips_path(manager):

    with patch("gns3server.config.Config.get_section_config", return_value={"dynamips_path": "/bin/test_fake"}):
        with pytest.raises(DynamipsError):
            manager.find_dynamips()


@pytest.mark.skipif(sys.platform.startswith("win"), reason="Not supported by Windows")
def test_vm_non_executable_dynamips_path(manager):
    tmpfile = tempfile.NamedTemporaryFile()
    with patch("gns3server.config.Config.get_section_config", return_value={"dynamips_path": tmpfile.name}):
        with pytest.raises(DynamipsError):
            manager.find_dynamips()


def test_get_dynamips_id(manager):

    project_1 = str(uuid.uuid4())
    project_2 = str(uuid.uuid4())
    project_3 = str(uuid.uuid4())

    assert manager.get_dynamips_id(project_1) == 1
    assert manager.get_dynamips_id(project_1) == 2
    assert manager.get_dynamips_id(project_2) == 1
    with pytest.raises(DynamipsError):
        for dynamips_id in range(1, 4098):
            manager.get_dynamips_id(project_3)


def test_take_dynamips_id(manager):

    project_1 = str(uuid.uuid4())
    manager.take_dynamips_id(project_1, 1)
    assert manager.get_dynamips_id(project_1) == 2
    with pytest.raises(DynamipsError):
        manager.take_dynamips_id(project_1, 1)


def test_release_dynamips_id(manager):

    project_1 = str(uuid.uuid4())
    project_2 = str(uuid.uuid4())
    manager.take_dynamips_id(project_1, 1)
    manager.release_dynamips_id(project_1, 1)
    assert manager.get_dynamips_id(project_1) == 1
    # Should not crash for 0 id
    manager.release_dynamips_id(project_2, 0)


async def test_project_closed(manager, compute_project):

    manager._dynamips_ids[compute_project.id] = set([1, 2, 3])

    project_dir = compute_project.module_working_path(manager.module_name.lower())
    os.makedirs(project_dir)
    open(os.path.join(project_dir, "test.ghost"), "w+").close()
    await manager.project_closed(compute_project)
    assert not os.path.exists(os.path.join(project_dir, "test.ghost"))
    assert compute_project.id not in manager._dynamips_ids


async def test_duplicate_node(manager, compute_project):
    """
    Duplicate dynamips do nothing it's manage outside the
    filesystem
    """
    with asyncio_patch('gns3server.compute.dynamips.nodes.c7200.C7200.create'):
        source_node = await manager.create_node(
            'R1',
            compute_project.id,
            str(uuid.uuid4()),
            platform="c7200"
        )
        destination_node = await manager.create_node(
            'R2',
            compute_project.id,
            str(uuid.uuid4()),
            platform="c7200"
        )
        destination_node._hypervisor = AsyncioMagicMock()

        with open(os.path.join(source_node.working_dir, 'c3600_i1_nvram'), 'w+') as f:
            f.write("1")
        with open(source_node.startup_config_path, 'w+') as f:
            f.write('hostname R1\necho TEST')
        await manager.duplicate_node(source_node.id, destination_node.id)
        assert not os.path.exists(os.path.join(destination_node.working_dir, 'c3600_i1_nvram'))
        with open(destination_node.startup_config_path) as f:
            content = f.read()
            assert content == '!\nhostname R2\necho TEST'
