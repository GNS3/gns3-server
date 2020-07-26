# -*- coding: utf-8 -*-
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

import aiohttp
import asyncio

from gns3server.web.route import Route
from gns3server.controller import Controller
from gns3server.utils import force_unix_path

from gns3server.schemas.node import (
    NODE_OBJECT_SCHEMA,
    NODE_UPDATE_SCHEMA,
    NODE_CREATE_SCHEMA,
    NODE_DUPLICATE_SCHEMA
)


class NodeHandler:
    """
    API entry point for node
    """

    @Route.post(
        r"/projects/{project_id}/nodes",
        parameters={
            "project_id": "Project UUID"
        },
        status_codes={
            201: "Instance created",
            400: "Invalid request"
        },
        description="Create a new node instance",
        input=NODE_CREATE_SCHEMA,
        output=NODE_OBJECT_SCHEMA)
    async def create(request, response):

        controller = Controller.instance()
        compute = controller.get_compute(request.json.pop("compute_id"))
        project = await controller.get_loaded_project(request.match_info["project_id"])
        node = await project.add_node(compute, request.json.pop("name"), request.json.pop("node_id", None), **request.json)
        response.set_status(201)
        response.json(node)

    @Route.get(
        r"/projects/{project_id}/nodes",
        parameters={
            "project_id": "Project UUID"
        },
        status_codes={
            200: "List of nodes returned",
        },
        description="List nodes of a project")
    async def list_nodes(request, response):

        project = await Controller.instance().get_loaded_project(request.match_info["project_id"])
        response.json([v for v in project.nodes.values()])

    @Route.post(
        r"/projects/{project_id}/nodes/start",
        parameters={
            "project_id": "Project UUID"
        },
        status_codes={
            204: "All nodes successfully started",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Start all nodes belonging to the project",
        output=NODE_OBJECT_SCHEMA)
    async def start_all(request, response):

        project = await Controller.instance().get_loaded_project(request.match_info["project_id"])
        await project.start_all()
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/nodes/stop",
        parameters={
            "project_id": "Project UUID"
        },
        status_codes={
            204: "All nodes successfully stopped",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Stop all nodes belonging to the project",
        output=NODE_OBJECT_SCHEMA)
    async def stop_all(request, response):

        project = await Controller.instance().get_loaded_project(request.match_info["project_id"])
        await project.stop_all()
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/nodes/suspend",
        parameters={
            "project_id": "Project UUID"
        },
        status_codes={
            204: "All nodes successfully suspended",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Suspend all nodes belonging to the project",
        output=NODE_OBJECT_SCHEMA)
    async def suspend_all(request, response):

        project = await Controller.instance().get_loaded_project(request.match_info["project_id"])
        await project.suspend_all()
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/nodes/reload",
        parameters={
            "project_id": "Project UUID"
        },
        status_codes={
            204: "All nodes successfully reloaded",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Reload all nodes belonging to the project",
        output=NODE_OBJECT_SCHEMA)
    async def reload_all(request, response):

        project = await Controller.instance().get_loaded_project(request.match_info["project_id"])
        await project.stop_all()
        await project.start_all()
        response.set_status(204)

    @Route.get(
        r"/projects/{project_id}/nodes/{node_id}",
        status_codes={
            200: "Node found",
            400: "Invalid request",
            404: "Node doesn't exist"
        },
        description="Get a node",
        output=NODE_OBJECT_SCHEMA)
    def get_node(request, response):
        project = Controller.instance().get_project(request.match_info["project_id"])
        node = project.get_node(request.match_info["node_id"])
        response.set_status(200)
        response.json(node)

    @Route.put(
        r"/projects/{project_id}/nodes/{node_id}",
        status_codes={
            200: "Instance updated",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Update a node instance",
        input=NODE_UPDATE_SCHEMA,
        output=NODE_OBJECT_SCHEMA)
    async def update(request, response):
        project = await Controller.instance().get_loaded_project(request.match_info["project_id"])
        node = project.get_node(request.match_info["node_id"])

        # Ignore these because we only use them when creating a node
        request.json.pop("node_id", None)
        request.json.pop("node_type", None)
        request.json.pop("compute_id", None)

        await node.update(**request.json)
        response.set_status(200)
        response.json(node)

    @Route.delete(
        r"/projects/{project_id}/nodes/{node_id}",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            204: "Instance deleted",
            400: "Invalid request",
            404: "Instance doesn't exist",
            409: "Cannot delete locked node"
        },
        description="Delete a node instance")
    async def delete(request, response):
        project = await Controller.instance().get_loaded_project(request.match_info["project_id"])
        await project.delete_node(request.match_info["node_id"])
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/nodes/{node_id}/duplicate",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            201: "Instance duplicated",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Duplicate a node instance",
        input=NODE_DUPLICATE_SCHEMA,
        output=NODE_OBJECT_SCHEMA)
    async def duplicate(request, response):

        project = await Controller.instance().get_loaded_project(request.match_info["project_id"])
        node = project.get_node(request.match_info["node_id"])
        new_node = await project.duplicate_node(
            node,
            request.json["x"],
            request.json["y"],
            request.json.get("z", 0))
        response.json(new_node)
        response.set_status(201)

    @Route.post(
        r"/projects/{project_id}/nodes/{node_id}/start",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            200: "Instance started",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Start a node instance",
        output=NODE_OBJECT_SCHEMA)
    async def start(request, response):

        project = await Controller.instance().get_loaded_project(request.match_info["project_id"])
        node = project.get_node(request.match_info["node_id"])
        await node.start(data=request.json)
        response.json(node)
        response.set_status(200)

    @Route.post(
        r"/projects/{project_id}/nodes/{node_id}/stop",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            200: "Instance stopped",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Stop a node instance",
        output=NODE_OBJECT_SCHEMA)
    async def stop(request, response):

        project = await Controller.instance().get_loaded_project(request.match_info["project_id"])
        node = project.get_node(request.match_info["node_id"])
        await node.stop()
        response.json(node)
        response.set_status(200)

    @Route.post(
        r"/projects/{project_id}/nodes/{node_id}/suspend",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            200: "Instance suspended",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Suspend a node instance",
        output=NODE_OBJECT_SCHEMA)
    async def suspend(request, response):

        project = await Controller.instance().get_loaded_project(request.match_info["project_id"])
        node = project.get_node(request.match_info["node_id"])
        await node.suspend()
        response.json(node)
        response.set_status(200)

    @Route.post(
        r"/projects/{project_id}/nodes/{node_id}/reload",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            200: "Instance reloaded",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Reload a node instance",
        output=NODE_OBJECT_SCHEMA)
    async def reload(request, response):

        project = await Controller.instance().get_loaded_project(request.match_info["project_id"])
        node = project.get_node(request.match_info["node_id"])
        await node.reload()
        response.json(node)
        response.set_status(200)

    @Route.get(
        r"/projects/{project_id}/nodes/{node_id}/links",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            200: "Links returned",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Return all the links connected to this node")
    async def links(request, response):

        project = await Controller.instance().get_loaded_project(request.match_info["project_id"])
        node = project.get_node(request.match_info["node_id"])
        links = []
        for link in node.links:
            links.append(link.__json__())
        response.json(links)
        response.set_status(200)

    @Route.get(
        r"/projects/{project_id}/nodes/{node_id}/dynamips/auto_idlepc",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            204: "Instance reloaded",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Compute the IDLE PC for a Dynamips node")
    async def auto_idlepc(request, response):

        project = await Controller.instance().get_loaded_project(request.match_info["project_id"])
        node = project.get_node(request.match_info["node_id"])
        idle = await node.dynamips_auto_idlepc()
        response.json(idle)
        response.set_status(200)

    @Route.get(
        r"/projects/{project_id}/nodes/{node_id}/dynamips/idlepc_proposals",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            204: "Instance reloaded",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Compute a list of potential idle PC for a node")
    async def idlepc_proposals(request, response):

        project = await Controller.instance().get_loaded_project(request.match_info["project_id"])
        node = project.get_node(request.match_info["node_id"])
        idle = await node.dynamips_idlepc_proposals()
        response.json(idle)
        response.set_status(200)

    @Route.post(
        r"/projects/{project_id}/nodes/{node_id}/resize_disk",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            201: "Disk image resized",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Reload a node instance")
    async def resize_disk(request, response):

        project = await Controller.instance().get_loaded_project(request.match_info["project_id"])
        node = project.get_node(request.match_info["node_id"])
        await node.post("/resize_disk", request.json)
        response.set_status(201)

    @Route.get(
        r"/projects/{project_id}/nodes/{node_id}/files/{path:.+}",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            204: "Instance reloaded",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Get a file in the node directory")
    async def get_file(request, response):

        project = await Controller.instance().get_loaded_project(request.match_info["project_id"])
        node = project.get_node(request.match_info["node_id"])
        path = request.match_info["path"]
        path = force_unix_path(path)

        # Raise error if user try to escape
        if path[0] == "." or "/../" in path:
            raise aiohttp.web.HTTPForbidden()

        node_type = node.node_type
        path = "/project-files/{}/{}/{}".format(node_type, node.id, path)
        res = await node.compute.http_query("GET", "/projects/{project_id}/files{path}".format(project_id=project.id, path=path), timeout=None, raw=True)
        response.set_status(res.status)
        if res.status == 200:
            response.content_type = "application/octet-stream"
            response.enable_chunked_encoding()
            await response.prepare(request)
            await response.write(res.body)

    @Route.post(
        r"/projects/{project_id}/nodes/{node_id}/files/{path:.+}",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            204: "Instance reloaded",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        raw=True,
        description="Write a file in the node directory")
    async def post_file(request, response):

        project = await Controller.instance().get_loaded_project(request.match_info["project_id"])
        node = project.get_node(request.match_info["node_id"])
        path = request.match_info["path"]
        path = force_unix_path(path)

        # Raise error if user try to escape
        if path[0] == "." or "/../" in path:
            raise aiohttp.web.HTTPForbidden()

        node_type = node.node_type
        path = "/project-files/{}/{}/{}".format(node_type, node.id, path)
        data = await request.content.read()  #FIXME: are we handling timeout or large files correctly?
        res = await node.compute.http_query("POST", "/projects/{project_id}/files{path}".format(project_id=project.id, path=path), data=data, timeout=None, raw=True)
        response.set_status(res.status)

    @Route.get(
        r"/projects/{project_id}/nodes/{node_id}/console/ws",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        description="Connect to WebSocket console",
        status_codes={
            200: "File returned",
            403: "Permission denied",
            404: "The file doesn't exist"
        })
    async def ws_console(request, response):

        project = await Controller.instance().get_loaded_project(request.match_info["project_id"])
        node = project.get_node(request.match_info["node_id"])
        compute = node.compute
        ws = aiohttp.web.WebSocketResponse()
        await ws.prepare(request)
        request.app['websockets'].add(ws)

        ws_console_compute_url = "ws://{compute_host}:{compute_port}/v2/compute/projects/{project_id}/{node_type}/nodes/{node_id}/console/ws".format(compute_host=compute.host,
                                                                                                                                                     compute_port=compute.port,
                                                                                                                                                     project_id=project.id,
                                                                                                                                                     node_type=node.node_type,
                                                                                                                                                     node_id=node.id)

        async def ws_forward(ws_client):
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    await ws_client.send_str(msg.data)
                elif msg.type == aiohttp.WSMsgType.BINARY:
                    await ws_client.send_bytes(msg.data)
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    break

        try:
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=None, force_close=True)) as session:
                async with session.ws_connect(ws_console_compute_url) as ws_client:
                    asyncio.ensure_future(ws_forward(ws_client))
                    async for msg in ws_client:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            await ws.send_str(msg.data)
                        elif msg.type == aiohttp.WSMsgType.BINARY:
                            await ws.send_bytes(msg.data)
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            break
        finally:
            if not ws.closed:
                await ws.close()
            request.app['websockets'].discard(ws)

        return ws

    @Route.post(
        r"/projects/{project_id}/nodes/console/reset",
        parameters={
            "project_id": "Project UUID"
        },
        status_codes={
            204: "All nodes successfully reset consoles",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Reset console for all nodes belonging to the project",
        output=NODE_OBJECT_SCHEMA)
    async def reset_console_all(request, response):

        project = await Controller.instance().get_loaded_project(request.match_info["project_id"])
        await project.reset_console_all()
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/nodes/{node_id}/console/reset",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            204: "Console reset",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Reload a node instance")
    async def console_reset(request, response):

        project = await Controller.instance().get_loaded_project(request.match_info["project_id"])
        node = project.get_node(request.match_info["node_id"])
        await node.post("/console/reset", request.json)
        response.set_status(204)
