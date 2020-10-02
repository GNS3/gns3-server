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
API endpoints for VPCS nodes.
"""

import os

from fastapi import APIRouter, Body, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from uuid import UUID

from gns3server.endpoints import schemas
from gns3server.compute.vpcs import VPCS
from gns3server.compute.project_manager import ProjectManager


router = APIRouter()


@router.post("/",
             response_model=schemas.VPCS,
             status_code=status.HTTP_201_CREATED,
             responses={409: {"model": schemas.ErrorMessage, "description": "Could not create VMware node"}})
async def create_vpcs_node(project_id: UUID, node_data: schemas.VPCSCreate):
    """
    Create a new VPCS node.
    """

    vpcs = VPCS.instance()
    node_data = jsonable_encoder(node_data, exclude_unset=True)
    vm = await vpcs.create_node(node_data["name"],
                                str(project_id),
                                node_data.get("node_id"),
                                console=node_data.get("console"),
                                console_type=node_data.get("console_type", "telnet"),
                                startup_script=node_data.get("startup_script"))

    return vm.__json__()


@router.get("/{node_id}",
            response_model=schemas.VPCS,
            responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
def get_vpcs_node(project_id: UUID, node_id: UUID):
    """
    Return a VPCS node.
    """

    vpcs_manager = VPCS.instance()
    vm = vpcs_manager.get_node(str(node_id), project_id=str(project_id))
    return vm.__json__()


@router.put("/{node_id}",
            response_model=schemas.VPCS,
            responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
def update_vpcs_node(project_id: UUID, node_id: UUID, node_data: schemas.VPCSUpdate):
    """
    Update a VPCS node.
    """

    vpcs_manager = VPCS.instance()
    vm = vpcs_manager.get_node(str(node_id), project_id=str(project_id))
    node_data = jsonable_encoder(node_data, exclude_unset=True)
    vm.name = node_data.get("name", vm.name)
    vm.console = node_data.get("console", vm.console)
    vm.console_type = node_data.get("console_type", vm.console_type)
    vm.updated()
    return vm.__json__()


@router.delete("/{node_id}",
               status_code=status.HTTP_204_NO_CONTENT,
               responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def delete_vpcs_node(project_id: UUID, node_id: UUID):
    """
    Delete a VPCS node.
    """

    # check the project_id exists
    ProjectManager.instance().get_project(str(project_id))
    await VPCS.instance().delete_node(str(node_id))


@router.post("/{node_id}/duplicate",
             response_model=schemas.VPCS,
             status_code=status.HTTP_201_CREATED,
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def duplicate_vpcs_node(project_id: UUID, node_id: UUID, destination_node_id: UUID = Body(..., embed=True)):
    """
    Duplicate a VPCS node.
    """

    new_node = await VPCS.instance().duplicate_node(str(node_id), str(destination_node_id))
    return new_node.__json__()


@router.post("/{node_id}/start",
             status_code=status.HTTP_204_NO_CONTENT,
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def start_vpcs_node(project_id: UUID, node_id: UUID):
    """
    Start a VPCS node.
    """

    vpcs_manager = VPCS.instance()
    vm = vpcs_manager.get_node(str(node_id), project_id=str(project_id))
    await vm.start()


@router.post("/{node_id}/stop",
             status_code=status.HTTP_204_NO_CONTENT,
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def stop_vpcs_node(project_id: UUID, node_id: UUID):
    """
    Stop a VPCS node.
    """

    vpcs_manager = VPCS.instance()
    vm = vpcs_manager.get_node(str(node_id), project_id=str(project_id))
    await vm.stop()


@router.post("/{node_id}/suspend",
             status_code=status.HTTP_204_NO_CONTENT,
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def suspend_vpcs_node(project_id: UUID, node_id: UUID):
    """
    Suspend a VPCS node.
    Does nothing, suspend is not supported by VPCS.
    """

    vpcs_manager = VPCS.instance()
    vpcs_manager.get_node(str(node_id), project_id=str(project_id))


@router.post("/{node_id}/reload",
             status_code=status.HTTP_204_NO_CONTENT,
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def reload_vpcs_node(project_id: UUID, node_id: UUID):
    """
    Reload a VPCS node.
    """

    vpcs_manager = VPCS.instance()
    vm = vpcs_manager.get_node(str(node_id), project_id=str(project_id))
    await vm.reload()


@router.post("/{node_id}/adapters/{adapter_number}/ports/{port_number}/nio",
             status_code=status.HTTP_201_CREATED,
             response_model=schemas.UDPNIO,
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def create_nio(project_id: UUID, node_id: UUID, adapter_number: int, port_number: int, nio_data: schemas.UDPNIO):
    """
    Add a NIO (Network Input/Output) to the node.
    The adapter number on the VPCS node is always 0.
    """

    vpcs_manager = VPCS.instance()
    vm = vpcs_manager.get_node(str(node_id), project_id=str(project_id))
    nio = vpcs_manager.create_nio(jsonable_encoder(nio_data, exclude_unset=True))
    await vm.port_add_nio_binding(port_number, nio)
    return nio.__json__()


@router.put("/{node_id}/adapters/{adapter_number}/ports/{port_number}/nio",
            status_code=status.HTTP_201_CREATED,
            response_model=schemas.UDPNIO,
            responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def update_nio(project_id: UUID, node_id: UUID, adapter_number: int, port_number: int, nio_data: schemas.UDPNIO):
    """
    Update a NIO (Network Input/Output) on the node.
    The adapter number on the VPCS node is always 0.
    """


    vpcs_manager = VPCS.instance()
    vm = vpcs_manager.get_node(str(node_id), project_id=str(project_id))
    nio = vm.get_nio(port_number)
    if nio_data.filters:
        nio.filters = nio_data.filters
    await vm.port_update_nio_binding(port_number, nio)
    return nio.__json__()


@router.delete("/{node_id}/adapters/{adapter_number}/ports/{port_number}/nio",
               status_code=status.HTTP_204_NO_CONTENT,
               responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def delete_nio(project_id: UUID, node_id: UUID, adapter_number: int, port_number: int):
    """
    Delete a NIO (Network Input/Output) from the node.
    The adapter number on the VPCS node is always 0.
    """

    vpcs_manager = VPCS.instance()
    vm = vpcs_manager.get_node(str(node_id), project_id=str(project_id))
    await vm.port_remove_nio_binding(port_number)


@router.post("/{node_id}/adapters/{adapter_number}/ports/{port_number}/start_capture",
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def start_capture(project_id: UUID, node_id: UUID, adapter_number: int, port_number: int, node_capture_data: schemas.NodeCapture):
    """
    Start a packet capture on the node.
    The adapter number on the VPCS node is always 0.
    """

    vpcs_manager = VPCS.instance()
    vm = vpcs_manager.get_node(str(node_id), project_id=str(project_id))
    pcap_file_path = os.path.join(vm.project.capture_working_directory(), node_capture_data.capture_file_name)
    await vm.start_capture(adapter_number, pcap_file_path)
    return {"pcap_file_path": pcap_file_path}


@router.post("/{node_id}/adapters/{adapter_number}/ports/{port_number}/stop_capture",
             status_code=status.HTTP_204_NO_CONTENT,
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def stop_capture(project_id: UUID, node_id: UUID, adapter_number: int, port_number: int):
    """
    Stop a packet capture on the node.
    The adapter number on the VPCS node is always 0.
    """

    vpcs_manager = VPCS.instance()
    vm = vpcs_manager.get_node(str(node_id), project_id=str(project_id))
    await vm.stop_capture(port_number)


@router.post("/{node_id}/console/reset",
             status_code=status.HTTP_204_NO_CONTENT,
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def reset_console(project_id: UUID, node_id: UUID):

    vpcs_manager = VPCS.instance()
    vm = vpcs_manager.get_node(str(node_id), project_id=str(project_id))
    await vm.reset_console()


@router.get("/{node_id}/adapters/{adapter_number}/ports/{port_number}/pcap",
            responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def stream_pcap_file(project_id: UUID, node_id: UUID, adapter_number: int, port_number: int):
    """
    Stream the pcap capture file.
    The adapter number on the VPCS node is always 0.
    """

    vpcs_manager = VPCS.instance()
    vm = vpcs_manager.get_node(str(node_id), project_id=str(project_id))
    nio = vm.get_nio(port_number)
    stream = vpcs_manager.stream_pcap_file(nio, vm.project.id)
    return StreamingResponse(stream, media_type="application/vnd.tcpdump.pcap")


# @Route.get(
#     r"/projects/{project_id}/vpcs/nodes/{node_id}/console/ws",
#     description="WebSocket for console",
#     parameters={
#         "project_id": "Project UUID",
#         "node_id": "Node UUID",
#     })
# async def console_ws(request, response):
#
#     vpcs_manager = VPCS.instance()
#     vm = vpcs_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
#     return await vm.start_websocket_console(request)
