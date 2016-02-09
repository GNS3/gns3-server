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

from ...web.route import Route
from ...schemas.nio import NIO_SCHEMA
from ...schemas.iou import IOU_CREATE_SCHEMA
from ...schemas.iou import IOU_START_SCHEMA
from ...schemas.iou import IOU_UPDATE_SCHEMA
from ...schemas.iou import IOU_OBJECT_SCHEMA
from ...schemas.iou import IOU_CONFIGS_SCHEMA
from ...schemas.vm import VM_LIST_IMAGES_SCHEMA
from ...schemas.vm import VM_CAPTURE_SCHEMA
from ...modules.iou import IOU


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
        vm = yield from iou.create_vm(request.json.pop("name"),
                                      request.match_info["project_id"],
                                      request.json.get("vm_id"),
                                      console=request.json.get("console"))

        for name, value in request.json.items():
            if hasattr(vm, name) and getattr(vm, name) != value:
                if name == "startup_config_content" and (vm.startup_config_content and len(vm.startup_config_content) > 0):
                    continue
                if name == "private_config_content" and (vm.private_config_content and len(vm.private_config_content) > 0):
                    continue
                setattr(vm, name, value)
        if "startup_config_content" in request.json:
            vm.startup_config = request.json.get("startup_config_content")
        if "private_config_content" in request.json:
            vm.private_config = request.json.get("private_config_content")
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

        for name, value in request.json.items():
            if hasattr(vm, name) and getattr(vm, name) != value:
                setattr(vm, name, value)
        if "startup_config_content" in request.json:
            vm.startup_config = request.json.get("startup_config_content")
        if "private_config_content" in request.json:
            vm.private_config = request.json.get("private_config_content")
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
            200: "Instance started",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        input=IOU_START_SCHEMA,
        output=IOU_OBJECT_SCHEMA,
        description="Start a IOU instance")
    def start(request, response):

        iou_manager = IOU.instance()
        vm = iou_manager.get_vm(request.match_info["vm_id"], project_id=request.match_info["project_id"])

        for name, value in request.json.items():
            if hasattr(vm, name) and getattr(vm, name) != value:
                setattr(vm, name, value)
                print(name)
                print(vm.iourc_path)

        yield from vm.start()
        response.json(vm)

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
        r"/projects/{project_id}/iou/vms/{vm_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio",
        parameters={
            "project_id": "UUID for the project",
            "vm_id": "UUID for the instance",
            "adapter_number": "Network adapter where the nio is located",
            "port_number": "Port where the nio should be added"
        },
        status_codes={
            201: "NIO created",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Add a NIO to a IOU instance",
        input=NIO_SCHEMA,
        output=NIO_SCHEMA)
    def create_nio(request, response):

        iou_manager = IOU.instance()
        vm = iou_manager.get_vm(request.match_info["vm_id"], project_id=request.match_info["project_id"])
        nio_type = request.json["type"]
        if nio_type not in ("nio_udp", "nio_tap", "nio_generic_ethernet"):
            raise HTTPConflict(text="NIO of type {} is not supported".format(nio_type))
        nio = iou_manager.create_nio(vm.iouyap_path, request.json)
        yield from vm.adapter_add_nio_binding(int(request.match_info["adapter_number"]), int(request.match_info["port_number"]), nio)
        response.set_status(201)
        response.json(nio)

    @classmethod
    @Route.delete(
        r"/projects/{project_id}/iou/vms/{vm_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio",
        parameters={
            "project_id": "UUID for the project",
            "vm_id": "UUID for the instance",
            "adapter_number": "Network adapter where the nio is located",
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
        yield from vm.adapter_remove_nio_binding(int(request.match_info["adapter_number"]), int(request.match_info["port_number"]))
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/iou/vms/{vm_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/start_capture",
        parameters={
            "project_id": "UUID for the project",
            "vm_id": "UUID for the instance",
            "adapter_number": "Adapter to start a packet capture",
            "port_number": "Port on the adapter"
        },
        status_codes={
            200: "Capture started",
            400: "Invalid request",
            404: "Instance doesn't exist",
            409: "VM not started"
        },
        description="Start a packet capture on a IOU VM instance",
        input=VM_CAPTURE_SCHEMA)
    def start_capture(request, response):

        iou_manager = IOU.instance()
        vm = iou_manager.get_vm(request.match_info["vm_id"], project_id=request.match_info["project_id"])
        adapter_number = int(request.match_info["adapter_number"])
        port_number = int(request.match_info["port_number"])
        pcap_file_path = os.path.join(vm.project.capture_working_directory(), request.json["capture_file_name"])

        if not vm.is_running():
            raise HTTPConflict(text="Cannot capture traffic on a non started VM")
        yield from vm.start_capture(adapter_number, port_number, pcap_file_path, request.json["data_link_type"])
        response.json({"pcap_file_path": str(pcap_file_path)})

    @Route.post(
        r"/projects/{project_id}/iou/vms/{vm_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/stop_capture",
        parameters={
            "project_id": "UUID for the project",
            "vm_id": "UUID for the instance",
            "adapter_number": "Adapter to stop a packet capture",
            "port_number": "Port on the adapter (always 0)"
        },
        status_codes={
            204: "Capture stopped",
            400: "Invalid request",
            404: "Instance doesn't exist",
            409: "VM not started"
        },
        description="Stop a packet capture on a IOU VM instance")
    def stop_capture(request, response):

        iou_manager = IOU.instance()
        vm = iou_manager.get_vm(request.match_info["vm_id"], project_id=request.match_info["project_id"])

        if not vm.is_running():
            raise HTTPConflict(text="Cannot capture traffic on a non started VM")

        adapter_number = int(request.match_info["adapter_number"])
        port_number = int(request.match_info["port_number"])
        yield from vm.stop_capture(adapter_number, port_number)
        response.set_status(204)

    @Route.get(
        r"/projects/{project_id}/iou/vms/{vm_id}/configs",
        status_codes={
            200: "Configs retrieved",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        output=IOU_CONFIGS_SCHEMA,
        description="Retrieve the startup and private configs content")
    def get_configs(request, response):

        iou_manager = IOU.instance()
        vm = iou_manager.get_vm(request.match_info["vm_id"], project_id=request.match_info["project_id"])

        startup_config_content, private_config_content = vm.extract_configs()
        result = {}
        if startup_config_content:
            result["startup_config_content"] = startup_config_content.decode("utf-8", errors='replace')
        else:
            # nvram doesn't exists if the VM has not been started at least once
            # in this case just use the startup-config file
            startup_config_content = vm.startup_config_content
            if startup_config_content:
                result["startup_config_content"] = startup_config_content

        if private_config_content:
            result["private_config_content"] = private_config_content.decode("utf-8", errors='replace')
        else:
            # nvram doesn't exists if the VM has not been started at least once
            # in this case just use the private-config file
            private_config_content = vm.private_config_content
            if private_config_content:
                result["private_config_content"] = private_config_content

        response.set_status(200)
        response.json(result)

    @Route.post(
        r"/projects/{project_id}/iou/vms/{vm_id}/configs/save",
        status_codes={
            200: "Configs saved",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Save the startup and private configs content")
    def save_configs(request, response):

        iou_manager = IOU.instance()
        vm = iou_manager.get_vm(request.match_info["vm_id"], project_id=request.match_info["project_id"])
        vm.save_configs()
        response.set_status(200)

    @Route.get(
        r"/iou/vms",
        status_codes={
            200: "List of IOU VM retrieved",
        },
        description="Retrieve the list of IOU VMS",
        output=VM_LIST_IMAGES_SCHEMA)
    def list_vms(request, response):

        iou_manager = IOU.instance()
        vms = yield from iou_manager.list_images()
        response.set_status(200)
        response.json(vms)

    @Route.post(
        r"/iou/vms/{path}",
        status_codes={
            204: "Image uploaded",
        },
        raw=True,
        description="Upload IOU image.")
    def upload_vm(request, response):

        iou_manager = IOU.instance()
        yield from iou_manager.write_image(request.match_info["path"], request.content)
        response.set_status(204)
