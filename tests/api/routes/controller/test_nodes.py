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

from fastapi import FastAPI, status
from httpx import AsyncClient

from unittest.mock import MagicMock
from tests.utils import AsyncioMagicMock

from gns3server.controller.node import Node
from gns3server.controller.project import Project
from gns3server.controller.compute import Compute

pytestmark = pytest.mark.asyncio


@pytest.fixture
def node(project: Project, compute: Compute) -> Node:

    node = Node(project, compute, "test", node_type="vpcs")
    project._nodes[node.id] = node
    return node


async def test_create_node(app: FastAPI, client: AsyncClient, project: Project, compute: Compute) -> None:

    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    response = await client.post(app.url_path_for("create_node", project_id=project.id), json={
        "name": "test",
        "node_type": "vpcs",
        "compute_id": "example.com",
        "properties": {
                "startup_script": "echo test"
        }
    })

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["name"] == "test"
    assert "name" not in response.json()["properties"]


async def test_list_node(app: FastAPI, client: AsyncClient, project: Project, compute: Compute) -> None:

    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    await client.post(app.url_path_for("create_node", project_id=project.id), json={
        "name": "test",
        "node_type": "vpcs",
        "compute_id": "example.com",
        "properties": {
                "startup_script": "echo test"
        }
    })

    response = await client.get(app.url_path_for("get_nodes", project_id=project.id))
    assert response.status_code == status.HTTP_200_OK
    assert response.json()[0]["name"] == "test"


async def test_get_node(app: FastAPI, client: AsyncClient, project: Project, compute: Compute) -> None:

    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    response = await client.post(app.url_path_for("create_node", project_id=project.id), json={
        "name": "test",
        "node_type": "vpcs",
        "compute_id": "example.com",
        "properties": {
                "startup_script": "echo test"
        }
    })

    response = await client.get(app.url_path_for("get_node", project_id=project.id, node_id=response.json()["node_id"]))
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["name"] == "test"


async def test_update_node(app: FastAPI, client: AsyncClient, project: Project, compute: Compute, node: Node) -> None:

    response = MagicMock()
    response.json = {"console": 2048}
    compute.put = AsyncioMagicMock(return_value=response)

    response = await client.put(app.url_path_for("update_node", project_id=project.id, node_id=node.id), json={
        "name": "test",
        "node_type": "vpcs",
        "compute_id": "example.com",
        "properties": {
                "startup_script": "echo test"
        }
    })

    assert response.status_code == 200
    assert response.json()["name"] == "test"
    assert "name" not in response.json()["properties"]


async def test_start_all_nodes(app: FastAPI, client: AsyncClient, project: Project, compute: Compute) -> None:

    compute.post = AsyncioMagicMock()
    response = await client.post(app.url_path_for("start_all_nodes", project_id=project.id))
    assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_stop_all_nodes(app: FastAPI, client: AsyncClient, project: Project, compute: Compute) -> None:

    compute.post = AsyncioMagicMock()
    response = await client.post(app.url_path_for("stop_all_nodes", project_id=project.id))
    assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_suspend_all_nodes(app: FastAPI, client: AsyncClient, project: Project, compute: Compute) -> None:

    compute.post = AsyncioMagicMock()
    response = await client.post(app.url_path_for("suspend_all_nodes", project_id=project.id))
    assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_reload_all_nodes(app: FastAPI, client: AsyncClient, project: Project, compute: Compute) -> None:

    compute.post = AsyncioMagicMock()
    response = await client.post(app.url_path_for("reload_all_nodes", project_id=project.id))
    assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_reset_console_all_nodes(app: FastAPI, client: AsyncClient, project: Project, compute: Compute) -> None:

    compute.post = AsyncioMagicMock()
    response = await client.post(app.url_path_for("reset_console_all_nodes", project_id=project.id))
    assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_start_node(app: FastAPI, client: AsyncClient, project: Project, compute: Compute, node: Node) -> None:

    compute.post = AsyncioMagicMock()
    response = await client.post(app.url_path_for("start_node", project_id=project.id, node_id=node.id), json={})
    assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_stop_node(app: FastAPI, client: AsyncClient, project: Project, compute: Compute, node: Node) -> None:

    compute.post = AsyncioMagicMock()
    response = await client.post(app.url_path_for("stop_node", project_id=project.id, node_id=node.id))
    assert response.status_code == status.HTTP_204_NO_CONTENT

async def test_suspend_node(app: FastAPI, client: AsyncClient, project: Project, compute: Compute, node: Node) -> None:

    compute.post = AsyncioMagicMock()
    response = await client.post(app.url_path_for("suspend_node", project_id=project.id, node_id=node.id))
    assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_reload_node(app: FastAPI, client: AsyncClient, project: Project, compute: Compute, node: Node):

    compute.post = AsyncioMagicMock()
    response = await client.post(app.url_path_for("reload_node", project_id=project.id, node_id=node.id))
    assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_isolate_node(app: FastAPI, client: AsyncClient, project: Project, compute: Compute, node: Node):

    compute.post = AsyncioMagicMock()
    response = await client.post(app.url_path_for("isolate_node", project_id=project.id, node_id=node.id))
    assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_unisolate_node(app: FastAPI, client: AsyncClient, project: Project, compute: Compute, node: Node):

    compute.post = AsyncioMagicMock()
    response = await client.post(app.url_path_for("unisolate_node", project_id=project.id, node_id=node.id))
    assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_duplicate_node(
        app: FastAPI,
        client: AsyncClient,
        project: Project,
        compute: Compute,
        node: Node) -> None:

    response = MagicMock()
    response.json({"console": 2035})
    compute.post = AsyncioMagicMock(return_value=response)

    response = await client.post(app.url_path_for("duplicate_node", project_id=project.id, node_id=node.id),
                                 json={"x": 10, "y": 5, "z": 0})
    assert response.status_code == status.HTTP_201_CREATED


async def test_delete_node(app: FastAPI, client: AsyncClient, project: Project, compute: Compute, node: Node) -> None:

    compute.post = AsyncioMagicMock()
    response = await client.delete(app.url_path_for("delete_node", project_id=project.id, node_id=node.id))
    assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_dynamips_idle_pc(
        app: FastAPI,
        client: AsyncClient,
        project: Project,
        compute: Compute,
        node: Node
) -> None:

    response = MagicMock()
    response.json = {"idlepc": "0x60606f54"}
    compute.get = AsyncioMagicMock(return_value=response)

    node._node_type = "dynamips"  # force Dynamips node type
    response = await client.get(app.url_path_for("auto_idlepc", project_id=project.id, node_id=node.id))
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["idlepc"] == "0x60606f54"


async def test_dynamips_idle_pc_wrong_node_type(
        app: FastAPI,
        client: AsyncClient,
        project: Project,
        compute: Compute,
        node: Node
) -> None:

    response = await client.get(app.url_path_for("auto_idlepc", project_id=project.id, node_id=node.id))
    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_dynamips_idlepc_proposals(
        app: FastAPI,
        client: AsyncClient,
        project: Project,
        compute: Compute,
        node: Node
) -> None:

    response = MagicMock()
    response.json = ["0x60606f54", "0x33805a22"]
    compute.get = AsyncioMagicMock(return_value=response)

    node._node_type = "dynamips"  # force Dynamips node type
    response = await client.get(app.url_path_for("idlepc_proposals", project_id=project.id, node_id=node.id))
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == ["0x60606f54", "0x33805a22"]


async def test_dynamips_idlepc_proposals_wrong_node_type(
        app: FastAPI,
        client: AsyncClient,
        project: Project,
        compute: Compute,
        node: Node
) -> None:

    response = await client.get(app.url_path_for("idlepc_proposals", project_id=project.id, node_id=node.id))
    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_qemu_disk_image_create(
        app: FastAPI,
        client: AsyncClient,
        project: Project,
        compute: Compute,
        node: Node
) -> None:

    response = MagicMock()
    compute.post = AsyncioMagicMock(return_value=response)

    node._node_type = "qemu"  # force Qemu node type
    response = await client.post(
        app.url_path_for("create_disk_image", project_id=project.id, node_id=node.id, disk_name="hda_disk.qcow2"),
        json={"format": "qcow2", "size": 30}
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_qemu_disk_image_create_wrong_node_type(
        app: FastAPI,
        client: AsyncClient,
        project: Project,
        compute: Compute,
        node: Node
) -> None:

    response = await client.post(
        app.url_path_for("create_disk_image", project_id=project.id, node_id=node.id, disk_name="hda_disk.qcow2"),
        json={"format": "qcow2", "size": 30}
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_qemu_disk_image_update(
        app: FastAPI,
        client: AsyncClient,
        project: Project,
        compute: Compute,
        node: Node
) -> None:

    response = MagicMock()
    compute.put = AsyncioMagicMock(return_value=response)

    node._node_type = "qemu"  # force Qemu node type
    response = await client.put(
        app.url_path_for("update_disk_image", project_id=project.id, node_id=node.id, disk_name="hda_disk.qcow2"),
        json={"extend": 10}
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_qemu_disk_image_update_wrong_node_type(
        app: FastAPI,
        client: AsyncClient,
        project: Project,
        compute: Compute,
        node: Node
) -> None:

    response = await client.put(
        app.url_path_for("update_disk_image", project_id=project.id, node_id=node.id, disk_name="hda_disk.qcow2"),
        json={"extend": 10}
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_qemu_disk_image_delete(
        app: FastAPI,
        client: AsyncClient,
        project: Project,
        compute: Compute,
        node: Node
) -> None:

    response = MagicMock()
    compute.delete = AsyncioMagicMock(return_value=response)

    node._node_type = "qemu"  # force Qemu node type
    response = await client.delete(
        app.url_path_for("delete_disk_image", project_id=project.id, node_id=node.id, disk_name="hda_disk.qcow2")
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_qemu_disk_image_delete_wrong_node_type(
        app: FastAPI,
        client: AsyncClient,
        project: Project,
        compute: Compute,
        node: Node
) -> None:

    response = await client.delete(
        app.url_path_for("delete_disk_image", project_id=project.id, node_id=node.id, disk_name="hda_disk.qcow2")
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_get_file(app: FastAPI, client: AsyncClient, project: Project, compute: Compute, node: Node) -> None:

    response = MagicMock()
    response.body = b"world"
    response.status = status.HTTP_200_OK
    compute.http_query = AsyncioMagicMock(return_value=response)

    response = await client.get(app.url_path_for("get_file", project_id=project.id, node_id=node.id, file_path="hello"))
    assert response.status_code == status.HTTP_200_OK
    assert response.content == b'world'

    compute.http_query.assert_called_with(
        "GET",
        "/projects/{project_id}/files/project-files/vpcs/{node_id}/hello".format(
            project_id=project.id,
            node_id=node.id),
        timeout=None,
        raw=True)

    response = await client.get(app.url_path_for(
        "get_file",
        project_id=project.id,
        node_id=node.id,
        file_path="../hello"))
    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_post_file(app: FastAPI, client: AsyncClient, project: Project, compute: Compute, node: Node) -> None:

    compute.http_query = AsyncioMagicMock()
    response = await client.post(app.url_path_for(
        "post_file",
        project_id=project.id,
        node_id=node.id,
        file_path="hello"), content=b"hello")
    assert response.status_code == status.HTTP_201_CREATED

    compute.http_query.assert_called_with("POST", "/projects/{project_id}/files/project-files/vpcs/{node_id}/hello".format(project_id=project.id, node_id=node.id), data=b'hello', timeout=None, raw=True)

    response = await client.get("/projects/{project_id}/nodes/{node_id}/files/../hello".format(project_id=project.id, node_id=node.id))
    assert response.status_code == status.HTTP_404_NOT_FOUND


# @pytest.mark.asyncio
# async def test_get_and_post_with_nested_paths_normalization(controller_api, project, node, compute):
#
#     response = MagicMock()
#     response.body = b"world"
#     compute.http_query = AsyncioMagicMock(return_value=response)
#     response = await controller_api.get("/projects/{project_id}/nodes/{node_id}/files/hello\\nested".format(project_id=project.id, node_id=node.id))
#     assert response.status_code == 200
#     assert response.content == b'world'
#
#     compute.http_query.assert_called_with("GET", "/projects/{project_id}/files/project-files/vpcs/{node_id}/hello/nested".format(project_id=project.id, node_id=node.id), timeout=None, raw=True)
#
#     compute.http_query = AsyncioMagicMock()
#     response = await controller_api.post("/projects/{project_id}/nodes/{node_id}/files/hello\\nested".format(project_id=project.id, node_id=node.id), body=b"hello", raw=True)
#     assert response.status_code == 201
#
#     compute.http_query.assert_called_with("POST", "/projects/{project_id}/files/project-files/vpcs/{node_id}/hello/nested".format(project_id=project.id, node_id=node.id), data=b'hello', timeout=None, raw=True)
