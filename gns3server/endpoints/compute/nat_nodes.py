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
API endpoints for NAT nodes.
"""

import os

from fastapi import APIRouter, Depends, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from typing import Union
from uuid import UUID

from gns3server import schemas
from gns3server.compute.builtin import Builtin
from gns3server.compute.builtin.nodes.nat import Nat

router = APIRouter()

responses = {
    404: {"model": schemas.ErrorMessage, "description": "Could not find project or NAT node"}
}


def dep_node(project_id: UUID, node_id: UUID):
    """
    Dependency to retrieve a node.
    """

    builtin_manager = Builtin.instance()
    node = builtin_manager.get_node(str(node_id), project_id=str(project_id))
    return node


@router.post("",
             response_model=schemas.NAT,
             status_code=status.HTTP_201_CREATED,
             responses={409: {"model": schemas.ErrorMessage, "description": "Could not create NAT node"}})
async def create_nat(project_id: UUID, node_data: schemas.NATCreate):
    """
    Create a new NAT node.
    """

    builtin_manager = Builtin.instance()
    node_data = jsonable_encoder(node_data, exclude_unset=True)
    node = await builtin_manager.create_node(node_data.pop("name"),
                                             str(project_id),
                                             node_data.get("node_id"),
                                             node_type="nat",
                                             ports=node_data.get("ports_mapping"))

    node.usage = node_data.get("usage", "")
    return node.__json__()


@router.get("/{node_id}",
            response_model=schemas.NAT,
            responses=responses)
def get_nat(node: Nat = Depends(dep_node)):
    """
    Return a NAT node.
    """

    return node.__json__()


@router.put("/{node_id}",
            response_model=schemas.NAT,
            responses=responses)
def update_nat(node_data: schemas.NATUpdate, node: Nat = Depends(dep_node)):
    """
    Update a NAT node.
    """

    node_data = jsonable_encoder(node_data, exclude_unset=True)
    for name, value in node_data.items():
        if hasattr(node, name) and getattr(node, name) != value:
            setattr(node, name, value)
    node.updated()
    return node.__json__()


@router.delete("/{node_id}",
               status_code=status.HTTP_204_NO_CONTENT,
               responses=responses)
async def delete_nat(node: Nat = Depends(dep_node)):
    """
    Delete a cloud node.
    """

    await Builtin.instance().delete_node(node.id)


@router.post("/{node_id}/start",
             status_code=status.HTTP_204_NO_CONTENT,
             responses=responses)
async def start_nat(node: Nat = Depends(dep_node)):
    """
    Start a NAT node.
    """

    await node.start()


@router.post("/{node_id}/stop",
             status_code=status.HTTP_204_NO_CONTENT,
             responses=responses)
async def stop_nat(node: Nat = Depends(dep_node)):
    """
    Stop a NAT node.
    This endpoint results in no action since cloud nodes cannot be stopped.
    """

    pass


@router.post("/{node_id}/suspend",
             status_code=status.HTTP_204_NO_CONTENT,
             responses=responses)
async def suspend_nat(node: Nat = Depends(dep_node)):
    """
    Suspend a NAT node.
    This endpoint results in no action since NAT nodes cannot be suspended.
    """

    pass


@router.post("/{node_id}/adapters/{adapter_number}/ports/{port_number}/nio",
             status_code=status.HTTP_201_CREATED,
             response_model=Union[schemas.EthernetNIO, schemas.TAPNIO, schemas.UDPNIO],
             responses=responses)
async def create_nio(adapter_number: int,
                     port_number: int,
                     nio_data: Union[schemas.EthernetNIO, schemas.TAPNIO, schemas.UDPNIO],
                     node: Nat = Depends(dep_node)):
    """
    Add a NIO (Network Input/Output) to the node.
    The adapter number on the cloud is always 0.
    """

    nio = Builtin.instance().create_nio(jsonable_encoder(nio_data, exclude_unset=True))
    await node.add_nio(nio, port_number)
    return nio.__json__()


@router.put("/{node_id}/adapters/{adapter_number}/ports/{port_number}/nio",
            status_code=status.HTTP_201_CREATED,
            response_model=Union[schemas.EthernetNIO, schemas.TAPNIO, schemas.UDPNIO],
            responses=responses)
async def update_nio(adapter_number: int,
                     port_number: int,
                     nio_data: Union[schemas.EthernetNIO, schemas.TAPNIO, schemas.UDPNIO],
                     node: Nat = Depends(dep_node)):
    """
    Update a NIO (Network Input/Output) to the node.
    The adapter number on the cloud is always 0.
    """

    nio = node.get_nio(port_number)
    if nio_data.filters:
        nio.filters = nio_data.filters
    await node.update_nio(port_number, nio)
    return nio.__json__()


@router.delete("/{node_id}/adapters/{adapter_number}/ports/{port_number}/nio",
               status_code=status.HTTP_204_NO_CONTENT,
               responses=responses)
async def delete_nio(adapter_number: int, port_number: int, node: Nat = Depends(dep_node)):
    """
    Remove a NIO (Network Input/Output) from the node.
    The adapter number on the cloud is always 0.
    """

    await node.remove_nio(port_number)


@router.post("/{node_id}/adapters/{adapter_number}/ports/{port_number}/capture/start",
             responses=responses)
async def start_capture(adapter_number: int,
                        port_number: int,
                        node_capture_data: schemas.NodeCapture,
                        node: Nat = Depends(dep_node)):
    """
    Start a packet capture on the node.
    The adapter number on the cloud is always 0.
    """

    pcap_file_path = os.path.join(node.project.capture_working_directory(), node_capture_data.capture_file_name)
    await node.start_capture(port_number, pcap_file_path, node_capture_data.data_link_type)
    return {"pcap_file_path": pcap_file_path}


@router.post("/{node_id}/adapters/{adapter_number}/ports/{port_number}/capture/stop",
             status_code=status.HTTP_204_NO_CONTENT,
             responses=responses)
async def stop_capture(adapter_number: int, port_number: int, node: Nat = Depends(dep_node)):
    """
    Stop a packet capture on the node.
    The adapter number on the cloud is always 0.
    """

    await node.stop_capture(port_number)


@router.get("/{node_id}/adapters/{adapter_number}/ports/{port_number}/capture/stream",
            responses=responses)
async def stream_pcap_file(adapter_number: int, port_number: int, node: Nat = Depends(dep_node)):
    """
    Stream the pcap capture file.
    The adapter number on the cloud is always 0.
    """

    nio = node.get_nio(port_number)
    stream = Builtin.instance().stream_pcap_file(nio, node.project.id)
    return StreamingResponse(stream, media_type="application/vnd.tcpdump.pcap")
