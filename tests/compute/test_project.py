#!/usr/bin/env python
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

import os
import uuid
import json
import asyncio
import pytest
import aiohttp
import zipfile
from uuid import uuid4
from unittest.mock import patch

from tests.utils import asyncio_patch
from gns3server.compute.project import Project
from gns3server.compute.notification_manager import NotificationManager
from gns3server.compute.vpcs import VPCS, VPCSVM
from gns3server.config import Config


@pytest.fixture(scope="function")
def manager(port_manager):
    m = VPCS.instance()
    m.port_manager = port_manager
    return m


@pytest.fixture(scope="function")
def node(project, manager, loop):
    node = manager.create_node("test", project.id, "00010203-0405-0607-0809-0a0b0c0d0e0f")
    return loop.run_until_complete(asyncio.async(node))


def test_affect_uuid():
    p = Project(project_id='00010203-0405-0607-0809-0a0b0c0d0e0f')
    assert p.id == '00010203-0405-0607-0809-0a0b0c0d0e0f'


def test_clean_tmp_directory(async_run):
    """
    The tmp directory should be clean at project open and close
    """

    p = Project(project_id='00010203-0405-0607-0809-0a0b0c0d0e0f')
    path = p.tmp_working_directory()
    os.makedirs(path)
    async_run(p.close())
    assert not os.path.exists(path)

    os.makedirs(path)
    p = Project(project_id='00010203-0405-0607-0809-0a0b0c0d0e0f')
    assert not os.path.exists(path)


def test_path(tmpdir):

    directory = Config.instance().get_section_config("Server").get("projects_path")

    with patch("gns3server.compute.project.Project.is_local", return_value=True):
        with patch("gns3server.utils.path.get_default_project_directory", return_value=directory):
            p = Project(project_id=str(uuid4()))
            assert p.path == os.path.join(directory, p.id)
            assert os.path.exists(os.path.join(directory, p.id))


def test_init_path(tmpdir):

    with patch("gns3server.compute.project.Project.is_local", return_value=True):
        p = Project(path=str(tmpdir), project_id=str(uuid4()))
        assert p.path == str(tmpdir)


def test_changing_path_not_allowed(tmpdir):
    with patch("gns3server.compute.project.Project.is_local", return_value=False):
        with pytest.raises(aiohttp.web.HTTPForbidden):
            p = Project(project_id=str(uuid4()))
            p.path = str(tmpdir)


def test_json(tmpdir):
    p = Project(project_id=str(uuid4()))
    assert p.__json__() == {"name": p.name, "project_id": p.id}


def test_node_working_directory(tmpdir, node):
    directory = Config.instance().get_section_config("Server").get("projects_path")

    with patch("gns3server.compute.project.Project.is_local", return_value=True):
        p = Project(project_id=str(uuid4()))
        assert p.node_working_directory(node) == os.path.join(directory, p.id, 'project-files', node.module_name, node.id)
        assert os.path.exists(p.node_working_directory(node))


def test_project_delete(loop):
    project = Project(project_id=str(uuid4()))
    directory = project.path
    assert os.path.exists(directory)
    loop.run_until_complete(asyncio.async(project.delete()))
    assert os.path.exists(directory) is False


def test_project_delete_permission_issue(loop):
    project = Project(project_id=str(uuid4()))
    directory = project.path
    assert os.path.exists(directory)
    os.chmod(directory, 0)
    with pytest.raises(aiohttp.web.HTTPInternalServerError):
        loop.run_until_complete(asyncio.async(project.delete()))
    os.chmod(directory, 700)


def test_project_add_node(manager):
    project = Project(project_id=str(uuid4()))
    node = VPCSVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", project, manager)
    project.add_node(node)
    assert len(project.nodes) == 1


def test_project_close(loop, node, project):

    with asyncio_patch("gns3server.compute.vpcs.vpcs_vm.VPCSVM.close") as mock:
        loop.run_until_complete(asyncio.async(project.close()))
        assert mock.called
    assert node.id not in node.manager._nodes


def test_list_files(tmpdir, loop):

    with patch("gns3server.config.Config.get_section_config", return_value={"projects_path": str(tmpdir)}):
        project = Project(project_id=str(uuid4()))
        path = project.path
        os.makedirs(os.path.join(path, "vm-1", "dynamips"))
        with open(os.path.join(path, "vm-1", "dynamips", "test.bin"), "w+") as f:
            f.write("test")
        open(os.path.join(path, "vm-1", "dynamips", "test.ghost"), "w+").close()
        with open(os.path.join(path, "test.txt"), "w+") as f:
            f.write("test2")

        files = loop.run_until_complete(asyncio.async(project.list_files()))

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


def test_emit(async_run):

    with NotificationManager.instance().queue() as queue:
        (action, event, context) = async_run(queue.get(0.5))  #  Ping

        project = Project(project_id=str(uuid4()))
        project.emit("test", {})
        (action, event, context) = async_run(queue.get(0.5))
        assert action == "test"
        assert context["project_id"] == project.id
