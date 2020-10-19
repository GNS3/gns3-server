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

"""
API endpoints for nodes.
"""

import aiohttp
import asyncio

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, Request, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.routing import APIRoute
from typing import List, Callable
from uuid import UUID

from gns3server.controller import Controller
from gns3server.controller.node import Node
from gns3server.controller.project import Project
from gns3server.utils import force_unix_path
from gns3server.controller.controller_error import ControllerForbiddenError
from gns3server.endpoints.schemas.common import ErrorMessage
from gns3server.endpoints import schemas

import logging
log = logging.getLogger(__name__)

node_locks = {}


class NodeConcurrency(APIRoute):
    """
    To avoid strange effects, we prevent concurrency
    between the same instance of the node
    (excepting when streaming a PCAP file and for WebSocket consoles).
    """

    def get_route_handler(self) -> Callable:
        original_route_handler = super().get_route_handler()

        async def custom_route_handler(request: Request) -> Response:

            node_id = request.path_params.get("node_id")
            project_id = request.path_params.get("project_id")

            if node_id and "pcap" not in request.url.path and not request.url.path.endswith("console/ws"):
                lock_key = "{}:{}".format(project_id, node_id)
                node_locks.setdefault(lock_key, {"lock": asyncio.Lock(), "concurrency": 0})
                node_locks[lock_key]["concurrency"] += 1

                async with node_locks[lock_key]["lock"]:
                    response = await original_route_handler(request)

                node_locks[lock_key]["concurrency"] -= 1
                if node_locks[lock_key]["concurrency"] <= 0:
                    del node_locks[lock_key]
            else:
                response = await original_route_handler(request)

            return response

        return custom_route_handler


router = APIRouter(route_class=NodeConcurrency)

responses = {
    404: {"model": ErrorMessage, "description": "Could not find project or node"}
}


async def dep_project(project_id: UUID):
    """
    Dependency to retrieve a project.
    """

    project = await Controller.instance().get_loaded_project(str(project_id))
    return project


async def dep_node(node_id: UUID, project: Project = Depends(dep_project)):
    """
    Dependency to retrieve a node.
    """

    node = project.get_node(str(node_id))
    return node


@router.post("",
             status_code=status.HTTP_201_CREATED,
             response_model=schemas.Node,
             responses={404: {"model": ErrorMessage, "description": "Could not find project"},
                        409: {"model": ErrorMessage, "description": "Could not create node"}})
async def create_node(node_data: schemas.Node, project: Project = Depends(dep_project)):
    """
    Create a new node.
    """

    controller = Controller.instance()
    compute = controller.get_compute(str(node_data.compute_id))
    node_data = jsonable_encoder(node_data, exclude_unset=True)
    node = await project.add_node(compute,
                                  node_data.pop("name"),
                                  node_data.pop("node_id", None),
                                  **node_data)
    return node.__json__()


@router.get("",
            response_model=List[schemas.Node],
            response_model_exclude_unset=True)
async def get_nodes(project: Project = Depends(dep_project)):
    """
    Return all nodes belonging to a given project.
    """

    return [v.__json__() for v in project.nodes.values()]


@router.post("/start",
             status_code=status.HTTP_204_NO_CONTENT,
             responses=responses)
async def start_all_nodes(project: Project = Depends(dep_project)):
    """
    Start all nodes belonging to a given project.
    """

    await project.start_all()


@router.post("/stop",
             status_code=status.HTTP_204_NO_CONTENT,
             responses=responses)
async def stop_all_nodes(project: Project = Depends(dep_project)):
    """
    Stop all nodes belonging to a given project.
    """

    await project.stop_all()


@router.post("/suspend",
             status_code=status.HTTP_204_NO_CONTENT,
             responses=responses)
async def suspend_all_nodes(project: Project = Depends(dep_project)):
    """
    Suspend all nodes belonging to a given project.
    """

    await project.suspend_all()


@router.post("/reload",
             status_code=status.HTTP_204_NO_CONTENT,
             responses=responses)
async def reload_all_nodes(project: Project = Depends(dep_project)):
    """
    Reload all nodes belonging to a given project.
    """

    await project.stop_all()
    await project.start_all()


@router.get("/{node_id}",
            response_model=schemas.Node,
            responses=responses)
def get_node(node: Node = Depends(dep_node)):
    """
    Return a node from a given project.
    """

    return node.__json__()


@router.put("/{node_id}",
            response_model=schemas.Node,
            response_model_exclude_unset=True,
            responses=responses)
async def update_node(node_data: schemas.NodeUpdate, node: Node = Depends(dep_node)):
    """
    Update a node.
    """

    node_data = jsonable_encoder(node_data, exclude_unset=True)

    # Ignore these because we only use them when creating a node
    node_data.pop("node_id", None)
    node_data.pop("node_type", None)
    node_data.pop("compute_id", None)

    await node.update(**node_data)
    return node.__json__()


@router.delete("/{node_id}",
               status_code=status.HTTP_204_NO_CONTENT,
               responses={**responses,
                          409: {"model": ErrorMessage, "description": "Cannot delete node"}})
async def delete_node(node_id: UUID, project: Project = Depends(dep_project)):
    """
    Delete a node from a project.
    """

    await project.delete_node(str(node_id))


@router.post("/{node_id}/duplicate",
             response_model=schemas.Node,
             status_code=status.HTTP_201_CREATED,
             responses=responses)
async def duplicate_node(duplicate_data: schemas.NodeDuplicate, node: Node = Depends(dep_node)):
    """
    Duplicate a node.
    """

    new_node = await node.project.duplicate_node(node,
                                                 duplicate_data.x,
                                                 duplicate_data.y,
                                                 duplicate_data.z)
    return new_node.__json__()


@router.post("/{node_id}/start",
             status_code=status.HTTP_204_NO_CONTENT,
             responses=responses)
async def start_node(start_data: dict, node: Node = Depends(dep_node)):
    """
    Start a node.
    """

    await node.start(data=start_data)


@router.post("/{node_id}/stop",
             status_code=status.HTTP_204_NO_CONTENT,
             responses=responses)
async def stop_node(node: Node = Depends(dep_node)):
    """
    Stop a node.
    """

    await node.stop()


@router.post("/{node_id}/suspend",
             status_code=status.HTTP_204_NO_CONTENT,
             responses=responses)
async def suspend_node(node: Node = Depends(dep_node)):
    """
    Suspend a node.
    """

    await node.suspend()


@router.post("/{node_id}/reload",
             status_code=status.HTTP_204_NO_CONTENT,
             responses=responses)
async def reload_node(node: Node = Depends(dep_node)):
    """
    Reload a node.
    """

    await node.reload()


@router.get("/{node_id}/links",
            response_model=List[schemas.Link],
            response_model_exclude_unset=True)
async def get_node_links(node: Node = Depends(dep_node)):
    """
    Return all the links connected to a node.
    """

    links = []
    for link in node.links:
        links.append(link.__json__())
    return links


@router.get("/{node_id}/dynamips/auto_idlepc",
            responses=responses)
async def auto_idlepc(node: Node = Depends(dep_node)):
    """
    Compute an Idle-PC value for a Dynamips node
    """

    return await node.dynamips_auto_idlepc()


@router.get("/{node_id}/dynamips/idlepc_proposals",
            responses=responses)
async def idlepc_proposals(node: Node = Depends(dep_node)):
    """
    Compute a list of potential idle-pc values for a Dynamips node
    """

    return await node.dynamips_idlepc_proposals()


@router.post("/{node_id}/resize_disk",
             status_code=status.HTTP_201_CREATED,
             responses=responses)
async def resize_disk(resize_data: dict, node: Node = Depends(dep_node)):
    """
    Resize a disk image.
    """
    await node.post("/resize_disk", **resize_data)


@router.get("/{node_id}/files/{file_path:path}",
            responses=responses)
async def get_file(file_path: str, node: Node = Depends(dep_node)):
    """
    Return a file in the node directory
    """

    path = force_unix_path(file_path)

    # Raise error if user try to escape
    if path[0] == ".":
        raise ControllerForbiddenError("It is forbidden to get a file outside the project directory")

    node_type = node.node_type
    path = "/project-files/{}/{}/{}".format(node_type, node.id, path)

    res = await node.compute.http_query("GET", "/projects/{project_id}/files{path}".format(project_id=node.project.id, path=path),
                                        timeout=None,
                                        raw=True)
    return Response(res.body, media_type="application/octet-stream")


@router.post("/{node_id}/files/{file_path:path}",
             status_code=status.HTTP_201_CREATED,
             responses=responses)
async def post_file(file_path: str, request: Request, node: Node = Depends(dep_node)):
    """
    Write a file in the node directory.
    """

    path = force_unix_path(file_path)

    # Raise error if user try to escape
    if path[0] == ".":
        raise ControllerForbiddenError("Cannot write outside the node directory")

    node_type = node.node_type
    path = "/project-files/{}/{}/{}".format(node_type, node.id, path)

    data = await request.body()  #FIXME: are we handling timeout or large files correctly?

    await node.compute.http_query("POST", "/projects/{project_id}/files{path}".format(project_id=node.project.id, path=path),
                                  data=data,
                                  timeout=None,
                                  raw=True)


@router.websocket("/{node_id}/console/ws")
async def ws_console(websocket: WebSocket, node: Node = Depends(dep_node)):
    """
    WebSocket console.
    """

    compute = node.compute
    await websocket.accept()
    log.info(f"New client {websocket.client.host}:{websocket.client.port} has connected to controller console WebSocket")
    ws_console_compute_url = f"ws://{compute.host}:{compute.port}/v2/compute/projects/" \
                             f"{node.project.id}/{node.node_type}/nodes/{node.id}/console/ws"

    async def ws_receive(ws_console_compute):
        """
        Receive WebSocket data from client and forward to compute console WebSocket.
        """

        try:
            while True:
                data = await websocket.receive_text()
                if data:
                    await ws_console_compute.send_str(data)
        except WebSocketDisconnect:
            await ws_console_compute.close()
            log.info(f"Client {websocket.client.host}:{websocket.client.port} has disconnected from controller"
                     f" console WebSocket")

    try:
        # receive WebSocket data from compute console WebSocket and forward to client.
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=None, force_close=True)) as session:
            async with session.ws_connect(ws_console_compute_url) as ws_console_compute:
                asyncio.ensure_future(ws_receive(ws_console_compute))
                async for msg in ws_console_compute:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        await websocket.send_text(msg.data)
                    elif msg.type == aiohttp.WSMsgType.BINARY:
                        await websocket.send_bytes(msg.data)
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        break
    except aiohttp.client_exceptions.ClientResponseError as e:
        log.error(f"Client response error received when forwarding to compute console WebSocket: {e}")


@router.post("/console/reset",
             status_code=status.HTTP_204_NO_CONTENT,
             responses=responses)
async def reset_console_all(project: Project = Depends(dep_project)):
    """
    Reset console for all nodes belonging to the project.
    """

    await project.reset_console_all()


@router.post("/{node_id}/console/reset",
             status_code=status.HTTP_204_NO_CONTENT,
             responses=responses)
async def console_reset(node: Node = Depends(dep_node)):

    await node.post("/console/reset")#, request.json)
