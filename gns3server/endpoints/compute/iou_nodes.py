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
API endpoints for IOU nodes.
"""

import os

from fastapi import APIRouter, Body, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from typing import Union
from uuid import UUID

from gns3server.endpoints import schemas
from gns3server.compute.iou import IOU

router = APIRouter()


@router.post("/",
             response_model=schemas.IOU,
             status_code=status.HTTP_201_CREATED,
             responses={409: {"model": schemas.ErrorMessage, "description": "Could not create IOU node"}})
async def create_iou_node(project_id: UUID, node_data: schemas.IOUCreate):
    """
    Create a new IOU node.
    """

    iou = IOU.instance()
    node_data = jsonable_encoder(node_data, exclude_unset=True)
    vm = await iou.create_node(node_data.pop("name"),
                               str(project_id),
                               node_data.get("node_id"),
                               application_id=node_data.get("application_id"),
                               path=node_data.get("path"),
                               console=node_data.get("console"),
                               console_type=node_data.get("console_type", "telnet"))

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
    return vm.__json__()


@router.get("/{node_id}",
            response_model=schemas.IOU,
            responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
def get_iou_node(project_id: UUID, node_id: UUID):
    """
    Return an IOU node.
    """

    iou_manager = IOU.instance()
    vm = iou_manager.get_node(str(node_id), project_id=str(project_id))
    return vm.__json__()


@router.put("/{node_id}",
            response_model=schemas.IOU,
            responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def update_iou_node(project_id: UUID, node_id: UUID, node_data: schemas.IOUUpdate):
    """
    Update an IOU node.
    """

    iou_manager = IOU.instance()
    vm = iou_manager.get_node(str(node_id), project_id=str(project_id))
    node_data = jsonable_encoder(node_data, exclude_unset=True)
    for name, value in node_data.items():
        if hasattr(vm, name) and getattr(vm, name) != value:
            if name == "application_id":
                continue  # we must ignore this to avoid overwriting the application_id allocated by the IOU manager
            setattr(vm, name, value)

    if vm.use_default_iou_values:
        # update the default IOU values in case the image or use_default_iou_values have changed
        # this is important to have the correct NVRAM amount in order to correctly push the configs to the NVRAM
        await vm.update_default_iou_values()
    vm.updated()
    return vm.__json__()


@router.delete("/{node_id}",
               status_code=status.HTTP_204_NO_CONTENT,
               responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def delete_iou_node(project_id: UUID, node_id: UUID):
    """
    Delete an IOU node.
    """

    await IOU.instance().delete_node(str(node_id))


@router.post("/{node_id}/duplicate",
             response_model=schemas.IOU,
             status_code=status.HTTP_201_CREATED,
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def duplicate_iou_node(project_id: UUID, node_id: UUID, destination_node_id: UUID = Body(..., embed=True)):
    """
    Duplicate an IOU node.
    """

    new_node = await IOU.instance().duplicate_node(str(node_id), str(destination_node_id))
    return new_node.__json__()


@router.post("/{node_id}/start",
             status_code=status.HTTP_204_NO_CONTENT,
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def start_iou_node(project_id: UUID, node_id: UUID, start_data: schemas.IOUStart):
    """
    Start an IOU node.
    """

    iou_manager = IOU.instance()
    vm = iou_manager.get_node(str(node_id), project_id=str(project_id))
    start_data = jsonable_encoder(start_data, exclude_unset=True)
    for name, value in start_data.items():
        if hasattr(vm, name) and getattr(vm, name) != value:
            setattr(vm, name, value)

    await vm.start()
    return vm.__json__()


@router.post("/{node_id}/stop",
             status_code=status.HTTP_204_NO_CONTENT,
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def stop(project_id: UUID, node_id: UUID):
    """
    Stop an IOU node.
    """

    iou_manager = IOU.instance()
    vm = iou_manager.get_node(str(node_id), project_id=str(project_id))
    await vm.stop()


@router.post("/{node_id}/stop",
             status_code=status.HTTP_204_NO_CONTENT,
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
def suspend_iou_node(project_id: UUID, node_id: UUID):
    """
    Suspend an IOU node.
    Does nothing since IOU doesn't support being suspended.
    """

    iou_manager = IOU.instance()
    iou_manager.get_node(str(node_id), project_id=str(project_id))


@router.post("/{node_id}/reload",
             status_code=status.HTTP_204_NO_CONTENT,
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def reload_iou_node(project_id: UUID, node_id: UUID):
    """
    Reload an IOU node.
    """

    iou_manager = IOU.instance()
    vm = iou_manager.get_node(str(node_id), project_id=str(project_id))
    await vm.reload()


@router.post("/{node_id}/adapters/{adapter_number}/ports/{port_number}/nio",
             status_code=status.HTTP_201_CREATED,
             response_model=Union[schemas.EthernetNIO, schemas.TAPNIO, schemas.UDPNIO],
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def create_nio(project_id: UUID,
                     node_id: UUID,
                     adapter_number: int,
                     port_number: int,
                     nio_data: Union[schemas.EthernetNIO, schemas.TAPNIO, schemas.UDPNIO]):
    """
    Add a NIO (Network Input/Output) to the node.
    """

    iou_manager = IOU.instance()
    vm = iou_manager.get_node(str(node_id), project_id=str(project_id))
    nio = iou_manager.create_nio(jsonable_encoder(nio_data, exclude_unset=True))
    await vm.adapter_add_nio_binding(adapter_number, port_number, nio)
    return nio.__json__()


@router.put("/{node_id}/adapters/{adapter_number}/ports/{port_number}/nio",
            status_code=status.HTTP_201_CREATED,
            response_model=Union[schemas.EthernetNIO, schemas.TAPNIO, schemas.UDPNIO],
            responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def update_nio(project_id: UUID,
                     node_id: UUID,
                     adapter_number: int,
                     port_number: int,
                     nio_data: Union[schemas.EthernetNIO, schemas.TAPNIO, schemas.UDPNIO]):
    """
    Update a NIO (Network Input/Output) on the node.
    """

    iou_manager = IOU.instance()
    vm = iou_manager.get_node(str(node_id), project_id=str(project_id))
    nio = vm.get_nio(adapter_number, port_number)
    if nio_data.filters:
        nio.filters = nio_data.filters
    await vm.adapter_update_nio_binding(adapter_number, port_number, nio)
    return nio.__json__()
    return nio.__json__()


@router.delete("/{node_id}/adapters/{adapter_number}/ports/{port_number}/nio",
               status_code=status.HTTP_204_NO_CONTENT,
               responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def delete_nio(project_id: UUID, node_id: UUID, adapter_number: int, port_number: int):
    """
    Delete a NIO (Network Input/Output) from the node.
    """

    iou_manager = IOU.instance()
    vm = iou_manager.get_node(str(node_id), project_id=str(project_id))
    await vm.adapter_remove_nio_binding(adapter_number, port_number)


@router.post("/{node_id}/adapters/{adapter_number}/ports/{port_number}/start_capture",
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def start_capture(project_id: UUID, node_id: UUID, adapter_number: int, port_number: int, node_capture_data: schemas.NodeCapture):
    """
    Start a packet capture on the node.
    """

    iou_manager = IOU.instance()
    vm = iou_manager.get_node(str(node_id), project_id=str(project_id))
    pcap_file_path = os.path.join(vm.project.capture_working_directory(), node_capture_data.capture_file_name)
    await vm.start_capture(adapter_number, pcap_file_path)
    return {"pcap_file_path": str(pcap_file_path)}


@router.post("/{node_id}/adapters/{adapter_number}/ports/{port_number}/stop_capture",
             status_code=status.HTTP_204_NO_CONTENT,
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def stop_capture(project_id: UUID, node_id: UUID, adapter_number: int, port_number: int):
    """
    Stop a packet capture on the node.
    """

    iou_manager = IOU.instance()
    vm = iou_manager.get_node(str(node_id), project_id=str(project_id))
    await vm.stop_capture(adapter_number, port_number)


@router.get("/{node_id}/adapters/{adapter_number}/ports/{port_number}/pcap",
            responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def stream_pcap_file(project_id: UUID, node_id: UUID, adapter_number: int, port_number: int):
    """
    Stream the pcap capture file.
    """

    iou_manager = IOU.instance()
    vm = iou_manager.get_node(str(node_id), project_id=str(project_id))
    nio = vm.get_nio(adapter_number, port_number)
    stream = iou_manager.stream_pcap_file(nio, vm.project.id)
    return StreamingResponse(stream, media_type="application/vnd.tcpdump.pcap")


@router.post("/{node_id}/console/reset",
             status_code=status.HTTP_204_NO_CONTENT,
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def reset_console(project_id: UUID, node_id: UUID):

    iou_manager = IOU.instance()
    vm = iou_manager.get_node(str(node_id), project_id=str(project_id))
    await vm.reset_console()


# @Route.get(
#     r"/projects/{project_id}/iou/nodes/{node_id}/console/ws",
#     description="WebSocket for console",
#     parameters={
#         "project_id": "Project UUID",
#         "node_id": "Node UUID",
#     })
# async def console_ws(request, response):
#
#     iou_manager = IOU.instance()
#     vm = iou_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
#     return await vm.start_websocket_console(request)
