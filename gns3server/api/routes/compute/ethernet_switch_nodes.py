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

The Ethernet switch is a builtin node backed by a Linux kernel bridge driven
through uBridge's ``brctl`` module (see
``gns3server.compute.builtin.nodes.ethernet_switch``).
"""

import os

from fastapi import APIRouter, Depends, Body, Path, status, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from uuid import UUID

from gns3server.compute.builtin import Builtin
from gns3server.compute.builtin.nodes.ethernet_switch import EthernetSwitch
from gns3server import schemas

responses = {404: {"model": schemas.ErrorMessage, "description": "Could not find project or Ethernet switch node"}}

router = APIRouter(responses=responses)


def dep_node(project_id: UUID, node_id: UUID) -> EthernetSwitch:
    """
    Dependency to retrieve a node.
    """

    builtin_manager = Builtin.instance()
    node = builtin_manager.get_node(str(node_id), project_id=str(project_id))
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

    builtin_manager = Builtin.instance()
    node_data = jsonable_encoder(node_data, exclude_unset=True)
    node = await builtin_manager.create_node(
        node_data.pop("name"),
        str(project_id),
        node_data.get("node_id"),
        console=node_data.get("console"),
        console_type=node_data.get("console_type"),
        node_type="ethernet_switch",
        ports=node_data.get("ports_mapping"),
    )
    node.usage = node_data.get("usage", "")
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

    new_node = await Builtin.instance().duplicate_node(node.id, str(destination_node_id))
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
        node.name = node_data["name"]
    if "usage" in node_data:
        node.usage = node_data["usage"]
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

    await Builtin.instance().delete_node(node.id)


@router.post("/{node_id}/start", status_code=status.HTTP_204_NO_CONTENT)
def start_ethernet_switch(node: EthernetSwitch = Depends(dep_node)) -> None:
    """
    Start an Ethernet switch.
    """

    raise HTTPException(
        status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
        detail="Start is not supported for Ethernet switches"
    )


@router.post("/{node_id}/stop", status_code=status.HTTP_204_NO_CONTENT)
def stop_ethernet_switch(node: EthernetSwitch = Depends(dep_node)) -> None:
    """
    Stop an Ethernet switch.
    """

    raise HTTPException(
        status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
        detail="Stop is not supported for Ethernet switches"
    )


@router.post("/{node_id}/suspend", status_code=status.HTTP_204_NO_CONTENT)
def suspend_ethernet_switch(node: EthernetSwitch = Depends(dep_node)) -> None:
    """
    Suspend an Ethernet switch.
    """

    raise HTTPException(
        status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
        detail="Suspend is not supported for Ethernet switches"
    )


@router.post("/{node_id}/reload", status_code=status.HTTP_204_NO_CONTENT)
def reload_ethernet_switch(node: EthernetSwitch = Depends(dep_node)) -> None:
    """
    Reload an Ethernet switch.
    This endpoint results in no action since Ethernet switch nodes are always on.
    """

    raise HTTPException(
        status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
        detail="Reload is not supported for Ethernet switches"
    )


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

    nio = Builtin.instance().create_nio(jsonable_encoder(nio_data, exclude_unset=True))
    await node.add_nio(nio, port_number)
    return nio.asdict()


@router.put(
    "/{node_id}/adapters/{adapter_number}/ports/{port_number}/nio",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.UDPNIO,
)
async def update_ethernet_switch_nio(
        *,
        adapter_number: int = Path(..., ge=0, le=0),
        port_number: int,
        nio_data: schemas.UDPNIO,
        node: EthernetSwitch = Depends(dep_node)
) -> schemas.UDPNIO:
    """
    Update a NIO (Network Input/Output) on the node: re-apply the packet
    filters and traffic-insight markers carried by the NIO onto the port's
    uBridge relay. The adapter number on the switch is always 0.
    """

    nio = node.get_nio(port_number)
    nio.filters.clear()
    if nio_data.filters:
        nio.filters = nio_data.filters
    nio.markers = nio_data.markers or {}
    await node.update_nio(port_number, nio)
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

    await node.remove_nio(port_number)


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
    stream = Builtin.instance().stream_pcap_file(nio, node.project.id)
    return StreamingResponse(stream, media_type="application/vnd.tcpdump.pcap")


@router.put("/{node_id}/markers/{marker_name}")
async def toggle_ethernet_switch_marker(
        marker_name: str,
        toggle_data: schemas.MarkerToggle,
        node: EthernetSwitch = Depends(dep_node)
) -> dict:
    """
    Toggle a marker filter on/off without an NIO rebuild (ubridge contract §3.2).
    """

    if not any(n == marker_name for (n, lid) in node._marker_filter_bridges):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Marker '{marker_name}' is not installed on this node",
        )
    await node._ubridge_set_marker_filter_state(marker_name, toggle_data.enabled)
    return {"marker_name": marker_name, "enabled": toggle_data.enabled}


@router.post("/{node_id}/markers/pause", status_code=status.HTTP_204_NO_CONTENT)
async def pause_ethernet_switch_markers(node: EthernetSwitch = Depends(dep_node)) -> None:

    await node._ubridge_marker_pause()


@router.post("/{node_id}/markers/resume", status_code=status.HTTP_204_NO_CONTENT)
async def resume_ethernet_switch_markers(node: EthernetSwitch = Depends(dep_node)) -> None:

    await node._ubridge_marker_resume()


@router.delete(
    "/{node_id}/adapters/{adapter_number}/ports/{port_number}/markers/{marker_name}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_ethernet_switch_marker_capture(
        *,
        marker_name: str,
        adapter_number: int = Path(..., ge=0, le=0),
        port_number: int,
        link_id: str = "",
        node: EthernetSwitch = Depends(dep_node)
) -> None:
    """
    Delete a marker's capture pcap (called by the controller when the marker is
    removed) so the file is cleaned up even with the switch stopped. Also drops
    the marker from the port NIO's cached spec so a switch restart won't
    reinstall it (and recreate an empty pcap). The adapter number is always 0.
    """

    nio = node.get_nio(port_number)
    await node.delete_marker_capture(marker_name, link_id, nio)


@router.put("/{node_id}/markers/{marker_name}/rebuild")
async def rebuild_ethernet_switch_marker(
        marker_name: str,
        rebuild_data: schemas.MarkerRebuild,
        node: EthernetSwitch = Depends(dep_node)
) -> dict:
    """
    Re-install a single marker filter with new BPF/tag/direction (delete + add,
    no bridge reset) so sibling markers' pcaps stay open.
    """

    await node.rebuild_marker_filter(
        marker_name, rebuild_data.link_id, rebuild_data.bpf,
        rebuild_data.tag, rebuild_data.direction, rebuild_data.enabled,
    )
    return {"marker_name": marker_name}
