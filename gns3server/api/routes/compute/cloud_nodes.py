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
API routes for cloud nodes.
"""

import os

from fastapi import APIRouter, Depends, Path, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from typing import Union
from uuid import UUID

from gns3server import schemas
from gns3server.compute.builtin import Builtin
from gns3server.compute.builtin.nodes.cloud import Cloud

responses = {404: {"model": schemas.ErrorMessage, "description": "Could not find project or cloud node"}}

router = APIRouter(responses=responses)


def dep_node(project_id: UUID, node_id: UUID) -> Cloud:
    """
    Dependency to retrieve a node.
    """

    builtin_manager = Builtin.instance()
    node = builtin_manager.get_node(str(node_id), project_id=str(project_id))
    return node


@router.post(
    "",
    response_model=schemas.Cloud,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": schemas.ErrorMessage, "description": "Could not create cloud node"}},
)
async def create_cloud(project_id: UUID, node_data: schemas.CloudCreate) -> schemas.Cloud:
    """
    Create a new cloud node.
    """

    builtin_manager = Builtin.instance()
    node_data = jsonable_encoder(node_data, exclude_unset=True)
    node = await builtin_manager.create_node(
        node_data.pop("name"),
        str(project_id),
        node_data.get("node_id"),
        node_type="cloud",
        ports=node_data.get("ports_mapping"),
    )

    # add the remote console settings
    node.remote_console_host = node_data.get("remote_console_host", node.remote_console_host)
    node.remote_console_port = node_data.get("remote_console_port", node.remote_console_port)
    node.remote_console_type = node_data.get("remote_console_type", node.remote_console_type)
    node.remote_console_http_path = node_data.get("remote_console_http_path", node.remote_console_http_path)
    node.usage = node_data.get("usage", "")
    return node.asdict()


@router.get("/{node_id}", response_model=schemas.Cloud)
def get_cloud(node: Cloud = Depends(dep_node)) -> schemas.Cloud:
    """
    Return a cloud node.
    """

    return node.asdict()


@router.put("/{node_id}", response_model=schemas.Cloud)
def update_cloud(node_data: schemas.CloudUpdate, node: Cloud = Depends(dep_node)) -> schemas.Cloud:
    """
    Update a cloud node.
    """

    node_data = jsonable_encoder(node_data, exclude_unset=True)
    for name, value in node_data.items():
        if hasattr(node, name) and getattr(node, name) != value:
            setattr(node, name, value)
    node.updated()
    return node.asdict()


@router.delete("/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cloud(node: Cloud = Depends(dep_node)) -> None:
    """
    Delete a cloud node.
    """

    await Builtin.instance().delete_node(node.id)


@router.post("/{node_id}/start", status_code=status.HTTP_204_NO_CONTENT)
async def start_cloud(node: Cloud = Depends(dep_node)) -> None:
    """
    Start a cloud node.
    """

    await node.start()


@router.post("/{node_id}/stop", status_code=status.HTTP_204_NO_CONTENT)
async def stop_cloud(node: Cloud = Depends(dep_node)) -> None:
    """
    Stop a cloud node.
    This endpoint results in no action since cloud nodes cannot be stopped.
    """

    pass


@router.post("/{node_id}/suspend", status_code=status.HTTP_204_NO_CONTENT)
async def suspend_cloud(node: Cloud = Depends(dep_node)) -> None:
    """
    Suspend a cloud node.
    This endpoint results in no action since cloud nodes cannot be suspended.
    """

    pass


@router.post(
    "/{node_id}/adapters/{adapter_number}/ports/{port_number}/nio",
    status_code=status.HTTP_201_CREATED,
    response_model=Union[schemas.EthernetNIO, schemas.TAPNIO, schemas.UDPNIO],
)
async def create_cloud_nio(
        *,
        adapter_number: int = Path(..., ge=0, le=0),
        port_number: int,
        nio_data: Union[schemas.EthernetNIO, schemas.TAPNIO, schemas.UDPNIO],
        node: Cloud = Depends(dep_node),
) -> Union[schemas.EthernetNIO, schemas.TAPNIO, schemas.UDPNIO]:
    """
    Add a NIO (Network Input/Output) to the node.
    The adapter number on the cloud is always 0.
    """

    nio = Builtin.instance().create_nio(jsonable_encoder(nio_data, exclude_unset=True))
    await node.add_nio(nio, port_number)
    return nio.asdict()


@router.put(
    "/{node_id}/adapters/{adapter_number}/ports/{port_number}/nio",
    status_code=status.HTTP_201_CREATED,
    response_model=Union[schemas.EthernetNIO, schemas.TAPNIO, schemas.UDPNIO],
)
async def update_cloud_nio(
        *,
        adapter_number: int = Path(..., ge=0, le=0),
        port_number: int,
        nio_data: Union[schemas.EthernetNIO, schemas.TAPNIO, schemas.UDPNIO],
        node: Cloud = Depends(dep_node),
) -> Union[schemas.EthernetNIO, schemas.TAPNIO, schemas.UDPNIO]:
    """
    Update a NIO (Network Input/Output) to the node.
    The adapter number on the cloud is always 0.
    """

    nio = node.get_nio(port_number)
    if nio_data.filters:
        nio.filters = nio_data.filters
    await node.update_nio(port_number, nio)
    return nio.asdict()


@router.delete("/{node_id}/adapters/{adapter_number}/ports/{port_number}/nio", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cloud_nio(
        *,
        adapter_number: int = Path(..., ge=0, le=0),
        port_number: int,
        node: Cloud = Depends(dep_node)
) -> None:
    """
    Remove a NIO (Network Input/Output) from the node.
    The adapter number on the cloud is always 0.
    """

    await node.remove_nio(port_number)


@router.post("/{node_id}/adapters/{adapter_number}/ports/{port_number}/capture/start")
async def start_cloud_capture(
        *,
        adapter_number: int = Path(..., ge=0, le=0),
        port_number: int,
        node_capture_data: schemas.NodeCapture,
        node: Cloud = Depends(dep_node)
) -> dict:
    """
    Start a packet capture on the node.
    The adapter number on the cloud is always 0.
    """

    pcap_file_path = os.path.join(node.project.capture_working_directory(), node_capture_data.capture_file_name)
    await node.start_capture(port_number, pcap_file_path, node_capture_data.data_link_type)
    return {"pcap_file_path": pcap_file_path}


@router.post(
    "/{node_id}/adapters/{adapter_number}/ports/{port_number}/capture/stop", status_code=status.HTTP_204_NO_CONTENT
)
async def stop_cloud_capture(
        *,
        adapter_number: int = Path(..., ge=0, le=0),
        port_number: int,
        node: Cloud = Depends(dep_node)
) -> None:
    """
    Stop a packet capture on the node.
    The adapter number on the cloud is always 0.
    """

    await node.stop_capture(port_number)


@router.get("/{node_id}/adapters/{adapter_number}/ports/{port_number}/pcap")
async def stream_pcap_file(
        *,
        adapter_number: int = Path(..., ge=0, le=0),
        port_number: int,
        node: Cloud = Depends(dep_node)
) -> StreamingResponse:
    """
    Stream the pcap capture file.
    The adapter number on the cloud is always 0.
    """

    nio = node.get_nio(port_number)
    stream = Builtin.instance().stream_pcap_file(nio, node.project.id)
    return StreamingResponse(stream, media_type="application/vnd.tcpdump.pcap")
