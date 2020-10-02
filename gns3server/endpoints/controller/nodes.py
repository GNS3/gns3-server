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

import asyncio

from fastapi import APIRouter, Request, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.routing import APIRoute
from typing import List, Callable
from uuid import UUID

from gns3server.controller import Controller
from gns3server.utils import force_unix_path
from gns3server.controller.controller_error import ControllerForbiddenError
from gns3server.endpoints.schemas.common import ErrorMessage
from gns3server.endpoints import schemas

import aiohttp

node_locks = {}


class NodeConcurrency(APIRoute):
    """
    To avoid strange effect we prevent concurrency
    between the same instance of the node
    (excepting when streaming a PCAP file and WebSocket consoles).
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

# # dependency to retrieve a node
# async def get_node(project_id: UUID, node_id: UUID):
#
#     project = await Controller.instance().get_loaded_project(str(project_id))
#     node = project.get_node(str(node_id))
#     return node


@router.post("/projects/{project_id}/nodes",
             summary="Create a new node",
             status_code=status.HTTP_201_CREATED,
             response_model=schemas.Node,
             responses={404: {"model": ErrorMessage, "description": "Could not find project"},
                        409: {"model": ErrorMessage, "description": "Could not create node"}})
async def create_node(project_id: UUID, node_data: schemas.Node):

    controller = Controller.instance()
    compute = controller.get_compute(str(node_data.compute_id))
    project = await controller.get_loaded_project(str(project_id))
    node_data = jsonable_encoder(node_data, exclude_unset=True)
    node = await project.add_node(compute,
                                  node_data.pop("name"),
                                  node_data.pop("node_id", None),
                                  **node_data)
    return node.__json__()


@router.get("/projects/{project_id}/nodes",
            summary="List of all nodes",
            response_model=List[schemas.Node],
            response_description="List of nodes",
            response_model_exclude_unset=True)
async def list_nodes(project_id: UUID):

    project = await Controller.instance().get_loaded_project(str(project_id))
    return [v.__json__() for v in project.nodes.values()]


@router.post("/projects/{project_id}/nodes/start",
             summary="Start all nodes",
             status_code=status.HTTP_204_NO_CONTENT,
             responses={404: {"model": ErrorMessage, "description": "Could not find project"}})
async def start_all_nodes(project_id: UUID):
    """
    Start all nodes belonging to the project
    """

    project = await Controller.instance().get_loaded_project(str(project_id))
    await project.start_all()


@router.post("/projects/{project_id}/nodes/stop",
             summary="Stop all nodes",
             status_code=status.HTTP_204_NO_CONTENT,
             responses={404: {"model": ErrorMessage, "description": "Could not find project"}})
async def stop_all_nodes(project_id: UUID):
    """
    Stop all nodes belonging to the project
    """

    project = await Controller.instance().get_loaded_project(str(project_id))
    await project.stop_all()


@router.post("/projects/{project_id}/nodes/suspend",
             summary="Stop all nodes",
             status_code=status.HTTP_204_NO_CONTENT,
             responses={404: {"model": ErrorMessage, "description": "Could not find project"}})
async def suspend_all_nodes(project_id: UUID):
    """
    Suspend all nodes belonging to the project
    """

    project = await Controller.instance().get_loaded_project(str(project_id))
    await project.suspend_all()


@router.post("/projects/{project_id}/nodes/reload",
             summary="Reload all nodes",
             status_code=status.HTTP_204_NO_CONTENT,
             responses={404: {"model": ErrorMessage, "description": "Could not find project"}})
async def reload_all_nodes(project_id: UUID):
    """
    Reload all nodes belonging to the project
    """

    project = await Controller.instance().get_loaded_project(str(project_id))
    await project.stop_all()
    await project.start_all()


@router.get("/projects/{project_id}/nodes/{node_id}",
            summary="Get a node",
            response_model=schemas.Node,
            responses={404: {"model": ErrorMessage, "description": "Could not find project or node"}})
def get_node(project_id: UUID, node_id: UUID):

    project = Controller.instance().get_project(str(project_id))
    node = project.get_node(str(node_id))
    return node.__json__()


@router.put("/projects/{project_id}/nodes/{node_id}",
            summary="Update a node",
            response_model=schemas.Node,
            response_description="Updated node",
            response_model_exclude_unset=True,
            responses={404: {"model": ErrorMessage, "description": "Project or node not found"}})
async def update_node(project_id: UUID, node_id: UUID, node_data: schemas.NodeUpdate):

    project = await Controller.instance().get_loaded_project(str(project_id))
    node = project.get_node(str(node_id))
    node_data = jsonable_encoder(node_data, exclude_unset=True)

    # Ignore these because we only use them when creating a node
    node_data.pop("node_id", None)
    node_data.pop("node_type", None)
    node_data.pop("compute_id", None)

    await node.update(**node_data)
    return node.__json__()


@router.delete("/projects/{project_id}/nodes/{node_id}",
               summary="Delete a node",
               status_code=status.HTTP_204_NO_CONTENT,
               responses={404: {"model": ErrorMessage, "description": "Could not find project or node"},
                          409: {"model": ErrorMessage, "description": "Cannot delete node"}})
async def delete_node(project_id: UUID, node_id: UUID):

    project = await Controller.instance().get_loaded_project(str(project_id))
    await project.delete_node(str(node_id))


@router.post("/projects/{project_id}/nodes/{node_id}/duplicate",
             summary="Duplicate a node",
             response_model=schemas.Node,
             status_code=status.HTTP_201_CREATED,
             responses={404: {"model": ErrorMessage, "description": "Could not find project or node"}})
async def duplicate_node(project_id: UUID, node_id: UUID, duplicate_data: schemas.NodeDuplicate):

    project = await Controller.instance().get_loaded_project(str(project_id))
    node = project.get_node(str(node_id))
    new_node = await project.duplicate_node(node,
                                            duplicate_data.x,
                                            duplicate_data.y,
                                            duplicate_data.z)
    return new_node.__json__()


@router.post("/projects/{project_id}/nodes/{node_id}/start",
             summary="Start a node",
             status_code=status.HTTP_204_NO_CONTENT,
             responses={404: {"model": ErrorMessage, "description": "Could not find project or node"}})
async def start_node(project_id: UUID, node_id: UUID, start_data: dict):

    project = await Controller.instance().get_loaded_project(str(project_id))
    node = project.get_node(str(node_id))
    await node.start(data=start_data)


@router.post("/projects/{project_id}/nodes/{node_id}/stop",
             summary="Stop a node",
             status_code=status.HTTP_204_NO_CONTENT,
             responses={404: {"model": ErrorMessage, "description": "Could not find project or node"}})
async def stop_node(project_id: UUID, node_id: UUID):

    project = await Controller.instance().get_loaded_project(str(project_id))
    node = project.get_node(str(node_id))
    await node.stop()


@router.post("/projects/{project_id}/nodes/{node_id}/suspend",
             summary="Suspend a node",
             status_code=status.HTTP_204_NO_CONTENT,
             responses={404: {"model": ErrorMessage, "description": "Could not find project or node"}})
async def suspend_node(project_id: UUID, node_id: UUID):

    project = await Controller.instance().get_loaded_project(str(project_id))
    node = project.get_node(str(node_id))
    await node.suspend()


@router.post("/projects/{project_id}/nodes/{node_id}/reload",
             summary="Reload a node",
             status_code=status.HTTP_204_NO_CONTENT,
             responses={404: {"model": ErrorMessage, "description": "Could not find project or node"}})
async def reload_node(project_id: UUID, node_id: UUID):

    project = await Controller.instance().get_loaded_project(str(project_id))
    node = project.get_node(str(node_id))
    await node.reload()


@router.get("/projects/{project_id}/nodes/{node_id}/links",
            summary="List of all node links",
            response_model=List[schemas.Link],
            response_description="List of links",
            response_model_exclude_unset=True)
async def node_links(project_id: UUID, node_id: UUID):
    """
    Return all the links connected to the node.
    """

    project = await Controller.instance().get_loaded_project(str(project_id))
    node = project.get_node(str(node_id))
    links = []
    for link in node.links:
        links.append(link.__json__())
    return links


@router.get("/projects/{project_id}/nodes/{node_id}/dynamips/auto_idlepc",
            summary="Compute an Idle-PC",
            responses={404: {"model": ErrorMessage, "description": "Could not find project or node"}})
async def auto_idlepc(project_id: UUID, node_id: UUID):
    """
    Compute an Idle-PC value for a Dynamips node
    """

    project = await Controller.instance().get_loaded_project(str(project_id))
    node = project.get_node(str(node_id))
    return await node.dynamips_auto_idlepc()


@router.get("/projects/{project_id}/nodes/{node_id}/dynamips/idlepc_proposals",
            summary="Compute list of Idle-PC values",
            responses={404: {"model": ErrorMessage, "description": "Could not find project or node"}})
async def idlepc_proposals(project_id: UUID, node_id: UUID):
    """
    Compute a list of potential idle-pc values for a Dynamips node
    """

    project = await Controller.instance().get_loaded_project(str(project_id))
    node = project.get_node(str(node_id))
    return await node.dynamips_idlepc_proposals()


@router.post("/projects/{project_id}/nodes/{node_id}/resize_disk",
             summary="Resize a disk",
             status_code=status.HTTP_201_CREATED,
             responses={404: {"model": ErrorMessage, "description": "Could not find project or node"}})
async def resize_disk(project_id: UUID, node_id: UUID, resize_data: dict):

    project = await Controller.instance().get_loaded_project(str(project_id))
    node = project.get_node(str(node_id))
    await node.post("/resize_disk", **resize_data)


@router.get("/projects/{project_id}/nodes/{node_id}/files/{file_path:path}",
            summary="Get a file in the node directory",
            responses={404: {"model": ErrorMessage, "description": "Could not find project or node"}})
async def get_file(project_id: UUID, node_id: UUID, file_path: str):

    project = await Controller.instance().get_loaded_project(str(project_id))
    node = project.get_node(str(node_id))
    path = force_unix_path(file_path)

    # Raise error if user try to escape
    if path[0] == ".":
        raise ControllerForbiddenError("It is forbidden to get a file outside the project directory")

    node_type = node.node_type
    path = "/project-files/{}/{}/{}".format(node_type, node.id, path)

    res = await node.compute.http_query("GET", "/projects/{project_id}/files{path}".format(project_id=project.id, path=path), timeout=None, raw=True)
    return Response(res.body, media_type="application/octet-stream")


@router.post("/projects/{project_id}/nodes/{node_id}/files/{file_path:path}",
             summary="Write a file in the node directory",
             status_code=status.HTTP_201_CREATED,
             responses={404: {"model": ErrorMessage, "description": "Could not find project or node"}})
async def post_file(project_id: UUID, node_id: UUID, file_path: str, request: Request):

    project = await Controller.instance().get_loaded_project(str(project_id))
    node = project.get_node(str(node_id))
    path = force_unix_path(file_path)

    # Raise error if user try to escape
    if path[0] == ".":
        raise ControllerForbiddenError("Cannot write outside the node directory")

    node_type = node.node_type
    path = "/project-files/{}/{}/{}".format(node_type, node.id, path)

    data = await request.body()  #FIXME: are we handling timeout or large files correctly?

    await node.compute.http_query("POST", "/projects/{project_id}/files{path}".format(project_id=project.id, path=path), data=data, timeout=None, raw=True)


# @Route.get(
#     r"/projects/{project_id}/nodes/{node_id}/console/ws",
#     parameters={
#         "project_id": "Project UUID",
#         "node_id": "Node UUID"
#     },
#     description="Connect to WebSocket console",
#     status_codes={
#         200: "File returned",
#         403: "Permission denied",
#         404: "The file doesn't exist"
#     })
# async def ws_console(request, response):
#
#     project = await Controller.instance().get_loaded_project(request.match_info["project_id"])
#     node = project.get_node(request.match_info["node_id"])
#     compute = node.compute
#     ws = aiohttp.web.WebSocketResponse()
#     await ws.prepare(request)
#     request.app['websockets'].add(ws)
#
#     ws_console_compute_url = "ws://{compute_host}:{compute_port}/v2/compute/projects/{project_id}/{node_type}/nodes/{node_id}/console/ws".format(compute_host=compute.host,
#                                                                                                                                                  compute_port=compute.port,
#                                                                                                                                                  project_id=project.id,
#                                                                                                                                                  node_type=node.node_type,
#                                                                                                                                                  node_id=node.id)
#
#     async def ws_forward(ws_client):
#         async for msg in ws:
#             if msg.type == aiohttp.WSMsgType.TEXT:
#                 await ws_client.send_str(msg.data)
#             elif msg.type == aiohttp.WSMsgType.BINARY:
#                 await ws_client.send_bytes(msg.data)
#             elif msg.type == aiohttp.WSMsgType.ERROR:
#                 break
#
#     try:
#         async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=None, force_close=True)) as session:
#             async with session.ws_connect(ws_console_compute_url) as ws_client:
#                 asyncio.ensure_future(ws_forward(ws_client))
#                 async for msg in ws_client:
#                     if msg.type == aiohttp.WSMsgType.TEXT:
#                         await ws.send_str(msg.data)
#                     elif msg.type == aiohttp.WSMsgType.BINARY:
#                         await ws.send_bytes(msg.data)
#                     elif msg.type == aiohttp.WSMsgType.ERROR:
#                         break
#     finally:
#         if not ws.closed:
#             await ws.close()
#         request.app['websockets'].discard(ws)
#
#     return ws


@router.post("/projects/{project_id}/nodes/console/reset",
             status_code=status.HTTP_204_NO_CONTENT,
             responses={404: {"model": ErrorMessage, "description": "Could not find project or node"}})
async def reset_console_all(project_id: UUID):
    """
    Reset console for all nodes belonging to the project.
    """

    project = await Controller.instance().get_loaded_project(str(project_id))
    await project.reset_console_all()


@router.post("/projects/{project_id}/nodes/{node_id}/console/reset",
             status_code=status.HTTP_204_NO_CONTENT,
             responses={404: {"model": ErrorMessage, "description": "Could not find project or node"}})
async def console_reset(project_id: UUID, node_id: UUID):

    project = await Controller.instance().get_loaded_project(str(project_id))
    node = project.get_node(str(node_id))
    await node.post("/console/reset")#, request.json)
