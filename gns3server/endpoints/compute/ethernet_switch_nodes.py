# -*- coding: utf-8 -*-
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
API endpoints for Ethernet switch nodes.
"""

import os

from fastapi import APIRouter, Body, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from uuid import UUID

from gns3server.compute.dynamips import Dynamips
from gns3server.endpoints import schemas

router = APIRouter()


@router.post("/",
             response_model=schemas.EthernetSwitch,
             status_code=status.HTTP_201_CREATED,
             responses={409: {"model": schemas.ErrorMessage, "description": "Could not create Ethernet hub node"}})
async def create_ethernet_switch(project_id: UUID, node_data: schemas.EthernetSwitchCreate):
    """
    Create a new Ethernet switch.
    """

    # Use the Dynamips Ethernet switch to simulate this node
    dynamips_manager = Dynamips.instance()
    node_data = jsonable_encoder(node_data, exclude_unset=True)
    node = await dynamips_manager.create_node(node_data.pop("name"),
                                              str(project_id),
                                              node_data.get("node_id"),
                                              console=node_data.get("console"),
                                              console_type=node_data.get("console_type"),
                                              node_type="ethernet_switch",
                                              ports=node_data.get("ports_mapping"))

    return node.__json__()


@router.get("/{node_id}",
            response_model=schemas.EthernetSwitch,
            responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
def get_ethernet_switch(project_id: UUID, node_id: UUID):

    dynamips_manager = Dynamips.instance()
    node = dynamips_manager.get_node(str(node_id), project_id=str(project_id))
    return node.__json__()


@router.post("/{node_id}/duplicate",
             response_model=schemas.EthernetSwitch,
             status_code=status.HTTP_201_CREATED,
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def duplicate_ethernet_switch(project_id: UUID, node_id: UUID, destination_node_id: UUID = Body(..., embed=True)):
    """
    Duplicate an Ethernet switch.
    """

    new_node = await Dynamips.instance().duplicate_node(str(node_id), str(destination_node_id))
    return new_node.__json__()


@router.put("/{node_id}",
            response_model=schemas.EthernetSwitch,
            responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def update_ethernet_switch(project_id: UUID, node_id: UUID, node_data: schemas.EthernetSwitchUpdate):
    """
    Update an Ethernet switch.
    """

    dynamips_manager = Dynamips.instance()
    node = dynamips_manager.get_node(str(node_id), project_id=str(project_id))
    node_data = jsonable_encoder(node_data, exclude_unset=True)
    if "name" in node_data and node.name != node_data["name"]:
        await node.set_name(node_data["name"])
    if "ports_mapping" in node_data:
        node.ports_mapping = node_data["ports_mapping"]
        await node.update_port_settings()
    if "console_type" in node_data:
        node.console_type = node_data["console_type"]
    node.updated()
    return node.__json__()


@router.delete("/{node_id}",
               status_code=status.HTTP_204_NO_CONTENT,
               responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def delete_ethernet_switch(project_id: UUID, node_id: UUID):
    """
    Delete an Ethernet switch.
    """

    dynamips_manager = Dynamips.instance()
    await dynamips_manager.delete_node(str(node_id))


@router.post("/{node_id}/start",
             status_code=status.HTTP_204_NO_CONTENT,
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
def start_ethernet_switch(project_id: UUID, node_id: UUID):
    """
    Start an Ethernet switch.
    This endpoint results in no action since Ethernet switch nodes are always on.
    """

    Dynamips.instance().get_node(str(node_id), project_id=str(project_id))


@router.post("/{node_id}/stop",
             status_code=status.HTTP_204_NO_CONTENT,
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
def stop_ethernet_switch(project_id: UUID, node_id: UUID):
    """
    Stop an Ethernet switch.
    This endpoint results in no action since Ethernet switch nodes are always on.
    """

    Dynamips.instance().get_node(str(node_id), project_id=str(project_id))


@router.post("/{node_id}/suspend",
             status_code=status.HTTP_204_NO_CONTENT,
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
def suspend(project_id: UUID, node_id: UUID):
    """
    Suspend an Ethernet switch.
    This endpoint results in no action since Ethernet switch nodes are always on.
    """

    Dynamips.instance().get_node(str(node_id), project_id=str(project_id))


@router.post("/{node_id}/adapters/{adapter_number}/ports/{port_number}/nio",
             status_code=status.HTTP_201_CREATED,
             response_model=schemas.UDPNIO,
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def create_nio(project_id: UUID, node_id: UUID, adapter_number: int, port_number: int, nio_data: schemas.UDPNIO):

    dynamips_manager = Dynamips.instance()
    node = dynamips_manager.get_node(str(node_id), project_id=str(project_id))
    nio = await dynamips_manager.create_nio(node, jsonable_encoder(nio_data, exclude_unset=True))
    await node.add_nio(nio, port_number)
    return nio.__json__()


@router.delete("/{node_id}/adapters/{adapter_number}/ports/{port_number}/nio",
               status_code=status.HTTP_204_NO_CONTENT,
               responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def delete_nio(project_id: UUID, node_id: UUID, adapter_number: int, port_number: int):
    """
    Delete a NIO (Network Input/Output) from the node.
    The adapter number on the switch is always 0.
    """

    dynamips_manager = Dynamips.instance()
    node = dynamips_manager.get_node(str(node_id), project_id=str(project_id))
    nio = await node.remove_nio(port_number)
    await nio.delete()


@router.post("/{node_id}/adapters/{adapter_number}/ports/{port_number}/start_capture",
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def start_capture(project_id: UUID, node_id: UUID, adapter_number: int, port_number: int, node_capture_data: schemas.NodeCapture):
    """
    Start a packet capture on the node.
    The adapter number on the switch is always 0.
    """

    dynamips_manager = Dynamips.instance()
    node = dynamips_manager.get_node(str(node_id), project_id=str(project_id))
    pcap_file_path = os.path.join(node.project.capture_working_directory(), node_capture_data.capture_file_name)
    await node.start_capture(port_number, pcap_file_path, node_capture_data.data_link_type)
    return {"pcap_file_path": pcap_file_path}

@router.post("/{node_id}/adapters/{adapter_number}/ports/{port_number}/stop_capture",
             status_code=status.HTTP_204_NO_CONTENT,
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def stop_capture(project_id: UUID, node_id: UUID, adapter_number: int, port_number: int):
    """
    Stop a packet capture on the node.
    The adapter number on the switch is always 0.
    """

    dynamips_manager = Dynamips.instance()
    node = dynamips_manager.get_node(str(node_id), project_id=str(project_id))
    await node.stop_capture(port_number)


@router.get("/{node_id}/adapters/{adapter_number}/ports/{port_number}/pcap",
            responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def stream_pcap_file(project_id: UUID, node_id: UUID, adapter_number: int, port_number: int):
    """
    Stream the pcap capture file.
    The adapter number on the switch is always 0.
    """

    dynamips_manager = Dynamips.instance()
    node = dynamips_manager.get_node(str(node_id), project_id=str(project_id))
    nio = node.get_nio(port_number)
    stream = dynamips_manager.stream_pcap_file(nio, node.project.id)
    return StreamingResponse(stream, media_type="application/vnd.tcpdump.pcap")

