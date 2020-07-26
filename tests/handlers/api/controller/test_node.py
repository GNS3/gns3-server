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

import sys
import pytest

from unittest.mock import MagicMock
from tests.utils import AsyncioMagicMock

from gns3server.controller.node import Node


@pytest.fixture
def node(project, compute):

    node = Node(project, compute, "test", node_type="vpcs")
    project._nodes[node.id] = node
    return node


async def test_create_node(controller_api, project, compute):

    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    response = await controller_api.post("/projects/{}/nodes".format(project.id), {
        "name": "test",
        "node_type": "vpcs",
        "compute_id": "example.com",
        "properties": {
                "startup_script": "echo test"
        }
    })

    assert response.status == 201
    assert response.json["name"] == "test"
    assert "name" not in response.json["properties"]


async def test_list_node(controller_api, project, compute):

    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    await controller_api.post("/projects/{}/nodes".format(project.id), {
        "name": "test",
        "node_type": "vpcs",
        "compute_id": "example.com",
        "properties": {
                "startup_script": "echo test"
        }
    })

    response = await controller_api.get("/projects/{}/nodes".format(project.id))
    assert response.status == 200
    assert response.json[0]["name"] == "test"


async def test_get_node(controller_api, project, compute):

    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    response = await controller_api.post("/projects/{}/nodes".format(project.id), {
        "name": "test",
        "node_type": "vpcs",
        "compute_id": "example.com",
        "properties": {
                "startup_script": "echo test"
        }
    })

    response = await controller_api.get("/projects/{}/nodes/{}".format(project.id, response.json["node_id"]))
    assert response.status == 200
    assert response.json["name"] == "test"


async def test_update_node(controller_api, project, compute, node):

    response = MagicMock()
    response.json = {"console": 2048}
    compute.put = AsyncioMagicMock(return_value=response)

    response = await controller_api.put("/projects/{}/nodes/{}".format(project.id, node.id), {
        "name": "test",
        "node_type": "vpcs",
        "compute_id": "example.com",
        "properties": {
                "startup_script": "echo test"
        }
    })

    assert response.status == 200
    assert response.json["name"] == "test"
    assert "name" not in response.json["properties"]


async def test_start_all_nodes(controller_api, project, compute):

    compute.post = AsyncioMagicMock()
    response = await controller_api.post("/projects/{}/nodes/start".format(project.id))
    assert response.status == 204


async def test_stop_all_nodes(controller_api, project, compute):

    compute.post = AsyncioMagicMock()
    response = await controller_api.post("/projects/{}/nodes/stop".format(project.id))
    assert response.status == 204


async def test_suspend_all_nodes(controller_api, project, compute):

    compute.post = AsyncioMagicMock()
    response = await controller_api.post("/projects/{}/nodes/suspend".format(project.id))
    assert response.status == 204


async def test_reload_all_nodes(controller_api, project, compute):

    compute.post = AsyncioMagicMock()
    response = await controller_api.post("/projects/{}/nodes/reload".format(project.id))
    assert response.status == 204


async def test_reset_console_all_nodes(controller_api, project, compute):

    compute.post = AsyncioMagicMock()
    response = await controller_api.post("/projects/{}/nodes/console/reset".format(project.id))
    assert response.status == 204


async def test_start_node(controller_api, project, node, compute):

    compute.post = AsyncioMagicMock()
    response = await controller_api.post("/projects/{}/nodes/{}/start".format(project.id, node.id))
    assert response.status == 200
    assert response.json == node.__json__()


async def test_stop_node(controller_api, project, node, compute):

    compute.post = AsyncioMagicMock()
    response = await controller_api.post("/projects/{}/nodes/{}/stop".format(project.id, node.id))
    assert response.status == 200
    assert response.json == node.__json__()


async def test_suspend_node(controller_api, project, node, compute):

    compute.post = AsyncioMagicMock()
    response = await controller_api.post("/projects/{}/nodes/{}/suspend".format(project.id, node.id))
    assert response.status == 200
    assert response.json == node.__json__()


async def test_reload_node(controller_api, project, node, compute):

    compute.post = AsyncioMagicMock()
    response = await controller_api.post("/projects/{}/nodes/{}/reload".format(project.id, node.id))
    assert response.status == 200
    assert response.json == node.__json__()


async def test_duplicate_node(controller_api, project, compute, node):

    response = MagicMock()
    response.json({"console": 2035})
    compute.post = AsyncioMagicMock(return_value=response)

    response = await controller_api.post("/projects/{}/nodes/{}/duplicate".format(project.id, node.id),
                                         {"x": 10,
                                          "y": 5,
                                          "z": 0})
    assert response.status == 201, response.body.decode()


async def test_delete_node(controller_api, project, node, compute):

    compute.post = AsyncioMagicMock()
    response = await controller_api.delete("/projects/{}/nodes/{}".format(project.id, node.id))
    assert response.status == 204


async def test_dynamips_idle_pc(controller_api, project, compute, node):

    response = MagicMock()
    response.json = {"idlepc": "0x60606f54"}
    compute.get = AsyncioMagicMock(return_value=response)

    response = await controller_api.get("/projects/{}/nodes/{}/dynamips/auto_idlepc".format(project.id, node.id))
    assert response.status == 200
    assert response.json["idlepc"] == "0x60606f54"


async def test_dynamips_idlepc_proposals(controller_api, project, compute, node):

    response = MagicMock()
    response.json = ["0x60606f54", "0x33805a22"]
    compute.get = AsyncioMagicMock(return_value=response)

    response = await controller_api.get("/projects/{}/nodes/{}/dynamips/idlepc_proposals".format(project.id, node.id))
    assert response.status == 200
    assert response.json == ["0x60606f54", "0x33805a22"]


async def test_get_file(controller_api, project, node, compute):

    response = MagicMock()
    response.body = b"world"
    response.status = 200
    compute.http_query = AsyncioMagicMock(return_value=response)

    response = await controller_api.get("/projects/{project_id}/nodes/{node_id}/files/hello".format(project_id=project.id, node_id=node.id))
    assert response.status == 200
    assert response.body == b'world'

    compute.http_query.assert_called_with("GET", "/projects/{project_id}/files/project-files/vpcs/{node_id}/hello".format(project_id=project.id, node_id=node.id), timeout=None, raw=True)

    response = await controller_api.get("/projects/{project_id}/nodes/{node_id}/files/../hello".format(project_id=project.id, node_id=node.id))
    assert response.status == 404


async def test_post_file(controller_api, project, node, compute):

    response = MagicMock()
    response.status = 201
    compute.http_query = AsyncioMagicMock(return_value=response)
    response = await controller_api.post("/projects/{project_id}/nodes/{node_id}/files/hello".format(project_id=project.id, node_id=node.id), body=b"hello", raw=True)
    assert response.status == 201

    compute.http_query.assert_called_with("POST", "/projects/{project_id}/files/project-files/vpcs/{node_id}/hello".format(project_id=project.id, node_id=node.id), data=b'hello', timeout=None, raw=True)

    response = await controller_api.get("/projects/{project_id}/nodes/{node_id}/files/../hello".format(project_id=project.id, node_id=node.id))
    assert response.status == 404


@pytest.mark.skipif(sys.platform.startswith("win"), reason="Does not work on Windows")
async def test_get_and_post_with_nested_paths_normalization(controller_api, project, node, compute):

    response = MagicMock()
    response.body = b"world"
    response.status = 200
    compute.http_query = AsyncioMagicMock(return_value=response)
    response = await controller_api.get("/projects/{project_id}/nodes/{node_id}/files/hello\\nested".format(project_id=project.id, node_id=node.id))
    assert response.status == 200
    assert response.body == b'world'

    compute.http_query.assert_called_with("GET", "/projects/{project_id}/files/project-files/vpcs/{node_id}/hello/nested".format(project_id=project.id, node_id=node.id), timeout=None, raw=True)

    response = MagicMock()
    response.status = 201
    compute.http_query = AsyncioMagicMock(return_value=response)
    response = await controller_api.post("/projects/{project_id}/nodes/{node_id}/files/hello\\nested".format(project_id=project.id, node_id=node.id), body=b"hello", raw=True)
    assert response.status == 201

    compute.http_query.assert_called_with("POST", "/projects/{project_id}/files/project-files/vpcs/{node_id}/hello/nested".format(project_id=project.id, node_id=node.id), data=b'hello', timeout=None, raw=True)
