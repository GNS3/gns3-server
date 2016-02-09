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
import sys
import base64

from ...web.route import Route
from ...schemas.nio import NIO_SCHEMA
from ...schemas.vm import VM_LIST_IMAGES_SCHEMA
from ...schemas.dynamips_vm import VM_CREATE_SCHEMA
from ...schemas.dynamips_vm import VM_UPDATE_SCHEMA
from ...schemas.dynamips_vm import VM_OBJECT_SCHEMA
from ...schemas.dynamips_vm import VM_CONFIGS_SCHEMA
from ...schemas.vm import VM_CAPTURE_SCHEMA
from ...modules.dynamips import Dynamips
from ...modules.dynamips.dynamips_error import DynamipsError
from ...modules.project_manager import ProjectManager

DEFAULT_CHASSIS = {
    "c1700": "1720",
    "c2600": "2610",
    "c3600": "3640"
}


class DynamipsVMHandler:

    """
    API entry points for Dynamips VMs.
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
        platform = request.json.pop("platform")
        default_chassis = None
        if platform in DEFAULT_CHASSIS:
            default_chassis = DEFAULT_CHASSIS[platform]
        vm = yield from dynamips_manager.create_vm(request.json.pop("name"),
                                                   request.match_info["project_id"],
                                                   request.json.get("vm_id"),
                                                   request.json.get("dynamips_id"),
                                                   platform,
                                                   console=request.json.get("console"),
                                                   aux=request.json.get("aux"),
                                                   chassis=request.json.pop("chassis", default_chassis))

        yield from dynamips_manager.update_vm_settings(vm, request.json)
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

        yield from dynamips_manager.update_vm_settings(vm, request.json)
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
        try:
            yield from dynamips_manager.ghost_ios_support(vm)
        except GeneratorExit:
            pass
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
    def resume(request, response):

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

    @Route.post(
        r"/projects/{project_id}/dynamips/vms/{vm_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio",
        parameters={
            "project_id": "UUID for the project",
            "vm_id": "UUID for the instance",
            "adapter_number": "Adapter where the nio should be added",
            "port_number": "Port on the adapter"
        },
        status_codes={
            201: "NIO created",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Add a NIO to a Dynamips VM instance",
        input=NIO_SCHEMA,
        output=NIO_SCHEMA)
    def create_nio(request, response):

        dynamips_manager = Dynamips.instance()
        vm = dynamips_manager.get_vm(request.match_info["vm_id"], project_id=request.match_info["project_id"])
        nio = yield from dynamips_manager.create_nio(vm, request.json)
        slot_number = int(request.match_info["adapter_number"])
        port_number = int(request.match_info["port_number"])
        yield from vm.slot_add_nio_binding(slot_number, port_number, nio)
        response.set_status(201)
        response.json(nio)

    @classmethod
    @Route.delete(
        r"/projects/{project_id}/dynamips/vms/{vm_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio",
        parameters={
            "project_id": "UUID for the project",
            "vm_id": "UUID for the instance",
            "adapter_number": "Adapter from where the nio should be removed",
            "port_number": "Port on the adapter"
        },
        status_codes={
            204: "NIO deleted",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Remove a NIO from a Dynamips VM instance")
    def delete_nio(request, response):

        dynamips_manager = Dynamips.instance()
        vm = dynamips_manager.get_vm(request.match_info["vm_id"], project_id=request.match_info["project_id"])
        slot_number = int(request.match_info["adapter_number"])
        port_number = int(request.match_info["port_number"])
        nio = yield from vm.slot_remove_nio_binding(slot_number, port_number)
        yield from nio.delete()
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/dynamips/vms/{vm_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/start_capture",
        parameters={
            "project_id": "UUID for the project",
            "vm_id": "UUID for the instance",
            "adapter_number": "Adapter to start a packet capture",
            "port_number": "Port on the adapter"
        },
        status_codes={
            200: "Capture started",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Start a packet capture on a Dynamips VM instance",
        input=VM_CAPTURE_SCHEMA)
    def start_capture(request, response):

        dynamips_manager = Dynamips.instance()
        vm = dynamips_manager.get_vm(request.match_info["vm_id"], project_id=request.match_info["project_id"])
        slot_number = int(request.match_info["adapter_number"])
        port_number = int(request.match_info["port_number"])
        pcap_file_path = os.path.join(vm.project.capture_working_directory(), request.json["capture_file_name"])

        if sys.platform.startswith('win'):
            # FIXME: Dynamips (Cygwin actually) doesn't like non ascii paths on Windows
            try:
                pcap_file_path.encode('ascii')
            except UnicodeEncodeError:
                raise DynamipsError('The capture file path "{}" must only contain ASCII (English) characters'.format(pcap_file_path))

        yield from vm.start_capture(slot_number, port_number, pcap_file_path, request.json["data_link_type"])
        response.json({"pcap_file_path": pcap_file_path})

    @Route.post(
        r"/projects/{project_id}/dynamips/vms/{vm_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/stop_capture",
        parameters={
            "project_id": "UUID for the project",
            "vm_id": "UUID for the instance",
            "adapter_number": "Adapter to stop a packet capture",
            "port_number": "Port on the adapter (always 0)"
        },
        status_codes={
            204: "Capture stopped",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Stop a packet capture on a Dynamips VM instance")
    def stop_capture(request, response):

        dynamips_manager = Dynamips.instance()
        vm = dynamips_manager.get_vm(request.match_info["vm_id"], project_id=request.match_info["project_id"])
        slot_number = int(request.match_info["adapter_number"])
        port_number = int(request.match_info["port_number"])
        yield from vm.stop_capture(slot_number, port_number)
        response.set_status(204)

    @Route.get(
        r"/projects/{project_id}/dynamips/vms/{vm_id}/configs",
        status_codes={
            200: "Configs retrieved",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        output=VM_CONFIGS_SCHEMA,
        description="Retrieve the startup and private configs content")
    def get_configs(request, response):

        dynamips_manager = Dynamips.instance()
        vm = dynamips_manager.get_vm(request.match_info["vm_id"],
                                     project_id=request.match_info["project_id"])

        startup_config_base64, private_config_base64 = yield from vm.extract_config()
        module_workdir = vm.project.module_working_directory(dynamips_manager.module_name.lower())
        result = {}
        if startup_config_base64:
            startup_config_content = base64.b64decode(startup_config_base64).decode("utf-8", errors='replace')
            result["startup_config_content"] = startup_config_content
        else:
            # nvram doesn't contain anything if the router has not been started at least once
            # in this case just use the startup-config file
            if vm.startup_config:
                startup_config_path = os.path.join(module_workdir, vm.startup_config)
                if os.path.isfile(startup_config_path):
                    try:
                        with open(startup_config_path, "rb") as f:
                            content = f.read().decode("utf-8", errors='replace')
                            if content:
                                result["startup_config_content"] = content
                    except OSError as e:
                        raise DynamipsError("Could not read the startup-config {}: {}".format(startup_config_path, e))

        if private_config_base64:
            private_config_content = base64.b64decode(private_config_base64).decode("utf-8", errors='replace')
            result["private_config_content"] = private_config_content
        else:
            # nvram doesn't contain anything if the router has not been started at least once
            # in this case just use the private-config file
            if vm.private_config:
                private_config_path = os.path.join(module_workdir, vm.private_config)
                if os.path.isfile(private_config_path):
                    try:
                        with open(private_config_path, "rb") as f:
                            content = f.read().decode("utf-8", errors='replace')
                            if content:
                                result["private_config_content"] = content
                    except OSError as e:
                        raise DynamipsError("Could not read the private-config {}: {}".format(private_config_path, e))

        response.set_status(200)
        response.json(result)

    @Route.post(
        r"/projects/{project_id}/dynamips/vms/{vm_id}/configs/save",
        status_codes={
            200: "Configs saved",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Save the startup and private configs content")
    def save_configs(request, response):

        dynamips_manager = Dynamips.instance()
        vm = dynamips_manager.get_vm(request.match_info["vm_id"],
                                     project_id=request.match_info["project_id"])

        yield from vm.save_configs()
        response.set_status(200)

    @Route.get(
        r"/projects/{project_id}/dynamips/vms/{vm_id}/idlepc_proposals",
        status_codes={
            200: "Idle-PCs retrieved",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Retrieve the idlepc proposals")
    def get_idlepcs(request, response):

        dynamips_manager = Dynamips.instance()
        vm = dynamips_manager.get_vm(request.match_info["vm_id"],
                                     project_id=request.match_info["project_id"])

        yield from vm.set_idlepc("0x0")
        idlepcs = yield from vm.get_idle_pc_prop()
        response.set_status(200)
        response.json(idlepcs)

    @Route.get(
        r"/projects/{project_id}/dynamips/vms/{vm_id}/auto_idlepc",
        status_codes={
            200: "Best Idle-pc value found",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Retrieve the idlepc proposals")
    def get_auto_idlepc(request, response):

        dynamips_manager = Dynamips.instance()
        vm = dynamips_manager.get_vm(request.match_info["vm_id"],
                                     project_id=request.match_info["project_id"])
        idlepc = yield from dynamips_manager.auto_idlepc(vm)
        response.set_status(200)
        response.json({"idlepc": idlepc})

    @Route.get(
        r"/dynamips/vms",
        status_codes={
            200: "List of Dynamips VM retrieved",
        },
        description="Retrieve the list of Dynamips VMS",
        output=VM_LIST_IMAGES_SCHEMA)
    def list_vms(request, response):

        dynamips_manager = Dynamips.instance()
        vms = yield from dynamips_manager.list_images()
        response.set_status(200)
        response.json(vms)

    @Route.post(
        r"/dynamips/vms/{path}",
        status_codes={
            204: "Image uploaded",
        },
        raw=True,
        description="Upload Dynamips image.")
    def upload_vm(request, response):

        dynamips_manager = Dynamips.instance()
        yield from dynamips_manager.write_image(request.match_info["path"], request.content)
        response.set_status(204)
