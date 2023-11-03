#
# Copyright (C) 2023 GNS3 Technologies Inc.
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
API routes for links.
"""

import multidict
import aiohttp

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import StreamingResponse
from fastapi.encoders import jsonable_encoder
from typing import List
from uuid import UUID

from gns3server.controller import Controller
from gns3server.controller.controller_error import ControllerError
from gns3server.db.repositories.rbac import RbacRepository
from gns3server.controller.link import Link
from gns3server.utils.http_client import HTTPClient
from gns3server import schemas

from .dependencies.database import get_repository
from .dependencies.rbac import has_privilege

import logging

log = logging.getLogger(__name__)

responses = {404: {"model": schemas.ErrorMessage, "description": "Could not find project or link"}}

router = APIRouter(responses=responses)


async def dep_link(project_id: UUID, link_id: UUID) -> Link:
    """
    Dependency to retrieve a link.
    """

    project = await Controller.instance().get_loaded_project(str(project_id))
    link = project.get_link(str(link_id))
    return link


@router.get(
    "",
    response_model=List[schemas.Link],
    response_model_exclude_unset=True,
    dependencies=[Depends(has_privilege("Link.Audit"))]
)
async def get_links(project_id: UUID) -> List[schemas.Link]:
    """
    Return all links for a given project.

    Required privilege: Link.Audit
    """

    project = await Controller.instance().get_loaded_project(str(project_id))
    if project.status == "closed":
        # allow to retrieve links from a closed project
        return project.links.values()
    return [v.asdict() for v in project.links.values()]


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.Link,
    responses={
        404: {"model": schemas.ErrorMessage, "description": "Could not find project"},
        409: {"model": schemas.ErrorMessage, "description": "Could not create link"},
    },
    dependencies=[Depends(has_privilege("Link.Allocate"))]
)
async def create_link(project_id: UUID, link_data: schemas.LinkCreate) -> schemas.Link:
    """
    Create a new link.

    Required privilege: Link.Allocate
    """

    project = await Controller.instance().get_loaded_project(str(project_id))
    link = await project.add_link()
    link_data = jsonable_encoder(link_data, exclude_unset=True)
    if "filters" in link_data:
        await link.update_filters(link_data["filters"])
    if "link_style" in link_data:
        await link.update_link_style(link_data["link_style"])
    if "suspend" in link_data:
        await link.update_suspend(link_data["suspend"])
    try:
        for node in link_data["nodes"]:
            await link.add_node(
                project.get_node(node["node_id"]),
                node.get("adapter_number", 0),
                node.get("port_number", 0),
                label=node.get("label"),
            )
    except ControllerError as e:
        await project.delete_link(link.id)
        raise e
    return link.asdict()


@router.get(
    "/{link_id}/available_filters",
    dependencies=[Depends(has_privilege("Link.Audit"))]
)
async def get_filters(link: Link = Depends(dep_link)) -> List[dict]:
    """
    Return all filters available for a given link.

    Required privilege: Link.Audit
    """

    return link.available_filters()


@router.get(
    "/{link_id}",
    response_model=schemas.Link,
    response_model_exclude_unset=True,
    dependencies=[Depends(has_privilege("Link.Audit"))]
)
async def get_link(link: Link = Depends(dep_link)) -> schemas.Link:
    """
    Return a link.

    Required privilege: Link.Audit
    """

    return link.asdict()


@router.put(
    "/{link_id}",
    response_model=schemas.Link,
    response_model_exclude_unset=True,
    dependencies=[Depends(has_privilege("Link.Modify"))]
)
async def update_link(link_data: schemas.LinkUpdate, link: Link = Depends(dep_link)) -> schemas.Link:
    """
    Update a link.

    Required privilege: Link.Modify
    """

    link_data = jsonable_encoder(link_data, exclude_unset=True)
    if "filters" in link_data:
        await link.update_filters(link_data["filters"])
    if "link_style" in link_data:
        await link.update_link_style(link_data["link_style"])
    if "suspend" in link_data:
        await link.update_suspend(link_data["suspend"])
    if "nodes" in link_data:
        await link.update_nodes(link_data["nodes"])
    return link.asdict()


@router.delete(
    "/{link_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(has_privilege("Link.Allocate"))]
)
async def delete_link(
        project_id: UUID,
        link: Link = Depends(dep_link),
        rbac_repo: RbacRepository = Depends(get_repository(RbacRepository))
) -> None:
    """
    Delete a link.

    Required privilege: Link.Allocate
    """

    project = await Controller.instance().get_loaded_project(str(project_id))
    await project.delete_link(link.id)
    await rbac_repo.delete_all_ace_starting_with_path(f"/links/{link.id}")


@router.post(
    "/{link_id}/reset",
    response_model=schemas.Link,
    dependencies=[Depends(has_privilege("Link.Modify"))]
)
async def reset_link(link: Link = Depends(dep_link)) -> schemas.Link:
    """
    Reset a link.

    Required privilege: Link.Modify
    """

    await link.reset()
    return link.asdict()


@router.post(
    "/{link_id}/capture/start",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.Link,
    dependencies=[Depends(has_privilege("Link.Capture"))]
)
async def start_capture(capture_data: dict, link: Link = Depends(dep_link)) -> schemas.Link:
    """
    Start packet capture on the link.

    Required privilege: Link.Capture
    """

    await link.start_capture(
        data_link_type=capture_data.get("data_link_type", "DLT_EN10MB"),
        capture_file_name=capture_data.get("capture_file_name"),
    )
    return link.asdict()


@router.post(
    "/{link_id}/capture/stop",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(has_privilege("Link.Capture"))]
)
async def stop_capture(link: Link = Depends(dep_link)) -> None:
    """
    Stop packet capture on the link.

    Required privilege: Link.Capture
    """

    await link.stop_capture()


@router.get(
    "/{link_id}/capture/stream",
    dependencies=[Depends(has_privilege("Link.Capture"))]
)
async def stream_pcap(request: Request, link: Link = Depends(dep_link)) -> StreamingResponse:
    """
    Stream the PCAP capture file from compute.

    Required privilege: Link.Capture
    """

    if not link.capturing:
        raise ControllerError("This link has no active packet capture")

    compute = link.compute
    pcap_streaming_url = link.pcap_streaming_url()
    headers = multidict.MultiDict(request.headers)
    headers["Host"] = compute.host
    headers["Router-Host"] = request.client.host
    body = await request.body()

    async def compute_pcap_stream():

        try:
            ssl_context = Controller.instance().ssl_context()
            async with HTTPClient.request(
                    request.method,
                    pcap_streaming_url,
                    user=compute.user,
                    password=compute.password,
                    ssl_context=ssl_context,
                    timeout=None,
                    data=body
            ) as response:
                async for data in response.content.iter_any():
                    if not data:
                        break
                    yield data
        except aiohttp.ClientError as e:
            raise ControllerError(f"Client error received when receiving pcap stream from compute: {e}")

    return StreamingResponse(compute_pcap_stream(), media_type="application/vnd.tcpdump.pcap")
