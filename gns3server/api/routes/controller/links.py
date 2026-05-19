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

import asyncio
import os
import multidict
import aiohttp

from fastapi import APIRouter, Depends, Request, status, WebSocket
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.encoders import jsonable_encoder
from typing import List, Union
from uuid import UUID

from gns3server.controller import Controller
from gns3server.controller.controller_error import ControllerError
from gns3server.db.repositories.rbac import RbacRepository
from gns3server.controller.link import Link
from gns3server.utils.http_client import HTTPClient
from gns3server.utils.port_allocator import link_id_to_port
from gns3server.utils.websocket_to_websocket import websocket_proxy
from gns3server import schemas
from gns3server.agent.web_wireshark.manager import WebWiresharkManager

from .dependencies.database import get_repository
from .dependencies.rbac import has_privilege, has_privilege_on_websocket

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
async def start_capture(
    capture_data: schemas.LinkCapture,
    http_request: Request,
    link: Link = Depends(dep_link)
) -> schemas.Link:
    """
    Start packet capture on the link.

    Required privilege: Link.Capture
    """

    # Extract JWT token from Authorization header
    auth_header = http_request.headers.get("Authorization", "")
    jwt_token = auth_header.replace("Bearer ", "") if auth_header else None

    await link.start_capture(
        data_link_type=capture_data.data_link_type,
        capture_file_name=capture_data.capture_file_name,
        wireshark=capture_data.wireshark,
        jwt_token=jwt_token
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


@router.post(
    "/{link_id}/capture/wireshark/restart",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(has_privilege("Link.Capture"))]
)
async def restart_wireshark(
    http_request: Request,
    link: Link = Depends(dep_link)
) -> dict:
    """
    Restart Wireshark window without stopping the capture.

    This allows recovery after accidentally closing the Wireshark window.

    Required privilege: Link.Capture
    """
    # Extract JWT token from Authorization header
    auth_header = http_request.headers.get("Authorization", "")
    jwt_token = auth_header.replace("Bearer ", "") if auth_header else None

    if not jwt_token:
        raise ControllerError("JWT token is required for Web Wireshark restart")

    await link._restart_web_wireshark(jwt_token)
    return {"status": "restarted"}


@router.get(
    "/{link_id}/capture/stream",
    dependencies=[Depends(has_privilege("Link.Capture"))]
)
async def stream_pcap(request: Request, link: Link = Depends(dep_link)) -> StreamingResponse:
    """
    Stream the PCAP capture file from compute.

    Required privilege: Link.Capture
    """

    # Check both capturing flag and capture_node to avoid race condition
    # when stop_capture() sets _capture_node = None before this check completes
    if not link.capturing or not link.capture_node:
        log.info(f"Stream pcap ended for link {link.id}: capture stopped before stream completed")
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


@router.get(
    "/{link_id}/capture/file",
    dependencies=[Depends(has_privilege("Link.Capture"))],
    response_class=FileResponse
)
async def download_capture_file(link: Link = Depends(dep_link)):
    """
    Download the PCAP capture file.

    This endpoint allows downloading the capture file even while capture is active.
    The file is streamed directly, so partial data may be received if capture is still running.

    Required privilege: Link.Capture
    """
    if not link.capture_file_path:
        raise ControllerError("No capture file path set for this link")

    if not os.path.exists(link.capture_file_path):
        raise ControllerError(f"Capture file not found: {link.capture_file_path}")

    return FileResponse(
        path=link.capture_file_path,
        filename=os.path.basename(link.capture_file_path),
        media_type="application/vnd.tcpdump.pcap"
    )


@router.websocket("/{link_id}/capture/web-wireshark")
async def web_wireshark_websocket(
    websocket: WebSocket,
    link_id: str,
    project_id: str,
    current_user: schemas.User = Depends(has_privilege_on_websocket("Link.Capture"))
):
    """
    WebSocket proxy endpoint for xpra container (Web Wireshark).

    Path: ws://host/v3/projects/{project_id}/links/{link_id}/capture/web-wireshark?token=<jwt_token>

    Required privilege: Link.Capture

    Note: The WebSocket connection is accepted by the authentication dependency
    (get_current_active_user_from_websocket) with the proper subprotocol negotiation.
    """
    log.info(f"New WebSocket connection for project {project_id}, link {link_id}, user {current_user.username}")

    try:
        # Get container information
        container_name = f"gns3-wireshark-{project_id}"

        # Calculate xpra port (using deterministic hash)
        xpra_port = link_id_to_port(link_id)

        # Get container IP
        manager = WebWiresharkManager()
        try:
            container_ip = await manager.get_container_ip(container_name)

            if not container_ip:
                log.error(f"Container {container_name} not found in wireshark network")
                await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
                return

            # Build container WebSocket URL
            container_ws_url = f"ws://{container_ip}:{xpra_port}"
            log.info(f"Proxying WebSocket to container: {container_ws_url}")

            # Get client's requested subprotocols from request headers
            scope = websocket.scope
            headers = dict(scope.get("headers", []))
            requested_protocols_header = headers.get(b"sec-websocket-protocol", b"")
            requested_protocols = [p.decode().strip() for p in requested_protocols_header.split(b",") if p.strip()]
            log.info(f"Client requested subprotocols: {requested_protocols}")

            # The WebSocket connection has already been accepted by the authentication dependency
            # with the proper subprotocol. Now we just proxy data to the backend.
            await websocket_proxy(websocket, container_ws_url, requested_protocols)
        finally:
            await manager.close()

    except Exception as e:
        log.error(f"Error in WebSocket proxy for link {link_id}: {e}")
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason=str(e))
        except:
            pass


@router.get(
    "/{link_id}/iface",
    response_model=Union[schemas.UDPPortInfo, schemas.EthernetPortInfo],
    dependencies=[Depends(has_privilege("Link.Audit"))]
)
async def get_iface(link: Link = Depends(dep_link)) -> Union[schemas.UDPPortInfo, schemas.EthernetPortInfo]:
    """
    Return iface info for links to Cloud or NAT devices.

    Required privilege: Link.Audit
    """

    ifaces_info = {}
    for node_data in link._nodes:
        node = node_data["node"]
        if node.node_type not in ("cloud", "nat"):
            continue

        port_number = node_data["port_number"]
        compute = node.compute
        project_id = link.project.id
        response = await compute.get(f"/projects/{project_id}/{node.node_type}/nodes/{node.id}")
        if "ports_mapping" not in response.json:
            continue
        ports_mapping = response.json["ports_mapping"]
        
        for port in ports_mapping:
            port_num = port.get("port_number")

            if port_num and int(port_num) == int(port_number):
                port_type = port.get("type", "")
                if "udp" in port_type.lower():
                    ifaces_info = {
                        "node_id": node.id,
                        "type": f"{port_type}",
                        "lport": port["lport"],
                        "rhost": port["rhost"],
                        "rport": port["rport"]
                    }
                else:
                    ifaces_info = {
                        "node_id": node.id,
                        "type": f"{port_type}",
                        "interface": port["interface"],
                    }
    
    if not ifaces_info:
        raise ControllerError("Link not connected to Cloud/NAT")
    return ifaces_info
