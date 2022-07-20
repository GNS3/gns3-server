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
API routes for ATM switch nodes.
"""

import os

from fastapi import APIRouter, Depends, Body, Path, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from uuid import UUID

from gns3server import schemas
from gns3server.compute.dynamips import Dynamips
from gns3server.compute.dynamips.nodes.atm_switch import ATMSwitch

responses = {404: {"model": schemas.ErrorMessage, "description": "Could not find project or ATM switch node"}}

router = APIRouter(responses=responses)


async def dep_node(project_id: UUID, node_id: UUID) -> ATMSwitch:
    """
    Dependency to retrieve a node.
    """

    dynamips_manager = Dynamips.instance()
    node = dynamips_manager.get_node(str(node_id), project_id=str(project_id))
    return node


@router.post(
    "",
    response_model=schemas.ATMSwitch,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": schemas.ErrorMessage, "description": "Could not create ATM switch node"}},
)
async def create_atm_switch(project_id: UUID, node_data: schemas.ATMSwitchCreate) -> schemas.ATMSwitch:
    """
    Create a new ATM switch node.
    """

    # Use the Dynamips ATM switch to simulate this node
    dynamips_manager = Dynamips.instance()
    node_data = jsonable_encoder(node_data, exclude_unset=True)
    node = await dynamips_manager.create_node(
        node_data.get("name"),
        str(project_id),
        node_data.get("node_id"),
        node_type="atm_switch",
        mappings=node_data.get("mappings"),
    )
    return node.asdict()


@router.get("/{node_id}", response_model=schemas.ATMSwitch)
def get_atm_switch(node: ATMSwitch = Depends(dep_node)) -> schemas.ATMSwitch:
    """
    Return an ATM switch node.
    """

    return node.asdict()


@router.post("/{node_id}/duplicate", response_model=schemas.ATMSwitch, status_code=status.HTTP_201_CREATED)
async def duplicate_atm_switch(
        destination_node_id: UUID = Body(..., embed=True),
        node: ATMSwitch = Depends(dep_node)
) -> schemas.ATMSwitch:
    """
    Duplicate an ATM switch node.
    """

    new_node = await Dynamips.instance().duplicate_node(node.id, str(destination_node_id))
    return new_node.asdict()


@router.put("/{node_id}", response_model=schemas.ATMSwitch)
async def update_atm_switch(
        node_data: schemas.ATMSwitchUpdate,
        node: ATMSwitch = Depends(dep_node)
) -> schemas.ATMSwitch:
    """
    Update an ATM switch node.
    """

    node_data = jsonable_encoder(node_data, exclude_unset=True)
    if "name" in node_data and node.name != node_data["name"]:
        await node.set_name(node_data["name"])
    if "mappings" in node_data:
        node.mappings = node_data["mappings"]
    node.updated()
    return node.asdict()


@router.delete("/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_atm_switch_node(node: ATMSwitch = Depends(dep_node)) -> None:
    """
    Delete an ATM switch node.
    """

    await Dynamips.instance().delete_node(node.id)


@router.post("/{node_id}/start", status_code=status.HTTP_204_NO_CONTENT)
def start_atm_switch(node: ATMSwitch = Depends(dep_node)) -> None:
    """
    Start an ATM switch node.
    This endpoint results in no action since ATM switch nodes are always on.
    """

    pass


@router.post("/{node_id}/stop", status_code=status.HTTP_204_NO_CONTENT)
def stop_atm_switch(node: ATMSwitch = Depends(dep_node)) -> None:
    """
    Stop an ATM switch node.
    This endpoint results in no action since ATM switch nodes are always on.
    """

    pass


@router.post("/{node_id}/suspend", status_code=status.HTTP_204_NO_CONTENT)
def suspend_atm_switch(node: ATMSwitch = Depends(dep_node)) -> None:
    """
    Suspend an ATM switch node.
    This endpoint results in no action since ATM switch nodes are always on.
    """

    pass


@router.post(
    "/{node_id}/adapters/{adapter_number}/ports/{port_number}/nio",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.UDPNIO,
)
async def create_nio(
        *,
        adapter_number: int = Path(..., ge=0, le=0),
        port_number: int,
        nio_data: schemas.UDPNIO,
        node: ATMSwitch = Depends(dep_node)
) -> schemas.UDPNIO:
    """
    Add a NIO (Network Input/Output) to the node.
    The adapter number on the switch is always 0.
    """

    nio = await Dynamips.instance().create_nio(node, jsonable_encoder(nio_data, exclude_unset=True))
    await node.add_nio(nio, port_number)
    return nio.asdict()


@router.delete("/{node_id}/adapters/{adapter_number}/ports/{port_number}/nio", status_code=status.HTTP_204_NO_CONTENT)
async def delete_nio(adapter_number: int, port_number: int, node: ATMSwitch = Depends(dep_node)) -> None:
    """
    Remove a NIO (Network Input/Output) from the node.
    The adapter number on the switch is always 0.
    """

    nio = await node.remove_nio(port_number)
    await nio.delete()


@router.post("/{node_id}/adapters/{adapter_number}/ports/{port_number}/capture/start")
async def start_capture(
        *,
        adapter_number: int = Path(..., ge=0, le=0),
        port_number: int,
        node_capture_data: schemas.NodeCapture,
        node: ATMSwitch = Depends(dep_node)
) -> dict:
    """
    Start a packet capture on the node.
    The adapter number on the switch is always 0.
    """

    pcap_file_path = os.path.join(node.project.capture_working_directory(), node_capture_data.capture_file_name)
    await node.start_capture(port_number, pcap_file_path, node_capture_data.data_link_type)
    return {"pcap_file_path": pcap_file_path}


@router.post(
    "/{node_id}/adapters/{adapter_number}/ports/{port_number}/capture/stop_capture",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def stop_capture(
        *,
        adapter_number: int = Path(..., ge=0, le=0),
        port_number: int,
        node: ATMSwitch = Depends(dep_node)
) -> None:
    """
    Stop a packet capture on the node.
    The adapter number on the switch is always 0.
    """

    await node.stop_capture(port_number)


@router.get("/{node_id}/adapters/{adapter_number}/ports/{port_number}/capture/stream")
async def stream_pcap_file(
        *,
        adapter_number: int = Path(..., ge=0, le=0),
        port_number: int,
        node: ATMSwitch = Depends(dep_node)
) -> StreamingResponse:
    """
    Stream the pcap capture file.
    The adapter number on the switch is always 0.
    """

    nio = node.get_nio(port_number)
    stream = Dynamips.instance().stream_pcap_file(nio, node.project.id)
    return StreamingResponse(stream, media_type="application/vnd.tcpdump.pcap")
