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

import pytest
import uuid
import asyncio
from unittest.mock import MagicMock


from tests.utils import AsyncioMagicMock

from gns3server.controller.node import Node
from gns3server.controller.project import Project


@pytest.fixture
def compute():
    s = AsyncioMagicMock()
    s.id = "http://test.com:42"
    return s


@pytest.fixture
def node(compute):
    project = Project(str(uuid.uuid4()))
    node = Node(project, compute,
                name="demo",
                node_id=str(uuid.uuid4()),
                node_type="vpcs",
                console_type="vnc",
                properties={"startup_script": "echo test"})
    return node


def test_json(node, compute):
    assert node.__json__() == {
        "compute_id": compute.id,
        "project_id": node.project.id,
        "node_id": node.id,
        "node_type": node.node_type,
        "name": "demo",
        "console": node.console,
        "console_type": node.console_type,
        "command_line": None,
        "node_directory": None,
        "properties": node.properties,
        "status": node.status
    }


def test_init_without_uuid(project, compute):
    node = Node(project, compute,
                node_type="vpcs",
                console_type="vnc")
    assert node.id is not None


def test_create(node, compute, project, async_run):
    node._console = 2048

    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    async_run(node.create())
    data = {
        "console": 2048,
        "console_type": "vnc",
        "node_id": node.id,
        "startup_script": "echo test",
        "name": "demo"
    }
    compute.post.assert_called_with("/projects/{}/vpcs/nodes".format(node.project.id), data=data)
    assert node._console == 2048
    assert node._properties == {"startup_script": "echo test"}


def test_update(node, compute, project, async_run):
    response = MagicMock()
    response.json = {"console": 2048}
    compute.put = AsyncioMagicMock(return_value=response)

    async_run(node.update(console=2048, console_type="vnc", properties={"startup_script": "echo test"}, name="demo"))
    data = {
        "console": 2048,
        "console_type": "vnc",
        "startup_script": "echo test",
        "name": "demo"
    }
    compute.put.assert_called_with("/projects/{}/vpcs/nodes/{}".format(node.project.id, node.id), data=data)
    assert node._console == 2048
    assert node._properties == {"startup_script": "echo test"}


def test_start(node, compute, project, async_run):

    compute.post = AsyncioMagicMock()

    async_run(node.start())
    compute.post.assert_called_with("/projects/{}/vpcs/nodes/{}/start".format(node.project.id, node.id))


def test_stop(node, compute, project, async_run):

    compute.post = AsyncioMagicMock()

    async_run(node.stop())
    compute.post.assert_called_with("/projects/{}/vpcs/nodes/{}/stop".format(node.project.id, node.id))


def test_suspend(node, compute, project, async_run):

    compute.post = AsyncioMagicMock()

    async_run(node.suspend())
    compute.post.assert_called_with("/projects/{}/vpcs/nodes/{}/suspend".format(node.project.id, node.id))


def test_reload(node, compute, project, async_run):

    compute.post = AsyncioMagicMock()

    async_run(node.reload())
    compute.post.assert_called_with("/projects/{}/vpcs/nodes/{}/reload".format(node.project.id, node.id))


def test_create_without_console(node, compute, project, async_run):
    """
    None properties should be send. Because it can mean the emulator doesn"t support it
    """

    response = MagicMock()
    response.json = {"console": 2048, "test_value": "success"}
    compute.post = AsyncioMagicMock(return_value=response)

    async_run(node.create())
    data = {
        "console_type": "vnc",
        "node_id": node.id,
        "startup_script": "echo test",
        "name": "demo"
    }
    compute.post.assert_called_with("/projects/{}/vpcs/nodes".format(node.project.id), data=data)
    assert node._console == 2048
    assert node._properties == {"test_value": "success", "startup_script": "echo test"}


def test_delete(node, compute, async_run):
    async_run(node.destroy())
    compute.delete.assert_called_with("/projects/{}/vpcs/nodes/{}".format(node.project.id, node.id))


def test_post(node, compute, async_run):
    async_run(node.post("/test", {"a": "b"}))
    compute.post.assert_called_with("/projects/{}/vpcs/nodes/{}/test".format(node.project.id, node.id), data={"a": "b"})


def test_delete(node, compute, async_run):
    async_run(node.delete("/test"))
    compute.delete.assert_called_with("/projects/{}/vpcs/nodes/{}/test".format(node.project.id, node.id))
