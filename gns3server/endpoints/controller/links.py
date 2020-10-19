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

import aiohttp
import multidict

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import StreamingResponse
from fastapi.encoders import jsonable_encoder
from typing import List
from uuid import UUID

from gns3server.controller import Controller
from gns3server.controller.controller_error import ControllerError
from gns3server.controller.link import Link
from gns3server.endpoints.schemas.common import ErrorMessage
from gns3server.endpoints import schemas

router = APIRouter()

responses = {
    404: {"model": ErrorMessage, "description": "Could not find project or link"}
}


async def dep_link(project_id: UUID, link_id: UUID):
    """
    Dependency to retrieve a link.
    """

    project = await Controller.instance().get_loaded_project(str(project_id))
    link = project.get_link(str(link_id))
    return link


@router.get("",
            response_model=List[schemas.Link],
            response_model_exclude_unset=True)
async def get_links(project_id: UUID):
    """
    Return all links for a given project.
    """

    project = await Controller.instance().get_loaded_project(str(project_id))
    return [v.__json__() for v in project.links.values()]


@router.post("",
             status_code=status.HTTP_201_CREATED,
             response_model=schemas.Link,
             responses={404: {"model": ErrorMessage, "description": "Could not find project"},
                        409: {"model": ErrorMessage, "description": "Could not create link"}})
async def create_link(project_id: UUID, link_data: schemas.Link):
    """
    Create a new link.
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


@router.get("/{link_id}/available_filters",
            responses=responses)
async def get_filters(link: Link = Depends(dep_link)):
    """
    Return all filters available for a given link.
    """

    return link.available_filters()


@router.get("/{link_id}",
            response_model=schemas.Link,
            response_model_exclude_unset=True,
            responses=responses)
async def get_link(link: Link = Depends(dep_link)):
    """
    Return a link.
    """

    return link.__json__()


@router.put("/{link_id}",
            response_model=schemas.Link,
            response_model_exclude_unset=True,
            responses=responses)
async def update_link(link_data: schemas.Link, link: Link = Depends(dep_link)):
    """
    Update a link.
    """

    link_data = jsonable_encoder(link_data, exclude_unset=True)
    if "filters" in link_data:
        await link.update_filters(link_data["filters"])
    if "suspend" in link_data:
        await link.update_suspend(link_data["suspend"])
    if "nodes" in link_data:
        await link.update_nodes(link_data["nodes"])
    return link.__json__()


@router.post("/{link_id}/start_capture",
             status_code=status.HTTP_201_CREATED,
             response_model=schemas.Link,
             responses=responses)
async def start_capture(capture_data: dict, link: Link = Depends(dep_link)):
    """
    Start packet capture on the link.
    """

    await link.start_capture(data_link_type=capture_data.get("data_link_type", "DLT_EN10MB"),
                             capture_file_name=capture_data.get("capture_file_name"))
    return link.__json__()


@router.post("/{link_id}/stop_capture",
             status_code=status.HTTP_201_CREATED,
             response_model=schemas.Link,
             responses=responses)
async def stop_capture(link: Link = Depends(dep_link)):
    """
    Stop packet capture on the link.
    """

    await link.stop_capture()
    return link.__json__()


@router.delete("/{link_id}",
               status_code=status.HTTP_204_NO_CONTENT,
               responses=responses)
async def delete_link(project_id: UUID, link: Link = Depends(dep_link)):
    """
    Delete a link.
    """

    project = await Controller.instance().get_loaded_project(str(project_id))
    await project.delete_link(link.id)


@router.post("/{link_id}/reset",
             response_model=schemas.Link,
             responses=responses)
async def reset_link(link: Link = Depends(dep_link)):
    """
    Reset a link.
    """

    await link.reset()
    return link.__json__()


@router.get("/{link_id}/pcap",
            responses=responses)
async def pcap(request: Request, link: Link = Depends(dep_link)):
    """
    Stream the PCAP capture file from compute.
    """

    if not link.capturing:
        raise ControllerError("This link has no active packet capture")

    compute = link.compute
    pcap_streaming_url = link.pcap_streaming_url()
    headers = multidict.MultiDict(request.headers)
    headers['Host'] = compute.host
    headers['Router-Host'] = request.client.host
    body = await request.body()

    async def compute_pcpa_stream():

        connector = aiohttp.TCPConnector(limit=None, force_close=True)
        async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
            async with session.request(request.method, pcap_streaming_url, timeout=None, data=body) as compute_response:
                async for data in compute_response.content.iter_any():
                    if not data:
                        break
                    yield data

    return StreamingResponse(compute_pcpa_stream(), media_type="application/vnd.tcpdump.pcap")
