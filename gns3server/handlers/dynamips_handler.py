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


import asyncio
from ..web.route import Route
from ..schemas.dynamips import VM_CREATE_SCHEMA
from ..schemas.dynamips import VM_UPDATE_SCHEMA
from ..schemas.dynamips import VM_OBJECT_SCHEMA
from ..modules.dynamips import Dynamips
from ..modules.project_manager import ProjectManager


class DynamipsHandler:

    """
    API entry points for Dynamips.
    """

    @classmethod
    @Route.post(
        r"/projects/{project_id}/dynamips/vms",
        parameters={
            "project_id": "UUID for the project"
        },
        status_codes={
            201: "Instance created",
            400: "Invalid request",
            409: "Conflict"
        },
        description="Create a new Dynamips VM instance",
        input=VM_CREATE_SCHEMA,
        output=VM_OBJECT_SCHEMA)
    def create(request, response):

        dynamips_manager = Dynamips.instance()
        vm = yield from dynamips_manager.create_vm(request.json.pop("name"),
                                                   request.match_info["project_id"],
                                                   request.json.get("vm_id"),
                                                   request.json.get("dynamips_id"),
                                                   request.json.pop("platform"))

        # set VM options
        for name, value in request.json.items():
            if hasattr(vm, name) and getattr(vm, name) != value:
                setter = getattr(vm, "set_{}".format(name))
                if asyncio.iscoroutinefunction(vm.close):
                    yield from setter(value)
                else:
                    setter(value)

        response.set_status(201)
        response.json(vm)

    @classmethod
    @Route.get(
        r"/projects/{project_id}/dynamips/vms/{vm_id}",
        parameters={
            "project_id": "UUID for the project",
            "vm_id": "UUID for the instance"
        },
        status_codes={
            200: "Success",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Get a Dynamips VM instance",
        output=VM_OBJECT_SCHEMA)
    def show(request, response):

        dynamips_manager = Dynamips.instance()
        vm = dynamips_manager.get_vm(request.match_info["vm_id"], project_id=request.match_info["project_id"])
        response.json(vm)

    @classmethod
    @Route.put(
        r"/projects/{project_id}/dynamips/vms/{vm_id}",
        parameters={
            "project_id": "UUID for the project",
            "vm_id": "UUID for the instance"
        },
        status_codes={
            200: "Instance updated",
            400: "Invalid request",
            404: "Instance doesn't exist",
            409: "Conflict"
        },
        description="Update a Dynamips VM instance",
        input=VM_UPDATE_SCHEMA,
        output=VM_OBJECT_SCHEMA)
    def update(request, response):

        dynamips_manager = Dynamips.instance()
        vm = dynamips_manager.get_vm(request.match_info["vm_id"], project_id=request.match_info["project_id"])

        # FIXME: set options
        #for name, value in request.json.items():
        #    if hasattr(vm, name) and getattr(vm, name) != value:
        #        setattr(vm, name, value)
        response.json(vm)

    @classmethod
    @Route.delete(
        r"/projects/{project_id}/dynamips/vms/{vm_id}",
        parameters={
            "project_id": "UUID for the project",
            "vm_id": "UUID for the instance"
        },
        status_codes={
            204: "Instance deleted",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Delete a Dynamips VM instance")
    def delete(request, response):

        # check the project_id exists
        ProjectManager.instance().get_project(request.match_info["project_id"])

        yield from Dynamips.instance().delete_vm(request.match_info["vm_id"])
        response.set_status(204)

    @classmethod
    @Route.post(
        r"/projects/{project_id}/dynamips/vms/{vm_id}/start",
        parameters={
            "project_id": "UUID for the project",
            "vm_id": "UUID for the instance"
        },
        status_codes={
            204: "Instance started",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Start a Dynamips VM instance")
    def start(request, response):

        dynamips_manager = Dynamips.instance()
        vm = dynamips_manager.get_vm(request.match_info["vm_id"], project_id=request.match_info["project_id"])
        yield from vm.start()
        response.set_status(204)

    @classmethod
    @Route.post(
        r"/projects/{project_id}/dynamips/vms/{vm_id}/stop",
        parameters={
            "project_id": "UUID for the project",
            "vm_id": "UUID for the instance"
        },
        status_codes={
            204: "Instance stopped",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Stop a Dynamips VM instance")
    def stop(request, response):

        dynamips_manager = Dynamips.instance()
        vm = dynamips_manager.get_vm(request.match_info["vm_id"], project_id=request.match_info["project_id"])
        yield from vm.stop()
        response.set_status(204)

    @classmethod
    @Route.post(
        r"/projects/{project_id}/dynamips/vms/{vm_id}/suspend",
        parameters={
            "project_id": "UUID for the project",
            "vm_id": "UUID for the instance"
        },
        status_codes={
            204: "Instance suspended",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Suspend a Dynamips VM instance")
    def suspend(request, response):

        dynamips_manager = Dynamips.instance()
        vm = dynamips_manager.get_vm(request.match_info["vm_id"], project_id=request.match_info["project_id"])
        yield from vm.suspend()
        response.set_status(204)

    @classmethod
    @Route.post(
        r"/projects/{project_id}/dynamips/vms/{vm_id}/resume",
        parameters={
            "project_id": "UUID for the project",
            "vm_id": "UUID for the instance"
        },
        status_codes={
            204: "Instance resumed",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Resume a suspended Dynamips VM instance")
    def suspend(request, response):

        dynamips_manager = Dynamips.instance()
        vm = dynamips_manager.get_vm(request.match_info["vm_id"], project_id=request.match_info["project_id"])
        yield from vm.resume()
        response.set_status(204)

    @classmethod
    @Route.post(
        r"/projects/{project_id}/dynamips/vms/{vm_id}/reload",
        parameters={
            "project_id": "UUID for the project",
            "vm_id": "UUID for the instance"
        },
        status_codes={
            204: "Instance reloaded",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Reload a Dynamips VM instance")
    def reload(request, response):

        dynamips_manager = Dynamips.instance()
        vm = dynamips_manager.get_vm(request.match_info["vm_id"], project_id=request.match_info["project_id"])
        yield from vm.reload()
        response.set_status(204)
