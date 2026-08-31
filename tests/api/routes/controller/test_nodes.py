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


import aiohttp
import logging

import pytest

from types import SimpleNamespace
from typing import List, Optional

from fastapi import FastAPI, HTTPException, WebSocketDisconnect, status
from httpx import AsyncClient
from pydantic import SecretStr

from unittest.mock import MagicMock
from tests.utils import AsyncioMagicMock

from gns3server.config import Config
from gns3server.controller.node import Node
from gns3server.controller.project import Project
from gns3server.controller.compute import Compute
from gns3server.utils.http_client import HTTPClient
from gns3server.api.routes.controller.nodes import ws_console, vnc_console

pytestmark = pytest.mark.asyncio


class TestNodeRoutes:
    

    @pytest.fixture
    def node(self, project: Project, compute: Compute) -> Node:
    
        node = Node(project, compute, "test", node_type="vpcs")
        project._nodes[node.id] = node
        return node
    
    
    async def test_create_node(self, app: FastAPI, client: AsyncClient, project: Project, compute: Compute) -> None:
    
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
    
    
    async def test_list_node(self, app: FastAPI, client: AsyncClient, project: Project, compute: Compute) -> None:
    
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
    
        # test listing nodes from a closed project
        await project.close(ignore_notification=True)
        response = await client.get(app.url_path_for("get_nodes", project_id=project.id))
        assert response.status_code == status.HTTP_200_OK
        assert response.json()[0]["name"] == "test"


    @pytest.mark.parametrize(
        "tags, expected_match",
        (
            ([], True),
            (["tag1"], True),
            (["tag1", "tag2"], True),
            (["tag42"], False),
            (["tag1", "tag3"], False),
        ),
    )
    async def test_list_nodes_with_tags(
            self,
            app: FastAPI,
            client: AsyncClient,
            project: Project,
            compute: Compute,
            tags: list,
            expected_match: bool
    ) -> None:
        response = MagicMock()
        response.json = {"console": 2048}
        compute.post = AsyncioMagicMock(return_value=response)

        await client.post(app.url_path_for("create_node", project_id=project.id), json={
            "name": "test",
            "node_type": "vpcs",
            "compute_id": "example.com",
            "tags": ["tag1", "tag2"],
            "properties": {
                "startup_script": "echo test"
            }
        })

        await client.post(app.url_path_for("create_node", project_id=project.id), json={
            "name": "test2",
            "node_type": "vpcs",
            "compute_id": "example.com",
            "tags": ["tag3", "tag4"],
            "properties": {
                "startup_script": "echo test"
            }
        })

        params = {"tags": tags}
        response = await client.get(app.url_path_for("get_nodes", project_id=project.id), params=params)
        assert response.status_code == status.HTTP_200_OK
        if expected_match:
            assert len(response.json()) > 0
        else:
            assert len(response.json()) == 0

    
    async def test_get_node(
            self,
            app: FastAPI,
            client: AsyncClient,
            project: Project,
            compute: Compute
    ) -> None:
    
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
    
    
    async def test_update_node(
            self,
            app: FastAPI,
            client: AsyncClient,
            project: Project,
            compute: Compute,
            node: Node
    ) -> None:
    
        response = MagicMock()
        response.json = {"console": 2048}
        compute.put = AsyncioMagicMock(return_value=response)
    
        response = await client.put(app.url_path_for("update_node", project_id=project.id, node_id=node.id), json={
            "name": "test",
            "node_type": "vpcs",
            "compute_id": "example.com",
            "tags": ["tag1", "tag2"],
            "properties": {
                    "startup_script": "echo test"
            }
        })
    
        assert response.status_code == 200
        assert response.json()["name"] == "test"
        assert "name" not in response.json()["properties"]
        assert response.json()["tags"] == ["tag1", "tag2"]


    async def test_start_all_nodes(
            self,
            app: FastAPI,
            client: AsyncClient,
            project: Project,
            compute: Compute
    ) -> None:
    
        compute.post = AsyncioMagicMock()
        response = await client.post(app.url_path_for("start_all_nodes", project_id=project.id))
        assert response.status_code == status.HTTP_204_NO_CONTENT
    
    
    async def test_stop_all_nodes(
            self,
            app: FastAPI,
            client: AsyncClient,
            project: Project,
            compute: Compute
    ) -> None:
    
        compute.post = AsyncioMagicMock()
        response = await client.post(app.url_path_for("stop_all_nodes", project_id=project.id))
        assert response.status_code == status.HTTP_204_NO_CONTENT
    
    
    async def test_suspend_all_nodes(
            self,
            app: FastAPI,
            client: AsyncClient,
            project: Project,
            compute: Compute
    ) -> None:
    
        compute.post = AsyncioMagicMock()
        response = await client.post(app.url_path_for("suspend_all_nodes", project_id=project.id))
        assert response.status_code == status.HTTP_204_NO_CONTENT
    
    
    async def test_reload_all_nodes(
            self,
            app: FastAPI,
            client: AsyncClient,
            project: Project,
            compute: Compute
    ) -> None:
    
        compute.post = AsyncioMagicMock()
        response = await client.post(app.url_path_for("reload_all_nodes", project_id=project.id))
        assert response.status_code == status.HTTP_204_NO_CONTENT
    
    
    async def test_reset_console_all_nodes(
            self,
            app: FastAPI,
            client: AsyncClient,
            project: Project,
            compute: Compute
    ) -> None:
    
        compute.post = AsyncioMagicMock()
        response = await client.post(app.url_path_for("reset_console_all_nodes", project_id=project.id))
        assert response.status_code == status.HTTP_204_NO_CONTENT
    
    
    async def test_start_node(
            self,
            app: FastAPI,
            client: AsyncClient,
            project: Project,
            compute: Compute,
            node: Node
    ) -> None:
    
        compute.post = AsyncioMagicMock()
        response = await client.post(app.url_path_for("start_node", project_id=project.id, node_id=node.id), json={})
        assert response.status_code == status.HTTP_204_NO_CONTENT
    
    
    async def test_stop_node(
            self,
            app: FastAPI,
            client: AsyncClient,
            project: Project,
            compute: Compute,
            node: Node
    ) -> None:
    
        compute.post = AsyncioMagicMock()
        response = await client.post(app.url_path_for("stop_node", project_id=project.id, node_id=node.id))
        assert response.status_code == status.HTTP_204_NO_CONTENT
    
    async def test_suspend_node(
            self,
            app: FastAPI,
            client: AsyncClient,
            project: Project,
            compute: Compute,
            node: Node
    ) -> None:

        compute.post = AsyncioMagicMock()
        response = await client.post(app.url_path_for("suspend_node", project_id=project.id, node_id=node.id))
        assert response.status_code == status.HTTP_204_NO_CONTENT

    async def test_suspend_node_unsupported(
            self,
            app: FastAPI,
            client: AsyncClient,
            project: Project,
            compute: Compute,
            node: Node
    ) -> None:

        # node types without suspend support (e.g. VPCS, IOU) must surface the
        # compute 405 instead of reporting a fake success
        compute.post = AsyncioMagicMock(
            side_effect=HTTPException(status_code=status.HTTP_405_METHOD_NOT_ALLOWED, detail="Suspend is not supported")
        )
        response = await client.post(app.url_path_for("suspend_node", project_id=project.id, node_id=node.id))
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    async def test_suspend_all_nodes_tolerates_unsupported(
            self,
            app: FastAPI,
            client: AsyncClient,
            project: Project,
            compute: Compute,
            node: Node
    ) -> None:

        # suspending all nodes of a mixed project stays best-effort: nodes
        # without suspend support are skipped without failing the request
        compute.post = AsyncioMagicMock(
            side_effect=HTTPException(status_code=status.HTTP_405_METHOD_NOT_ALLOWED, detail="Suspend is not supported")
        )
        response = await client.post(app.url_path_for("suspend_all_nodes", project_id=project.id))
        assert response.status_code == status.HTTP_204_NO_CONTENT
    
    
    async def test_reload_node(
            self,
            app: FastAPI,
            client: AsyncClient,
            project: Project,
            compute: Compute,
            node: Node
    ):
    
        compute.post = AsyncioMagicMock()
        response = await client.post(app.url_path_for("reload_node", project_id=project.id, node_id=node.id))
        assert response.status_code == status.HTTP_204_NO_CONTENT
    
    
    async def test_isolate_node(
            self,
            app: FastAPI,
            client: AsyncClient,
            project: Project,
            compute: Compute,
            node: Node
    ):
    
        compute.post = AsyncioMagicMock()
        response = await client.post(app.url_path_for("isolate_node", project_id=project.id, node_id=node.id))
        assert response.status_code == status.HTTP_204_NO_CONTENT
    
    
    async def test_unisolate_node(
            self,
            app: FastAPI,
            client: AsyncClient,
            project: Project,
            compute: Compute,
            node: Node
    ) -> None:
    
        compute.post = AsyncioMagicMock()
        response = await client.post(app.url_path_for("unisolate_node", project_id=project.id, node_id=node.id))
        assert response.status_code == status.HTTP_204_NO_CONTENT
    
    
    async def test_duplicate_node(
            self,
            app: FastAPI,
            client: AsyncClient,
            project: Project,
            compute: Compute,
            node: Node
    ) -> None:
    
        response = MagicMock()
        response.json({"console": 2035})
        compute.post = AsyncioMagicMock(return_value=response)
    
        response = await client.post(app.url_path_for("duplicate_node", project_id=project.id, node_id=node.id),
                                     json={"x": 10, "y": 5, "z": 0})
        assert response.status_code == status.HTTP_201_CREATED
    
    
    async def test_delete_node(
            self,
            app: FastAPI,
            client: AsyncClient,
            project: Project,
            compute: Compute,
            node: Node
    ) -> None:
    
        compute.post = AsyncioMagicMock()
        response = await client.delete(app.url_path_for("delete_node", project_id=project.id, node_id=node.id))
        assert response.status_code == status.HTTP_204_NO_CONTENT
    
    
    async def test_dynamips_idle_pc(
            self,
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
            self,
            app: FastAPI,
            client: AsyncClient,
            project: Project,
            compute: Compute,
            node: Node
    ) -> None:
    
        response = await client.get(app.url_path_for("auto_idlepc", project_id=project.id, node_id=node.id))
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    
    async def test_dynamips_idlepc_proposals(
            self,
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
            self,
            app: FastAPI,
            client: AsyncClient,
            project: Project,
            compute: Compute,
            node: Node
    ) -> None:
    
        response = await client.get(app.url_path_for("idlepc_proposals", project_id=project.id, node_id=node.id))
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    
    async def test_qemu_disk_image_create(
            self,
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
            self,
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
            self,
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
            self,
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
            self,
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
            self,
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
    
    
    async def test_get_file(
            self,
            app: FastAPI,
            client: AsyncClient,
            project: Project,
            compute: Compute,
            node: Node
    ) -> None:

        # Mock the streaming response
        async def mock_iter_chunked(chunk_size):
            yield b"world"

        mock_stream = AsyncioMagicMock()
        mock_stream.iter_chunked = mock_iter_chunked
        mock_stream.close = MagicMock()

        mock_response = AsyncioMagicMock()
        mock_response.status = status.HTTP_200_OK
        mock_response.content = mock_stream

        compute.http_query = AsyncioMagicMock(return_value=mock_response)

        response = await client.get(app.url_path_for("get_file", project_id=project.id, node_id=node.id, file_path="hello"))
        assert response.status_code == status.HTTP_200_OK
        assert response.content == b'world'

        compute.http_query.assert_called_with(
            "GET",
            "/projects/{project_id}/files/project-files/vpcs/{node_id}/hello".format(
                project_id=project.id,
                node_id=node.id),
            timeout=None,
            stream=True)

        response = await client.get(app.url_path_for(
            "get_file",
            project_id=project.id,
            node_id=node.id,
            file_path="../hello"))
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    
    async def test_post_file(
            self,
            app: FastAPI,
            client: AsyncClient,
            project: Project,
            compute: Compute,
            node: Node
    ) -> None:
    
        compute.http_query = AsyncioMagicMock()
        response = await client.post(app.url_path_for(
            "post_file",
            project_id=project.id,
            node_id=node.id,
            file_path="hello"), content=b"hello")
        assert response.status_code == status.HTTP_201_CREATED

        # Verify http_query was called with stream parameter
        compute.http_query.assert_called_once()
        call_args = compute.http_query.call_args
        assert call_args[0][0] == "POST"
        assert call_args[0][1] == "/projects/{project_id}/files/project-files/vpcs/{node_id}/hello".format(project_id=project.id, node_id=node.id)
        assert call_args[1]["timeout"] is None
        # data should be an async generator from request.stream()
        assert hasattr(call_args[1]["data"], "__aiter__")
    
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


class FakeComputeConsoleWebSocket:
    """
    Stand-in for the aiohttp ClientWebSocketResponse returned when connecting
    to the compute console WebSocket, yielding queued messages.
    """

    def __init__(self, messages: List[aiohttp.WSMessage]):

        self._messages = messages
        self.closed = False

    async def __aenter__(self) -> "FakeComputeConsoleWebSocket":

        return self

    async def __aexit__(self, *exc_info) -> bool:

        self.closed = True
        return False

    def __aiter__(self):

        return self._iterate_messages()

    async def _iterate_messages(self):

        for message in self._messages:
            yield message

    async def close(self) -> None:

        self.closed = True

    async def send_str(self, data: str) -> None:
        # client -> compute traffic, not exercised here
        pass

    async def send_bytes(self, data: bytes) -> None:
        pass


class FakeClientWebSocket:
    """
    Stand-in for the starlette WebSocket facing the client. When fail_after is
    set, raises WebSocketDisconnect once that many sends succeeded, mimicking
    uvicorn raising ClientDisconnected when the client is gone mid-stream.
    """

    def __init__(self, fail_after: Optional[int] = None):

        self.url = SimpleNamespace(scheme="http")
        self.client = SimpleNamespace(host="127.0.0.1", port=5000)
        self.sent: List[tuple] = []
        self._fail_after = fail_after

    async def receive(self) -> dict:

        # the client is already gone from the receive side
        return {"type": "websocket.disconnect"}

    async def receive_bytes(self) -> bytes:

        raise WebSocketDisconnect(code=1006)

    async def send_text(self, data: str) -> None:

        self._check_client_alive()
        self.sent.append(("text", data))

    async def send_bytes(self, data: bytes) -> None:

        self._check_client_alive()
        self.sent.append(("bytes", data))

    def _check_client_alive(self) -> None:

        if self._fail_after is not None and len(self.sent) >= self._fail_after:
            raise WebSocketDisconnect(code=1006)


class TestNodeConsoleWebSocketRoutes:
    """
    Exercise the console/VNC WebSocket forwarding handlers directly.

    The in-process ASGI WebSocket transport never raises on send once the
    client disconnected (unlike uvicorn's real WebSocket protocol), so client
    disconnects mid-stream are reproduced with a fake client WebSocket.
    """

    @pytest.fixture
    def node(self, project: Project, compute: Compute) -> Node:

        compute.host = "127.0.0.1"
        compute.port = 3080
        node = Node(project, compute, "test", node_type="vpcs")
        project._nodes[node.id] = node
        return node

    @pytest.fixture
    def compute_credentials(self) -> None:

        server_config = Config.instance().settings.Server
        server_config.compute_username = "admin"
        server_config.compute_password = SecretStr("password")

    @staticmethod
    def _forward_compute_ws(monkeypatch, messages: List[aiohttp.WSMessage]) -> FakeComputeConsoleWebSocket:

        compute_ws = FakeComputeConsoleWebSocket(messages)
        monkeypatch.setattr(
            HTTPClient,
            "get_client",
            classmethod(lambda cls: SimpleNamespace(ws_connect=lambda *args, **kwargs: compute_ws))
        )
        return compute_ws

    async def test_console_forwards_compute_output_to_client(
            self,
            compute_credentials,
            node: Node,
            monkeypatch
    ) -> None:

        compute_ws = self._forward_compute_ws(monkeypatch, [
            aiohttp.WSMessage(aiohttp.WSMsgType.TEXT, "device output", None),
            aiohttp.WSMessage(aiohttp.WSMsgType.BINARY, b"\x00\x01", None),
        ])
        websocket = FakeClientWebSocket()

        await ws_console(websocket, current_user=MagicMock(), node=node)

        assert websocket.sent == [("text", "device output"), ("bytes", b"\x00\x01")]
        assert compute_ws.closed

    async def test_console_client_disconnect_mid_stream(
            self,
            compute_credentials,
            node: Node,
            monkeypatch,
            caplog
    ) -> None:
        # regression test: the client disconnects while the compute is still
        # streaming console output, send must not leak WebSocketDisconnect
        compute_ws = self._forward_compute_ws(monkeypatch, [
            aiohttp.WSMessage(aiohttp.WSMsgType.TEXT, "line 1", None),
            aiohttp.WSMessage(aiohttp.WSMsgType.TEXT, "line 2", None),
            aiohttp.WSMessage(aiohttp.WSMsgType.TEXT, "line 3", None),
        ])
        websocket = FakeClientWebSocket(fail_after=1)

        with caplog.at_level(logging.INFO):
            await ws_console(websocket, current_user=MagicMock(), node=node)

        assert websocket.sent == [("text", "line 1")]
        assert compute_ws.closed
        assert any("has disconnected from controller console WebSocket" in record.message for record in caplog.records)

    async def test_vnc_console_client_disconnect_mid_stream(
            self,
            compute_credentials,
            node: Node,
            monkeypatch
    ) -> None:
        # regression test: same as above for the VNC console forwarding loop
        compute_ws = self._forward_compute_ws(monkeypatch, [
            aiohttp.WSMessage(aiohttp.WSMsgType.BINARY, b"\x01\x02", None),
            aiohttp.WSMessage(aiohttp.WSMsgType.BINARY, b"\x03\x04", None),
        ])
        websocket = FakeClientWebSocket(fail_after=0)

        await vnc_console(websocket, current_user=MagicMock(), node=node)

        assert websocket.sent == []
        assert compute_ws.closed
