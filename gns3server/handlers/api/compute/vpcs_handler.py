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
from gns3server.web.route import Route
from gns3server.schemas.nio import NIO_SCHEMA
from gns3server.schemas.node import NODE_CAPTURE_SCHEMA
from gns3server.compute.vpcs import VPCS

from gns3server.schemas.vpcs import (
    VPCS_CREATE_SCHEMA,
    VPCS_UPDATE_SCHEMA,
    VPCS_OBJECT_SCHEMA
)


class VPCSHandler:

    """
    API entry points for VPCS.
    """

    @Route.post(
        r"/projects/{project_id}/vpcs/nodes",
        parameters={
            "project_id": "Project UUID"
        },
        status_codes={
            201: "Instance created",
            400: "Invalid request",
            409: "Conflict"
        },
        description="Create a new VPCS instance",
        input=VPCS_CREATE_SCHEMA,
        output=VPCS_OBJECT_SCHEMA)
    def create(request, response):

        vpcs = VPCS.instance()
        vm = yield from vpcs.create_node(request.json["name"],
                                         request.match_info["project_id"],
                                         request.json.get("node_id"),
                                         console=request.json.get("console"),
                                         startup_script=request.json.get("startup_script"))
        response.set_status(201)
        response.json(vm)

    @Route.get(
        r"/projects/{project_id}/vpcs/nodes/{node_id}",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            200: "Success",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Get a VPCS instance",
        output=VPCS_OBJECT_SCHEMA)
    def show(request, response):

        vpcs_manager = VPCS.instance()
        vm = vpcs_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        response.json(vm)

    @Route.put(
        r"/projects/{project_id}/vpcs/nodes/{node_id}",
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
        description="Update a VPCS instance",
        input=VPCS_UPDATE_SCHEMA,
        output=VPCS_OBJECT_SCHEMA)
    def update(request, response):

        vpcs_manager = VPCS.instance()
        vm = vpcs_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        vm.name = request.json.get("name", vm.name)
        vm.console = request.json.get("console", vm.console)
        vm.updated()
        response.json(vm)

    @Route.delete(
        r"/projects/{project_id}/vpcs/nodes/{node_id}",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            204: "Instance deleted",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Delete a VPCS instance")
    def delete(request, response):

        yield from VPCS.instance().delete_node(request.match_info["node_id"])
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/vpcs/nodes/{node_id}/start",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            204: "Instance started",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Start a VPCS instance",
        output=VPCS_OBJECT_SCHEMA)
    def start(request, response):

        vpcs_manager = VPCS.instance()
        vm = vpcs_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        yield from vm.start()
        response.json(vm)

    @Route.post(
        r"/projects/{project_id}/vpcs/nodes/{node_id}/stop",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            204: "Instance stopped",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Stop a VPCS instance")
    def stop(request, response):

        vpcs_manager = VPCS.instance()
        vm = vpcs_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        yield from vm.stop()
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/vpcs/nodes/{node_id}/suspend",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            204: "Instance stopped",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Suspend a VPCS instance (stop it)")
    def stop(request, response):

        vpcs_manager = VPCS.instance()
        vm = vpcs_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        yield from vm.stop()
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/vpcs/nodes/{node_id}/reload",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID",
        },
        status_codes={
            204: "Instance reloaded",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Reload a VPCS instance")
    def reload(request, response):

        vpcs_manager = VPCS.instance()
        vm = vpcs_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        yield from vm.reload()
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/vpcs/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio",
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
        description="Add a NIO to a VPCS instance",
        input=NIO_SCHEMA,
        output=NIO_SCHEMA)
    def create_nio(request, response):

        vpcs_manager = VPCS.instance()
        vm = vpcs_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        nio_type = request.json["type"]
        if nio_type not in ("nio_udp", "nio_tap"):
            raise HTTPConflict(text="NIO of type {} is not supported".format(nio_type))
        nio = vpcs_manager.create_nio(request.json)
        yield from vm.port_add_nio_binding(int(request.match_info["port_number"]), nio)
        response.set_status(201)
        response.json(nio)

    @Route.delete(
        r"/projects/{project_id}/vpcs/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio",
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
        description="Remove a NIO from a VPCS instance")
    def delete_nio(request, response):

        vpcs_manager = VPCS.instance()
        vm = vpcs_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        yield from vm.port_remove_nio_binding(int(request.match_info["port_number"]))
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/vpcs/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/start_capture",
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
        description="Start a packet capture on a VPCS instance",
        input=NODE_CAPTURE_SCHEMA)
    def start_capture(request, response):

        vpcs_manager = VPCS.instance()
        vm = vpcs_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        port_number = int(request.match_info["port_number"])
        pcap_file_path = os.path.join(vm.project.capture_working_directory(), request.json["capture_file_name"])
        yield from vm.start_capture(port_number, pcap_file_path)
        response.json({"pcap_file_path": pcap_file_path})

    @Route.post(
        r"/projects/{project_id}/vpcs/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/stop_capture",
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
        description="Stop a packet capture on a VPCS instance")
    def stop_capture(request, response):

        vpcs_manager = VPCS.instance()
        vm = vpcs_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        port_number = int(request.match_info["port_number"])
        yield from vm.stop_capture(port_number)
        response.set_status(204)
