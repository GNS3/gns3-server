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
import pytest
import aiohttp
from unittest.mock import MagicMock
from tests.utils import AsyncioMagicMock
from unittest.mock import patch
from uuid import uuid4

from gns3server.controller.project import Project
from gns3server.config import Config


@pytest.fixture
def project(controller):
    return Project(controller=controller)


def test_affect_uuid():
    p = Project()
    assert len(p.id) == 36

    p = Project(project_id='00010203-0405-0607-0809-0a0b0c0d0e0f')
    assert p.id == '00010203-0405-0607-0809-0a0b0c0d0e0f'


def test_json(tmpdir):
    p = Project()
    assert p.__json__() == {"name": p.name, "project_id": p.id, "path": p.path, "status": "opened"}


def test_path(tmpdir):

    directory = Config.instance().get_section_config("Server").get("projects_path")

    with patch("gns3server.utils.path.get_default_project_directory", return_value=directory):
        p = Project(project_id=str(uuid4()))
        assert p.path == os.path.join(directory, p.id)
        assert os.path.exists(os.path.join(directory, p.id))


def test_init_path(tmpdir):

    p = Project(path=str(tmpdir), project_id=str(uuid4()))
    assert p.path == str(tmpdir)


def test_changing_path_with_quote_not_allowed(tmpdir):
    with pytest.raises(aiohttp.web.HTTPForbidden):
        p = Project(project_id=str(uuid4()))
        p.path = str(tmpdir / "project\"53")


def test_captures_directory(tmpdir):
    p = Project(path=str(tmpdir))
    assert p.captures_directory == str(tmpdir / "project-files" / "captures")
    assert os.path.exists(p.captures_directory)


def test_add_node_local(async_run, controller):
    """
    For a local server we send the project path
    """
    compute = MagicMock()
    compute.id = "local"
    project = Project(controller=controller)
    controller._notification = MagicMock()

    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    node = async_run(project.add_node(compute, "test", None, node_type="vpcs", properties={"startup_config": "test.cfg"}))
    assert node.id in project._nodes

    compute.post.assert_any_call('/projects', data={
        "name": project._name,
        "project_id": project._id,
        "path": project._path
    })
    compute.post.assert_any_call('/projects/{}/vpcs/nodes'.format(project.id),
                                 data={'node_id': node.id,
                                       'startup_config': 'test.cfg',
                                       'name': 'test'})
    assert compute in project._project_created_on_compute
    controller.notification.emit.assert_any_call("node.created", node.__json__())


def test_add_node_non_local(async_run, controller):
    """
    For a non local server we do not send the project path
    """
    compute = MagicMock()
    compute.id = "remote"
    project = Project(controller=controller)
    controller._notification = MagicMock()

    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    node = async_run(project.add_node(compute, "test", None, node_type="vpcs", properties={"startup_config": "test.cfg"}))

    compute.post.assert_any_call('/projects', data={
        "name": project._name,
        "project_id": project._id
    })
    compute.post.assert_any_call('/projects/{}/vpcs/nodes'.format(project.id),
                                 data={'node_id': node.id,
                                       'startup_config': 'test.cfg',
                                       'name': 'test'})
    assert compute in project._project_created_on_compute
    controller.notification.emit.assert_any_call("node.created", node.__json__())


def test_delete_node(async_run, controller):
    """
    For a local server we send the project path
    """
    compute = MagicMock()
    project = Project(controller=controller)
    controller._notification = MagicMock()

    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    node = async_run(project.add_node(compute, "test", None, node_type="vpcs", properties={"startup_config": "test.cfg"}))
    assert node.id in project._nodes
    async_run(project.delete_node(node.id))
    assert node.id not in project._nodes

    compute.delete.assert_any_call('/projects/{}/vpcs/nodes/{}'.format(project.id, node.id))
    controller.notification.emit.assert_any_call("node.deleted", node.__json__())


def test_getVM(async_run, controller):
    compute = MagicMock()
    project = Project(controller=controller)

    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    vm = async_run(project.add_node(compute, "test", None, node_type="vpcs", properties={"startup_config": "test.cfg"}))
    assert project.get_node(vm.id) == vm

    with pytest.raises(aiohttp.web_exceptions.HTTPNotFound):
        project.get_node("test")


def test_addLink(async_run, project, controller):
    compute = MagicMock()

    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    vm1 = async_run(project.add_node(compute, "test1", None, node_type="vpcs", properties={"startup_config": "test.cfg"}))
    vm2 = async_run(project.add_node(compute, "test2", None, node_type="vpcs", properties={"startup_config": "test.cfg"}))
    controller._notification = MagicMock()
    link = async_run(project.add_link())
    async_run(link.add_node(vm1, 3, 1))
    async_run(link.add_node(vm2, 4, 2))
    assert len(link._nodes) == 2
    controller.notification.emit.assert_any_call("link.created", link.__json__())


def test_getLink(async_run, project):
    compute = MagicMock()

    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    link = async_run(project.add_link())
    assert project.get_link(link.id) == link

    with pytest.raises(aiohttp.web_exceptions.HTTPNotFound):
        project.get_link("test")


def test_deleteLink(async_run, project, controller):
    compute = MagicMock()

    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    assert len(project._links) == 0
    link = async_run(project.add_link())
    assert len(project._links) == 1
    controller._notification = MagicMock()
    async_run(project.delete_link(link.id))
    controller.notification.emit.assert_any_call("link.deleted", link.__json__())
    assert len(project._links) == 0


def test_delete(async_run, project, controller):
    assert os.path.exists(project.path)
    async_run(project.delete())
    assert not os.path.exists(project.path)


def test_dump():
    directory = Config.instance().get_section_config("Server").get("projects_path")

    with patch("gns3server.utils.path.get_default_project_directory", return_value=directory):
        p = Project(project_id='00010203-0405-0607-0809-0a0b0c0d0e0f', name="Test")
        p.dump()
        with open(os.path.join(directory, p.id, "Test.gns3")) as f:
            content = f.read()
            assert "00010203-0405-0607-0809-0a0b0c0d0e0f" in content


def test_open_close(async_run, controller):
    project = Project(controller=controller, status="closed")
    assert project.status == "closed"
    async_run(project.open())
    assert project.status == "opened"
    async_run(project.close())
    assert project.status == "closed"
