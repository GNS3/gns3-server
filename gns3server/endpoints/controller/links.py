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

"""
API endpoints for links.
"""

from fastapi import APIRouter, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from typing import List
from uuid import UUID

from gns3server.controller import Controller
from gns3server.controller.controller_error import ControllerError
from gns3server.endpoints.schemas.common import ErrorMessage
from gns3server.endpoints.schemas.links import Link

import aiohttp
import multidict


router = APIRouter()


@router.get("/projects/{project_id}/links",
            summary="List of all links",
            response_model=List[Link],
            response_description="List of links",
            response_model_exclude_unset=True)
async def list_links(project_id: UUID):

    project = await Controller.instance().get_loaded_project(str(project_id))
    return [v.__json__() for v in project.links.values()]


@router.post("/projects/{project_id}/links",
             summary="Create a new link",
             status_code=status.HTTP_201_CREATED,
             response_model=Link,
             responses={404: {"model": ErrorMessage, "description": "Could not find project"},
                        409: {"model": ErrorMessage, "description": "Could not create link"}})
async def create_link(project_id: UUID, link_data: Link):
    """
    Create a new link on the controller.
    """

    project = await Controller.instance().get_loaded_project(str(project_id))
    link = await project.add_link()
    link_data = jsonable_encoder(link_data, exclude_unset=True)
    if "filters" in link_data:
        await link.update_filters(link_data["filters"])
    if "suspend" in link_data:
        await link.update_suspend(link_data["suspend"])
    try:
        for node in link_data["nodes"]:
            await link.add_node(project.get_node(node["node_id"]),
                                node.get("adapter_number", 0),
                                node.get("port_number", 0),
                                label=node.get("label"))
    except ControllerError as e:
        await project.delete_link(link.id)
        raise e
    return link.__json__()


@router.get("/projects/{project_id}/links/{link_id}/available_filters",
            summary="List of filters",
            responses={404: {"model": ErrorMessage, "description": "Could not find project or link"}})
async def list_filters(project_id: UUID, link_id: UUID):
    """
    Return the list of filters available for this link.
    """

    project = await Controller.instance().get_loaded_project(str(project_id))
    link = project.get_link(str(link_id))
    return link.available_filters()


@router.get("/projects/{project_id}/links/{link_id}",
            summary="Get a link",
            response_model=Link,
            response_description="Link data",
            response_model_exclude_unset=True,
            responses={404: {"model": ErrorMessage, "description": "Could not find project or link"}})
async def get_link(project_id: UUID, link_id: UUID):

    project = await Controller.instance().get_loaded_project(str(project_id))
    link = project.get_link(str(link_id))
    return link.__json__()


@router.put("/projects/{project_id}/links/{link_id}",
            summary="Update a link",
            response_model=Link,
            response_description="Updated link",
            response_model_exclude_unset=True,
            responses={404: {"model": ErrorMessage, "description": "Project or link not found"}})
async def update_link(project_id: UUID, link_id: UUID, link_data: Link):

    project = await Controller.instance().get_loaded_project(str(project_id))
    link = project.get_link(str(link_id))
    link_data = jsonable_encoder(link_data, exclude_unset=True)
    if "filters" in link_data:
        await link.update_filters(link_data["filters"])
    if "suspend" in link_data:
        await link.update_suspend(link_data["suspend"])
    if "nodes" in link_data:
        await link.update_nodes(link_data["nodes"])
    return link.__json__()


@router.post("/projects/{project_id}/links/{link_id}/start_capture",
             summary="Start a packet capture",
             status_code=status.HTTP_201_CREATED,
             response_model=Link,
             responses={404: {"model": ErrorMessage, "description": "Project or link not found"}})
async def start_capture(project_id: UUID, link_id: UUID, capture_data: dict):
    """
    Start packet capture on the link.
    """

    project = await Controller.instance().get_loaded_project(str(project_id))
    link = project.get_link(str(link_id))
    await link.start_capture(data_link_type=capture_data.get("data_link_type", "DLT_EN10MB"),
                             capture_file_name=capture_data.get("capture_file_name"))
    return link.__json__()


@router.post("/projects/{project_id}/links/{link_id}/stop_capture",
             summary="Stop a packet capture",
             status_code=status.HTTP_201_CREATED,
             response_model=Link,
             responses={404: {"model": ErrorMessage, "description": "Project or link not found"}})
async def stop_capture(project_id: UUID, link_id: UUID):
    """
    Stop packet capture on the link.
    """

    project = await Controller.instance().get_loaded_project(str(project_id))
    link = project.get_link(str(link_id))
    await link.stop_capture()
    return link.__json__()


@router.delete("/projects/{project_id}/links/{link_id}",
             summary="Delete a link",
             status_code=status.HTTP_204_NO_CONTENT,
             responses={404: {"model": ErrorMessage, "description": "Project or link not found"}})
async def delete(project_id: UUID, link_id: UUID):
    """
    Delete link from the project.
    """

    project = await Controller.instance().get_loaded_project(str(project_id))
    await project.delete_link(str(link_id))


@router.post("/projects/{project_id}/links/{link_id}/reset",
             summary="Reset a link",
             response_model=Link,
             responses={404: {"model": ErrorMessage, "description": "Project or link not found"}})
async def reset(project_id: UUID, link_id: UUID):

    project = await Controller.instance().get_loaded_project(str(project_id))
    link = project.get_link(str(link_id))
    await link.reset()
    return link.__json__()


# @router.post("/projects/{project_id}/links/{link_id}/pcap",
#              summary="Stream a packet capture",
#              responses={404: {"model": ErrorMessage, "description": "Project or link not found"}})
# async def pcap(project_id: UUID, link_id: UUID, request: Request):
#     """
#     Stream the PCAP capture file from compute.
#     """
#
#     project = await Controller.instance().get_loaded_project(str(project_id))
#     link = project.get_link(str(link_id))
#     if not link.capturing:
#         raise ControllerError("This link has no active packet capture")
#
#     compute = link.compute
#     pcap_streaming_url = link.pcap_streaming_url()
#     headers = multidict.MultiDict(request.headers)
#     headers['Host'] = compute.host
#     headers['Router-Host'] = request.client.host
#     body = await request.body()
#
#     connector = aiohttp.TCPConnector(limit=None, force_close=True)
#     async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
#         async with session.request(request.method, pcap_streaming_url, timeout=None, data=body) as response:
#             proxied_response = aiohttp.web.Response(headers=response.headers, status=response.status)
#             if response.headers.get('Transfer-Encoding', '').lower() == 'chunked':
#                 proxied_response.enable_chunked_encoding()
#
#             await proxied_response.prepare(request)
#             async for data in response.content.iter_any():
#                 if not data:
#                     break
#                 await proxied_response.write(data)
#
#     #return StreamingResponse(file_like, media_type="video/mp4"))