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

from ....web.route import Route
from ....schemas.node import NODE_OBJECT_SCHEMA, NODE_UPDATE_SCHEMA
from ....controller import Controller


class NodeHandler:
    """
    API entry point for node
    """

    @classmethod
    @Route.post(
        r"/projects/{project_id}/nodes",
        parameters={
            "project_id": "UUID for the project"
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
        compute = controller.getCompute(request.json.pop("compute_id"))
        project = controller.get_project(request.match_info["project_id"])
        node = yield from project.add_node(compute, request.json.pop("node_id", None), **request.json)
        response.set_status(201)
        response.json(node)

    @classmethod
    @Route.get(
        r"/projects/{project_id}/nodes",
        parameters={
            "project_id": "UUID for the project"
        },
        status_codes={
            200: "List of nodes",
        },
        description="List nodes of a project")
    def list_nodes(request, response):

        controller = Controller.instance()
        project = controller.get_project(request.match_info["project_id"])
        response.json([ v for v in project.nodes.values() ])

    @classmethod
    @Route.put(
        r"/projects/{project_id}/nodes/{node_id}",
        status_codes={
            201: "Instance created",
            400: "Invalid request"
        },
        description="Update a node instance",
        input=NODE_UPDATE_SCHEMA,
        output=NODE_OBJECT_SCHEMA)
    def update(request, response):
        project = Controller.instance().get_project(request.match_info["project_id"])
        node = project.get_node(request.match_info["node_id"])

        # Ignore this, because we use it only in create
        request.json.pop("node_id", None)
        request.json.pop("node_type", None)
        request.json.pop("compute_id", None)

        yield from node.update(**request.json)
        response.set_status(201)
        response.json(node)

    @classmethod
    @Route.post(
        r"/projects/{project_id}/nodes/{node_id}/start",
        parameters={
            "project_id": "UUID for the project",
            "node_id": "UUID for the node"
        },
        status_codes={
            201: "Instance created",
            400: "Invalid request"
        },
        description="Start a node instance",
        output=NODE_OBJECT_SCHEMA)
    def start(request, response):

        project = Controller.instance().get_project(request.match_info["project_id"])
        node = project.get_node(request.match_info["node_id"])
        yield from node.start()
        response.set_status(201)
        response.json(node)

    @classmethod
    @Route.post(
        r"/projects/{project_id}/nodes/{node_id}/stop",
        parameters={
            "project_id": "UUID for the project",
            "node_id": "UUID for the node"
        },
        status_codes={
            201: "Instance created",
            400: "Invalid request"
        },
        description="Start a node instance",
        output=NODE_OBJECT_SCHEMA)
    def stop(request, response):

        project = Controller.instance().get_project(request.match_info["project_id"])
        node = project.get_node(request.match_info["node_id"])
        yield from node.stop()
        response.set_status(201)
        response.json(node)

    @classmethod
    @Route.post(
        r"/projects/{project_id}/nodes/{node_id}/suspend",
        parameters={
            "project_id": "UUID for the project",
            "node_id": "UUID for the node"
        },
        status_codes={
            201: "Instance created",
            400: "Invalid request"
        },
        description="Start a node instance",
        output=NODE_OBJECT_SCHEMA)
    def suspend(request, response):

        project = Controller.instance().get_project(request.match_info["project_id"])
        node = project.get_node(request.match_info["node_id"])
        yield from node.suspend()
        response.set_status(201)
        response.json(node)

    @classmethod
    @Route.post(
        r"/projects/{project_id}/nodes/{node_id}/reload",
        parameters={
            "project_id": "UUID for the project",
            "node_id": "UUID for the node"
        },
        status_codes={
            201: "Instance created",
            400: "Invalid request"
        },
        description="Reload a node instance",
        output=NODE_OBJECT_SCHEMA)
    def reload(request, response):

        project = Controller.instance().get_project(request.match_info["project_id"])
        node = project.get_node(request.match_info["node_id"])
        yield from node.reload()
        response.set_status(201)
        response.json(node)

    @classmethod
    @Route.delete(
        r"/projects/{project_id}/nodes/{node_id}",
        parameters={
            "project_id": "UUID for the project",
            "node_id": "UUID for the node"
        },
        status_codes={
            201: "Instance deleted",
            400: "Invalid request"
        },
        description="Delete a node instance")
    def delete(request, response):
        project = Controller.instance().get_project(request.match_info["project_id"])
        node = project.get_node(request.match_info["node_id"])
        yield from node.destroy()
        response.set_status(201)
