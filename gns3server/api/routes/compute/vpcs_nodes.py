#
# Copyright (C) 2020 GNS3 Technologies Inc.
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
API routes for VPCS nodes.
"""

import os

from fastapi import APIRouter, WebSocket, Depends, Body, Path, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from typing import Union
from uuid import UUID

from gns3server import schemas
from gns3server.compute.vpcs import VPCS
from gns3server.compute.vpcs.vpcs_vm import VPCSVM

from .dependencies.authentication import compute_authentication, ws_compute_authentication

responses = {404: {"model": schemas.ErrorMessage, "description": "Could not find project or VMware node"}}

router = APIRouter(responses=responses)


def dep_node(project_id: UUID, node_id: UUID) -> VPCSVM:
    """
    Dependency to retrieve a node.
    """

    vpcs_manager = VPCS.instance()
    node = vpcs_manager.get_node(str(node_id), project_id=str(project_id))
    return node


@router.post(
    "",
    response_model=schemas.VPCS,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": schemas.ErrorMessage, "description": "Could not create VMware node"}},
    dependencies=[Depends(compute_authentication)]
)
async def create_vpcs_node(project_id: UUID, node_data: schemas.VPCSCreate) -> schemas.VPCS:
    """
    Create a new VPCS node.
    """

    vpcs = VPCS.instance()
    node_data = jsonable_encoder(node_data, exclude_unset=True)
    vm = await vpcs.create_node(
        node_data["name"],
        str(project_id),
        node_data.get("node_id"),
        console=node_data.get("console"),
        console_type=node_data.get("console_type", "telnet"),
        startup_script=node_data.get("startup_script"),
    )

    return vm.asdict()


@router.get(
    "/{node_id}",
    response_model=schemas.VPCS,
    dependencies=[Depends(compute_authentication)]
)
def get_vpcs_node(node: VPCSVM = Depends(dep_node)) -> schemas.VPCS:
    """
    Return a VPCS node.
    """

    return node.asdict()


@router.put(
    "/{node_id}",
    response_model=schemas.VPCS,
    dependencies=[Depends(compute_authentication)]
)
def update_vpcs_node(node_data: schemas.VPCSUpdate, node: VPCSVM = Depends(dep_node)) -> schemas.VPCS:
    """
    Update a VPCS node.
    """

    node_data = jsonable_encoder(node_data, exclude_unset=True)
    node.name = node_data.get("name", node.name)
    node.console = node_data.get("console", node.console)
    node.console_type = node_data.get("console_type", node.console_type)
    node.updated()
    return node.asdict()


@router.delete(
    "/{node_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(compute_authentication)]
)
async def delete_vpcs_node(node: VPCSVM = Depends(dep_node)) -> None:
    """
    Delete a VPCS node.
    """

    await VPCS.instance().delete_node(node.id)


@router.post(
    "/{node_id}/duplicate",
    response_model=schemas.VPCS,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(compute_authentication)]
)
async def duplicate_vpcs_node(
        destination_node_id: UUID = Body(..., embed=True),
        node: VPCSVM = Depends(dep_node)) -> None:
    """
    Duplicate a VPCS node.
    """

    new_node = await VPCS.instance().duplicate_node(node.id, str(destination_node_id))
    return new_node.asdict()


@router.post(
    "/{node_id}/start",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(compute_authentication)]
)
async def start_vpcs_node(node: VPCSVM = Depends(dep_node)) -> None:
    """
    Start a VPCS node.
    """

    await node.start()


@router.post(
    "/{node_id}/stop",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(compute_authentication)]
)
async def stop_vpcs_node(node: VPCSVM = Depends(dep_node)) -> None:
    """
    Stop a VPCS node.
    """

    await node.stop()


@router.post(
    "/{node_id}/suspend",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(compute_authentication)]
)
async def suspend_vpcs_node(node: VPCSVM = Depends(dep_node)) -> None:
    """
    Suspend a VPCS node.
    Does nothing, suspend is not supported by VPCS.
    """

    pass


@router.post(
    "/{node_id}/reload",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(compute_authentication)]
)
async def reload_vpcs_node(node: VPCSVM = Depends(dep_node)) -> None:
    """
    Reload a VPCS node.
    """

    await node.reload()


@router.post(
    "/{node_id}/adapters/{adapter_number}/ports/{port_number}/nio",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.UDPNIO,
    dependencies=[Depends(compute_authentication)]
)
async def create_vpcs_node_nio(
        *,
        adapter_number: int = Path(..., ge=0, le=0),
        port_number: int,
        nio_data: schemas.UDPNIO,
        node: VPCSVM = Depends(dep_node)
) -> schemas.UDPNIO:
    """
    Add a NIO (Network Input/Output) to the node.
    The adapter number on the VPCS node is always 0.
    """

    nio = VPCS.instance().create_nio(jsonable_encoder(nio_data, exclude_unset=True))
    await node.port_add_nio_binding(port_number, nio)
    return nio.asdict()


@router.put(
    "/{node_id}/adapters/{adapter_number}/ports/{port_number}/nio",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.UDPNIO,
    dependencies=[Depends(compute_authentication)]
)
async def update_vpcs_node_nio(
        *,
        adapter_number: int = Path(..., ge=0, le=0),
        port_number: int,
        nio_data: schemas.UDPNIO,
        node: VPCSVM = Depends(dep_node)
) -> schemas.UDPNIO:
    """
    Update a NIO (Network Input/Output) on the node.
    The adapter number on the VPCS node is always 0.
    """

    nio = node.get_nio(port_number)
    if nio_data.filters:
        nio.filters = nio_data.filters
    await node.port_update_nio_binding(port_number, nio)
    return nio.asdict()


@router.delete(
    "/{node_id}/adapters/{adapter_number}/ports/{port_number}/nio",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(compute_authentication)]
)
async def delete_vpcs_node_nio(
        *,
        adapter_number: int = Path(..., ge=0, le=0),
        port_number: int,
        node: VPCSVM = Depends(dep_node)
) -> None:
    """
    Delete a NIO (Network Input/Output) from the node.
    The adapter number on the VPCS node is always 0.
    """

    await node.port_remove_nio_binding(port_number)


@router.post(
    "/{node_id}/adapters/{adapter_number}/ports/{port_number}/capture/start",
    dependencies=[Depends(compute_authentication)]
)
async def start_vpcs_node_capture(
        *,
        adapter_number: int = Path(..., ge=0, le=0),
        port_number: int,
        node_capture_data: schemas.NodeCapture,
        node: VPCSVM = Depends(dep_node)
) -> dict:
    """
    Start a packet capture on the node.
    The adapter number on the VPCS node is always 0.
    """

    pcap_file_path = os.path.join(node.project.capture_working_directory(), node_capture_data.capture_file_name)
    await node.start_capture(adapter_number, pcap_file_path)
    return {"pcap_file_path": pcap_file_path}


@router.post(
    "/{node_id}/adapters/{adapter_number}/ports/{port_number}/capture/stop",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(compute_authentication)]
)
async def stop_vpcs_node_capture(
        *,
        adapter_number: int = Path(..., ge=0, le=0),
        port_number: int,
        node: VPCSVM = Depends(dep_node)
) -> None:
    """
    Stop a packet capture on the node.
    The adapter number on the VPCS node is always 0.
    """

    await node.stop_capture(port_number)


@router.get(
    "/{node_id}/adapters/{adapter_number}/ports/{port_number}/capture/stream",
    dependencies=[Depends(compute_authentication)]
)
async def stream_pcap_file(
        *,
        adapter_number: int = Path(..., ge=0, le=0),
        port_number: int,
        node: VPCSVM = Depends(dep_node)
) -> StreamingResponse:
    """
    Stream the pcap capture file.
    The adapter number on the VPCS node is always 0.
    """

    nio = node.get_nio(port_number)
    stream = VPCS.instance().stream_pcap_file(nio, node.project.id)
    return StreamingResponse(stream, media_type="application/vnd.tcpdump.pcap")


@router.websocket(
    "/{node_id}/console/ws"
)
async def console_ws(
        websocket: Union[None, WebSocket] = Depends(ws_compute_authentication),
        node: VPCSVM = Depends(dep_node)) -> None:
    """
    Console WebSocket.
    """

    await node.start_websocket_console(websocket)


@router.post(
    "/{node_id}/console/reset",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(compute_authentication)]
)
async def reset_console(node: VPCSVM = Depends(dep_node)) -> None:

    await node.reset_console()
