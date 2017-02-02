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
from gns3server.compute.iou import IOU

from gns3server.schemas.node import (
    NODE_CAPTURE_SCHEMA,
    NODE_LIST_IMAGES_SCHEMA,
)

from gns3server.schemas.iou import (
    IOU_CREATE_SCHEMA,
    IOU_START_SCHEMA,
    IOU_OBJECT_SCHEMA
)


class IOUHandler:

    """
    API entry points for IOU.
    """

    @Route.post(
        r"/projects/{project_id}/iou/nodes",
        parameters={
            "project_id": "Project UUID"
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
        vm = yield from iou.create_node(request.json.pop("name"),
                                        request.match_info["project_id"],
                                        request.json.get("node_id"),
                                        console=request.json.get("console"))

        for name, value in request.json.items():
            if hasattr(vm, name) and getattr(vm, name) != value:
                if name == "startup_config_content" and (vm.startup_config_content and len(vm.startup_config_content) > 0):
                    continue
                if name == "private_config_content" and (vm.private_config_content and len(vm.private_config_content) > 0):
                    continue
                setattr(vm, name, value)
        response.set_status(201)
        response.json(vm)

    @Route.get(
        r"/projects/{project_id}/iou/nodes/{node_id}",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            200: "Success",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Get an IOU instance",
        output=IOU_OBJECT_SCHEMA)
    def show(request, response):

        iou_manager = IOU.instance()
        vm = iou_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        response.json(vm)

    @Route.put(
        r"/projects/{project_id}/iou/nodes/{node_id}",
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
        description="Update an IOU instance",
        input=IOU_OBJECT_SCHEMA,
        output=IOU_OBJECT_SCHEMA)
    def update(request, response):

        iou_manager = IOU.instance()
        vm = iou_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])

        for name, value in request.json.items():
            if hasattr(vm, name) and getattr(vm, name) != value:
                setattr(vm, name, value)
        vm.updated()
        response.json(vm)

    @Route.delete(
        r"/projects/{project_id}/iou/nodes/{node_id}",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            204: "Instance deleted",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Delete an IOU instance")
    def delete(request, response):

        yield from IOU.instance().delete_node(request.match_info["node_id"])
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/iou/nodes/{node_id}/start",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            200: "Instance started",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        input=IOU_START_SCHEMA,
        output=IOU_OBJECT_SCHEMA,
        description="Start an IOU instance")
    def start(request, response):

        iou_manager = IOU.instance()
        vm = iou_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])

        for name, value in request.json.items():
            if hasattr(vm, name) and getattr(vm, name) != value:
                setattr(vm, name, value)

        yield from vm.start()
        response.json(vm)

    @Route.post(
        r"/projects/{project_id}/iou/nodes/{node_id}/stop",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID"
        },
        status_codes={
            204: "Instance stopped",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Stop an IOU instance")
    def stop(request, response):

        iou_manager = IOU.instance()
        vm = iou_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        yield from vm.stop()
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/iou/nodes/{node_id}/reload",
        parameters={
            "project_id": "Project UUID",
            "node_id": "Node UUID",
        },
        status_codes={
            204: "Instance reloaded",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Reload an IOU instance")
    def reload(request, response):

        iou_manager = IOU.instance()
        vm = iou_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        yield from vm.reload()
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/iou/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio",
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
        description="Add a NIO to a IOU instance",
        input=NIO_SCHEMA,
        output=NIO_SCHEMA)
    def create_nio(request, response):

        iou_manager = IOU.instance()
        vm = iou_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        nio_type = request.json["type"]
        if nio_type not in ("nio_udp", "nio_tap", "nio_ethernet", "nio_generic_ethernet"):
            raise HTTPConflict(text="NIO of type {} is not supported".format(nio_type))
        nio = iou_manager.create_nio(request.json)
        yield from vm.adapter_add_nio_binding(int(request.match_info["adapter_number"]), int(request.match_info["port_number"]), nio)
        response.set_status(201)
        response.json(nio)

    @Route.delete(
        r"/projects/{project_id}/iou/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio",
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
        description="Remove a NIO from a IOU instance")
    def delete_nio(request, response):

        iou_manager = IOU.instance()
        vm = iou_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        yield from vm.adapter_remove_nio_binding(int(request.match_info["adapter_number"]), int(request.match_info["port_number"]))
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/iou/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/start_capture",
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
            409: "VM not started"
        },
        description="Start a packet capture on an IOU VM instance",
        input=NODE_CAPTURE_SCHEMA)
    def start_capture(request, response):

        iou_manager = IOU.instance()
        vm = iou_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
        adapter_number = int(request.match_info["adapter_number"])
        port_number = int(request.match_info["port_number"])
        pcap_file_path = os.path.join(vm.project.capture_working_directory(), request.json["capture_file_name"])
        yield from vm.start_capture(adapter_number, port_number, pcap_file_path, request.json["data_link_type"])
        response.json({"pcap_file_path": str(pcap_file_path)})

    @Route.post(
        r"/projects/{project_id}/iou/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/stop_capture",
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
            409: "VM not started"
        },
        description="Stop a packet capture on an IOU VM instance")
    def stop_capture(request, response):

        iou_manager = IOU.instance()
        vm = iou_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])

        adapter_number = int(request.match_info["adapter_number"])
        port_number = int(request.match_info["port_number"])
        yield from vm.stop_capture(adapter_number, port_number)
        response.set_status(204)

    @Route.get(
        r"/iou/images",
        status_codes={
            200: "List of IOU images",
        },
        description="Retrieve the list of IOU images",
        output=NODE_LIST_IMAGES_SCHEMA)
    def list_iou_images(request, response):

        iou_manager = IOU.instance()
        images = yield from iou_manager.list_images()
        response.set_status(200)
        response.json(images)

    @Route.post(
        r"/iou/images/{filename:.+}",
        parameters={
            "filename": "Image filename"
        },
        status_codes={
            204: "Image uploaded",
        },
        raw=True,
        description="Upload an IOU image")
    def upload_image(request, response):

        iou_manager = IOU.instance()
        yield from iou_manager.write_image(request.match_info["filename"], request.content)
        response.set_status(204)
