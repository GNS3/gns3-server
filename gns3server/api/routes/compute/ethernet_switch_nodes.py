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
from typing import Any, Union
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Path, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse

from gns3server import schemas
from gns3server.compute.builtin import Builtin
from gns3server.compute.builtin.nodes.ethernet_switch import EthernetSwitch

responses: dict[int | str, dict[str, Any]] = {
    404: {"model": schemas.ErrorMessage, "description": "Could not find project or Ethernet switch node"}
}

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
    data = jsonable_encoder(node_data, exclude_unset=True)
    node = await builtin_manager.create_node(
        data.pop("name"),
        str(project_id),
        data.get("node_id"),
        console=data.get("console"),
        console_type=data.get("console_type"),
        node_type="ethernet_switch",
        ports=data.get("ports_mapping"),
    )
    node.usage = data.get("usage", "")
    return node.asdict()


@router.get("/{node_id}", response_model=schemas.EthernetSwitch)
def get_ethernet_switch(node: EthernetSwitch = Depends(dep_node)) -> schemas.EthernetSwitch:

    return node.asdict()


@router.post("/{node_id}/duplicate", response_model=schemas.EthernetSwitch, status_code=status.HTTP_201_CREATED)
async def duplicate_ethernet_switch(
    destination_node_id: UUID = Body(..., embed=True), node: EthernetSwitch = Depends(dep_node)
) -> schemas.EthernetSwitch:
    """
    Duplicate an Ethernet switch.
    """

    new_node = await Builtin.instance().duplicate_node(node.id, str(destination_node_id))
    return new_node.asdict()


@router.put("/{node_id}", response_model=schemas.EthernetSwitch)
async def update_ethernet_switch(
    node_data: schemas.EthernetSwitchUpdate, node: EthernetSwitch = Depends(dep_node)
) -> schemas.EthernetSwitch:
    """
    Update an Ethernet switch.
    """

    data = jsonable_encoder(node_data, exclude_unset=True)
    if "name" in data and node.name != data["name"]:
        node.name = data["name"]
    if "usage" in data:
        node.usage = data["usage"]
    if "ports_mapping" in data:
        # capture the mapping before the setter replaces it: the VLAN
        # reconcile diffs old against new to touch only what changed, in
        # place (the setter itself keeps the port-count guard)
        previous_mapping = [dict(port) for port in node.ports_mapping]
        node.ports_mapping = data["ports_mapping"]
        try:
            await node.update_port_settings(previous_mapping)
        except Exception:
            # Nothing, or only part, of the new mapping was applied — keep
            # the old one so the failed change stays visible in GET and a
            # retry still diffs against it. A kept-new mapping would turn
            # the retry into a no-op that reports success with the VLANs
            # never applied.
            node.ports_mapping = previous_mapping
            raise
    if "console_type" in data:
        node.console_type = data["console_type"]
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
        status_code=status.HTTP_405_METHOD_NOT_ALLOWED, detail="Start is not supported for Ethernet switches"
    )


@router.post("/{node_id}/stop", status_code=status.HTTP_204_NO_CONTENT)
def stop_ethernet_switch(node: EthernetSwitch = Depends(dep_node)) -> None:
    """
    Stop an Ethernet switch.
    """

    raise HTTPException(
        status_code=status.HTTP_405_METHOD_NOT_ALLOWED, detail="Stop is not supported for Ethernet switches"
    )


@router.post("/{node_id}/suspend", status_code=status.HTTP_204_NO_CONTENT)
def suspend_ethernet_switch(node: EthernetSwitch = Depends(dep_node)) -> None:
    """
    Suspend an Ethernet switch.
    """

    raise HTTPException(
        status_code=status.HTTP_405_METHOD_NOT_ALLOWED, detail="Suspend is not supported for Ethernet switches"
    )


@router.post("/{node_id}/reload", status_code=status.HTTP_204_NO_CONTENT)
def reload_ethernet_switch(node: EthernetSwitch = Depends(dep_node)) -> None:
    """
    Reload an Ethernet switch.
    This endpoint results in no action since Ethernet switch nodes are always on.
    """

    raise HTTPException(
        status_code=status.HTTP_405_METHOD_NOT_ALLOWED, detail="Reload is not supported for Ethernet switches"
    )


@router.post(
    "/{node_id}/adapters/{adapter_number}/ports/{port_number}/nio",
    status_code=status.HTTP_201_CREATED,
    response_model=Union[schemas.UDPNIO, schemas.AnchorNIO],
)
async def create_ethernet_switch_nio(
    *,
    adapter_number: int = Path(..., ge=0, le=0),
    port_number: int,
    nio_data: Union[schemas.UDPNIO, schemas.AnchorNIO],
    node: EthernetSwitch = Depends(dep_node),
) -> Union[schemas.UDPNIO, schemas.AnchorNIO]:
    """
    Add a NIO (Network Input/Output) to the node: a UDP NIO wires the relay
    datapath, an anchor NIO absorbs the peer's kernel anchor into this
    switch's kernel bridge. The adapter number on the switch is always 0.
    """

    nio = Builtin.instance().create_nio(jsonable_encoder(nio_data, exclude_unset=True))
    await node.add_nio(nio, port_number)
    return nio.asdict()


@router.put(
    "/{node_id}/adapters/{adapter_number}/ports/{port_number}/nio",
    status_code=status.HTTP_201_CREATED,
    response_model=Union[schemas.UDPNIO, schemas.AnchorNIO],
)
async def update_ethernet_switch_nio(
    *,
    adapter_number: int = Path(..., ge=0, le=0),
    port_number: int,
    nio_data: Union[schemas.UDPNIO, schemas.AnchorNIO],
    node: EthernetSwitch = Depends(dep_node),
) -> Union[schemas.UDPNIO, schemas.AnchorNIO]:
    """
    Update a NIO (Network Input/Output) on the node: re-apply the packet
    filters, traffic-insight markers and suspend state carried by the NIO —
    on the port's uBridge relay for a relay port, on the absorbed anchor
    (tc + kernel markers + carrier) for a kernel port. The adapter number
    on the switch is always 0.
    """

    nio = node.get_nio(port_number)
    nio.filters.clear()
    if nio_data.filters:
        nio.filters = nio_data.filters
    nio.markers = nio_data.markers or {}
    # Suspend is what the compute turns into an admin-down anchor on a
    # kernel link (native carrier), so it must reach the NIO like it does
    # on the other node routes.
    nio.suspend = getattr(nio_data, "suspend", None) or False
    await node.update_nio(port_number, nio)
    return nio.asdict()


@router.delete("/{node_id}/adapters/{adapter_number}/ports/{port_number}/nio", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ethernet_switch_nio(
    *, adapter_number: int = Path(..., ge=0, le=0), port_number: int, node: EthernetSwitch = Depends(dep_node)
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
    *, adapter_number: int = Path(..., ge=0, le=0), port_number: int, node: EthernetSwitch = Depends(dep_node)
) -> None:
    """
    Stop a packet capture on the node.
    The adapter number on the switch is always 0.
    """

    await node.stop_capture(port_number)


@router.get("/{node_id}/adapters/{adapter_number}/ports/{port_number}/capture/stream")
async def stream_pcap_file(
    *, adapter_number: int = Path(..., ge=0, le=0), port_number: int, node: EthernetSwitch = Depends(dep_node)
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
    marker_name: str, toggle_data: schemas.MarkerToggle, node: EthernetSwitch = Depends(dep_node)
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
    node: EthernetSwitch = Depends(dep_node),
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
    marker_name: str, rebuild_data: schemas.MarkerRebuild, node: EthernetSwitch = Depends(dep_node)
) -> dict:
    """
    Re-install a single marker filter with new BPF/tag/direction (delete + add,
    no bridge reset) so sibling markers' pcaps stay open.
    """

    await node.rebuild_marker_filter(
        marker_name,
        rebuild_data.link_id,
        rebuild_data.bpf,
        rebuild_data.tag,
        rebuild_data.direction,
        rebuild_data.enabled,
    )
    return {"marker_name": marker_name}
