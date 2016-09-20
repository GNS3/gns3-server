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

"""
This test suite check /project endpoint
"""

import uuid
import os
import asyncio
import aiohttp
import pytest


from unittest.mock import patch, MagicMock
from tests.utils import asyncio_patch, AsyncioMagicMock

from gns3server.handlers.api.controller.project_handler import ProjectHandler
from gns3server.controller import Controller
from gns3server.controller.node import Node


@pytest.fixture
def compute(http_controller, async_run):
    compute = MagicMock()
    compute.id = "example.com"
    compute.host = "example.org"
    Controller.instance()._computes = {"example.com": compute}
    return compute


@pytest.fixture
def project(http_controller, async_run):
    return async_run(Controller.instance().add_project(name="Test"))


@pytest.fixture
def node(project, compute, async_run):
    node = Node(project, compute, "test", node_type="vpcs")
    project._nodes[node.id] = node
    return node


def test_create_node(http_controller, tmpdir, project, compute):
    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    response = http_controller.post("/projects/{}/nodes".format(project.id), {
        "name": "test",
        "node_type": "vpcs",
        "compute_id": "example.com",
        "properties": {
                "startup_script": "echo test"
        }
    }, example=True)
    assert response.status == 201
    assert response.json["name"] == "test"
    assert "name" not in response.json["properties"]


def test_list_node(http_controller, tmpdir, project, compute):
    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    response = http_controller.post("/projects/{}/nodes".format(project.id), {
        "name": "test",
        "node_type": "vpcs",
        "compute_id": "example.com",
        "properties": {
                "startup_script": "echo test"
        }
    })
    response = http_controller.get("/projects/{}/nodes".format(project.id), example=True)
    assert response.status == 200
    assert response.json[0]["name"] == "test"


def test_get_node(http_controller, tmpdir, project, compute):
    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    response = http_controller.post("/projects/{}/nodes".format(project.id), {
        "name": "test",
        "node_type": "vpcs",
        "compute_id": "example.com",
        "properties": {
                "startup_script": "echo test"
        }
    })
    response = http_controller.get("/projects/{}/nodes/{}".format(project.id, response.json["node_id"]), example=True)
    assert response.status == 200
    assert response.json["name"] == "test"


def test_update_node(http_controller, tmpdir, project, compute, node):
    response = MagicMock()
    response.json = {"console": 2048}
    compute.put = AsyncioMagicMock(return_value=response)

    response = http_controller.put("/projects/{}/nodes/{}".format(project.id, node.id), {
        "name": "test",
        "node_type": "vpcs",
        "compute_id": "example.com",
        "properties": {
                "startup_script": "echo test"
        }
    }, example=True)
    assert response.status == 200
    assert response.json["name"] == "test"
    assert "name" not in response.json["properties"]


def test_start_all_nodes(http_controller, tmpdir, project, compute):
    response = MagicMock()
    compute.post = AsyncioMagicMock()

    response = http_controller.post("/projects/{}/nodes/start".format(project.id), example=True)
    assert response.status == 204


def test_stop_all_nodes(http_controller, tmpdir, project, compute):
    response = MagicMock()
    compute.post = AsyncioMagicMock()

    response = http_controller.post("/projects/{}/nodes/stop".format(project.id), example=True)
    assert response.status == 204


def test_suspend_all_nodes(http_controller, tmpdir, project, compute):
    response = MagicMock()
    compute.post = AsyncioMagicMock()

    response = http_controller.post("/projects/{}/nodes/suspend".format(project.id), example=True)
    assert response.status == 204


def test_reload_all_nodes(http_controller, tmpdir, project, compute):
    response = MagicMock()
    compute.post = AsyncioMagicMock()

    response = http_controller.post("/projects/{}/nodes/reload".format(project.id), example=True)
    assert response.status == 204


def test_start_node(http_controller, tmpdir, project, compute, node):
    response = MagicMock()
    compute.post = AsyncioMagicMock()

    response = http_controller.post("/projects/{}/nodes/{}/start".format(project.id, node.id), example=True)
    assert response.status == 201
    assert response.json == node.__json__()


def test_stop_node(http_controller, tmpdir, project, compute, node):
    response = MagicMock()
    compute.post = AsyncioMagicMock()

    response = http_controller.post("/projects/{}/nodes/{}/stop".format(project.id, node.id), example=True)
    assert response.status == 201
    assert response.json == node.__json__()


def test_suspend_node(http_controller, tmpdir, project, compute, node):
    response = MagicMock()
    compute.post = AsyncioMagicMock()

    response = http_controller.post("/projects/{}/nodes/{}/suspend".format(project.id, node.id), example=True)
    assert response.status == 201
    assert response.json == node.__json__()


def test_reload_node(http_controller, tmpdir, project, compute, node):
    response = MagicMock()
    compute.post = AsyncioMagicMock()

    response = http_controller.post("/projects/{}/nodes/{}/reload".format(project.id, node.id), example=True)
    assert response.status == 201
    assert response.json == node.__json__()


def test_delete_node(http_controller, tmpdir, project, compute, node):
    response = MagicMock()
    compute.post = AsyncioMagicMock()

    response = http_controller.delete("/projects/{}/nodes/{}".format(project.id, node.id), example=True)
    assert response.status == 204


def test_dynamips_idle_pc(http_controller, tmpdir, project, compute, node):
    response = MagicMock()
    response.json = {"idlepc": "0x60606f54"}
    compute.get = AsyncioMagicMock(return_value=response)

    response = http_controller.get("/projects/{}/nodes/{}/dynamips/auto_idlepc".format(project.id, node.id), example=True)
    assert response.status == 200
    assert response.json["idlepc"] == "0x60606f54"


def test_dynamips_idlepc_proposals(http_controller, tmpdir, project, compute, node):
    response = MagicMock()
    response.json = ["0x60606f54", "0x33805a22"]
    compute.get = AsyncioMagicMock(return_value=response)

    response = http_controller.get("/projects/{}/nodes/{}/dynamips/idlepc_proposals".format(project.id, node.id), example=True)
    assert response.status == 200
    assert response.json == ["0x60606f54", "0x33805a22"]


def test_get_file(http_controller, tmpdir, project, node, compute):
    response = MagicMock()
    response.body = b"world"
    compute.http_query = AsyncioMagicMock(return_value=response)
    response = http_controller.get("/projects/{project_id}/nodes/{node_id}/files/hello".format(project_id=project.id, node_id=node.id), raw=True)
    assert response.status == 200
    assert response.body == b'world'

    compute.http_query.assert_called_with("GET", "/projects/{project_id}/files/project-files/vpcs/{node_id}/hello".format(project_id=project.id, node_id=node.id), timeout=None, raw=True)

    response = http_controller.get("/projects/{project_id}/nodes/{node_id}/files/../hello".format(project_id=project.id, node_id=node.id), raw=True)
    assert response.status == 403


def test_post_file(http_controller, tmpdir, project, node, compute):
    compute.http_query = AsyncioMagicMock()
    response = http_controller.post("/projects/{project_id}/nodes/{node_id}/files/hello".format(project_id=project.id, node_id=node.id), body=b"hello", raw=True)
    assert response.status == 201

    compute.http_query.assert_called_with("POST", "/projects/{project_id}/files/project-files/vpcs/{node_id}/hello".format(project_id=project.id, node_id=node.id), data=b'hello', timeout=None, raw=True)

    response = http_controller.get("/projects/{project_id}/nodes/{node_id}/files/../hello".format(project_id=project.id, node_id=node.id), raw=True)
    assert response.status == 403
