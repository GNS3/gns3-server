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

from aiohttp.web import HTTPConflict
from ...web.route import Route
from ...schemas.nio import NIO_SCHEMA
from ...schemas.qemu import QEMU_CREATE_SCHEMA
from ...schemas.qemu import QEMU_UPDATE_SCHEMA
from ...schemas.qemu import QEMU_OBJECT_SCHEMA
from ...schemas.qemu import QEMU_BINARY_LIST_SCHEMA
from ...modules.qemu import Qemu


class QEMUHandler:

    """
    API entry points for QEMU.
    """

    @classmethod
    @Route.post(
        r"/projects/{project_id}/qemu/vms",
        parameters={
            "project_id": "UUID for the project"
        },
        status_codes={
            201: "Instance created",
            400: "Invalid request",
            409: "Conflict"
        },
        description="Create a new Qemu VM instance",
        input=QEMU_CREATE_SCHEMA,
        output=QEMU_OBJECT_SCHEMA)
    def create(request, response):

        qemu = Qemu.instance()
        vm = yield from qemu.create_vm(request.json.pop("name"),
                                       request.match_info["project_id"],
                                       request.json.get("vm_id"),
                                       qemu_path=request.json.get("qemu_path"),
                                       console=request.json.get("console"))

        for name, value in request.json.items():
            if hasattr(vm, name) and getattr(vm, name) != value:
                setattr(vm, name, value)

        response.set_status(201)
        response.json(vm)

    @classmethod
    @Route.get(
        r"/projects/{project_id}/qemu/vms/{vm_id}",
        parameters={
            "project_id": "UUID for the project",
            "vm_id": "UUID for the instance"
        },
        status_codes={
            200: "Success",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Get a Qemu VM instance",
        output=QEMU_OBJECT_SCHEMA)
    def show(request, response):

        qemu_manager = Qemu.instance()
        vm = qemu_manager.get_vm(request.match_info["vm_id"], project_id=request.match_info["project_id"])
        response.json(vm)

    @classmethod
    @Route.put(
        r"/projects/{project_id}/qemu/vms/{vm_id}",
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
        description="Update a Qemu VM instance",
        input=QEMU_UPDATE_SCHEMA,
        output=QEMU_OBJECT_SCHEMA)
    def update(request, response):

        qemu_manager = Qemu.instance()
        vm = qemu_manager.get_vm(request.match_info["vm_id"], project_id=request.match_info["project_id"])

        for name, value in request.json.items():
            if hasattr(vm, name) and getattr(vm, name) != value:
                setattr(vm, name, value)

        response.json(vm)

    @classmethod
    @Route.delete(
        r"/projects/{project_id}/qemu/vms/{vm_id}",
        parameters={
            "project_id": "UUID for the project",
            "vm_id": "UUID for the instance"
        },
        status_codes={
            204: "Instance deleted",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Delete a Qemu VM instance")
    def delete(request, response):

        yield from Qemu.instance().delete_vm(request.match_info["vm_id"])
        response.set_status(204)

    @classmethod
    @Route.post(
        r"/projects/{project_id}/qemu/vms/{vm_id}/start",
        parameters={
            "project_id": "UUID for the project",
            "vm_id": "UUID for the instance"
        },
        status_codes={
            204: "Instance started",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Start a Qemu VM instance")
    def start(request, response):

        qemu_manager = Qemu.instance()
        vm = qemu_manager.get_vm(request.match_info["vm_id"], project_id=request.match_info["project_id"])
        yield from vm.start()
        response.set_status(204)

    @classmethod
    @Route.post(
        r"/projects/{project_id}/qemu/vms/{vm_id}/stop",
        parameters={
            "project_id": "UUID for the project",
            "vm_id": "UUID for the instance"
        },
        status_codes={
            204: "Instance stopped",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Stop a Qemu VM instance")
    def stop(request, response):

        qemu_manager = Qemu.instance()
        vm = qemu_manager.get_vm(request.match_info["vm_id"], project_id=request.match_info["project_id"])
        yield from vm.stop()
        response.set_status(204)

    @classmethod
    @Route.post(
        r"/projects/{project_id}/qemu/vms/{vm_id}/reload",
        parameters={
            "project_id": "UUID for the project",
            "vm_id": "UUID for the instance",
        },
        status_codes={
            204: "Instance reloaded",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Reload a Qemu VM instance")
    def reload(request, response):

        qemu_manager = Qemu.instance()
        vm = qemu_manager.get_vm(request.match_info["vm_id"], project_id=request.match_info["project_id"])
        yield from vm.reload()
        response.set_status(204)

    @classmethod
    @Route.post(
        r"/projects/{project_id}/qemu/vms/{vm_id}/suspend",
        parameters={
            "project_id": "UUID for the project",
            "vm_id": "UUID for the instance",
        },
        status_codes={
            204: "Instance suspended",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Suspend a Qemu VM instance")
    def suspend(request, response):

        qemu_manager = Qemu.instance()
        vm = qemu_manager.get_vm(request.match_info["vm_id"], project_id=request.match_info["project_id"])
        yield from vm.suspend()
        response.set_status(204)

    @classmethod
    @Route.post(
        r"/projects/{project_id}/qemu/vms/{vm_id}/resume",
        parameters={
            "project_id": "UUID for the project",
            "vm_id": "UUID for the instance",
        },
        status_codes={
            204: "Instance resumed",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Resume a Qemu VM instance")
    def resume(request, response):

        qemu_manager = Qemu.instance()
        vm = qemu_manager.get_vm(request.match_info["vm_id"], project_id=request.match_info["project_id"])
        yield from vm.resume()
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/qemu/vms/{vm_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio",
        parameters={
            "project_id": "UUID for the project",
            "vm_id": "UUID for the instance",
            "adapter_number": "Network adapter where the nio is located",
            "port_number": "Port on the adapter (always 0)"
        },
        status_codes={
            201: "NIO created",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Add a NIO to a Qemu VM instance",
        input=NIO_SCHEMA,
        output=NIO_SCHEMA)
    def create_nio(request, response):

        qemu_manager = Qemu.instance()
        vm = qemu_manager.get_vm(request.match_info["vm_id"], project_id=request.match_info["project_id"])
        nio_type = request.json["type"]
        if nio_type not in ("nio_udp", "nio_tap", "nio_nat"):
            raise HTTPConflict(text="NIO of type {} is not supported".format(nio_type))
        nio = qemu_manager.create_nio(vm.qemu_path, request.json)
        yield from vm.adapter_add_nio_binding(int(request.match_info["adapter_number"]), nio)
        response.set_status(201)
        response.json(nio)

    @classmethod
    @Route.delete(
        r"/projects/{project_id}/qemu/vms/{vm_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio",
        parameters={
            "project_id": "UUID for the project",
            "vm_id": "UUID for the instance",
            "adapter_number": "Network adapter where the nio is located",
            "port_number": "Port on the adapter (always 0)"
        },
        status_codes={
            204: "NIO deleted",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Remove a NIO from a Qemu VM instance")
    def delete_nio(request, response):

        qemu_manager = Qemu.instance()
        vm = qemu_manager.get_vm(request.match_info["vm_id"], project_id=request.match_info["project_id"])
        yield from vm.adapter_remove_nio_binding(int(request.match_info["adapter_number"]))
        response.set_status(204)

    @classmethod
    @Route.get(
        r"/qemu/binaries",
        status_codes={
            200: "Success",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Get a list of available Qemu binaries",
        output=QEMU_BINARY_LIST_SCHEMA)
    def list_binaries(request, response):

        binaries = yield from Qemu.binary_list()
        response.json(binaries)
