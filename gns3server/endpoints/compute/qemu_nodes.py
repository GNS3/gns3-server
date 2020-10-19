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

from fastapi import APIRouter, WebSocket, Depends, Body, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from uuid import UUID

from gns3server.endpoints import schemas
from gns3server.compute.project_manager import ProjectManager
from gns3server.compute.qemu import Qemu
from gns3server.compute.qemu.qemu_vm import QemuVM

router = APIRouter()

responses = {
    404: {"model": schemas.ErrorMessage, "description": "Could not find project or Qemu node"}
}


def dep_node(project_id: UUID, node_id: UUID):
    """
    Dependency to retrieve a node.
    """

    qemu_manager = Qemu.instance()
    node = qemu_manager.get_node(str(node_id), project_id=str(project_id))
    return node


@router.post("",
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
            responses=responses)
def get_qemu_node(node: QemuVM = Depends(dep_node)):
    """
    Return a Qemu node.
    """

    return node.__json__()


@router.put("/{node_id}",
            response_model=schemas.Qemu,
            responses=responses)
async def update_qemu_node(node_data: schemas.QemuUpdate, node: QemuVM = Depends(dep_node)):
    """
    Update a Qemu node.
    """

    node_data = jsonable_encoder(node_data, exclude_unset=True)
    # update the console first to avoid issue if updating console type
    node.console = node_data.pop("console", node.console)
    for name, value in node_data.items():
        if hasattr(node, name) and getattr(node, name) != value:
            await node.update_property(name, value)
    node.updated()
    return node.__json__()


@router.delete("/{node_id}",
               status_code=status.HTTP_204_NO_CONTENT,
               responses=responses)
async def delete_qemu_node(node: QemuVM = Depends(dep_node)):
    """
    Delete a Qemu node.
    """

    await Qemu.instance().delete_node(node.id)


@router.post("/{node_id}/duplicate",
             response_model=schemas.Qemu,
             status_code=status.HTTP_201_CREATED,
             responses=responses)
async def duplicate_qemu_node(destination_node_id: UUID = Body(..., embed=True), node: QemuVM = Depends(dep_node)):
    """
    Duplicate a Qemu node.
    """

    new_node = await Qemu.instance().duplicate_node(node.id, str(destination_node_id))
    return new_node.__json__()


@router.post("/{node_id}/resize_disk",
             status_code=status.HTTP_204_NO_CONTENT,
             responses=responses)
async def resize_qemu_node_disk(node_data: schemas.QemuDiskResize, node: QemuVM = Depends(dep_node)):

    await node.resize_disk(node_data.drive_name, node_data.extend)


@router.post("/{node_id}/start",
             status_code=status.HTTP_204_NO_CONTENT,
             responses=responses)
async def start_qemu_node(node: QemuVM = Depends(dep_node)):
    """
    Start a Qemu node.
    """

    qemu_manager = Qemu.instance()
    hardware_accel = qemu_manager.config.get_section_config("Qemu").getboolean("enable_hardware_acceleration", True)
    if sys.platform.startswith("linux"):
        # the enable_kvm option was used before version 2.0 and has priority
        enable_kvm = qemu_manager.config.get_section_config("Qemu").getboolean("enable_kvm")
        if enable_kvm is not None:
            hardware_accel = enable_kvm
    if hardware_accel and "-no-kvm" not in node.options and "-no-hax" not in node.options:
        pm = ProjectManager.instance()
        if pm.check_hardware_virtualization(node) is False:
            pass  #FIXME: check this
            #raise ComputeError("Cannot start VM with hardware acceleration (KVM/HAX) enabled because hardware virtualization (VT-x/AMD-V) is already used by another software like VMware or VirtualBox")
    await node.start()


@router.post("/{node_id}/stop",
             status_code=status.HTTP_204_NO_CONTENT,
             responses=responses)
async def stop_qemu_node(node: QemuVM = Depends(dep_node)):
    """
    Stop a Qemu node.
    """

    await node.stop()


@router.post("/{node_id}/reload",
             status_code=status.HTTP_204_NO_CONTENT,
             responses=responses)
async def reload_qemu_node(node: QemuVM = Depends(dep_node)):
    """
    Reload a Qemu node.
    """

    await node.reload()


@router.post("/{node_id}/suspend",
             status_code=status.HTTP_204_NO_CONTENT,
             responses=responses)
async def suspend_qemu_node(node: QemuVM = Depends(dep_node)):
    """
    Suspend a Qemu node.
    """

    await node.suspend()


@router.post("/{node_id}/resume",
             status_code=status.HTTP_204_NO_CONTENT,
             responses=responses)
async def resume_qemu_node(node: QemuVM = Depends(dep_node)):
    """
    Resume a Qemu node.
    """

    await node.resume()


@router.post("/{node_id}/adapters/{adapter_number}/ports/{port_number}/nio",
             status_code=status.HTTP_201_CREATED,
             response_model=schemas.UDPNIO,
             responses=responses)
async def create_nio(adapter_number: int, port_number: int, nio_data: schemas.UDPNIO, node: QemuVM = Depends(dep_node)):
    """
    Add a NIO (Network Input/Output) to the node.
    The port number on the Qemu node is always 0.
    """

    nio = Qemu.instance().create_nio(jsonable_encoder(nio_data, exclude_unset=True))
    await node.adapter_add_nio_binding(adapter_number, nio)
    return nio.__json__()


@router.put("/{node_id}/adapters/{adapter_number}/ports/{port_number}/nio",
            status_code=status.HTTP_201_CREATED,
            response_model=schemas.UDPNIO,
            responses=responses)
async def update_nio(adapter_number: int, port_number: int, nio_data: schemas.UDPNIO, node: QemuVM = Depends(dep_node)):
    """
    Update a NIO (Network Input/Output) on the node.
    The port number on the Qemu node is always 0.
    """

    nio = node.get_nio(adapter_number)
    if nio_data.filters:
        nio.filters = nio_data.filters
    if nio_data.suspend:
        nio.suspend = nio_data.suspend
    await node.adapter_update_nio_binding(adapter_number, nio)
    return nio.__json__()


@router.delete("/{node_id}/adapters/{adapter_number}/ports/{port_number}/nio",
               status_code=status.HTTP_204_NO_CONTENT,
               responses=responses)
async def delete_nio(adapter_number: int, port_number: int, node: QemuVM = Depends(dep_node)):
    """
    Delete a NIO (Network Input/Output) from the node.
    The port number on the Qemu node is always 0.
    """

    await node.adapter_remove_nio_binding(adapter_number)


@router.post("/{node_id}/adapters/{adapter_number}/ports/{port_number}/start_capture",
             responses=responses)
async def start_capture(adapter_number: int,
                        port_number: int,
                        node_capture_data: schemas.NodeCapture,
                        node: QemuVM = Depends(dep_node)):
    """
    Start a packet capture on the node.
    The port number on the Qemu node is always 0.
    """

    pcap_file_path = os.path.join(node.project.capture_working_directory(), node_capture_data.capture_file_name)
    await node.start_capture(adapter_number, pcap_file_path)
    return {"pcap_file_path": str(pcap_file_path)}


@router.post("/{node_id}/adapters/{adapter_number}/ports/{port_number}/stop_capture",
             status_code=status.HTTP_204_NO_CONTENT,
             responses=responses)
async def stop_capture(adapter_number: int, port_number: int, node: QemuVM = Depends(dep_node)):
    """
    Stop a packet capture on the node.
    The port number on the Qemu node is always 0.
    """

    await node.stop_capture(adapter_number)


@router.get("/{node_id}/adapters/{adapter_number}/ports/{port_number}/pcap",
            responses=responses)
async def stream_pcap_file(adapter_number: int, port_number: int, node: QemuVM = Depends(dep_node)):
    """
    Stream the pcap capture file.
    The port number on the Qemu node is always 0.
    """

    nio = node.get_nio(adapter_number)
    stream = Qemu.instance().stream_pcap_file(nio, node.project.id)
    return StreamingResponse(stream, media_type="application/vnd.tcpdump.pcap")


@router.websocket("/{node_id}/console/ws")
async def console_ws(websocket: WebSocket, node: QemuVM = Depends(dep_node)):
    """
    Console WebSocket.
    """

    await node.start_websocket_console(websocket)


@router.post("/{node_id}/console/reset",
             status_code=status.HTTP_204_NO_CONTENT,
             responses=responses)
async def reset_console(node: QemuVM = Depends(dep_node)):

    await node.reset_console()
