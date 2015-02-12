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

from ..web.route import Route
from ..schemas.iou import IOU_CREATE_SCHEMA
from ..schemas.iou import IOU_UPDATE_SCHEMA
from ..schemas.iou import IOU_OBJECT_SCHEMA
from ..schemas.iou import IOU_NIO_SCHEMA
from ..modules.iou import IOU


class IOUHandler:

    """
    API entry points for IOU.
    """

    @classmethod
    @Route.post(
        r"/projects/{project_id}/iou/vms",
        parameters={
            "project_id": "UUID for the project"
        },
        status_codes={
            201: "Instance created",
            400: "Invalid request",
            409: "Conflict"
        },
        description="Create a new IOU instance",
        input=IOU_CREATE_SCHEMA,
        output=IOU_OBJECT_SCHEMA)
    def create(request, response):

        iou = IOU.instance()
        vm = yield from iou.create_vm(request.json["name"],
                                      request.match_info["project_id"],
                                      request.json.get("vm_id"),
                                      console=request.json.get("console"),
                                      serial_adapters=request.json.get("serial_adapters"),
                                      ethernet_adapters=request.json.get("ethernet_adapters"),
                                      ram=request.json.get("ram"),
                                      nvram=request.json.get("nvram")
                                      )
        vm.path = request.json.get("path", vm.path)
        vm.iourc_path = request.json.get("iourc_path", vm.iourc_path)
        response.set_status(201)
        response.json(vm)

    @classmethod
    @Route.get(
        r"/projects/{project_id}/iou/vms/{vm_id}",
        parameters={
            "project_id": "UUID for the project",
            "vm_id": "UUID for the instance"
        },
        status_codes={
            200: "Success",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Get a IOU instance",
        output=IOU_OBJECT_SCHEMA)
    def show(request, response):

        iou_manager = IOU.instance()
        vm = iou_manager.get_vm(request.match_info["vm_id"], project_id=request.match_info["project_id"])
        response.json(vm)

    @classmethod
    @Route.put(
        r"/projects/{project_id}/iou/vms/{vm_id}",
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
        description="Update a IOU instance",
        input=IOU_UPDATE_SCHEMA,
        output=IOU_OBJECT_SCHEMA)
    def update(request, response):

        iou_manager = IOU.instance()
        vm = iou_manager.get_vm(request.match_info["vm_id"], project_id=request.match_info["project_id"])
        vm.name = request.json.get("name", vm.name)
        vm.console = request.json.get("console", vm.console)
        vm.path = request.json.get("path", vm.path)
        vm.iourc_path = request.json.get("iourc_path", vm.iourc_path)
        vm.ethernet_adapters = request.json.get("ethernet_adapters", vm.ethernet_adapters)
        vm.serial_adapters = request.json.get("serial_adapters", vm.serial_adapters)
        vm.ram = request.json.get("ram", vm.ram)
        vm.nvram = request.json.get("nvram", vm.nvram)

        response.json(vm)

    @classmethod
    @Route.delete(
        r"/projects/{project_id}/iou/vms/{vm_id}",
        parameters={
            "project_id": "UUID for the project",
            "vm_id": "UUID for the instance"
        },
        status_codes={
            204: "Instance deleted",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Delete a IOU instance")
    def delete(request, response):

        yield from IOU.instance().delete_vm(request.match_info["vm_id"])
        response.set_status(204)

    @classmethod
    @Route.post(
        r"/projects/{project_id}/iou/vms/{vm_id}/start",
        parameters={
            "project_id": "UUID for the project",
            "vm_id": "UUID for the instance"
        },
        status_codes={
            204: "Instance started",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Start a IOU instance")
    def start(request, response):

        iou_manager = IOU.instance()
        vm = iou_manager.get_vm(request.match_info["vm_id"], project_id=request.match_info["project_id"])
        yield from vm.start()
        response.set_status(204)

    @classmethod
    @Route.post(
        r"/projects/{project_id}/iou/vms/{vm_id}/stop",
        parameters={
            "project_id": "UUID for the project",
            "vm_id": "UUID for the instance"
        },
        status_codes={
            204: "Instance stopped",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Stop a IOU instance")
    def stop(request, response):

        iou_manager = IOU.instance()
        vm = iou_manager.get_vm(request.match_info["vm_id"], project_id=request.match_info["project_id"])
        yield from vm.stop()
        response.set_status(204)

    @classmethod
    @Route.post(
        r"/projects/{project_id}/iou/vms/{vm_id}/reload",
        parameters={
            "project_id": "UUID for the project",
            "vm_id": "UUID for the instance",
        },
        status_codes={
            204: "Instance reloaded",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Reload a IOU instance")
    def reload(request, response):

        iou_manager = IOU.instance()
        vm = iou_manager.get_vm(request.match_info["vm_id"], project_id=request.match_info["project_id"])
        yield from vm.reload()
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/iou/vms/{vm_id}/ports/{port_number:\d+}/nio",
        parameters={
            "project_id": "UUID for the project",
            "vm_id": "UUID for the instance",
            "port_number": "Port where the nio should be added"
        },
        status_codes={
            201: "NIO created",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Add a NIO to a IOU instance",
        input=IOU_NIO_SCHEMA,
        output=IOU_NIO_SCHEMA)
    def create_nio(request, response):

        iou_manager = IOU.instance()
        vm = iou_manager.get_vm(request.match_info["vm_id"], project_id=request.match_info["project_id"])
        nio = iou_manager.create_nio(vm.iouyap_path, request.json)
        vm.slot_add_nio_binding(0, int(request.match_info["port_number"]), nio)
        response.set_status(201)
        response.json(nio)

    @classmethod
    @Route.delete(
        r"/projects/{project_id}/iou/vms/{vm_id}/ports/{port_number:\d+}/nio",
        parameters={
            "project_id": "UUID for the project",
            "vm_id": "UUID for the instance",
            "port_number": "Port from where the nio should be removed"
        },
        status_codes={
            204: "NIO deleted",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Remove a NIO from a IOU instance")
    def delete_nio(request, response):

        iou_manager = IOU.instance()
        vm = iou_manager.get_vm(request.match_info["vm_id"], project_id=request.match_info["project_id"])
        vm.slot_remove_nio_binding(0, int(request.match_info["port_number"]))
        response.set_status(204)
