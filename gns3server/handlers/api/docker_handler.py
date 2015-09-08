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

from ...web.route import Route
from ...modules.docker import Docker

from ...schemas.docker import (
    DOCKER_CREATE_SCHEMA, DOCKER_UPDATE_SCHEMA, DOCKER_CAPTURE_SCHEMA,
    DOCKER_OBJECT_SCHEMA
)


class DockerHandler:
    """API entry points for Docker."""

    @classmethod
    @Route.get(
        r"/docker/images",
        status_codes={
            200: "Success",
        },
        description="Get all available Docker images")
    def show(request, response):
        docker_manager = Docker.instance()
        images = yield from docker_manager.list_images()
        response.json(images)

    @classmethod
    @Route.post(
        r"/projects/{project_id}/docker/images",
        parameters={
            "project_id": "UUID for the project"
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
        container = yield from docker_manager.create_vm(
            request.json.pop("name"),
            request.match_info["project_id"],
            request.json.pop("imagename")
        )
        # FIXME: DO WE NEED THIS?
        for name, value in request.json.items():
            if name != "vm_id":
                if hasattr(container, name) and getattr(container, name) != value:
                    setattr(container, name, value)

        response.set_status(201)
        response.json(container)

    @classmethod
    @Route.post(
        r"/projects/{project_id}/docker/images/{id}/start",
        parameters={
            "project_id": "UUID of the project",
            "id": "ID of the container"
        },
        status_codes={
            204: "Instance started",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Start a Docker container",
        input=DOCKER_CREATE_SCHEMA,
        output=DOCKER_OBJECT_SCHEMA)
    def start(request, response):
        docker_manager = Docker.instance()
        container = docker_manager.get_container(
            request.match_info["id"],
            project_id=request.match_info["project_id"])
        yield from container.start()
        response.set_status(204)

    @classmethod
    @Route.post(
        r"/projects/{project_id}/docker/images/{id}/stop",
        parameters={
            "project_id": "UUID of the project",
            "id": "ID of the container"
        },
        status_codes={
            204: "Instance stopped",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Stop a Docker container",
        input=DOCKER_CREATE_SCHEMA,
        output=DOCKER_OBJECT_SCHEMA)
    def stop(request, response):
        docker_manager = Docker.instance()
        container = docker_manager.get_container(
            request.match_info["id"],
            project_id=request.match_info["project_id"])
        yield from container.stop()
        response.set_status(204)

    @classmethod
    @Route.post(
        r"/projects/{project_id}/docker/images/{id}/reload",
        parameters={
            "project_id": "UUID of the project",
            "id": "ID of the container"
        },
        status_codes={
            204: "Instance restarted",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Restart a Docker container",
        input=DOCKER_CREATE_SCHEMA,
        output=DOCKER_OBJECT_SCHEMA)
    def reload(request, response):
        docker_manager = Docker.instance()
        container = docker_manager.get_container(
            request.match_info["id"],
            project_id=request.match_info["project_id"])
        yield from container.restart()
        response.set_status(204)

    @classmethod
    @Route.delete(
        r"/projects/{project_id}/docker/images/{id}",
        parameters={
            "id": "ID for the container",
            "project_id": "UUID for the project"
        },
        status_codes={
            204: "Instance deleted",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Delete a Docker container")
    def delete(request, response):
        docker_manager = Docker.instance()
        container = docker_manager.get_container(
            request.match_info["id"],
            project_id=request.match_info["project_id"])
        yield from container.remove()
        response.set_status(204)

    @classmethod
    @Route.post(
        r"/projects/{project_id}/docker/images/{id}/suspend",
        parameters={
            "project_id": "UUID of the project",
            "id": "ID of the container"
        },
        status_codes={
            204: "Instance paused",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Pause a Docker container",
        input=DOCKER_CREATE_SCHEMA,
        output=DOCKER_OBJECT_SCHEMA)
    def suspend(request, response):
        docker_manager = Docker.instance()
        container = docker_manager.get_container(
            request.match_info["id"],
            project_id=request.match_info["project_id"])
        yield from container.pause()
        response.set_status(204)
