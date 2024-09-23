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

import aiohttp.web

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
    QEMU_RESIZE_SCHEMA,
    QEMU_BINARY_LIST_SCHEMA,
    QEMU_BINARY_FILTER_SCHEMA,
    QEMU_CAPABILITY_LIST_SCHEMA,
    QEMU_IMAGE_CREATE_SCHEMA,
    QEMU_IMAGE_UPDATE_SCHEMA
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
    async def create(request, response):

        qemu = Qemu.instance()
        vm = await qemu.create_node(request.json.pop("name"),
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
    async def update(request, response):

        qemu_manager = Qemu.instance()
        vm = qemu_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        # update the console first to avoid issue if updating console type
        vm.console = request.json.pop("console", vm.console)
        for name, value in request.json.items():
            if hasattr(vm, name) and getattr(vm, name) != value:
                await vm.update_property(name, value)
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
    async def delete(request, response):

        await Qemu.instance().delete_node(request.match_info["node_id"])
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/qemu/nodes/{node_id}/duplicate",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            201: "Instance duplicated",
            404: "Instance doesn't exist"
        },
        description="Duplicate a Qemu instance")
    async def duplicate(request, response):

        new_node = await Qemu.instance().duplicate_node(
            request.match_info["node_id"],
            request.json["destination_node_id"]
        )
        response.set_status(201)
        response.json(new_node)

    @Route.post(
        r"/projects/{project_id}/qemu/nodes/{node_id}/resize_disk",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            201: "Instance updated",
            404: "Instance doesn't exist"
        },
        description="Resize a Qemu VM disk image",
        input=QEMU_RESIZE_SCHEMA)
    async def resize_disk(request, response):

        qemu_manager = Qemu.instance()
        vm = qemu_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        await vm.resize_disk(request.json["drive_name"], request.json["extend"])
        response.set_status(201)

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
    async def start(request, response):

        qemu_manager = Qemu.instance()
        vm = qemu_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        hardware_accel = qemu_manager.config.get_section_config("Qemu").getboolean("enable_hardware_acceleration", True)
        if sys.platform.startswith("linux"):
            # the enable_kvm option was used before version 2.0 and has priority
            enable_kvm = qemu_manager.config.get_section_config("Qemu").getboolean("enable_kvm")
            if enable_kvm is not None:
                hardware_accel = enable_kvm
        if hardware_accel and "-machine accel=tcg" not in vm.options:
            pm = ProjectManager.instance()
            if pm.check_hardware_virtualization(vm) is False:
                raise aiohttp.web.HTTPConflict(text="Cannot start VM with hardware acceleration (KVM/HAX) enabled because hardware virtualization (VT-x/AMD-V) is already used by another software like VMware or VirtualBox")
        await vm.start()
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
    async def stop(request, response):

        qemu_manager = Qemu.instance()
        vm = qemu_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        await vm.stop()
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
    async def reload(request, response):

        qemu_manager = Qemu.instance()
        vm = qemu_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        await vm.reload()
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
    async def suspend(request, response):

        qemu_manager = Qemu.instance()
        vm = qemu_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        await vm.suspend()
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
    async def resume(request, response):

        qemu_manager = Qemu.instance()
        vm = qemu_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        await vm.resume()
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
    async def create_nio(request, response):

        qemu_manager = Qemu.instance()
        vm = qemu_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        nio_type = request.json["type"]
        if nio_type not in ("nio_udp"):
            raise aiohttp.web.HTTPConflict(text="NIO of type {} is not supported".format(nio_type))
        nio = qemu_manager.create_nio(request.json)
        await vm.adapter_add_nio_binding(int(request.match_info["adapter_number"]), nio)
        response.set_status(201)
        response.json(nio)

    @Route.put(
        r"/projects/{project_id}/qemu/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID",
            "adapter_number": "Network adapter where the nio is located",
            "port_number": "Port from where the nio should be updated"
        },
        status_codes={
            201: "NIO updated",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        input=NIO_SCHEMA,
        output=NIO_SCHEMA,
        description="Update a NIO on a Qemu instance")
    async def update_nio(request, response):

        qemu_manager = Qemu.instance()
        vm = qemu_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        adapter_number = int(request.match_info["adapter_number"])
        nio = vm.get_nio(adapter_number)
        if "filters" in request.json:
            nio.filters = request.json["filters"]
        if "suspend" in request.json:
            nio.suspend = request.json["suspend"]
        await vm.adapter_update_nio_binding(adapter_number, nio)
        response.set_status(201)
        response.json(request.json)

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
    async def delete_nio(request, response):

        qemu_manager = Qemu.instance()
        vm = qemu_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        adapter_number = int(request.match_info["adapter_number"])
        await vm.adapter_remove_nio_binding(adapter_number)
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
    async def start_capture(request, response):

        qemu_manager = Qemu.instance()
        vm = qemu_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        adapter_number = int(request.match_info["adapter_number"])
        pcap_file_path = os.path.join(vm.project.capture_working_directory(), request.json["capture_file_name"])
        await vm.start_capture(adapter_number, pcap_file_path)
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
    async def stop_capture(request, response):

        qemu_manager = Qemu.instance()
        vm = qemu_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        adapter_number = int(request.match_info["adapter_number"])
        await vm.stop_capture(adapter_number)
        response.set_status(204)

    @Route.get(
        r"/projects/{project_id}/qemu/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/pcap",
        description="Stream the pcap capture file",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID",
            "adapter_number": "Adapter to steam a packet capture",
            "port_number": "Port on the adapter (always 0)"
        },
        status_codes={
            200: "File returned",
            403: "Permission denied",
            404: "The file doesn't exist"
        })
    async def stream_pcap_file(request, response):

        qemu_manager = Qemu.instance()
        vm = qemu_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        adapter_number = int(request.match_info["adapter_number"])
        nio = vm.get_nio(adapter_number)
        await qemu_manager.stream_pcap_file(nio, vm.project.id, request, response)

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
    async def list_binaries(request, response):

        binaries = await Qemu.binary_list(request.json.get("archs", None))
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
    async def list_img_binaries(request, response):

        binaries = await Qemu.img_binary_list()
        response.json(binaries)

    @Route.get(
        r"/qemu/capabilities",
        status_codes={
            200: "Success"
        },
        description="Get a list of Qemu capabilities on this server",
        output=QEMU_CAPABILITY_LIST_SCHEMA
    )
    async def get_capabilities(request, response):
        capabilities = {"kvm": []}
        kvms = await Qemu.get_kvm_archs()
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
    async def create_img(request, response):

        qemu_img = request.json.pop("qemu_img")
        path = request.json.pop("path")
        if os.path.isabs(path):
            config = Config.instance()
            if config.get_section_config("Server").getboolean("local", False) is False:
                response.set_status(403)
                return

        await Qemu.instance().create_disk(qemu_img, path, request.json)
        response.set_status(201)

    @Route.put(
        r"/qemu/img",
        status_codes={
            201: "Image Updated",
        },
        description="Update a Qemu image",
        input=QEMU_IMAGE_UPDATE_SCHEMA
    )
    async def update_img(request, response):

        qemu_img = request.json.pop("qemu_img")
        path = request.json.pop("path")
        if os.path.isabs(path):
            config = Config.instance()
            if config.get_section_config("Server").getboolean("local", False) is False:
                response.set_status(403)
                return

        if "extend" in request.json:
            await Qemu.instance().resize_disk(qemu_img, path, request.json.pop("extend"))
        response.set_status(201)

    @Route.get(
        r"/qemu/images",
        status_codes={
            200: "List of Qemu images",
        },
        description="Retrieve the list of Qemu images",
        output=NODE_LIST_IMAGES_SCHEMA)
    async def list_qemu_images(request, response):

        qemu_manager = Qemu.instance()
        images = await qemu_manager.list_images()
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
    async def upload_image(request, response):

        qemu_manager = Qemu.instance()
        filename = os.path.normpath(request.match_info["filename"])
        await qemu_manager.write_image(filename, request.content)
        response.set_status(204)

    @Route.get(
        r"/qemu/images/{filename:.+}",
        parameters={
            "filename": "Image filename"
        },
        status_codes={
            200: "Image returned",
        },
        raw=True,
        description="Download Qemu image")
    async def download_image(request, response):

        filename = os.path.normpath(request.match_info["filename"])

        # Raise error if user try to escape
        if filename[0] == "." or os.path.sep in filename:
            raise aiohttp.web.HTTPForbidden()

        qemu_manager = Qemu.instance()
        image_path = qemu_manager.get_abs_image_path(filename)
        await response.stream_file(image_path)

    @Route.get(
        r"/projects/{project_id}/qemu/nodes/{node_id}/console/ws",
        description="WebSocket for console",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID",
        })
    async def console_ws(request, response):

        qemu_manager = Qemu.instance()
        vm = qemu_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        return await vm.start_websocket_console(request)

    @Route.post(
        r"/projects/{project_id}/qemu/nodes/{node_id}/console/reset",
        description="Reset console",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID",
        },
        status_codes={
            204: "Console has been reset",
            400: "Invalid request",
            404: "Instance doesn't exist",
            409: "Container not started"
        })
    async def reset_console(request, response):

        qemu_manager = Qemu.instance()
        vm = qemu_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        await vm.reset_console()
        response.set_status(204)
