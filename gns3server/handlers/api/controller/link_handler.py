# -*- coding: utf-8 -*-
#
# Copyright (C) 2016 GNS3 Technologies Inc.
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

import aiohttp
import asyncio

from ....web.route import Route
from ....schemas.link import LINK_OBJECT_SCHEMA, LINK_CAPTURE_SCHEMA
from ....controller.project import Project
from ....controller import Controller


class LinkHandler:
    """
    API entry point for Link
    """

    @classmethod
    @Route.post(
        r"/projects/{project_id}/links",
        parameters={
            "project_id": "UUID for the project"
        },
        status_codes={
            201: "Link created",
            400: "Invalid request"
        },
        description="Create a new link instance",
        input=LINK_OBJECT_SCHEMA,
        output=LINK_OBJECT_SCHEMA)
    def create(request, response):

        controller = Controller.instance()
        project = controller.getProject(request.match_info["project_id"])
        link = yield from project.addLink()
        for vm in request.json["vms"]:
            yield from link.addVM(project.getVM(vm["vm_id"]),
                                  vm["adapter_number"],
                                  vm["port_number"])
        yield from link.create()
        response.set_status(201)
        response.json(link)

    @classmethod
    @Route.post(
        r"/projects/{project_id}/links/{link_id}/start_capture",
        parameters={
            "project_id": "UUID for the project",
            "link_id": "UUID of the link"
        },
        status_codes={
            201: "Capture started",
            400: "Invalid request"
        },
        input=LINK_CAPTURE_SCHEMA,
        output=LINK_OBJECT_SCHEMA,
        description="Start capture on a link instance. By default we consider it as an ethernet link")
    def start_capture(request, response):

        controller = Controller.instance()
        project = controller.getProject(request.match_info["project_id"])
        link = project.getLink(request.match_info["link_id"])
        yield from link.start_capture(data_link_type=request.json.get("data_link_type", "DLT_EN10MB"), capture_file_name=request.json.get("capture_file_name"))
        response.set_status(201)
        response.json(link)

    @classmethod
    @Route.post(
        r"/projects/{project_id}/links/{link_id}/stop_capture",
        parameters={
            "project_id": "UUID for the project",
            "link_id": "UUID of the link"
        },
        status_codes={
            201: "Capture stopped",
            400: "Invalid request"
        },
        description="Stop capture on a link instance")
    def stop_capture(request, response):

        controller = Controller.instance()
        project = controller.getProject(request.match_info["project_id"])
        link = project.getLink(request.match_info["link_id"])
        yield from link.stop_capture()
        response.set_status(201)
        response.json(link)

    @classmethod
    @Route.delete(
        r"/projects/{project_id}/links/{link_id}",
        parameters={
            "project_id": "UUID for the project",
            "link_id": "UUID of the link"
        },
        status_codes={
            204: "Link deleted",
            400: "Invalid request"
        },
        description="Delete a link instance")
    def delete(request, response):

        controller = Controller.instance()
        project = controller.getProject(request.match_info["project_id"])
        link = project.getLink(request.match_info["link_id"])
        yield from link.delete()
        response.set_status(204)
        response.json(link)

    @classmethod
    @Route.get(
        r"/projects/{project_id}/links/{link_id}/pcap",
        parameters={
            "project_id": "UUID for the project",
            "link_id": "UUID of the link"
        },
        description="Get the pcap from the capture",
        status_codes={
            200: "Return the file",
            403: "Permission denied",
            404: "The file doesn't exist"
        })
    def pcap(request, response):

        controller = Controller.instance()
        project = controller.getProject(request.match_info["project_id"])
        link = project.getLink(request.match_info["link_id"])

        if link.capture_file_path is None:
            raise aiohttp.web.HTTPNotFound(text="pcap file not found")

        try:
            print(link.capture_file_path)
            with open(link.capture_file_path, "rb") as f:

                response.content_type = "application/vnd.tcpdump.pcap"
                response.set_status(200)
                response.enable_chunked_encoding()
                # Very important: do not send a content length otherwise QT close the connection but curl can consume the Feed
                response.content_length = None
                response.start(request)

                while True:
                    chunk = f.read(4096)
                    if not chunk:
                        break
                    yield from response.write(chunk)
        except OSError:
            raise aiohttp.web.HTTPNotFound(text="pcap file {} not found or not accessible".format(link.capture_file_path))
