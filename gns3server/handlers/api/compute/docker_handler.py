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

import os
from aiohttp.web import HTTPConflict

from gns3server.web.route import Route
from gns3server.compute.docker import Docker
from gns3server.schemas.node import NODE_CAPTURE_SCHEMA
from gns3server.schemas.nio import NIO_SCHEMA

from gns3server.schemas.docker import (
    DOCKER_CREATE_SCHEMA,
    DOCKER_OBJECT_SCHEMA,
    DOCKER_LIST_IMAGES_SCHEMA
)


class DockerHandler:
    """API entry points for Docker containers."""

    @Route.post(
        r"/projects/{project_id}/docker/nodes",
        parameters={
            "project_id": "Project UUID"
        },
        status_codes={
            201: "Instance created",
            400: "Invalid request",
            409: "Conflict"
        },
        description="Create a new Docker container",
        input=DOCKER_CREATE_SCHEMA,
        output=DOCKER_OBJECT_SCHEMA)
    def create(request, response):
        docker_manager = Docker.instance()
        container = yield from docker_manager.create_node(request.json.pop("name"),
                                                          request.match_info["project_id"],
                                                          request.json.get("node_id"),
                                                          image=request.json.pop("image"),
                                                          start_command=request.json.get("start_command"),
                                                          environment=request.json.get("environment"),
                                                          adapters=request.json.get("adapters"),
                                                          console=request.json.get("console"),
                                                          console_type=request.json.get("console_type"),
                                                          console_resolution=request.json.get("console_resolution", "1024x768"),
                                                          console_http_port=request.json.get("console_http_port", 80),
                                                          console_http_path=request.json.get("console_http_path", "/"),
                                                          aux=request.json.get("aux"))
        for name, value in request.json.items():
            if name != "node_id":
                if hasattr(container, name) and getattr(container, name) != value:
                    setattr(container, name, value)

        response.set_status(201)
        response.json(container)

    @Route.post(
        r"/projects/{project_id}/docker/nodes/{node_id}/start",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            204: "Instance started",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Start a Docker container")
    def start(request, response):
        docker_manager = Docker.instance()
        container = docker_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        yield from container.start()
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/docker/nodes/{node_id}/stop",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            204: "Instance stopped",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Stop a Docker container")
    def stop(request, response):
        docker_manager = Docker.instance()
        container = docker_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        yield from container.stop()
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/docker/nodes/{node_id}/reload",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            204: "Instance restarted",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Restart a Docker container")
    def reload(request, response):
        docker_manager = Docker.instance()
        container = docker_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        yield from container.restart()
        response.set_status(204)

    @Route.delete(
        r"/projects/{project_id}/docker/nodes/{node_id}",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID",
        },
        status_codes={
            204: "Instance deleted",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Delete a Docker container")
    def delete(request, response):
        docker_manager = Docker.instance()
        container = docker_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        yield from container.delete()
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/docker/nodes/{node_id}/pause",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            204: "Instance paused",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Pause a Docker container")
    def pause(request, response):
        docker_manager = Docker.instance()
        container = docker_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        yield from container.pause()
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/docker/nodes/{node_id}/unpause",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            204: "Instance unpaused",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Unpause a Docker container")
    def unpause(request, response):
        docker_manager = Docker.instance()
        container = docker_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        yield from container.unpause()
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/docker/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID",
            "adapter_number": "Adapter where the nio should be added",
            "port_number": "Port on the adapter"
        },
        status_codes={
            201: "NIO created",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Add a NIO to a Docker container",
        input=NIO_SCHEMA,
        output=NIO_SCHEMA)
    def create_nio(request, response):
        docker_manager = Docker.instance()
        container = docker_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        nio_type = request.json["type"]
        if nio_type != "nio_udp":
            raise HTTPConflict(text="NIO of type {} is not supported".format(nio_type))
        nio = docker_manager.create_nio(request.json)
        yield from container.adapter_add_nio_binding(int(request.match_info["adapter_number"]), nio)
        response.set_status(201)
        response.json(nio)

    @Route.delete(
        r"/projects/{project_id}/docker/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID",
            "adapter_number": "Adapter where the nio should be added",
            "port_number": "Port on the adapter"
        },
        status_codes={
            204: "NIO deleted",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Remove a NIO from a Docker container")
    def delete_nio(request, response):
        docker_manager = Docker.instance()
        container = docker_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        yield from container.adapter_remove_nio_binding(int(request.match_info["adapter_number"]))
        response.set_status(204)

    @Route.put(
        r"/projects/{project_id}/docker/nodes/{node_id}",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            200: "Instance updated",
            400: "Invalid request",
            404: "Instance doesn't exist",
            409: "Conflict"
        },
        description="Update a Docker instance",
        input=DOCKER_OBJECT_SCHEMA,
        output=DOCKER_OBJECT_SCHEMA)
    def update(request, response):

        docker_manager = Docker.instance()
        container = docker_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])

        props = [
            "name", "console", "aux", "console_type", "console_resolution",
            "console_http_port", "console_http_path", "start_command",
            "environment", "adapters"
        ]

        changed = False
        for prop in props:
            if prop in request.json and request.json[prop] != getattr(container, prop):
                setattr(container, prop, request.json[prop])
                changed = True
        # We don't call container.update for nothing because it will restart the container
        if changed:
            yield from container.update()
        container.updated()
        response.json(container)

    @Route.post(
        r"/projects/{project_id}/docker/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/start_capture",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID",
            "adapter_number": "Adapter to start a packet capture",
            "port_number": "Port on the adapter"
        },
        status_codes={
            200: "Capture started",
            400: "Invalid request",
            404: "Instance doesn't exist",
            409: "Node not started"
        },
        description="Start a packet capture on a Docker container instance",
        input=NODE_CAPTURE_SCHEMA)
    def start_capture(request, response):

        docker_manager = Docker.instance()
        container = docker_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        adapter_number = int(request.match_info["adapter_number"])
        pcap_file_path = os.path.join(container.project.capture_working_directory(), request.json["capture_file_name"])

        yield from container.start_capture(adapter_number, pcap_file_path)
        response.json({"pcap_file_path": str(pcap_file_path)})

    @Route.post(
        r"/projects/{project_id}/docker/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/stop_capture",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID",
            "adapter_number": "Adapter to stop a packet capture",
            "port_number": "Port on the adapter (always 0)"
        },
        status_codes={
            204: "Capture stopped",
            400: "Invalid request",
            404: "Instance doesn't exist",
            409: "Container not started"
        },
        description="Stop a packet capture on a Docker container instance")
    def stop_capture(request, response):

        docker_manager = Docker.instance()
        container = docker_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])

        adapter_number = int(request.match_info["adapter_number"])
        yield from container.stop_capture(adapter_number)
        response.set_status(204)

    @Route.get(
        r"/docker/images",
        status_codes={
            200: "Success",
        },
        output=DOCKER_LIST_IMAGES_SCHEMA,
        description="Get all available Docker images")
    def show(request, response):
        docker_manager = Docker.instance()
        images = yield from docker_manager.list_images()
        response.json(images)
