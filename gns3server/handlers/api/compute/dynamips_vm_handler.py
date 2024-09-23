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
import aiohttp

from gns3server.web.route import Route
from gns3server.schemas.nio import NIO_SCHEMA
from gns3server.compute.dynamips import Dynamips
from gns3server.compute.dynamips.dynamips_error import DynamipsError
from gns3server.compute.project_manager import ProjectManager

from gns3server.schemas.node import (
    NODE_CAPTURE_SCHEMA,
    NODE_LIST_IMAGES_SCHEMA,
)

from gns3server.schemas.dynamips_vm import (
    VM_CREATE_SCHEMA,
    VM_UPDATE_SCHEMA,
    VM_OBJECT_SCHEMA
)

DEFAULT_CHASSIS = {
    "c1700": "1720",
    "c2600": "2610",
    "c3600": "3640"
}


class DynamipsVMHandler:

    """
    API entry points for Dynamips VMs.
    """

    @Route.post(
        r"/projects/{project_id}/dynamips/nodes",
        parameters={
            "project_id": "Project UUID"
        },
        status_codes={
            201: "Instance created",
            400: "Invalid request",
            409: "Conflict"
        },
        description="Create a new Dynamips VM instance",
        input=VM_CREATE_SCHEMA,
        output=VM_OBJECT_SCHEMA)
    async def create(request, response):

        dynamips_manager = Dynamips.instance()
        platform = request.json.pop("platform")
        default_chassis = None
        if platform in DEFAULT_CHASSIS:
            default_chassis = DEFAULT_CHASSIS[platform]
        vm = await dynamips_manager.create_node(request.json.pop("name"),
                                                request.match_info["project_id"],
                                                request.json.get("node_id"),
                                                dynamips_id=request.json.get("dynamips_id"),
                                                platform=platform,
                                                console=request.json.get("console"),
                                                console_type=request.json.get("console_type", "telnet"),
                                                aux=request.json.get("aux"),
                                                chassis=request.json.pop("chassis", default_chassis),
                                                node_type="dynamips")
        await dynamips_manager.update_vm_settings(vm, request.json)
        response.set_status(201)
        response.json(vm)

    @Route.get(
        r"/projects/{project_id}/dynamips/nodes/{node_id}",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
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
        vm = dynamips_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        response.json(vm)

    @Route.put(
        r"/projects/{project_id}/dynamips/nodes/{node_id}",
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
        description="Update a Dynamips VM instance",
        input=VM_UPDATE_SCHEMA,
        output=VM_OBJECT_SCHEMA)
    async def update(request, response):

        dynamips_manager = Dynamips.instance()
        vm = dynamips_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        await dynamips_manager.update_vm_settings(vm, request.json)
        vm.updated()
        response.json(vm)

    @Route.delete(
        r"/projects/{project_id}/dynamips/nodes/{node_id}",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            204: "Instance deleted",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Delete a Dynamips VM instance")
    async def delete(request, response):

        # check the project_id exists
        ProjectManager.instance().get_project(request.match_info["project_id"])
        await Dynamips.instance().delete_node(request.match_info["node_id"])
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/dynamips/nodes/{node_id}/start",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            204: "Instance started",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Start a Dynamips VM instance")
    async def start(request, response):

        dynamips_manager = Dynamips.instance()
        vm = dynamips_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        try:
            await dynamips_manager.ghost_ios_support(vm)
        except GeneratorExit:
            pass
        await vm.start()
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/dynamips/nodes/{node_id}/stop",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            204: "Instance stopped",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Stop a Dynamips VM instance")
    async def stop(request, response):

        dynamips_manager = Dynamips.instance()
        vm = dynamips_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        await vm.stop()
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/dynamips/nodes/{node_id}/suspend",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            204: "Instance suspended",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Suspend a Dynamips VM instance")
    async def suspend(request, response):

        dynamips_manager = Dynamips.instance()
        vm = dynamips_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        await vm.suspend()
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/dynamips/nodes/{node_id}/resume",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            204: "Instance resumed",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Resume a suspended Dynamips VM instance")
    async def resume(request, response):

        dynamips_manager = Dynamips.instance()
        vm = dynamips_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        await vm.resume()
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/dynamips/nodes/{node_id}/reload",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            204: "Instance reloaded",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Reload a Dynamips VM instance")
    async def reload(request, response):

        dynamips_manager = Dynamips.instance()
        vm = dynamips_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        await vm.reload()
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/dynamips/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio",
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
        description="Add a NIO to a Dynamips VM instance",
        input=NIO_SCHEMA,
        output=NIO_SCHEMA)
    async def create_nio(request, response):

        dynamips_manager = Dynamips.instance()
        vm = dynamips_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        nio = await dynamips_manager.create_nio(vm, request.json)
        slot_number = int(request.match_info["adapter_number"])
        port_number = int(request.match_info["port_number"])
        await vm.slot_add_nio_binding(slot_number, port_number, nio)
        response.set_status(201)
        response.json(nio)

    @Route.put(
        r"/projects/{project_id}/dynamips/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio",
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
        description="Update a NIO on a Dynamips instance")
    async def update_nio(request, response):

        dynamips_manager = Dynamips.instance()
        vm = dynamips_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        slot_number = int(request.match_info["adapter_number"])
        port_number = int(request.match_info["port_number"])
        nio = vm.get_nio(slot_number, port_number)
        if "filters" in request.json:
            nio.filters = request.json["filters"]
        await vm.slot_update_nio_binding(slot_number, port_number, nio)
        response.set_status(201)
        response.json(request.json)

    @Route.delete(
        r"/projects/{project_id}/dynamips/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID",
            "adapter_number": "Adapter from where the nio should be removed",
            "port_number": "Port on the adapter"
        },
        status_codes={
            204: "NIO deleted",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Remove a NIO from a Dynamips VM instance")
    async def delete_nio(request, response):

        dynamips_manager = Dynamips.instance()
        vm = dynamips_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        slot_number = int(request.match_info["adapter_number"])
        port_number = int(request.match_info["port_number"])
        nio = await vm.slot_remove_nio_binding(slot_number, port_number)
        await nio.delete()
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/dynamips/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/start_capture",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID",
            "adapter_number": "Adapter to start a packet capture",
            "port_number": "Port on the adapter"
        },
        status_codes={
            200: "Capture started",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Start a packet capture on a Dynamips VM instance",
        input=NODE_CAPTURE_SCHEMA)
    async def start_capture(request, response):

        dynamips_manager = Dynamips.instance()
        vm = dynamips_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        slot_number = int(request.match_info["adapter_number"])
        port_number = int(request.match_info["port_number"])
        pcap_file_path = os.path.join(vm.project.capture_working_directory(), request.json["capture_file_name"])

        if sys.platform.startswith('win'):
            # FIXME: Dynamips (Cygwin actually) doesn't like non ascii paths on Windows
            try:
                pcap_file_path.encode('ascii')
            except UnicodeEncodeError:
                raise DynamipsError('The capture file path "{}" must only contain ASCII (English) characters'.format(pcap_file_path))

        await vm.start_capture(slot_number, port_number, pcap_file_path, request.json["data_link_type"])
        response.json({"pcap_file_path": pcap_file_path})

    @Route.post(
        r"/projects/{project_id}/dynamips/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/stop_capture",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID",
            "adapter_number": "Adapter to stop a packet capture",
            "port_number": "Port on the adapter (always 0)"
        },
        status_codes={
            204: "Capture stopped",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Stop a packet capture on a Dynamips VM instance")
    async def stop_capture(request, response):

        dynamips_manager = Dynamips.instance()
        vm = dynamips_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        slot_number = int(request.match_info["adapter_number"])
        port_number = int(request.match_info["port_number"])
        await vm.stop_capture(slot_number, port_number)
        response.set_status(204)

    @Route.get(
        r"/projects/{project_id}/dynamips/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/pcap",
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

        dynamips_manager = Dynamips.instance()
        vm = dynamips_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        slot_number = int(request.match_info["adapter_number"])
        port_number = int(request.match_info["port_number"])
        nio = vm.get_nio(slot_number, port_number)
        await dynamips_manager.stream_pcap_file(nio, vm.project.id, request, response)

    @Route.get(
        r"/projects/{project_id}/dynamips/nodes/{node_id}/idlepc_proposals",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID",
        },
        status_codes={
            200: "Idle-PCs retrieved",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Retrieve the idlepc proposals")
    async def get_idlepcs(request, response):

        dynamips_manager = Dynamips.instance()
        vm = dynamips_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        await vm.set_idlepc("0x0")
        idlepcs = await vm.get_idle_pc_prop()
        response.set_status(200)
        response.json(idlepcs)

    @Route.get(
        r"/projects/{project_id}/dynamips/nodes/{node_id}/auto_idlepc",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID",
        },
        status_codes={
            200: "Best Idle-pc value found",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Retrieve the idlepc proposals")
    async def get_auto_idlepc(request, response):

        dynamips_manager = Dynamips.instance()
        vm = dynamips_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        idlepc = await dynamips_manager.auto_idlepc(vm)
        response.set_status(200)
        response.json({"idlepc": idlepc})

    @Route.get(
        r"/dynamips/images",
        status_codes={
            200: "List of Dynamips IOS images",
        },
        description="Retrieve the list of Dynamips IOS images",
        output=NODE_LIST_IMAGES_SCHEMA)
    async def list_images(request, response):

        dynamips_manager = Dynamips.instance()
        images = await dynamips_manager.list_images()
        response.set_status(200)
        response.json(images)

    @Route.post(
        r"/dynamips/images/{filename:.+}",
        parameters={
            "filename": "Image filename"
        },
        status_codes={
            204: "Upload a Dynamips IOS image",
        },
        raw=True,
        description="Upload a Dynamips IOS image")
    async def upload_image(request, response):

        dynamips_manager = Dynamips.instance()
        filename = os.path.normpath(request.match_info["filename"])
        await dynamips_manager.write_image(filename, request.content)
        response.set_status(204)

    @Route.get(
        r"/dynamips/images/{filename:.+}",
        parameters={
            "filename": "Image filename"
        },
        status_codes={
            200: "Image returned",
        },
        raw=True,
        description="Download a Dynamips IOS image")
    async def download_image(request, response):

        filename = os.path.normpath(request.match_info["filename"])

        # Raise error if user try to escape
        if filename[0] == "." or os.path.sep in filename:
            raise aiohttp.web.HTTPForbidden()

        dynamips_manager = Dynamips.instance()
        image_path = dynamips_manager.get_abs_image_path(filename)
        await response.stream_file(image_path)

    @Route.post(
        r"/projects/{project_id}/dynamips/nodes/{node_id}/duplicate",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            201: "Instance duplicated",
            404: "Instance doesn't exist"
        },
        description="Duplicate a dynamips instance")
    async def duplicate(request, response):

        new_node = await Dynamips.instance().duplicate_node(request.match_info["node_id"],
                                                            request.json["destination_node_id"])
        response.set_status(201)
        response.json(new_node)

    @Route.get(
        r"/projects/{project_id}/dynamips/nodes/{node_id}/console/ws",
        description="WebSocket for console",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID",
        })
    async def console_ws(request, response):

        dynamips_manager = Dynamips.instance()
        vm = dynamips_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        return await vm.start_websocket_console(request)

    @Route.post(
        r"/projects/{project_id}/dynamips/nodes/{node_id}/console/reset",
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

        dynamips_manager = Dynamips.instance()
        vm = dynamips_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        await vm.reset_console()
        response.set_status(204)
