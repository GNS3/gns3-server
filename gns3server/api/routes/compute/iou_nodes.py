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
API routes for IOU nodes.
"""

import os

from fastapi import APIRouter, WebSocket, Depends, Body, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from typing import Union
from uuid import UUID

from gns3server import schemas
from gns3server.compute.iou import IOU
from gns3server.compute.iou.iou_vm import IOUVM

from .dependencies.authentication import compute_authentication, ws_compute_authentication

responses = {404: {"model": schemas.ErrorMessage, "description": "Could not find project or IOU node"}}

router = APIRouter(responses=responses)


def dep_node(project_id: UUID, node_id: UUID) -> IOUVM:
    """
    Dependency to retrieve a node.
    """

    iou_manager = IOU.instance()
    node = iou_manager.get_node(str(node_id), project_id=str(project_id))
    return node


@router.post(
    "",
    response_model=schemas.IOU,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": schemas.ErrorMessage, "description": "Could not create IOU node"}},
    dependencies=[Depends(compute_authentication)]
)
async def create_iou_node(project_id: UUID, node_data: schemas.IOUCreate) -> schemas.IOU:
    """
    Create a new IOU node.
    """

    iou = IOU.instance()
    node_data = jsonable_encoder(node_data, exclude_unset=True)
    vm = await iou.create_node(
        node_data.pop("name"),
        str(project_id),
        node_data.get("node_id"),
        application_id=node_data.get("application_id"),
        path=node_data.get("path"),
        console=node_data.get("console"),
        console_type=node_data.get("console_type", "telnet"),
    )

    for name, value in node_data.items():
        if hasattr(vm, name) and getattr(vm, name) != value:
            if name == "application_id":
                continue  # we must ignore this to avoid overwriting the application_id allocated by the controller
            if name == "startup_config_content" and (vm.startup_config_content and len(vm.startup_config_content) > 0):
                continue
            if name == "private_config_content" and (vm.private_config_content and len(vm.private_config_content) > 0):
                continue
            if node_data.get("use_default_iou_values") and (name == "ram" or name == "nvram"):
                continue
            setattr(vm, name, value)
    return vm.asdict()


@router.get(
    "/{node_id}",
    response_model=schemas.IOU,
    dependencies=[Depends(compute_authentication)]
)
def get_iou_node(node: IOUVM = Depends(dep_node)) -> schemas.IOU:
    """
    Return an IOU node.
    """

    return node.asdict()


@router.put(
    "/{node_id}",
    response_model=schemas.IOU,
    dependencies=[Depends(compute_authentication)]
)
async def update_iou_node(node_data: schemas.IOUUpdate, node: IOUVM = Depends(dep_node)) -> schemas.IOU:
    """
    Update an IOU node.
    """

    node_data = jsonable_encoder(node_data, exclude_unset=True)
    for name, value in node_data.items():
        if hasattr(node, name) and getattr(node, name) != value:
            if name == "application_id":
                continue  # we must ignore this to avoid overwriting the application_id allocated by the IOU manager
            setattr(node, name, value)

    if node.use_default_iou_values:
        # update the default IOU values in case the image or use_default_iou_values have changed
        # this is important to have the correct NVRAM amount in order to correctly push the configs to the NVRAM
        await node.update_default_iou_values()
    node.updated()
    return node.asdict()


@router.delete(
    "/{node_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(compute_authentication)]
)
async def delete_iou_node(node: IOUVM = Depends(dep_node)) -> None:
    """
    Delete an IOU node.
    """

    await IOU.instance().delete_node(node.id)


@router.post(
    "/{node_id}/duplicate",
    response_model=schemas.IOU,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(compute_authentication)]
)
async def duplicate_iou_node(
        destination_node_id: UUID = Body(..., embed=True),
        node: IOUVM = Depends(dep_node)
) -> schemas.IOU:
    """
    Duplicate an IOU node.
    """

    new_node = await IOU.instance().duplicate_node(node.id, str(destination_node_id))
    return new_node.asdict()


@router.post(
    "/{node_id}/start",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(compute_authentication)]
)
async def start_iou_node(start_data: schemas.IOUStart, node: IOUVM = Depends(dep_node)) -> None:
    """
    Start an IOU node.
    """

    start_data = jsonable_encoder(start_data, exclude_unset=True)
    for name, value in start_data.items():
        if hasattr(node, name) and getattr(node, name) != value:
            setattr(node, name, value)

    await node.start()


@router.post(
    "/{node_id}/stop",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(compute_authentication)]
)
async def stop_iou_node(node: IOUVM = Depends(dep_node)) -> None:
    """
    Stop an IOU node.
    """

    await node.stop()


@router.post(
    "/{node_id}/stop",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(compute_authentication)]
)
def suspend_iou_node(node: IOUVM = Depends(dep_node)) -> None:
    """
    Suspend an IOU node.
    Does nothing since IOU doesn't support being suspended.
    """

    pass


@router.post(
    "/{node_id}/reload",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(compute_authentication)]
)
async def reload_iou_node(node: IOUVM = Depends(dep_node)) -> None:
    """
    Reload an IOU node.
    """

    await node.reload()


@router.post(
    "/{node_id}/adapters/{adapter_number}/ports/{port_number}/nio",
    status_code=status.HTTP_201_CREATED,
    response_model=Union[schemas.EthernetNIO, schemas.TAPNIO, schemas.UDPNIO],
    dependencies=[Depends(compute_authentication)]
)
async def create_iou_node_nio(
    adapter_number: int,
    port_number: int,
    nio_data: Union[schemas.EthernetNIO, schemas.TAPNIO, schemas.UDPNIO],
    node: IOUVM = Depends(dep_node),
) -> Union[schemas.EthernetNIO, schemas.TAPNIO, schemas.UDPNIO]:
    """
    Add a NIO (Network Input/Output) to the node.
    """

    nio = IOU.instance().create_nio(jsonable_encoder(nio_data, exclude_unset=True))
    await node.adapter_add_nio_binding(adapter_number, port_number, nio)
    return nio.asdict()


@router.put(
    "/{node_id}/adapters/{adapter_number}/ports/{port_number}/nio",
    status_code=status.HTTP_201_CREATED,
    response_model=Union[schemas.EthernetNIO, schemas.TAPNIO, schemas.UDPNIO],
    dependencies=[Depends(compute_authentication)]
)
async def update_iou_node_nio(
    adapter_number: int,
    port_number: int,
    nio_data: Union[schemas.EthernetNIO, schemas.TAPNIO, schemas.UDPNIO],
    node: IOUVM = Depends(dep_node),
) -> Union[schemas.EthernetNIO, schemas.TAPNIO, schemas.UDPNIO]:
    """
    Update a NIO (Network Input/Output) on the node.
    """

    nio = node.get_nio(adapter_number, port_number)
    if nio_data.filters:
        nio.filters = nio_data.filters
    await node.adapter_update_nio_binding(adapter_number, port_number, nio)
    return nio.asdict()


@router.delete(
    "/{node_id}/adapters/{adapter_number}/ports/{port_number}/nio",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(compute_authentication)]
)
async def delete_iou_node_nio(adapter_number: int, port_number: int, node: IOUVM = Depends(dep_node)) -> None:
    """
    Delete a NIO (Network Input/Output) from the node.
    """

    await node.adapter_remove_nio_binding(adapter_number, port_number)


@router.post(
    "/{node_id}/adapters/{adapter_number}/ports/{port_number}/capture/start",
    dependencies=[Depends(compute_authentication)]
)
async def start_iou_node_capture(
        adapter_number: int,
        port_number: int,
        node_capture_data: schemas.NodeCapture,
        node: IOUVM = Depends(dep_node)
) -> dict:
    """
    Start a packet capture on the node.
    """

    pcap_file_path = os.path.join(node.project.capture_working_directory(), node_capture_data.capture_file_name)
    await node.start_capture(adapter_number, pcap_file_path)
    return {"pcap_file_path": str(pcap_file_path)}


@router.post(
    "/{node_id}/adapters/{adapter_number}/ports/{port_number}/capture/stop",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(compute_authentication)]
)
async def stop_iou_node_capture(adapter_number: int, port_number: int, node: IOUVM = Depends(dep_node)) -> None:
    """
    Stop a packet capture on the node.
    """

    await node.stop_capture(adapter_number, port_number)


@router.get(
    "/{node_id}/adapters/{adapter_number}/ports/{port_number}/capture/stream",
    dependencies=[Depends(compute_authentication)]
)
async def stream_pcap_file(
        adapter_number: int,
        port_number: int,
        node: IOUVM = Depends(dep_node)
) -> StreamingResponse:
    """
    Stream the pcap capture file.
    """

    nio = node.get_nio(adapter_number, port_number)
    stream = IOU.instance().stream_pcap_file(nio, node.project.id)
    return StreamingResponse(stream, media_type="application/vnd.tcpdump.pcap")


@router.websocket(
    "/{node_id}/console/ws",
)
async def console_ws(
        websocket: Union[None, WebSocket] = Depends(ws_compute_authentication),
        node: IOUVM = Depends(dep_node)
) -> None:
    """
    Console WebSocket.
    """

    if websocket:
        await node.start_websocket_console(websocket)


@router.post(
    "/{node_id}/console/reset",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(compute_authentication)]
)
async def reset_console(node: IOUVM = Depends(dep_node)) -> None:

    await node.reset_console()
