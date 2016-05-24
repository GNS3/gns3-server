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

from gns3server.web.route import Route
from gns3server.controller import Controller
from gns3server.utils.asyncio.pool import Pool

from gns3server.schemas.node import (
    NODE_OBJECT_SCHEMA,
    NODE_UPDATE_SCHEMA
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
        input=NODE_OBJECT_SCHEMA,
        output=NODE_OBJECT_SCHEMA)
    def create(request, response):

        controller = Controller.instance()
        compute = controller.get_compute(request.json.pop("compute_id"))
        project = controller.get_project(request.match_info["project_id"])
        node = yield from project.add_node(compute, request.json.pop("node_id", None), **request.json)
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
    def list_nodes(request, response):

        controller = Controller.instance()
        project = controller.get_project(request.match_info["project_id"])
        response.json([v for v in project.nodes.values()])

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
    def update(request, response):
        project = Controller.instance().get_project(request.match_info["project_id"])
        node = project.get_node(request.match_info["node_id"])

        # Ignore these because we only use them when creating a node
        request.json.pop("node_id", None)
        request.json.pop("node_type", None)
        request.json.pop("compute_id", None)

        yield from node.update(**request.json)
        response.set_status(200)
        response.json(node)

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
    def start_all(request, response):

        project = Controller.instance().get_project(request.match_info["project_id"])
        pool = Pool(concurrency=3)
        for node in project.nodes.values():
            pool.append(node.start)
        yield from pool.join()
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
    def stop_all(request, response):

        project = Controller.instance().get_project(request.match_info["project_id"])
        pool = Pool(concurrency=3)
        for node in project.nodes.values():
            pool.append(node.stop)
        yield from pool.join()
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
    def suspend_all(request, response):

        project = Controller.instance().get_project(request.match_info["project_id"])
        pool = Pool(concurrency=3)
        for node in project.nodes.values():
            pool.append(node.suspend)
        yield from pool.join()
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
    def reload_all(request, response):

        project = Controller.instance().get_project(request.match_info["project_id"])
        pool = Pool(concurrency=3)
        for node in project.nodes.values():
            pool.append(node.stop)
        yield from pool.join()
        for node in project.nodes.values():
            pool.append(node.start)
        yield from pool.join()
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/nodes/{node_id}/start",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            204: "Instance started",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Start a node instance",
        output=NODE_OBJECT_SCHEMA)
    def start(request, response):

        project = Controller.instance().get_project(request.match_info["project_id"])
        node = project.get_node(request.match_info["node_id"])
        yield from node.start()
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/nodes/{node_id}/stop",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            204: "Instance stopped",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Stop a node instance",
        output=NODE_OBJECT_SCHEMA)
    def stop(request, response):

        project = Controller.instance().get_project(request.match_info["project_id"])
        node = project.get_node(request.match_info["node_id"])
        yield from node.stop()
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/nodes/{node_id}/suspend",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            204: "Instance suspended",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Suspend a node instance",
        output=NODE_OBJECT_SCHEMA)
    def suspend(request, response):

        project = Controller.instance().get_project(request.match_info["project_id"])
        node = project.get_node(request.match_info["node_id"])
        yield from node.suspend()
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/nodes/{node_id}/reload",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            204: "Instance reloaded",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Reload a node instance",
        output=NODE_OBJECT_SCHEMA)
    def reload(request, response):

        project = Controller.instance().get_project(request.match_info["project_id"])
        node = project.get_node(request.match_info["node_id"])
        yield from node.reload()
        response.set_status(204)

    @Route.delete(
        r"/projects/{project_id}/nodes/{node_id}",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            204: "Instance deleted",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Delete a node instance")
    def delete(request, response):
        project = Controller.instance().get_project(request.match_info["project_id"])
        yield from project.delete_node(request.match_info["node_id"])
        response.set_status(204)

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
    def auto_idlepc(request, response):

        project = Controller.instance().get_project(request.match_info["project_id"])
        node = project.get_node(request.match_info["node_id"])
        idle = yield from node.dynamips_auto_idlepc()
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
    def idlepc_proposals(request, response):

        project = Controller.instance().get_project(request.match_info["project_id"])
        node = project.get_node(request.match_info["node_id"])
        idle = yield from node.dynamips_idlepc_proposals()
        response.json(idle)
        response.set_status(200)
