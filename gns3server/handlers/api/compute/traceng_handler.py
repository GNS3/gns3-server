# -*- coding: utf-8 -*-
#
# Copyright (C) 2018 GNS3 Technologies Inc.
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
from gns3server.web.route import Route
from gns3server.schemas.nio import NIO_SCHEMA
from gns3server.schemas.node import NODE_CAPTURE_SCHEMA
from gns3server.compute.traceng import TraceNG

from gns3server.schemas.traceng import (
    TRACENG_CREATE_SCHEMA,
    TRACENG_UPDATE_SCHEMA,
    TRACENG_START_SCHEMA,
    TRACENG_OBJECT_SCHEMA
)


class TraceNGHandler:
    """
    API entry points for TraceNG.
    """

    @Route.post(
        r"/projects/{project_id}/traceng/nodes",
        parameters={
            "project_id": "Project UUID"
        },
        status_codes={
            201: "Instance created",
            400: "Invalid request",
            409: "Conflict"
        },
        description="Create a new TraceNG instance",
        input=TRACENG_CREATE_SCHEMA,
        output=TRACENG_OBJECT_SCHEMA)
    async def create(request, response):

        traceng = TraceNG.instance()
        vm = await traceng.create_node(request.json["name"],
                                            request.match_info["project_id"],
                                            request.json.get("node_id"),
                                            console=request.json.get("console"))
        vm.ip_address = request.json.get("ip_address", "")
        vm.default_destination = request.json.get("default_destination", "")
        response.set_status(201)
        response.json(vm)

    @Route.get(
        r"/projects/{project_id}/traceng/nodes/{node_id}",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            200: "Success",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Get a TraceNG instance",
        output=TRACENG_OBJECT_SCHEMA)
    def show(request, response):

        traceng_manager = TraceNG.instance()
        vm = traceng_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        response.json(vm)

    @Route.put(
        r"/projects/{project_id}/traceng/nodes/{node_id}",
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
        description="Update a TraceNG instance",
        input=TRACENG_UPDATE_SCHEMA,
        output=TRACENG_OBJECT_SCHEMA)
    def update(request, response):

        traceng_manager = TraceNG.instance()
        vm = traceng_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        vm.name = request.json.get("name", vm.name)
        vm.ip_address = request.json.get("ip_address", vm.ip_address)
        vm.default_destination = request.json.get("default_destination", vm.default_destination)
        vm.updated()
        response.json(vm)

    @Route.delete(
        r"/projects/{project_id}/traceng/nodes/{node_id}",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            204: "Instance deleted",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Delete a TraceNG instance")
    async def delete(request, response):

        await TraceNG.instance().delete_node(request.match_info["node_id"])
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/traceng/nodes/{node_id}/duplicate",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            201: "Instance duplicated",
            404: "Instance doesn't exist"
        },
        description="Duplicate a TraceNG instance")
    async def duplicate(request, response):

        new_node = await TraceNG.instance().duplicate_node(
            request.match_info["node_id"],
            request.json["destination_node_id"]
        )
        response.set_status(201)
        response.json(new_node)

    @Route.post(
        r"/projects/{project_id}/traceng/nodes/{node_id}/start",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            204: "Instance started",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Start a TraceNG instance",
        input=TRACENG_START_SCHEMA,
        output=TRACENG_OBJECT_SCHEMA)
    async def start(request, response):

        traceng_manager = TraceNG.instance()
        vm = traceng_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        await vm.start(request.get("destination"))
        response.json(vm)

    @Route.post(
        r"/projects/{project_id}/traceng/nodes/{node_id}/stop",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            204: "Instance stopped",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Stop a TraceNG instance")
    async def stop(request, response):

        traceng_manager = TraceNG.instance()
        vm = traceng_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        await vm.stop()
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/traceng/nodes/{node_id}/suspend",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            204: "Instance suspended",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Suspend a TraceNG instance (does nothing)")
    def suspend(request, response):

        traceng_manager = TraceNG.instance()
        traceng_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/traceng/nodes/{node_id}/reload",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID",
        },
        status_codes={
            204: "Instance reloaded",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Reload a TraceNG instance")
    async def reload(request, response):

        traceng_manager = TraceNG.instance()
        vm = traceng_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        await vm.reload()
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/traceng/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID",
            "adapter_number": "Network adapter where the nio is located",
            "port_number": "Port where the nio should be added"
        },
        status_codes={
            201: "NIO created",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Add a NIO to a TraceNG instance",
        input=NIO_SCHEMA,
        output=NIO_SCHEMA)
    async def create_nio(request, response):

        traceng_manager = TraceNG.instance()
        vm = traceng_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        nio_type = request.json["type"]
        if nio_type not in ("nio_udp"):
            raise HTTPConflict(text="NIO of type {} is not supported".format(nio_type))
        nio = traceng_manager.create_nio(request.json)
        await vm.port_add_nio_binding(int(request.match_info["port_number"]), nio)
        response.set_status(201)
        response.json(nio)

    @Route.put(
        r"/projects/{project_id}/traceng/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio",
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
        description="Update a NIO on a TraceNG instance")
    async def update_nio(request, response):

        traceng_manager = TraceNG.instance()
        vm = traceng_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        port_number = int(request.match_info["port_number"])
        nio = vm.get_nio(port_number)
        if "filters" in request.json:
            nio.filters = request.json["filters"]
        await vm.port_update_nio_binding(port_number, nio)
        response.set_status(201)
        response.json(request.json)

    @Route.delete(
        r"/projects/{project_id}/traceng/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID",
            "adapter_number": "Network adapter where the nio is located",
            "port_number": "Port from where the nio should be removed"
        },
        status_codes={
            204: "NIO deleted",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Remove a NIO from a TraceNG instance")
    async def delete_nio(request, response):

        traceng_manager = TraceNG.instance()
        vm = traceng_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        port_number = int(request.match_info["port_number"])
        await vm.port_remove_nio_binding(port_number)
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/traceng/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/start_capture",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID",
            "adapter_number": "Adapter to start a packet capture",
            "port_number": "Port on the adapter"
        },
        status_codes={
            200: "Capture started",
            400: "Invalid request",
            404: "Instance doesn't exist",
        },
        description="Start a packet capture on a TraceNG instance",
        input=NODE_CAPTURE_SCHEMA)
    async def start_capture(request, response):

        traceng_manager = TraceNG.instance()
        vm = traceng_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        port_number = int(request.match_info["port_number"])
        pcap_file_path = os.path.join(vm.project.capture_working_directory(), request.json["capture_file_name"])
        await vm.start_capture(port_number, pcap_file_path)
        response.json({"pcap_file_path": pcap_file_path})

    @Route.post(
        r"/projects/{project_id}/traceng/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/stop_capture",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID",
            "adapter_number": "Adapter to stop a packet capture",
            "port_number": "Port on the adapter"
        },
        status_codes={
            204: "Capture stopped",
            400: "Invalid request",
            404: "Instance doesn't exist",
        },
        description="Stop a packet capture on a TraceNG instance")
    async def stop_capture(request, response):

        traceng_manager = TraceNG.instance()
        vm = traceng_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        port_number = int(request.match_info["port_number"])
        await vm.stop_capture(port_number)
        response.set_status(204)

    @Route.get(
        r"/projects/{project_id}/traceng/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/pcap",
        description="Stream the pcap capture file",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID",
            "adapter_number": "Adapter to steam a packet capture",
            "port_number": "Port on the adapter"
        },
        status_codes={
            200: "File returned",
            403: "Permission denied",
            404: "The file doesn't exist"
        })
    async def stream_pcap_file(request, response):

        traceng_manager = TraceNG.instance()
        vm = traceng_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        port_number = int(request.match_info["port_number"])
        nio = vm.get_nio(port_number)
        await traceng_manager.stream_pcap_file(nio, vm.project.id, request, response)
