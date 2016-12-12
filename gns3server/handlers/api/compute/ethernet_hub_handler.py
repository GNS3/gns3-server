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

from gns3server.web.route import Route
from gns3server.schemas.node import NODE_CAPTURE_SCHEMA
from gns3server.schemas.nio import NIO_SCHEMA
from gns3server.compute.builtin import Builtin
from gns3server.compute.dynamips import Dynamips

from gns3server.schemas.ethernet_hub import (
    ETHERNET_HUB_CREATE_SCHEMA,
    ETHERNET_HUB_UPDATE_SCHEMA,
    ETHERNET_HUB_OBJECT_SCHEMA
)


class EthernetHubHandler:

    """
    API entry points for Ethernet hub.
    """

    @Route.post(
        r"/projects/{project_id}/ethernet_hub/nodes",
        parameters={
            "project_id": "Project UUID"
        },
        status_codes={
            201: "Instance created",
            400: "Invalid request",
            409: "Conflict"
        },
        description="Create a new Ethernet hub instance",
        input=ETHERNET_HUB_CREATE_SCHEMA,
        output=ETHERNET_HUB_OBJECT_SCHEMA)
    def create(request, response):

        # Use the Dynamips Ethernet hub to simulate this node
        dynamips_manager = Dynamips.instance()
        node = yield from dynamips_manager.create_node(request.json.pop("name"),
                                                         request.match_info["project_id"],
                                                         request.json.get("node_id"),
                                                         node_type="ethernet_hub",
                                                         ports=request.json.get("ports_mapping"))

        response.set_status(201)
        response.json(node)

    @Route.get(
        r"/projects/{project_id}/ethernet_hub/nodes/{node_id}",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            200: "Success",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Get an Ethernet hub instance",
        output=ETHERNET_HUB_OBJECT_SCHEMA)
    def show(request, response):

        dynamips_manager = Dynamips.instance()
        node = dynamips_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])

        response.json(node)

    @Route.put(
        r"/projects/{project_id}/ethernet_hub/nodes/{node_id}",
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
        description="Update an Ethernet hub instance",
        input=ETHERNET_HUB_UPDATE_SCHEMA,
        output=ETHERNET_HUB_OBJECT_SCHEMA)
    def update(request, response):

        dynamips_manager = Dynamips.instance()
        node = dynamips_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        if "name" in request.json and node.name != request.json["name"]:
            yield from node.set_name(request.json["name"])
        if "ports_mapping" in request.json:
            node.ports_mapping = request.json["ports_mapping"]

        node.updated()
        response.json(node)

    @Route.delete(
        r"/projects/{project_id}/ethernet_hub/nodes/{node_id}",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            204: "Instance deleted",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Delete an Ethernet hub instance")
    def delete(request, response):

        dynamips_manager = Dynamips.instance()
        yield from dynamips_manager.delete_node(request.match_info["node_id"])
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/ethernet_hub/nodes/{node_id}/start",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            204: "Instance started",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Start an Ethernet hub")
    def start(request, response):

        Dynamips.instance().get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/ethernet_hub/nodes/{node_id}/stop",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            204: "Instance stopped",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Stop an Ethernet hub")
    def stop(request, response):

        Dynamips.instance().get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/ethernet_hub/nodes/{node_id}/suspend",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            204: "Instance suspended",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Suspend an Ethernet hub")
    def suspend(request, response):

        Dynamips.instance().get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/ethernet_hub/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID",
            "adapter_number": "Adapter on the hub (always 0)",
            "port_number": "Port on the hub"
        },
        status_codes={
            201: "NIO created",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Add a NIO to an Ethernet hub instance",
        input=NIO_SCHEMA,
        output=NIO_SCHEMA)
    def create_nio(request, response):

        dynamips_manager = Dynamips.instance()
        node = dynamips_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        nio = yield from dynamips_manager.create_nio(node, request.json)
        port_number = int(request.match_info["port_number"])
        yield from node.add_nio(nio, port_number)

        response.set_status(201)
        response.json(nio)

    @Route.delete(
        r"/projects/{project_id}/ethernet_hub/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID",
            "adapter_number": "Adapter on the hub (always 0)",
            "port_number": "Port on the hub"
        },
        status_codes={
            204: "NIO deleted",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Remove a NIO from an Ethernet hub instance")
    def delete_nio(request, response):

        dynamips_manager = Dynamips.instance()
        node = dynamips_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        port_number = int(request.match_info["port_number"])
        nio = yield from node.remove_nio(port_number)
        yield from nio.delete()
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/ethernet_hub/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/start_capture",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID",
            "adapter_number": "Adapter on the hub (always 0)",
            "port_number": "Port on the hub"
        },
        status_codes={
            200: "Capture started",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Start a packet capture on an Ethernet hub instance",
        input=NODE_CAPTURE_SCHEMA)
    def start_capture(request, response):

        dynamips_manager = Dynamips.instance()
        node = dynamips_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        port_number = int(request.match_info["port_number"])
        pcap_file_path = os.path.join(node.project.capture_working_directory(), request.json["capture_file_name"])
        yield from node.start_capture(port_number, pcap_file_path, request.json["data_link_type"])
        response.json({"pcap_file_path": pcap_file_path})

    @Route.post(
        r"/projects/{project_id}/ethernet_hub/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/stop_capture",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID",
            "adapter_number": "Adapter on the hub (always 0)",
            "port_number": "Port on the hub"
        },
        status_codes={
            204: "Capture stopped",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Stop a packet capture on an Ethernet hub instance")
    def stop_capture(request, response):

        dynamips_manager = Dynamips.instance()
        node = dynamips_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        port_number = int(request.match_info["port_number"])
        yield from node.stop_capture(port_number)
        response.set_status(204)
