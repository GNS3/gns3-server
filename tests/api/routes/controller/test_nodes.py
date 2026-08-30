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


import asyncio
import contextlib
import logging

import aiohttp
import pytest

from fastapi import FastAPI, HTTPException, status
from httpx import AsyncClient
from httpx_ws import aconnect_ws, WebSocketDisconnect
from httpx_ws.transport import ASGIWebSocketTransport, ASGIWebSocketAsyncNetworkStream

from unittest.mock import MagicMock, patch
from tests.utils import AsyncioMagicMock

from gns3server.controller.node import Node
from gns3server.controller.project import Project
from gns3server.controller.compute import Compute
from gns3server.services import auth_service
from gns3server.services.authentication import DEFAULT_JWT_SECRET_KEY

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


class _FakeComputeWebSocket:
    """
    Mimics the aiohttp client WebSocket the controller forwards console traffic to.

    Pass a list of WSMessage to emulate a compute that sends data then closes the
    session, or None to emulate a busy console streaming binary frames forever
    (until the controller cancels the forwarding task).
    """

    def __init__(self, messages=None) -> None:
        self._messages = messages
        self.sent = []  # frames received from the client
        self.closed = False
        self.stream_cancelled = False

    async def send_str(self, data: str) -> None:
        self.sent.append(("text", data))

    async def send_bytes(self, data: bytes) -> None:
        self.sent.append(("bytes", data))

    async def close(self) -> None:
        self.closed = True

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._messages is not None:
            if not self._messages:
                raise StopAsyncIteration
            return self._messages.pop(0)
        try:
            await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            self.stream_cancelled = True
            raise
        return aiohttp.WSMessage(aiohttp.WSMsgType.BINARY, b"console output", "")


class _FakeComputeWebSocketContext:
    """Async context manager mimicking the object returned by aiohttp ws_connect()."""

    def __init__(self, websocket: _FakeComputeWebSocket) -> None:
        self._websocket = websocket

    async def __aenter__(self) -> _FakeComputeWebSocket:
        return self._websocket

    async def __aexit__(self, *exc_info) -> bool:
        await self._websocket.close()
        return False


# The in-memory ASGI WebSocket transport notifies the app of a client close with a
# non-conformant "websocket.close" message, which starlette's receive() rejects.
# Patch it to deliver "websocket.disconnect" like a real ASGI server (uvicorn) does.
_original_stream_send = ASGIWebSocketAsyncNetworkStream.send


async def _conforming_stream_send(self, message):
    if message.get("type") == "websocket.close":
        message = {"type": "websocket.disconnect", "code": message.get("code") or 1000}
    await _original_stream_send(self, message)


class TestConsoleWebSocketRoutes:
    """
    The controller console WebSocket endpoints forward data in both directions and
    must tear down cleanly when either side goes away, instead of letting a
    WebSocketDisconnect escape as an ASGI error.
    """

    @pytest.fixture
    def node(self, project: Project, compute: Compute) -> Node:

        node = Node(project, compute, "test", node_type="qemu")
        project._nodes[node.id] = node
        return node

    @staticmethod
    def _patches(fake_ws: _FakeComputeWebSocket):
        """
        Make HTTPClient.get_client().ws_connect() yield the fake compute WebSocket,
        and make the in-memory transport deliver a conformant disconnect message.
        """

        stack = contextlib.ExitStack()
        http_client = MagicMock()
        http_client.ws_connect = MagicMock(return_value=_FakeComputeWebSocketContext(fake_ws))
        stack.enter_context(patch(
            "gns3server.api.routes.controller.nodes.HTTPClient.get_client",
            return_value=http_client
        ))
        stack.enter_context(patch.object(ASGIWebSocketAsyncNetworkStream, "send", _conforming_stream_send))
        return stack

    @staticmethod
    def _admin_token() -> str:

        return auth_service.create_access_token("admin", secret_key=DEFAULT_JWT_SECRET_KEY)

    @staticmethod
    async def _wait_for_teardown(fake_ws: _FakeComputeWebSocket) -> None:
        # the handler keeps running on the event loop after the client is gone
        for _ in range(100):
            if fake_ws.closed:
                await asyncio.sleep(0.1)  # give cancelled tasks a chance to finish
                return
            await asyncio.sleep(0.05)

    async def test_console_ws_client_disconnect(
            self,
            app: FastAPI,
            client: AsyncClient,
            project: Project,
            compute: Compute,
            node: Node,
            caplog
    ) -> None:
        """
        A client disconnecting while the compute keeps streaming console output
        must not raise: the forwarding tasks are cancelled and the compute
        console WebSocket is closed.
        """

        fake_ws = _FakeComputeWebSocket(messages=None)
        with self._patches(fake_ws), caplog.at_level(logging.INFO):
            async with AsyncClient(base_url="http://test-api", transport=ASGIWebSocketTransport(app=app)) as ws_client:
                async with aconnect_ws(
                    app.url_path_for("ws_console", project_id=project.id, node_id=node.id),
                    ws_client,
                    params={"token": self._admin_token()},
                ) as ws:
                    # compute -> client
                    assert await ws.receive_bytes() == b"console output"
                    # client -> compute
                    await ws.send_text("dir")
                    await ws.send_bytes(b"\x01\x02")
            await self._wait_for_teardown(fake_ws)

        assert fake_ws.sent == [("text", "dir"), ("bytes", b"\x01\x02")]
        assert fake_ws.stream_cancelled, "the compute -> client forwarding task should have been cancelled"
        assert fake_ws.closed, "the compute console WebSocket should have been closed"
        assert any(
            "has disconnected from controller console WebSocket" in record.getMessage()
            for record in caplog.records
        )

    async def test_console_ws_compute_closes_session(
            self,
            app: FastAPI,
            client: AsyncClient,
            project: Project,
            compute: Compute,
            node: Node
    ) -> None:
        """
        When the compute closes the console WebSocket the client should receive
        the frames sent before the close, then the close itself.
        """

        fake_ws = _FakeComputeWebSocket(messages=[
            aiohttp.WSMessage(aiohttp.WSMsgType.BINARY, b"output", ""),
            aiohttp.WSMessage(aiohttp.WSMsgType.TEXT, "done", ""),
        ])
        with self._patches(fake_ws):
            async with AsyncClient(base_url="http://test-api", transport=ASGIWebSocketTransport(app=app)) as ws_client:
                async with aconnect_ws(
                    app.url_path_for("ws_console", project_id=project.id, node_id=node.id),
                    ws_client,
                    params={"token": self._admin_token()},
                ) as ws:
                    assert await ws.receive_bytes() == b"output"
                    assert await ws.receive_text() == "done"
                    with pytest.raises(WebSocketDisconnect):
                        await ws.receive_bytes()

        assert fake_ws.closed

    async def test_vnc_console_ws_client_disconnect(
            self,
            app: FastAPI,
            client: AsyncClient,
            project: Project,
            compute: Compute,
            node: Node,
            caplog
    ) -> None:
        """
        Same as the console test, for the VNC endpoint (binary frames only).
        """

        fake_ws = _FakeComputeWebSocket(messages=None)
        with self._patches(fake_ws), caplog.at_level(logging.INFO):
            async with AsyncClient(base_url="http://test-api", transport=ASGIWebSocketTransport(app=app)) as ws_client:
                async with aconnect_ws(
                    app.url_path_for("vnc_console", project_id=project.id, node_id=node.id),
                    ws_client,
                    params={"token": self._admin_token()},
                ) as ws:
                    assert await ws.receive_bytes() == b"console output"
                    await ws.send_bytes(b"\x01\x02")
            await self._wait_for_teardown(fake_ws)

        assert fake_ws.sent == [("bytes", b"\x01\x02")]
        assert fake_ws.stream_cancelled, "the compute -> client forwarding task should have been cancelled"
        assert fake_ws.closed, "the compute VNC console WebSocket should have been closed"
        assert any(
            "has disconnected from controller VNC console WebSocket" in record.getMessage()
            for record in caplog.records
        )
