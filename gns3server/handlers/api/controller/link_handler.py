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

import asyncio
import aiohttp

from gns3server.web.route import Route
from gns3server.controller import Controller

from gns3server.schemas.link import (
    LINK_OBJECT_SCHEMA,
    LINK_CAPTURE_SCHEMA
)


class LinkHandler:
    """
    API entry point for Link
    """

    @Route.get(
        r"/projects/{project_id}/links",
        parameters={
            "project_id": "Project UUID"
        },
        status_codes={
            200: "List of links returned",
        },
        description="List links of a project")
    def list_links(request, response):

        project = yield from Controller.instance().get_loaded_project(request.match_info["project_id"])
        response.json([v for v in project.links.values()])

    @Route.post(
        r"/projects/{project_id}/links",
        parameters={
            "project_id": "Project UUID"
        },
        status_codes={
            201: "Link created",
            400: "Invalid request"
        },
        description="Create a new link instance",
        input=LINK_OBJECT_SCHEMA,
        output=LINK_OBJECT_SCHEMA)
    def create(request, response):

        project = yield from Controller.instance().get_loaded_project(request.match_info["project_id"])
        link = yield from project.add_link()
        try:
            for node in request.json["nodes"]:
                yield from link.add_node(project.get_node(node["node_id"]),
                                         node.get("adapter_number", 0),
                                         node.get("port_number", 0),
                                         label=node.get("label"))
        except aiohttp.web_exceptions.HTTPException as e:
            yield from project.delete_link(link.id)
            raise e
        response.set_status(201)
        response.json(link)

    @Route.put(
        r"/projects/{project_id}/links/{link_id}",
        parameters={
            "project_id": "Project UUID",
            "link_id": "Link UUID"
        },
        status_codes={
            201: "Link updated",
            400: "Invalid request"
        },
        description="Update a link instance",
        input=LINK_OBJECT_SCHEMA,
        output=LINK_OBJECT_SCHEMA)
    def update(request, response):

        project = yield from Controller.instance().get_loaded_project(request.match_info["project_id"])
        link = project.get_link(request.match_info["link_id"])
        yield from link.update_nodes(request.json["nodes"])
        response.set_status(201)
        response.json(link)

    @Route.post(
        r"/projects/{project_id}/links/{link_id}/start_capture",
        parameters={
            "project_id": "Project UUID",
            "link_id": "Link UUID"
        },
        status_codes={
            201: "Capture started",
            400: "Invalid request"
        },
        input=LINK_CAPTURE_SCHEMA,
        output=LINK_OBJECT_SCHEMA,
        description="Start capture on a link instance. By default we consider it as an Ethernet link")
    def start_capture(request, response):

        project = yield from Controller.instance().get_loaded_project(request.match_info["project_id"])
        link = project.get_link(request.match_info["link_id"])
        yield from link.start_capture(data_link_type=request.json.get("data_link_type", "DLT_EN10MB"), capture_file_name=request.json.get("capture_file_name"))
        response.set_status(201)
        response.json(link)

    @Route.post(
        r"/projects/{project_id}/links/{link_id}/stop_capture",
        parameters={
            "project_id": "Project UUID",
            "link_id": "Link UUID"
        },
        status_codes={
            201: "Capture stopped",
            400: "Invalid request"
        },
        description="Stop capture on a link instance")
    def stop_capture(request, response):

        project = yield from Controller.instance().get_loaded_project(request.match_info["project_id"])
        link = project.get_link(request.match_info["link_id"])
        yield from link.stop_capture()
        response.set_status(201)
        response.json(link)

    @Route.delete(
        r"/projects/{project_id}/links/{link_id}",
        parameters={
            "project_id": "Project UUID",
            "link_id": "Link UUID"
        },
        status_codes={
            204: "Link deleted",
            400: "Invalid request"
        },
        description="Delete a link instance")
    def delete(request, response):

        project = yield from Controller.instance().get_loaded_project(request.match_info["project_id"])
        yield from project.delete_link(request.match_info["link_id"])
        response.set_status(204)

    @Route.get(
        r"/projects/{project_id}/links/{link_id}/pcap",
        parameters={
            "project_id": "Project UUID",
            "link_id": "Link UUID"
        },
        description="Stream the pcap capture file",
        status_codes={
            200: "File returned",
            403: "Permission denied",
            404: "The file doesn't exist"
        })
    def pcap(request, response):

        project = yield from Controller.instance().get_loaded_project(request.match_info["project_id"])
        link = project.get_link(request.match_info["link_id"])

        if link.capture_file_path is None:
            raise aiohttp.web.HTTPNotFound(text="pcap file not found")

        try:
            with open(link.capture_file_path, "rb") as f:

                response.content_type = "application/vnd.tcpdump.pcap"
                response.set_status(200)
                response.enable_chunked_encoding()
                # Very important: do not send a content length otherwise QT closes the connection (curl can consume the feed)
                response.content_length = None
                response.start(request)

                while True:
                    chunk = f.read(4096)
                    if not chunk:
                        yield from asyncio.sleep(0.1)
                    yield from response.write(chunk)
        except OSError:
            raise aiohttp.web.HTTPNotFound(text="pcap file {} not found or not accessible".format(link.capture_file_path))
