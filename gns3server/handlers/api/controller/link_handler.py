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
import multidict

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
    async def list_links(request, response):

        project = await Controller.instance().get_loaded_project(request.match_info["project_id"])
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
    async def create(request, response):

        project = await Controller.instance().get_loaded_project(request.match_info["project_id"])
        link = await project.add_link()
        if "filters" in request.json:
            await link.update_filters(request.json["filters"])
        if "link_style" in request.json:
            await link.update_link_style(request.json["link_style"])
        if "suspend" in request.json:
            await link.update_suspend(request.json["suspend"])
        try:
            for node in request.json["nodes"]:
                await link.add_node(project.get_node(node["node_id"]),
                                         node.get("adapter_number", 0),
                                         node.get("port_number", 0),
                                         label=node.get("label"))
        except aiohttp.web.HTTPException as e:
            await project.delete_link(link.id)
            raise e
        response.set_status(201)
        response.json(link)

    @Route.get(
        r"/projects/{project_id}/links/{link_id}/available_filters",
        parameters={
            "project_id": "Project UUID",
            "link_id": "Link UUID"
        },
        status_codes={
            200: "List of filters",
            400: "Invalid request"
        },
        description="Return the list of filters available for this link")
    async def list_filters(request, response):

        project = await Controller.instance().get_loaded_project(request.match_info["project_id"])
        link = project.get_link(request.match_info["link_id"])
        response.set_status(200)
        response.json(link.available_filters())

    @Route.get(
        r"/projects/{project_id}/links/{link_id}",
        parameters={
            "project_id": "Project UUID",
            "link_id": "Link UUID"
        },
        status_codes={
            200: "Link found",
            400: "Invalid request",
            404: "Link doesn't exist"
        },
        description="Get a link instance",
        output=LINK_OBJECT_SCHEMA)
    async def get_link(request, response):

        project = await Controller.instance().get_loaded_project(request.match_info["project_id"])
        link = project.get_link(request.match_info["link_id"])
        response.set_status(200)
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
    async def update(request, response):

        project = await Controller.instance().get_loaded_project(request.match_info["project_id"])
        link = project.get_link(request.match_info["link_id"])
        if "filters" in request.json:
            await link.update_filters(request.json["filters"])
        if "link_style" in request.json:
            await link.update_link_style(request.json["link_style"])
        if "suspend" in request.json:
            await link.update_suspend(request.json["suspend"])
        if "nodes" in request.json:
            await link.update_nodes(request.json["nodes"])
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
    async def start_capture(request, response):

        project = await Controller.instance().get_loaded_project(request.match_info["project_id"])
        link = project.get_link(request.match_info["link_id"])
        await link.start_capture(data_link_type=request.json.get("data_link_type", "DLT_EN10MB"),
                                 capture_file_name=request.json.get("capture_file_name"))
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
    async def stop_capture(request, response):

        project = await Controller.instance().get_loaded_project(request.match_info["project_id"])
        link = project.get_link(request.match_info["link_id"])
        await link.stop_capture()
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
    async def delete(request, response):

        project = await Controller.instance().get_loaded_project(request.match_info["project_id"])
        await project.delete_link(request.match_info["link_id"])
        response.set_status(204)

    @Route.get(
        r"/projects/{project_id}/links/{link_id}/pcap",
        parameters={
            "project_id": "Project UUID",
            "link_id": "Link UUID"
        },
        description="Stream the PCAP capture file from compute",
        status_codes={
            200: "File returned",
            403: "Permission denied",
            404: "The file doesn't exist"
        })
    async def pcap(request, response):

        project = await Controller.instance().get_loaded_project(request.match_info["project_id"])
        ssl_context = Controller.instance().ssl_context()
        link = project.get_link(request.match_info["link_id"])
        if not link.capturing:
            raise aiohttp.web.HTTPConflict(text="This link has no active packet capture")

        compute = link.compute
        pcap_streaming_url = link.pcap_streaming_url()
        headers = multidict.MultiDict(request.headers)
        headers['Host'] = compute.host
        headers['Router-Host'] = request.host
        body = await request.read()

        connector = aiohttp.TCPConnector(limit=None, force_close=True, ssl_context=ssl_context)
        async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
            async with session.request(request.method, pcap_streaming_url, timeout=None, data=body) as response:
                proxied_response = aiohttp.web.Response(headers=response.headers, status=response.status)
                if response.headers.get('Transfer-Encoding', '').lower() == 'chunked':
                    proxied_response.enable_chunked_encoding()

                await proxied_response.prepare(request)
                async for data in response.content.iter_any():
                    if not data:
                        break
                    await proxied_response.write(data)
