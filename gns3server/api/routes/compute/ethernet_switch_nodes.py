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
API routes for Ethernet switch nodes.
"""

import os

from fastapi import APIRouter, Depends, Body, Path, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from uuid import UUID

from gns3server.compute.dynamips import Dynamips
from gns3server.compute.dynamips.nodes.ethernet_switch import EthernetSwitch
from gns3server import schemas

responses = {404: {"model": schemas.ErrorMessage, "description": "Could not find project or Ethernet switch node"}}

router = APIRouter(responses=responses)


def dep_node(project_id: UUID, node_id: UUID) -> EthernetSwitch:
    """
    Dependency to retrieve a node.
    """

    dynamips_manager = Dynamips.instance()
    node = dynamips_manager.get_node(str(node_id), project_id=str(project_id))
    return node


@router.post(
    "",
    response_model=schemas.EthernetSwitch,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": schemas.ErrorMessage, "description": "Could not create Ethernet switch node"}},
)
async def create_ethernet_switch(project_id: UUID, node_data: schemas.EthernetSwitchCreate) -> schemas.EthernetSwitch:
    """
    Create a new Ethernet switch.
    """

    # Use the Dynamips Ethernet switch to simulate this node
    dynamips_manager = Dynamips.instance()
    node_data = jsonable_encoder(node_data, exclude_unset=True)
    node = await dynamips_manager.create_node(
        node_data.pop("name"),
        str(project_id),
        node_data.get("node_id"),
        console=node_data.get("console"),
        console_type=node_data.get("console_type"),
        node_type="ethernet_switch",
        ports=node_data.get("ports_mapping"),
    )

    return node.asdict()


@router.get("/{node_id}", response_model=schemas.EthernetSwitch)
def get_ethernet_switch(node: EthernetSwitch = Depends(dep_node)) -> schemas.EthernetSwitch:

    return node.asdict()


@router.post("/{node_id}/duplicate", response_model=schemas.EthernetSwitch, status_code=status.HTTP_201_CREATED)
async def duplicate_ethernet_switch(
        destination_node_id: UUID = Body(..., embed=True),
        node: EthernetSwitch = Depends(dep_node)
) -> schemas.EthernetSwitch:
    """
    Duplicate an Ethernet switch.
    """

    new_node = await Dynamips.instance().duplicate_node(node.id, str(destination_node_id))
    return new_node.asdict()


@router.put("/{node_id}", response_model=schemas.EthernetSwitch)
async def update_ethernet_switch(
        node_data: schemas.EthernetSwitchUpdate,
        node: EthernetSwitch = Depends(dep_node)
) -> schemas.EthernetSwitch:
    """
    Update an Ethernet switch.
    """

    node_data = jsonable_encoder(node_data, exclude_unset=True)
    if "name" in node_data and node.name != node_data["name"]:
        await node.set_name(node_data["name"])
    if "ports_mapping" in node_data:
        node.ports_mapping = node_data["ports_mapping"]
        await node.update_port_settings()
    if "console_type" in node_data:
        node.console_type = node_data["console_type"]
    node.updated()
    return node.asdict()


@router.delete("/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ethernet_switch(node: EthernetSwitch = Depends(dep_node)) -> None:
    """
    Delete an Ethernet switch.
    """

    await Dynamips.instance().delete_node(node.id)


@router.post("/{node_id}/start", status_code=status.HTTP_204_NO_CONTENT)
def start_ethernet_switch(node: EthernetSwitch = Depends(dep_node)) -> None:
    """
    Start an Ethernet switch.
    This endpoint results in no action since Ethernet switch nodes are always on.
    """

    pass


@router.post("/{node_id}/stop", status_code=status.HTTP_204_NO_CONTENT)
def stop_ethernet_switch(node: EthernetSwitch = Depends(dep_node)) -> None:
    """
    Stop an Ethernet switch.
    This endpoint results in no action since Ethernet switch nodes are always on.
    """

    pass


@router.post("/{node_id}/suspend", status_code=status.HTTP_204_NO_CONTENT)
def suspend_ethernet_switch(node: EthernetSwitch = Depends(dep_node)) -> None:
    """
    Suspend an Ethernet switch.
    This endpoint results in no action since Ethernet switch nodes are always on.
    """

    pass


@router.post("/{node_id}/reload", status_code=status.HTTP_204_NO_CONTENT)
def reload_ethernet_switch(node: EthernetSwitch = Depends(dep_node)) -> None:
    """
    Reload an Ethernet switch.
    This endpoint results in no action since Ethernet switch nodes are always on.
    """

    pass


@router.post(
    "/{node_id}/adapters/{adapter_number}/ports/{port_number}/nio",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.UDPNIO,
)
async def create_ethernet_switch_nio(
        *,
        adapter_number: int = Path(..., ge=0, le=0),
        port_number: int,
        nio_data: schemas.UDPNIO,
        node: EthernetSwitch = Depends(dep_node)
) -> schemas.UDPNIO:

    nio = await Dynamips.instance().create_nio(node, jsonable_encoder(nio_data, exclude_unset=True))
    await node.add_nio(nio, port_number)
    return nio.asdict()


@router.delete("/{node_id}/adapters/{adapter_number}/ports/{port_number}/nio", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ethernet_switch_nio(
        *,
        adapter_number: int = Path(..., ge=0, le=0),
        port_number: int,
        node: EthernetSwitch = Depends(dep_node)
) -> None:
    """
    Delete a NIO (Network Input/Output) from the node.
    The adapter number on the switch is always 0.
    """

    nio = await node.remove_nio(port_number)
    await nio.delete()


@router.post("/{node_id}/adapters/{adapter_number}/ports/{port_number}/capture/start")
async def start_ethernet_switch_capture(
        *,
        adapter_number: int = Path(..., ge=0, le=0),
        port_number: int,
        node_capture_data: schemas.NodeCapture,
        node: EthernetSwitch = Depends(dep_node),
) -> dict:
    """
    Start a packet capture on the node.
    The adapter number on the switch is always 0.
    """

    pcap_file_path = os.path.join(node.project.capture_working_directory(), node_capture_data.capture_file_name)
    await node.start_capture(port_number, pcap_file_path, node_capture_data.data_link_type)
    return {"pcap_file_path": pcap_file_path}


@router.post(
    "/{node_id}/adapters/{adapter_number}/ports/{port_number}/capture/stop", status_code=status.HTTP_204_NO_CONTENT
)
async def stop_ethernet_switch_capture(
        *,
        adapter_number: int = Path(..., ge=0, le=0),
        port_number: int,
        node: EthernetSwitch = Depends(dep_node)
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
        node: EthernetSwitch = Depends(dep_node)
) -> StreamingResponse:
    """
    Stream the pcap capture file.
    The adapter number on the switch is always 0.
    """

    nio = node.get_nio(port_number)
    stream = Dynamips.instance().stream_pcap_file(nio, node.project.id)
    return StreamingResponse(stream, media_type="application/vnd.tcpdump.pcap")
