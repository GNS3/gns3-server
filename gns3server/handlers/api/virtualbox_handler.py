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
from ...schemas.virtualbox import VBOX_CREATE_SCHEMA
from ...schemas.virtualbox import VBOX_UPDATE_SCHEMA
from ...schemas.virtualbox import VBOX_OBJECT_SCHEMA
from ...schemas.vm import VM_CAPTURE_SCHEMA
from ...modules.virtualbox import VirtualBox
from ...modules.project_manager import ProjectManager


class VirtualBoxHandler:

    """
    API entry points for VirtualBox.
    """

    @classmethod
    @Route.get(
        r"/virtualbox/vms",
        status_codes={
            200: "Success",
        },
        description="Get all VirtualBox VMs available")
    def index(request, response):

        vbox_manager = VirtualBox.instance()
        vms = yield from vbox_manager.list_images()
        response.json(vms)

    @classmethod
    @Route.post(
        r"/projects/{project_id}/virtualbox/vms",
        parameters={
            "project_id": "UUID for the project"
        },
        status_codes={
            201: "Instance created",
            400: "Invalid request",
            409: "Conflict"
        },
        description="Create a new VirtualBox VM instance",
        input=VBOX_CREATE_SCHEMA,
        output=VBOX_OBJECT_SCHEMA)
    def create(request, response):

        vbox_manager = VirtualBox.instance()
        vm = yield from vbox_manager.create_vm(request.json.pop("name"),
                                               request.match_info["project_id"],
                                               request.json.get("vm_id"),
                                               request.json.pop("vmname"),
                                               request.json.pop("linked_clone"),
                                               console=request.json.get("console", None),
                                               adapters=request.json.get("adapters", 0))

        if "enable_remote_console" in request.json:
            yield from vm.set_enable_remote_console(request.json.pop("enable_remote_console"))

        if "ram" in request.json:
            ram = request.json.pop("ram")
            if ram != vm.ram:
                yield from vm.set_ram(ram)

        for name, value in request.json.items():
            if name != "vm_id":
                if hasattr(vm, name) and getattr(vm, name) != value:
                    setattr(vm, name, value)

        response.set_status(201)
        response.json(vm)

    @classmethod
    @Route.get(
        r"/projects/{project_id}/virtualbox/vms/{vm_id}",
        parameters={
            "project_id": "UUID for the project",
            "vm_id": "UUID for the instance"
        },
        status_codes={
            200: "Success",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Get a VirtualBox VM instance",
        output=VBOX_OBJECT_SCHEMA)
    def show(request, response):

        vbox_manager = VirtualBox.instance()
        vm = vbox_manager.get_vm(request.match_info["vm_id"], project_id=request.match_info["project_id"])
        response.json(vm)

    @classmethod
    @Route.put(
        r"/projects/{project_id}/virtualbox/vms/{vm_id}",
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
        description="Update a VirtualBox VM instance",
        input=VBOX_UPDATE_SCHEMA,
        output=VBOX_OBJECT_SCHEMA)
    def update(request, response):

        vbox_manager = VirtualBox.instance()
        vm = vbox_manager.get_vm(request.match_info["vm_id"], project_id=request.match_info["project_id"])

        if "vmname" in request.json:
            vmname = request.json.pop("vmname")
            if vmname != vm.vmname:
                yield from vm.set_vmname(vmname)

        if "enable_remote_console" in request.json:
            yield from vm.set_enable_remote_console(request.json.pop("enable_remote_console"))

        if "adapters" in request.json:
            adapters = int(request.json.pop("adapters"))
            if adapters != vm.adapters:
                yield from vm.set_adapters(adapters)

        if "ram" in request.json:
            ram = request.json.pop("ram")
            if ram != vm.ram:
                yield from vm.set_ram(ram)

        for name, value in request.json.items():
            if hasattr(vm, name) and getattr(vm, name) != value:
                setattr(vm, name, value)

        response.json(vm)

    @classmethod
    @Route.delete(
        r"/projects/{project_id}/virtualbox/vms/{vm_id}",
        parameters={
            "project_id": "UUID for the project",
            "vm_id": "UUID for the instance"
        },
        status_codes={
            204: "Instance deleted",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Delete a VirtualBox VM instance")
    def delete(request, response):

        # check the project_id exists
        ProjectManager.instance().get_project(request.match_info["project_id"])

        yield from VirtualBox.instance().delete_vm(request.match_info["vm_id"])
        response.set_status(204)

    @classmethod
    @Route.post(
        r"/projects/{project_id}/virtualbox/vms/{vm_id}/start",
        parameters={
            "project_id": "UUID for the project",
            "vm_id": "UUID for the instance"
        },
        status_codes={
            204: "Instance started",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Start a VirtualBox VM instance")
    def start(request, response):

        vbox_manager = VirtualBox.instance()
        vm = vbox_manager.get_vm(request.match_info["vm_id"], project_id=request.match_info["project_id"])
        if (yield from vm.check_hw_virtualization()):
            pm = ProjectManager.instance()
            if pm.check_hardware_virtualization(vm) is False:
                raise HTTPConflict(text="Cannot start VM because hardware virtualization (VT-x/AMD-V) is already used by another software like VMware or KVM (on Linux)")
        yield from vm.start()
        response.set_status(204)

    @classmethod
    @Route.post(
        r"/projects/{project_id}/virtualbox/vms/{vm_id}/stop",
        parameters={
            "project_id": "UUID for the project",
            "vm_id": "UUID for the instance"
        },
        status_codes={
            204: "Instance stopped",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Stop a VirtualBox VM instance")
    def stop(request, response):

        vbox_manager = VirtualBox.instance()
        vm = vbox_manager.get_vm(request.match_info["vm_id"], project_id=request.match_info["project_id"])
        yield from vm.stop()
        response.set_status(204)

    @classmethod
    @Route.post(
        r"/projects/{project_id}/virtualbox/vms/{vm_id}/suspend",
        parameters={
            "project_id": "UUID for the project",
            "vm_id": "UUID for the instance"
        },
        status_codes={
            204: "Instance suspended",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Suspend a VirtualBox VM instance")
    def suspend(request, response):

        vbox_manager = VirtualBox.instance()
        vm = vbox_manager.get_vm(request.match_info["vm_id"], project_id=request.match_info["project_id"])
        yield from vm.suspend()
        response.set_status(204)

    @classmethod
    @Route.post(
        r"/projects/{project_id}/virtualbox/vms/{vm_id}/resume",
        parameters={
            "project_id": "UUID for the project",
            "vm_id": "UUID for the instance"
        },
        status_codes={
            204: "Instance resumed",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Resume a suspended VirtualBox VM instance")
    def resume(request, response):

        vbox_manager = VirtualBox.instance()
        vm = vbox_manager.get_vm(request.match_info["vm_id"], project_id=request.match_info["project_id"])
        yield from vm.resume()
        response.set_status(204)

    @classmethod
    @Route.post(
        r"/projects/{project_id}/virtualbox/vms/{vm_id}/reload",
        parameters={
            "project_id": "UUID for the project",
            "vm_id": "UUID for the instance"
        },
        status_codes={
            204: "Instance reloaded",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Reload a VirtualBox VM instance")
    def reload(request, response):

        vbox_manager = VirtualBox.instance()
        vm = vbox_manager.get_vm(request.match_info["vm_id"], project_id=request.match_info["project_id"])
        yield from vm.reload()
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/virtualbox/vms/{vm_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio",
        parameters={
            "project_id": "UUID for the project",
            "vm_id": "UUID for the instance",
            "adapter_number": "Adapter where the nio should be added",
            "port_number": "Port on the adapter (always 0)"
        },
        status_codes={
            201: "NIO created",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Add a NIO to a VirtualBox VM instance",
        input=NIO_SCHEMA,
        output=NIO_SCHEMA)
    def create_nio(request, response):

        vbox_manager = VirtualBox.instance()
        vm = vbox_manager.get_vm(request.match_info["vm_id"], project_id=request.match_info["project_id"])
        nio_type = request.json["type"]
        if nio_type not in ("nio_udp", "nio_nat"):
            raise HTTPConflict(text="NIO of type {} is not supported".format(nio_type))
        nio = vbox_manager.create_nio(vbox_manager.vboxmanage_path, request.json)
        yield from vm.adapter_add_nio_binding(int(request.match_info["adapter_number"]), nio)
        response.set_status(201)
        response.json(nio)

    @classmethod
    @Route.delete(
        r"/projects/{project_id}/virtualbox/vms/{vm_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio",
        parameters={
            "project_id": "UUID for the project",
            "vm_id": "UUID for the instance",
            "adapter_number": "Adapter from where the nio should be removed",
            "port_number": "Port on the adapter (always 0)"
        },
        status_codes={
            204: "NIO deleted",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Remove a NIO from a VirtualBox VM instance")
    def delete_nio(request, response):

        vbox_manager = VirtualBox.instance()
        vm = vbox_manager.get_vm(request.match_info["vm_id"], project_id=request.match_info["project_id"])
        yield from vm.adapter_remove_nio_binding(int(request.match_info["adapter_number"]))
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/virtualbox/vms/{vm_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/start_capture",
        parameters={
            "project_id": "UUID for the project",
            "vm_id": "UUID for the instance",
            "adapter_number": "Adapter to start a packet capture",
            "port_number": "Port on the adapter (always 0)"
        },
        status_codes={
            200: "Capture started",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Start a packet capture on a VirtualBox VM instance",
        input=VM_CAPTURE_SCHEMA)
    def start_capture(request, response):

        vbox_manager = VirtualBox.instance()
        vm = vbox_manager.get_vm(request.match_info["vm_id"], project_id=request.match_info["project_id"])
        adapter_number = int(request.match_info["adapter_number"])
        pcap_file_path = os.path.join(vm.project.capture_working_directory(), request.json["capture_file_name"])
        yield from vm.start_capture(adapter_number, pcap_file_path)
        response.json({"pcap_file_path": pcap_file_path})

    @Route.post(
        r"/projects/{project_id}/virtualbox/vms/{vm_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/stop_capture",
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
        description="Stop a packet capture on a VirtualBox VM instance")
    def stop_capture(request, response):

        vbox_manager = VirtualBox.instance()
        vm = vbox_manager.get_vm(request.match_info["vm_id"], project_id=request.match_info["project_id"])
        vm.stop_capture(int(request.match_info["adapter_number"]))
        response.set_status(204)
