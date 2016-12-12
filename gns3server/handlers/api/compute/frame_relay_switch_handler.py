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
from gns3server.compute.dynamips import Dynamips

from gns3server.schemas.frame_relay_switch import (
    FRAME_RELAY_SWITCH_CREATE_SCHEMA,
    FRAME_RELAY_SWITCH_OBJECT_SCHEMA,
    FRAME_RELAY_SWITCH_UPDATE_SCHEMA
)


class FrameRelaySwitchHandler:

    """
    API entry points for Frame Relay switch.
    """

    @Route.post(
        r"/projects/{project_id}/frame_relay_switch/nodes",
        parameters={
            "project_id": "Project UUID"
        },
        status_codes={
            201: "Instance created",
            400: "Invalid request",
            409: "Conflict"
        },
        description="Create a new Frame Relay switch instance",
        input=FRAME_RELAY_SWITCH_CREATE_SCHEMA,
        output=FRAME_RELAY_SWITCH_OBJECT_SCHEMA)
    def create(request, response):

        # Use the Dynamips Frame Relay switch to simulate this node
        dynamips_manager = Dynamips.instance()
        node = yield from dynamips_manager.create_node(request.json.pop("name"),
                                                         request.match_info["project_id"],
                                                         request.json.get("node_id"),
                                                         node_type="frame_relay_switch",
                                                         mappings=request.json.get("mappings"))
        response.set_status(201)
        response.json(node)

    @Route.get(
        r"/projects/{project_id}/frame_relay_switch/nodes/{node_id}",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            200: "Success",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Get a Frame Relay switch instance",
        output=FRAME_RELAY_SWITCH_OBJECT_SCHEMA)
    def show(request, response):

        dynamips_manager = Dynamips.instance()
        node = dynamips_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        response.json(node)

    @Route.put(
        r"/projects/{project_id}/frame_relay_switch/nodes/{node_id}",
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
        description="Update a Frame Relay switch instance",
        input=FRAME_RELAY_SWITCH_UPDATE_SCHEMA,
        output=FRAME_RELAY_SWITCH_OBJECT_SCHEMA)
    def update(request, response):

        dynamips_manager = Dynamips.instance()
        node = dynamips_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        if "name" in request.json and node.name != request.json["name"]:
            yield from node.set_name(request.json["name"])
        if "mappings" in request.json:
            node.mappings = request.json["mappings"]
        node.updated()
        response.json(node)

    @Route.delete(
        r"/projects/{project_id}/frame_relay_switch/nodes/{node_id}",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            204: "Instance deleted",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Delete a Frame Relay switch instance")
    def delete(request, response):

        dynamips_manager = Dynamips.instance()
        yield from dynamips_manager.delete_node(request.match_info["node_id"])
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/frame_relay_switch/nodes/{node_id}/start",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            204: "Instance started",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Start a Frame Relay switch")
    def start(request, response):

        Dynamips.instance().get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/frame_relay_switch/nodes/{node_id}/stop",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            204: "Instance stopped",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Stop a Frame Relay switch")
    def stop(request, response):

        Dynamips.instance().get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/frame_relay_switch/nodes/{node_id}/suspend",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            204: "Instance suspended",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Suspend a Frame Relay switch")
    def suspend(request, response):

        Dynamips.instance().get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/frame_relay_switch/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID",
            "adapter_number": "Adapter on the switch (always 0)",
            "port_number": "Port on the switch"
        },
        status_codes={
            201: "NIO created",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Add a NIO to a Frame Relay switch instance",
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
        r"/projects/{project_id}/frame_relay_switch/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID",
            "adapter_number": "Adapter on the switch (always 0)",
            "port_number": "Port on the switch"
        },
        status_codes={
            204: "NIO deleted",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Remove a NIO from a Frame Relay switch instance")
    def delete_nio(request, response):

        dynamips_manager = Dynamips.instance()
        node = dynamips_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        port_number = int(request.match_info["port_number"])
        nio = yield from node.remove_nio(port_number)
        yield from nio.delete()
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/frame_relay_switch/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/start_capture",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID",
            "adapter_number": "Adapter on the switch (always 0)",
            "port_number": "Port on the switch"
        },
        status_codes={
            200: "Capture started",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Start a packet capture on a Frame Relay switch instance",
        input=NODE_CAPTURE_SCHEMA)
    def start_capture(request, response):

        dynamips_manager = Dynamips.instance()
        node = dynamips_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        port_number = int(request.match_info["port_number"])
        pcap_file_path = os.path.join(node.project.capture_working_directory(), request.json["capture_file_name"])
        yield from node.start_capture(port_number, pcap_file_path, request.json["data_link_type"])
        response.json({"pcap_file_path": pcap_file_path})

    @Route.post(
        r"/projects/{project_id}/frame_relay_switch/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/stop_capture",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID",
            "adapter_number": "Adapter on the switch (always 0)",
            "port_number": "Port on the switch"
        },
        status_codes={
            204: "Capture stopped",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Stop a packet capture on a Frame Relay switch instance")
    def stop_capture(request, response):

        dynamips_manager = Dynamips.instance()
        node = dynamips_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        port_number = int(request.match_info["port_number"])
        yield from node.stop_capture(port_number)
        response.set_status(204)
