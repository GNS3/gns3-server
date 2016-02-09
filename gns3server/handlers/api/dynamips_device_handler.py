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
import asyncio
from ...web.route import Route
from ...schemas.dynamips_device import DEVICE_CREATE_SCHEMA
from ...schemas.dynamips_device import DEVICE_UPDATE_SCHEMA
from ...schemas.dynamips_device import DEVICE_OBJECT_SCHEMA
from ...schemas.dynamips_device import DEVICE_NIO_SCHEMA
from ...schemas.vm import VM_CAPTURE_SCHEMA
from ...modules.dynamips import Dynamips


class DynamipsDeviceHandler:

    """
    API entry points for Dynamips devices.
    """

    @classmethod
    @Route.post(
        r"/projects/{project_id}/dynamips/devices",
        parameters={
            "project_id": "UUID for the project"
        },
        status_codes={
            201: "Instance created",
            400: "Invalid request",
            409: "Conflict"
        },
        description="Create a new Dynamips device instance",
        input=DEVICE_CREATE_SCHEMA,
        output=DEVICE_OBJECT_SCHEMA)
    def create(request, response):

        dynamips_manager = Dynamips.instance()
        device = yield from dynamips_manager.create_device(request.json.pop("name"),
                                                           request.match_info["project_id"],
                                                           request.json.get("device_id"),
                                                           request.json.get("device_type"))

        response.set_status(201)
        response.json(device)

    @classmethod
    @Route.get(
        r"/projects/{project_id}/dynamips/devices/{device_id}",
        parameters={
            "project_id": "UUID for the project",
            "device_id": "UUID for the instance"
        },
        status_codes={
            200: "Success",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Get a Dynamips device instance",
        output=DEVICE_OBJECT_SCHEMA)
    def show(request, response):

        dynamips_manager = Dynamips.instance()
        device = dynamips_manager.get_device(request.match_info["device_id"], project_id=request.match_info["project_id"])
        response.json(device)

    @classmethod
    @Route.put(
        r"/projects/{project_id}/dynamips/devices/{device_id}",
        parameters={
            "project_id": "UUID for the project",
            "device_id": "UUID for the instance"
        },
        status_codes={
            200: "Instance updated",
            400: "Invalid request",
            404: "Instance doesn't exist",
            409: "Conflict"
        },
        description="Update a Dynamips device instance",
        input=DEVICE_UPDATE_SCHEMA,
        output=DEVICE_OBJECT_SCHEMA)
    def update(request, response):

        dynamips_manager = Dynamips.instance()
        device = dynamips_manager.get_device(request.match_info["device_id"], project_id=request.match_info["project_id"])

        if "name" in request.json:
            yield from device.set_name(request.json["name"])

        if "ports" in request.json:
            for port in request.json["ports"]:
                yield from device.set_port_settings(port["port"], port)

        response.json(device)

    @classmethod
    @Route.delete(
        r"/projects/{project_id}/dynamips/devices/{device_id}",
        parameters={
            "project_id": "UUID for the project",
            "device_id": "UUID for the instance"
        },
        status_codes={
            204: "Instance deleted",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Delete a Dynamips device instance")
    def delete(request, response):

        dynamips_manager = Dynamips.instance()
        yield from dynamips_manager.delete_device(request.match_info["device_id"])
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/dynamips/devices/{device_id}/ports/{port_number:\d+}/nio",
        parameters={
            "project_id": "UUID for the project",
            "device_id": "UUID for the instance",
            "port_number": "Port on the device"
        },
        status_codes={
            201: "NIO created",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Add a NIO to a Dynamips device instance",
        input=DEVICE_NIO_SCHEMA)
    def create_nio(request, response):

        dynamips_manager = Dynamips.instance()
        device = dynamips_manager.get_device(request.match_info["device_id"], project_id=request.match_info["project_id"])
        nio = yield from dynamips_manager.create_nio(device, request.json["nio"])
        port_number = int(request.match_info["port_number"])
        port_settings = request.json.get("port_settings")
        mappings = request.json.get("mappings")

        if asyncio.iscoroutinefunction(device.add_nio):
            yield from device.add_nio(nio, port_number)
        else:
            device.add_nio(nio, port_number)

        if port_settings:
            yield from device.set_port_settings(port_number, port_settings)
        elif mappings:
            yield from device.set_mappings(mappings)

        response.set_status(201)
        response.json(nio)

    @classmethod
    @Route.delete(
        r"/projects/{project_id}/dynamips/devices/{device_id}/ports/{port_number:\d+}/nio",
        parameters={
            "project_id": "UUID for the project",
            "device_id": "UUID for the instance",
            "port_number": "Port on the device"
        },
        status_codes={
            204: "NIO deleted",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Remove a NIO from a Dynamips device instance")
    def delete_nio(request, response):

        dynamips_manager = Dynamips.instance()
        device = dynamips_manager.get_device(request.match_info["device_id"], project_id=request.match_info["project_id"])
        port_number = int(request.match_info["port_number"])
        nio = yield from device.remove_nio(port_number)
        yield from nio.delete()
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/dynamips/devices/{device_id}/ports/{port_number:\d+}/start_capture",
        parameters={
            "project_id": "UUID for the project",
            "device_id": "UUID for the instance",
            "port_number": "Port on the device"
        },
        status_codes={
            200: "Capture started",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Start a packet capture on a Dynamips device instance",
        input=VM_CAPTURE_SCHEMA)
    def start_capture(request, response):

        dynamips_manager = Dynamips.instance()
        device = dynamips_manager.get_device(request.match_info["device_id"], project_id=request.match_info["project_id"])
        port_number = int(request.match_info["port_number"])
        pcap_file_path = os.path.join(device.project.capture_working_directory(), request.json["capture_file_name"])
        yield from device.start_capture(port_number, pcap_file_path, request.json["data_link_type"])
        response.json({"pcap_file_path": pcap_file_path})

    @Route.post(
        r"/projects/{project_id}/dynamips/devices/{device_id}/ports/{port_number:\d+}/stop_capture",
        parameters={
            "project_id": "UUID for the project",
            "device_id": "UUID for the instance",
            "port_number": "Port on the device"
        },
        status_codes={
            204: "Capture stopped",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Stop a packet capture on a Dynamips device instance")
    def stop_capture(request, response):

        dynamips_manager = Dynamips.instance()
        device = dynamips_manager.get_device(request.match_info["device_id"], project_id=request.match_info["project_id"])
        port_number = int(request.match_info["port_number"])
        yield from device.stop_capture(port_number)
        response.set_status(204)
