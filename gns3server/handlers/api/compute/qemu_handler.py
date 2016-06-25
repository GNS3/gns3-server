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

import sys
import os.path

from aiohttp.web import HTTPConflict

from gns3server.web.route import Route
from gns3server.compute.project_manager import ProjectManager
from gns3server.schemas.nio import NIO_SCHEMA
from gns3server.compute.qemu import Qemu
from gns3server.config import Config

from gns3server.schemas.node import (
    NODE_LIST_IMAGES_SCHEMA,
    NODE_CAPTURE_SCHEMA
)

from gns3server.schemas.qemu import (
    QEMU_CREATE_SCHEMA,
    QEMU_UPDATE_SCHEMA,
    QEMU_OBJECT_SCHEMA,
    QEMU_BINARY_LIST_SCHEMA,
    QEMU_BINARY_FILTER_SCHEMA,
    QEMU_CAPABILITY_LIST_SCHEMA,
    QEMU_IMAGE_CREATE_SCHEMA
)


class QEMUHandler:

    """
    API entry points for QEMU.
    """

    @Route.post(
        r"/projects/{project_id}/qemu/nodes",
        parameters={
            "project_id": "Project UUID"
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
        vm = yield from qemu.create_node(request.json.pop("name"),
                                         request.match_info["project_id"],
                                         request.json.pop("node_id", None),
                                         linked_clone=request.json.get("linked_clone", True),
                                         qemu_path=request.json.pop("qemu_path", None),
                                         console=request.json.pop("console", None),
                                         console_type=request.json.pop("console_type", "telnet"),
                                         platform=request.json.pop("platform", None))

        for name, value in request.json.items():
            if hasattr(vm, name) and getattr(vm, name) != value:
                setattr(vm, name, value)

        response.set_status(201)
        response.json(vm)

    @Route.get(
        r"/projects/{project_id}/qemu/nodes/{node_id}",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
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
        vm = qemu_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        response.json(vm)

    @Route.put(
        r"/projects/{project_id}/qemu/nodes/{node_id}",
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
        description="Update a Qemu VM instance",
        input=QEMU_UPDATE_SCHEMA,
        output=QEMU_OBJECT_SCHEMA)
    def update(request, response):

        qemu_manager = Qemu.instance()
        vm = qemu_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])

        for name, value in request.json.items():
            if hasattr(vm, name) and getattr(vm, name) != value:
                setattr(vm, name, value)

        vm.updated()
        response.json(vm)

    @Route.delete(
        r"/projects/{project_id}/qemu/nodes/{node_id}",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            204: "Instance deleted",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Delete a Qemu VM instance")
    def delete(request, response):

        yield from Qemu.instance().delete_node(request.match_info["node_id"])
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/qemu/nodes/{node_id}/start",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            200: "Instance started",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Start a Qemu VM instance",
        output=QEMU_OBJECT_SCHEMA)
    def start(request, response):

        qemu_manager = Qemu.instance()
        vm = qemu_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        if sys.platform.startswith("linux") and qemu_manager.config.get_section_config("Qemu").getboolean("enable_kvm", True) and "-no-kvm" not in vm.options:
            pm = ProjectManager.instance()
            if pm.check_hardware_virtualization(vm) is False:
                raise HTTPConflict(text="Cannot start VM with KVM enabled because hardware virtualization (VT-x/AMD-V) is already used by another software like VMware or VirtualBox")
        yield from vm.start()
        response.json(vm)

    @Route.post(
        r"/projects/{project_id}/qemu/nodes/{node_id}/stop",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            204: "Instance stopped",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Stop a Qemu VM instance")
    def stop(request, response):

        qemu_manager = Qemu.instance()
        vm = qemu_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        yield from vm.stop()
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/qemu/nodes/{node_id}/reload",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID",
        },
        status_codes={
            204: "Instance reloaded",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Reload a Qemu VM instance")
    def reload(request, response):

        qemu_manager = Qemu.instance()
        vm = qemu_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        yield from vm.reload()
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/qemu/nodes/{node_id}/suspend",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID",
        },
        status_codes={
            204: "Instance suspended",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Suspend a Qemu VM instance")
    def suspend(request, response):

        qemu_manager = Qemu.instance()
        vm = qemu_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        yield from vm.suspend()
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/qemu/nodes/{node_id}/resume",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID",
        },
        status_codes={
            204: "Instance resumed",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Resume a Qemu VM instance")
    def resume(request, response):

        qemu_manager = Qemu.instance()
        vm = qemu_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        yield from vm.resume()
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/qemu/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID",
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
        vm = qemu_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        nio_type = request.json["type"]
        if nio_type not in ("nio_udp", "nio_tap", "nio_nat"):
            raise HTTPConflict(text="NIO of type {} is not supported".format(nio_type))
        nio = qemu_manager.create_nio(request.json)
        yield from vm.adapter_add_nio_binding(int(request.match_info["adapter_number"]), nio)
        response.set_status(201)
        response.json(nio)

    @Route.delete(
        r"/projects/{project_id}/qemu/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID",
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
        vm = qemu_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        yield from vm.adapter_remove_nio_binding(int(request.match_info["adapter_number"]))
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/qemu/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/start_capture",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID",
            "adapter_number": "Adapter to start a packet capture",
            "port_number": "Port on the adapter (always 0)"
        },
        status_codes={
            200: "Capture started",
            400: "Invalid request",
            404: "Instance doesn't exist",
        },
        description="Start a packet capture on a Qemu VM instance",
        input=NODE_CAPTURE_SCHEMA)
    def start_capture(request, response):

        qemu_manager = Qemu.instance()
        vm = qemu_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        adapter_number = int(request.match_info["adapter_number"])
        pcap_file_path = os.path.join(vm.project.capture_working_directory(), request.json["capture_file_name"])
        yield from vm.start_capture(adapter_number, pcap_file_path)
        response.json({"pcap_file_path": pcap_file_path})


    @Route.post(
        r"/projects/{project_id}/qemu/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/stop_capture",
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
        },
        description="Stop a packet capture on a Qemu VM instance")
    def stop_capture(request, response):

        qemu_manager = Qemu.instance()
        vm = qemu_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        adapter_number = int(request.match_info["adapter_number"])
        yield from vm.stop_capture(adapter_number)
        response.set_status(204)

    @Route.get(
        r"/qemu/binaries",
        status_codes={
            200: "Success",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Get a list of available Qemu binaries",
        input=QEMU_BINARY_FILTER_SCHEMA,
        output=QEMU_BINARY_LIST_SCHEMA)
    def list_binaries(request, response):

        binaries = yield from Qemu.binary_list(request.json.get("archs", None))
        response.json(binaries)

    @Route.get(
        r"/qemu/img-binaries",
        status_codes={
            200: "Success",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Get a list of available Qemu-img binaries",
        output=QEMU_BINARY_LIST_SCHEMA)
    def list_img_binaries(request, response):

        binaries = yield from Qemu.img_binary_list()
        response.json(binaries)

    @Route.get(
        r"/qemu/capabilities",
        status_codes={
            200: "Success"
        },
        description="Get a list of Qemu capabilities on this server",
        output=QEMU_CAPABILITY_LIST_SCHEMA
    )
    def get_capabilities(request, response):
        capabilities = {"kvm": []}
        kvms = yield from Qemu.get_kvm_archs()
        if kvms:
            capabilities["kvm"] = kvms
        response.json(capabilities)

    @Route.post(
        r"/qemu/img",
        status_codes={
            201: "Image created",
        },
        description="Create a Qemu image",
        input=QEMU_IMAGE_CREATE_SCHEMA
    )
    def create_img(request, response):

        qemu_img = request.json.pop("qemu_img")
        path = request.json.pop("path")
        if os.path.isabs(path):
            config = Config.instance()
            if config.get_section_config("Server").getboolean("local", False) is False:
                response.set_status(403)
                return

        yield from Qemu.instance().create_disk(qemu_img, path, request.json)
        response.set_status(201)

    @Route.get(
        r"/qemu/images",
        status_codes={
            200: "List of Qemu images",
        },
        description="Retrieve the list of Qemu images",
        output=NODE_LIST_IMAGES_SCHEMA)
    def list_qemu_images(request, response):

        qemu_manager = Qemu.instance()
        images = yield from qemu_manager.list_images()
        response.set_status(200)
        response.json(images)

    @Route.post(
        r"/qemu/images/{filename:.+}",
        parameters={
            "filename": "Image filename"
        },
        status_codes={
            204: "Image uploaded",
        },
        raw=True,
        description="Upload Qemu image")
    def upload_image(request, response):

        qemu_manager = Qemu.instance()
        yield from qemu_manager.write_image(request.match_info["filename"], request.content)
        response.set_status(204)
