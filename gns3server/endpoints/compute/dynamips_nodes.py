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
API endpoints for Dynamips nodes.
"""

import os
import sys

from fastapi import APIRouter, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from typing import List
from uuid import UUID

from gns3server.compute.dynamips import Dynamips
from gns3server.compute.dynamips.dynamips_error import DynamipsError
from gns3server.compute.project_manager import ProjectManager
from gns3server.endpoints import schemas

router = APIRouter()

DEFAULT_CHASSIS = {
    "c1700": "1720",
    "c2600": "2610",
    "c3600": "3640"
}


@router.post("/",
             response_model=schemas.Dynamips,
             status_code=status.HTTP_201_CREATED,
             responses={409: {"model": schemas.ErrorMessage, "description": "Could not create Dynamips node"}})
async def create_router(project_id: UUID, node_data: schemas.DynamipsCreate):
    """
    Create a new Dynamips router.
    """

    dynamips_manager = Dynamips.instance()
    platform = node_data.platform
    chassis = None
    if not node_data.chassis and platform in DEFAULT_CHASSIS:
        chassis = DEFAULT_CHASSIS[platform]
    node_data = jsonable_encoder(node_data, exclude_unset=True)
    vm = await dynamips_manager.create_node(node_data.pop("name"),
                                            str(project_id),
                                            node_data.get("node_id"),
                                            dynamips_id=node_data.get("dynamips_id"),
                                            platform=platform,
                                            console=node_data.get("console"),
                                            console_type=node_data.get("console_type", "telnet"),
                                            aux=node_data.get("aux"),
                                            aux_type=node_data.pop("aux_type", "none"),
                                            chassis=chassis,
                                            node_type="dynamips")
    await dynamips_manager.update_vm_settings(vm, node_data)
    return vm.__json__()


@router.get("/{node_id}",
            response_model=schemas.Dynamips,
            responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
def get_router(project_id: UUID, node_id: UUID):
    """
    Return Dynamips router.
    """

    dynamips_manager = Dynamips.instance()
    vm = dynamips_manager.get_node(str(node_id), project_id=str(project_id))
    return vm.__json__()


@router.put("/{node_id}",
            response_model=schemas.Dynamips,
            responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def update_router(project_id: UUID, node_id: UUID, node_data: schemas.DynamipsUpdate):
    """
    Update a Dynamips router.
    """

    dynamips_manager = Dynamips.instance()
    vm = dynamips_manager.get_node(str(node_id), project_id=str(project_id))
    await dynamips_manager.update_vm_settings(vm, jsonable_encoder(node_data, exclude_unset=True))
    vm.updated()
    return vm.__json__()


@router.delete("/{node_id}",
               status_code=status.HTTP_204_NO_CONTENT,
               responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def delete_router(project_id: UUID, node_id: UUID):
    """
    Delete a Dynamips router.
    """

    # check the project_id exists
    ProjectManager.instance().get_project(str(project_id))
    await Dynamips.instance().delete_node(str(node_id))


@router.post("/{node_id}/start",
             status_code=status.HTTP_204_NO_CONTENT,
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def start_router(project_id: UUID, node_id: UUID):
    """
    Start a Dynamips router.
    """

    dynamips_manager = Dynamips.instance()
    vm = dynamips_manager.get_node(str(node_id), project_id=str(project_id))
    try:
        await dynamips_manager.ghost_ios_support(vm)
    except GeneratorExit:
        pass
    await vm.start()


@router.post("/{node_id}/stop",
             status_code=status.HTTP_204_NO_CONTENT,
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def stop_router(project_id: UUID, node_id: UUID):
    """
    Stop a Dynamips router.
    """

    dynamips_manager = Dynamips.instance()
    vm = dynamips_manager.get_node(str(node_id), project_id=str(project_id))
    await vm.stop()


@router.post("/{node_id}/suspend",
             status_code=status.HTTP_204_NO_CONTENT,
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def suspend_router(project_id: UUID, node_id: UUID):

    dynamips_manager = Dynamips.instance()
    vm = dynamips_manager.get_node(str(node_id), project_id=str(project_id))
    await vm.suspend()


@router.post("/{node_id}/resume",
             status_code=status.HTTP_204_NO_CONTENT,
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def resume_router(project_id: UUID, node_id: UUID):
    """
    Resume a suspended Dynamips router.
    """

    dynamips_manager = Dynamips.instance()
    vm = dynamips_manager.get_node(str(node_id), project_id=str(project_id))
    await vm.resume()


@router.post("/{node_id}/reload",
             status_code=status.HTTP_204_NO_CONTENT,
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def reload(project_id: UUID, node_id: UUID):
    """
    Reload a suspended Dynamips router.
    """

    dynamips_manager = Dynamips.instance()
    vm = dynamips_manager.get_node(str(node_id), project_id=str(project_id))
    await vm.reload()


@router.post("/{node_id}/adapters/{adapter_number}/ports/{port_number}/nio",
             status_code=status.HTTP_201_CREATED,
             response_model=schemas.UDPNIO,
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def create_nio(project_id: UUID, node_id: UUID, adapter_number: int, port_number: int, nio_data: schemas.UDPNIO):
    """
    Add a NIO (Network Input/Output) to the node.
    """

    dynamips_manager = Dynamips.instance()
    vm = dynamips_manager.get_node(str(node_id), project_id=str(project_id))
    nio = await dynamips_manager.create_nio(vm, jsonable_encoder(nio_data, exclude_unset=True))
    await vm.slot_add_nio_binding(adapter_number, port_number, nio)
    return nio.__json__()


@router.put("/{node_id}/adapters/{adapter_number}/ports/{port_number}/nio",
            status_code=status.HTTP_201_CREATED,
            response_model=schemas.UDPNIO,
            responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def update_nio(project_id: UUID, node_id: UUID, adapter_number: int, port_number: int, nio_data: schemas.UDPNIO):
    """
    Update a NIO (Network Input/Output) on the node.
    """

    dynamips_manager = Dynamips.instance()
    vm = dynamips_manager.get_node(str(node_id), project_id=str(project_id))
    nio = vm.get_nio(adapter_number, port_number)
    if nio_data.filters:
        nio.filters = nio_data.filters
    await vm.slot_update_nio_binding(adapter_number, port_number, nio)
    return nio.__json__()


@router.delete("/{node_id}/adapters/{adapter_number}/ports/{port_number}/nio",
               status_code=status.HTTP_204_NO_CONTENT,
               responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def delete_nio(project_id: UUID, node_id: UUID, adapter_number: int, port_number: int):
    """
    Delete a NIO (Network Input/Output) from the node.
    """

    dynamips_manager = Dynamips.instance()
    vm = dynamips_manager.get_node(str(node_id), project_id=str(project_id))
    nio = await vm.slot_remove_nio_binding(adapter_number, port_number)
    await nio.delete()


@router.post("/{node_id}/adapters/{adapter_number}/ports/{port_number}/start_capture",
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def start_capture(project_id: UUID, node_id: UUID, adapter_number: int, port_number: int, node_capture_data: schemas.NodeCapture):
    """
    Start a packet capture on the node.
    """

    dynamips_manager = Dynamips.instance()
    vm = dynamips_manager.get_node(str(node_id), project_id=str(project_id))
    pcap_file_path = os.path.join(vm.project.capture_working_directory(), node_capture_data.capture_file_name)

    if sys.platform.startswith('win'):
        # FIXME: Dynamips (Cygwin actually) doesn't like non ascii paths on Windows
        try:
            pcap_file_path.encode('ascii')
        except UnicodeEncodeError:
            raise DynamipsError('The capture file path "{}" must only contain ASCII (English) characters'.format(pcap_file_path))

    await vm.start_capture(adapter_number, port_number, pcap_file_path, node_capture_data.data_link_type)
    return {"pcap_file_path": pcap_file_path}


@router.post("/{node_id}/adapters/{adapter_number}/ports/{port_number}/stop_capture",
             status_code=status.HTTP_204_NO_CONTENT,
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def stop_capture(project_id: UUID, node_id: UUID, adapter_number: int, port_number: int):
    """
    Stop a packet capture on the node.
    """

    dynamips_manager = Dynamips.instance()
    vm = dynamips_manager.get_node(str(node_id), project_id=str(project_id))
    await vm.stop_capture(adapter_number, port_number)


@router.get("/{node_id}/adapters/{adapter_number}/ports/{port_number}/pcap",
            responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def stream_pcap_file(project_id: UUID, node_id: UUID, adapter_number: int, port_number: int):
    """
    Stream the pcap capture file.
    """

    dynamips_manager = Dynamips.instance()
    vm = dynamips_manager.get_node(str(node_id), project_id=str(project_id))
    nio = vm.get_nio(adapter_number, port_number)
    stream = dynamips_manager.stream_pcap_file(nio, vm.project.id)
    return StreamingResponse(stream, media_type="application/vnd.tcpdump.pcap")


@router.get("/{node_id}/idlepc_proposals",
            responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def get_idlepcs(project_id: UUID, node_id: UUID) -> List[str]:
    """
    Retrieve Dynamips idle-pc proposals
    """

    dynamips_manager = Dynamips.instance()
    vm = dynamips_manager.get_node(str(node_id), project_id=str(project_id))
    await vm.set_idlepc("0x0")
    return await vm.get_idle_pc_prop()


@router.get("/{node_id}/auto_idlepc",
            responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def get_auto_idlepc(project_id: UUID, node_id: UUID) -> dict:
    """
    Get an automatically guessed best idle-pc value.
    """

    dynamips_manager = Dynamips.instance()
    vm = dynamips_manager.get_node(str(node_id), project_id=str(project_id))
    idlepc = await dynamips_manager.auto_idlepc(vm)
    return {"idlepc": idlepc}


@router.post("/{node_id}/duplicate",
             status_code=status.HTTP_201_CREATED,
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def duplicate_router(project_id: UUID, node_id: UUID, destination_node_id: UUID):
    """
    Duplicate a router.
    """

    new_node = await Dynamips.instance().duplicate_node(str(node_id), str(destination_node_id))
    return new_node.__json__()


# @Route.get(
#     r"/projects/{project_id}/dynamips/nodes/{node_id}/console/ws",
#     description="WebSocket for console",
#     parameters={
#         "project_id": "Project UUID",
#         "node_id": "Node UUID",
#     })
# async def console_ws(request, response):
#
#     dynamips_manager = Dynamips.instance()
#     vm = dynamips_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
#     return await vm.start_websocket_console(request)


@router.post("/{node_id}/console/reset",
             status_code=status.HTTP_204_NO_CONTENT,
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def reset_console(project_id: UUID, node_id: UUID):

    dynamips_manager = Dynamips.instance()
    vm = dynamips_manager.get_node(str(node_id), project_id=str(project_id))
    await vm.reset_console()
