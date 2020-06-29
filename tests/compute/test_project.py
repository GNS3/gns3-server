#!/usr/bin/env python
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
import sys
import uuid
import asyncio
import pytest
import aiohttp
from uuid import uuid4
from unittest.mock import patch

from tests.utils import asyncio_patch
from gns3server.compute.project import Project
from gns3server.compute.notification_manager import NotificationManager
from gns3server.compute.vpcs import VPCS, VPCSVM
from gns3server.config import Config


@pytest.fixture(scope="function")
async def manager(loop, port_manager):

    m = VPCS.instance()
    m.port_manager = port_manager
    return m


@pytest.fixture(scope="function")
async def node(compute_project, manager):

    node = manager.create_node("test", compute_project.id, "00010203-0405-0607-0809-0a0b0c0d0e0f")
    return await node


async def test_affect_uuid():

    p = Project(project_id='00010203-0405-0607-0809-0a0b0c0d0e0f')
    assert p.id == '00010203-0405-0607-0809-0a0b0c0d0e0f'


async def test_clean_tmp_directory():
    """
    The tmp directory should be clean at project open and close
    """

    p = Project(project_id='00010203-0405-0607-0809-0a0b0c0d0e0f')
    path = p.tmp_working_directory()
    os.makedirs(path)
    await p.close()
    assert not os.path.exists(path)

    os.makedirs(path)
    p = Project(project_id='00010203-0405-0607-0809-0a0b0c0d0e0f')
    assert not os.path.exists(path)


async def test_path(projects_dir):

    directory = projects_dir
    with patch("gns3server.compute.project.Project.is_local", return_value=True):
        with patch("gns3server.utils.path.get_default_project_directory", return_value=directory):
            p = Project(project_id=str(uuid4()))
            assert p.path == os.path.join(directory, p.id)
            assert os.path.exists(os.path.join(directory, p.id))


async def test_init_path(tmpdir):

    with patch("gns3server.compute.project.Project.is_local", return_value=True):
        p = Project(path=str(tmpdir), project_id=str(uuid4()))
        assert p.path == str(tmpdir)


async def test_changing_path_not_allowed(tmpdir):

    with patch("gns3server.compute.project.Project.is_local", return_value=False):
        with pytest.raises(aiohttp.web.HTTPForbidden):
            p = Project(project_id=str(uuid4()))
            p.path = str(tmpdir)


async def test_variables():

    variables = [{"name": "VAR1", "value": "VAL1"}]
    p = Project(project_id=str(uuid4()), variables=variables)
    assert p.variables == variables


async def test_json():

    p = Project(project_id=str(uuid4()))
    assert p.__json__() == {
        "name": p.name,
        "project_id": p.id,
        "variables": None
    }


async def test_json_with_variables():

    variables = [{"name": "VAR1", "value": "VAL1"}]
    p = Project(project_id=str(uuid4()), variables=variables)
    assert p.__json__() == {
        "name": p.name,
        "project_id": p.id,
        "variables": variables
    }


async def test_node_working_directory(node, projects_dir):

    directory = projects_dir
    with patch("gns3server.compute.project.Project.is_local", return_value=True):
        p = Project(project_id=str(uuid4()))
        assert p.node_working_directory(node) == os.path.join(directory, p.id, 'project-files', node.module_name, node.id)
        assert os.path.exists(p.node_working_directory(node))


async def test_node_working_path(node, projects_dir):

    directory = projects_dir
    with patch("gns3server.compute.project.Project.is_local", return_value=True):
        p = Project(project_id=str(uuid4()))
        assert p.node_working_path(node) == os.path.join(directory, p.id, 'project-files', node.module_name, node.id)
        # after this execution directory structure should not be created
        assert not os.path.exists(p.node_working_path(node))


async def test_project_delete():

    project = Project(project_id=str(uuid4()))
    directory = project.path
    assert os.path.exists(directory)
    await project.delete()
    assert os.path.exists(directory) is False


@pytest.mark.skipif(not sys.platform.startswith("win") and os.getuid() == 0, reason="Root can delete any project")
async def test_project_delete_permission_issue():

    project = Project(project_id=str(uuid4()))
    directory = project.path
    assert os.path.exists(directory)
    os.chmod(directory, 0)
    with pytest.raises(aiohttp.web.HTTPInternalServerError):
        await project.delete()
    os.chmod(directory, 700)


async def test_project_add_node(manager):

    project = Project(project_id=str(uuid4()))
    node = VPCSVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", project, manager)
    project.add_node(node)
    assert len(project.nodes) == 1


async def test_project_close(node, compute_project):

    with asyncio_patch("gns3server.compute.vpcs.vpcs_vm.VPCSVM.close") as mock:
        await compute_project.close()
        assert mock.called
    assert node.id not in node.manager._nodes


async def test_list_files(tmpdir):

    with patch("gns3server.config.Config.get_section_config", return_value={"projects_path": str(tmpdir)}):
        project = Project(project_id=str(uuid4()))
        path = project.path
        os.makedirs(os.path.join(path, "vm-1", "dynamips"))
        with open(os.path.join(path, "vm-1", "dynamips", "test.bin"), "w+") as f:
            f.write("test")
        open(os.path.join(path, "vm-1", "dynamips", "test.ghost"), "w+").close()
        with open(os.path.join(path, "test.txt"), "w+") as f:
            f.write("test2")

        files = await project.list_files()

        assert files == [
            {
                "path": "test.txt",
                "md5sum": "ad0234829205b9033196ba818f7a872b"
            },
            {
                "path": os.path.join("vm-1", "dynamips", "test.bin"),
                "md5sum": "098f6bcd4621d373cade4e832627b4f6"
            }
        ]


async def test_emit():

    with NotificationManager.instance().queue() as queue:
        await queue.get(0.5)  #  Ping

        project = Project(project_id=str(uuid4()))
        project.emit("test", {})
        (action, event, context) = await queue.get(0.5)
        assert action == "test"
        assert context["project_id"] == project.id


async def test_update_project():

    variables = [{"name": "TEST", "value": "VAL"}]
    project = Project(project_id=str(uuid.uuid4()))
    await project.update(variables=variables)
    assert project.variables == variables
