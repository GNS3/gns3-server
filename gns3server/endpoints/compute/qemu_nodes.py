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
API endpoints for Qemu nodes.
"""

import os
import sys

from fastapi import APIRouter, Body, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from uuid import UUID

from gns3server.endpoints import schemas
from gns3server.compute.project_manager import ProjectManager
from gns3server.compute.compute_error import ComputeError
from gns3server.compute.qemu import Qemu

router = APIRouter()


@router.post("/",
             response_model=schemas.Qemu,
             status_code=status.HTTP_201_CREATED,
             responses={409: {"model": schemas.ErrorMessage, "description": "Could not create Qemu node"}})
async def create_qemu_node(project_id: UUID, node_data: schemas.QemuCreate):
    """
    Create a new Qemu node.
    """

    qemu = Qemu.instance()
    node_data = jsonable_encoder(node_data, exclude_unset=True)
    vm = await qemu.create_node(node_data.pop("name"),
                                str(project_id),
                                node_data.pop("node_id", None),
                                linked_clone=node_data.get("linked_clone", True),
                                qemu_path=node_data.pop("qemu_path", None),
                                console=node_data.pop("console", None),
                                console_type=node_data.pop("console_type", "telnet"),
                                aux=node_data.get("aux"),
                                aux_type=node_data.pop("aux_type", "none"),
                                platform=node_data.pop("platform", None))

    for name, value in node_data.items():
        if hasattr(vm, name) and getattr(vm, name) != value:
            setattr(vm, name, value)

    return vm.__json__()


@router.get("/{node_id}",
            response_model=schemas.Qemu,
            responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
def get_qemu_node(project_id: UUID, node_id: UUID):
    """
    Return a Qemu node.
    """

    qemu_manager = Qemu.instance()
    vm = qemu_manager.get_node(str(node_id), project_id=str(project_id))
    return vm.__json__()


@router.put("/{node_id}",
            response_model=schemas.Qemu,
            responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def update_qemu_node(project_id: UUID, node_id: UUID, node_data: schemas.QemuUpdate):
    """
    Update a Qemu node.
    """

    qemu_manager = Qemu.instance()
    vm = qemu_manager.get_node(str(node_id), project_id=str(project_id))
    node_data = jsonable_encoder(node_data, exclude_unset=True)
    # update the console first to avoid issue if updating console type
    vm.console = node_data.pop("console", vm.console)
    for name, value in node_data.items():
        if hasattr(vm, name) and getattr(vm, name) != value:
            await vm.update_property(name, value)
    vm.updated()
    return vm.__json__()


@router.delete("/{node_id}",
               status_code=status.HTTP_204_NO_CONTENT,
               responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def delete_qemu_node(project_id: UUID, node_id: UUID):
    """
    Delete a Qemu node.
    """

    await Qemu.instance().delete_node(str(node_id))


@router.post("/{node_id}/duplicate",
             response_model=schemas.Qemu,
             status_code=status.HTTP_201_CREATED,
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def duplicate_qemu_node(project_id: UUID, node_id: UUID, destination_node_id: UUID = Body(..., embed=True)):
    """
    Duplicate a Qemu node.
    """

    new_node = await Qemu.instance().duplicate_node(str(node_id), str(destination_node_id))
    return new_node.__json__()


@router.post("/{node_id}/resize_disk",
             status_code=status.HTTP_204_NO_CONTENT,
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def resize_qemu_node_disk(project_id: UUID, node_id: UUID, node_data: schemas.QemuDiskResize):

    qemu_manager = Qemu.instance()
    vm = qemu_manager.get_node(str(node_id), project_id=str(project_id))
    await vm.resize_disk(node_data.drive_name, node_data.extend)


@router.post("/{node_id}/start",
             status_code=status.HTTP_204_NO_CONTENT,
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def start_qemu_node(project_id: UUID, node_id: UUID):
    """
    Start a Qemu node.
    """

    qemu_manager = Qemu.instance()
    vm = qemu_manager.get_node(str(node_id), project_id=str(project_id))
    hardware_accel = qemu_manager.config.get_section_config("Qemu").getboolean("enable_hardware_acceleration", True)
    if sys.platform.startswith("linux"):
        # the enable_kvm option was used before version 2.0 and has priority
        enable_kvm = qemu_manager.config.get_section_config("Qemu").getboolean("enable_kvm")
        if enable_kvm is not None:
            hardware_accel = enable_kvm
    if hardware_accel and "-no-kvm" not in vm.options and "-no-hax" not in vm.options:
        pm = ProjectManager.instance()
        if pm.check_hardware_virtualization(vm) is False:
            pass  #FIXME: check this
            #raise ComputeError("Cannot start VM with hardware acceleration (KVM/HAX) enabled because hardware virtualization (VT-x/AMD-V) is already used by another software like VMware or VirtualBox")
    await vm.start()


@router.post("/{node_id}/stop",
             status_code=status.HTTP_204_NO_CONTENT,
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def stop_qemu_node(project_id: UUID, node_id: UUID):
    """
    Stop a Qemu node.
    """

    qemu_manager = Qemu.instance()
    vm = qemu_manager.get_node(str(node_id), project_id=str(project_id))
    await vm.stop()


@router.post("/{node_id}/reload",
             status_code=status.HTTP_204_NO_CONTENT,
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def reload_qemu_node(project_id: UUID, node_id: UUID):
    """
    Reload a Qemu node.
    """

    qemu_manager = Qemu.instance()
    vm = qemu_manager.get_node(str(node_id), project_id=str(project_id))
    await vm.reload()


@router.post("/{node_id}/suspend",
             status_code=status.HTTP_204_NO_CONTENT,
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def suspend_qemu_node(project_id: UUID, node_id: UUID):
    """
    Suspend a Qemu node.
    """

    qemu_manager = Qemu.instance()
    vm = qemu_manager.get_node(str(node_id), project_id=str(project_id))
    await vm.suspend()


@router.post("/{node_id}/resume",
             status_code=status.HTTP_204_NO_CONTENT,
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def resume_qemu_node(project_id: UUID, node_id: UUID):
    """
    Resume a Qemu node.
    """

    qemu_manager = Qemu.instance()
    vm = qemu_manager.get_node(str(node_id), project_id=str(project_id))
    await vm.resume()


@router.post("/{node_id}/adapters/{adapter_number}/ports/{port_number}/nio",
             status_code=status.HTTP_201_CREATED,
             response_model=schemas.UDPNIO,
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def create_nio(project_id: UUID, node_id: UUID, adapter_number: int, port_number: int, nio_data: schemas.UDPNIO):
    """
    Add a NIO (Network Input/Output) to the node.
    The port number on the Qemu node is always 0.
    """

    qemu_manager = Qemu.instance()
    vm = qemu_manager.get_node(str(node_id), project_id=str(project_id))
    nio = qemu_manager.create_nio(jsonable_encoder(nio_data, exclude_unset=True))
    await vm.adapter_add_nio_binding(adapter_number, nio)
    return nio.__json__()


@router.put("/{node_id}/adapters/{adapter_number}/ports/{port_number}/nio",
            status_code=status.HTTP_201_CREATED,
            response_model=schemas.UDPNIO,
            responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def update_nio(project_id: UUID, node_id: UUID, adapter_number: int, port_number: int, nio_data: schemas.UDPNIO):
    """
    Update a NIO (Network Input/Output) on the node.
    The port number on the Qemu node is always 0.
    """

    qemu_manager = Qemu.instance()
    vm = qemu_manager.get_node(str(node_id), project_id=str(project_id))
    nio = vm.get_nio(adapter_number)
    if nio_data.filters:
        nio.filters = nio_data.filters
    if nio_data.suspend:
        nio.suspend = nio_data.suspend
    await vm.adapter_update_nio_binding(adapter_number, nio)
    return nio.__json__()


@router.delete("/{node_id}/adapters/{adapter_number}/ports/{port_number}/nio",
               status_code=status.HTTP_204_NO_CONTENT,
               responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def delete_nio(project_id: UUID, node_id: UUID, adapter_number: int, port_number: int):
    """
    Delete a NIO (Network Input/Output) from the node.
    The port number on the Qemu node is always 0.
    """

    qemu_manager = Qemu.instance()
    vm = qemu_manager.get_node(str(node_id), project_id=str(project_id))
    await vm.adapter_remove_nio_binding(adapter_number)


@router.post("/{node_id}/adapters/{adapter_number}/ports/{port_number}/start_capture",
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def start_capture(project_id: UUID, node_id: UUID, adapter_number: int, port_number: int, node_capture_data: schemas.NodeCapture):
    """
    Start a packet capture on the node.
    The port number on the Qemu node is always 0.
    """

    qemu_manager = Qemu.instance()
    vm = qemu_manager.get_node(str(node_id), project_id=str(project_id))
    pcap_file_path = os.path.join(vm.project.capture_working_directory(), node_capture_data.capture_file_name)
    await vm.start_capture(adapter_number, pcap_file_path)
    return {"pcap_file_path": str(pcap_file_path)}


@router.post("/{node_id}/adapters/{adapter_number}/ports/{port_number}/stop_capture",
             status_code=status.HTTP_204_NO_CONTENT,
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def stop_capture(project_id: UUID, node_id: UUID, adapter_number: int, port_number: int):
    """
    Stop a packet capture on the node.
    The port number on the Qemu node is always 0.
    """

    qemu_manager = Qemu.instance()
    vm = qemu_manager.get_node(str(node_id), project_id=str(project_id))
    await vm.stop_capture(adapter_number)


@router.post("/{node_id}/console/reset",
             status_code=status.HTTP_204_NO_CONTENT,
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def reset_console(project_id: UUID, node_id: UUID):

    qemu_manager = Qemu.instance()
    vm = qemu_manager.get_node(str(node_id), project_id=str(project_id))
    await vm.reset_console()


@router.get("/{node_id}/adapters/{adapter_number}/ports/{port_number}/pcap",
            responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def stream_pcap_file(project_id: UUID, node_id: UUID, adapter_number: int, port_number: int):
    """
    Stream the pcap capture file.
    The port number on the Qemu node is always 0.
    """

    qemu_manager = Qemu.instance()
    vm = qemu_manager.get_node(str(node_id), project_id=str(project_id))
    nio = vm.get_nio(adapter_number)
    stream = qemu_manager.stream_pcap_file(nio, vm.project.id)
    return StreamingResponse(stream, media_type="application/vnd.tcpdump.pcap")


# @Route.get(
#     r"/projects/{project_id}/qemu/nodes/{node_id}/console/ws",
#     description="WebSocket for console",
#     parameters={
#         "project_id": "Project UUID",
#         "node_id": "Node UUID",
#     })
# async def console_ws(request, response):
#
#     qemu_manager = Qemu.instance()
#     vm = qemu_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
#     return await vm.start_websocket_console(request)

