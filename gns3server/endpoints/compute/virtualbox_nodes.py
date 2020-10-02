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
API endpoints for VirtualBox nodes.
"""

import os

from fastapi import APIRouter, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from uuid import UUID

from gns3server.endpoints import schemas
from gns3server.compute.virtualbox import VirtualBox
from gns3server.compute.virtualbox.virtualbox_error import VirtualBoxError
from gns3server.compute.project_manager import ProjectManager

router = APIRouter()


@router.post("/",
             response_model=schemas.VirtualBox,
             status_code=status.HTTP_201_CREATED,
             responses={409: {"model": schemas.ErrorMessage, "description": "Could not create VirtualBox node"}})
async def create_virtualbox_node(project_id: UUID, node_data: schemas.VirtualBoxCreate):
    """
    Create a new VirtualBox node.
    """

    vbox_manager = VirtualBox.instance()
    node_data = jsonable_encoder(node_data, exclude_unset=True)
    vm = await vbox_manager.create_node(node_data.pop("name"),
                                        str(project_id),
                                        node_data.get("node_id"),
                                        node_data.pop("vmname"),
                                        linked_clone=node_data.pop("linked_clone", False),
                                        console=node_data.get("console", None),
                                        console_type=node_data.get("console_type", "telnet"),
                                        adapters=node_data.get("adapters", 0))

    if "ram" in node_data:
        ram = node_data.pop("ram")
        if ram != vm.ram:
            await vm.set_ram(ram)

    for name, value in node_data.items():
        if name != "node_id":
            if hasattr(vm, name) and getattr(vm, name) != value:
                setattr(vm, name, value)

    return vm.__json__()


@router.get("/{node_id}",
            response_model=schemas.VirtualBox,
            responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
def get_virtualbox_node(project_id: UUID, node_id: UUID):
    """
    Return a VirtualBox node.
    """

    vbox_manager = VirtualBox.instance()
    vm = vbox_manager.get_node(str(node_id), project_id=str(project_id))
    return vm.__json__()


@router.put("/{node_id}",
            response_model=schemas.VirtualBox,
            responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def update_virtualbox_node(project_id: UUID, node_id: UUID, node_data: schemas.VirtualBoxUpdate):
    """
    Update a VirtualBox node.
    """

    vbox_manager = VirtualBox.instance()
    vm = vbox_manager.get_node(str(node_id), project_id=str(project_id))
    node_data = jsonable_encoder(node_data, exclude_unset=True)

    if "name" in node_data:
        name = node_data.pop("name")
        vmname = node_data.pop("vmname", None)
        if name != vm.name:
            oldname = vm.name
            vm.name = name
            if vm.linked_clone:
                try:
                    await vm.set_vmname(vm.name)
                except VirtualBoxError as e:  # In case of error we rollback (we can't change the name when running)
                    vm.name = oldname
                    vm.updated()
                    raise e

    if "adapters" in node_data:
        adapters = node_data.pop("adapters")
        if adapters != vm.adapters:
            await vm.set_adapters(adapters)

    if "ram" in node_data:
        ram = node_data.pop("ram")
        if ram != vm.ram:
            await vm.set_ram(ram)

    # update the console first to avoid issue if updating console type
    vm.console = node_data.pop("console", vm.console)

    for name, value in node_data.items():
        if hasattr(vm, name) and getattr(vm, name) != value:
            setattr(vm, name, value)

    vm.updated()
    return vm.__json__()


@router.delete("/{node_id}",
               status_code=status.HTTP_204_NO_CONTENT,
               responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def delete_virtualbox_node(project_id: UUID, node_id: UUID):
    """
    Delete a VirtualBox node.
    """

    # check the project_id exists
    ProjectManager.instance().get_project(str(project_id))
    await VirtualBox.instance().delete_node(str(node_id))


@router.post("/{node_id}/start",
             status_code=status.HTTP_204_NO_CONTENT,
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def start_virtualbox_node(project_id: UUID, node_id: UUID):
    """
    Start a VirtualBox node.
    """

    vbox_manager = VirtualBox.instance()
    vm = vbox_manager.get_node(str(node_id), project_id=str(project_id))
    if await vm.check_hw_virtualization():
        pm = ProjectManager.instance()
        if pm.check_hardware_virtualization(vm) is False:
            pass # FIXME: check this
            #raise ComputeError("Cannot start VM with hardware acceleration (KVM/HAX) enabled because hardware virtualization (VT-x/AMD-V) is already used by another software like VMware or VirtualBox")
    await vm.start()


@router.post("/{node_id}/stop",
             status_code=status.HTTP_204_NO_CONTENT,
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def stop_virtualbox_node(project_id: UUID, node_id: UUID):
    """
    Stop a VirtualBox node.
    """

    vbox_manager = VirtualBox.instance()
    vm = vbox_manager.get_node(str(node_id), project_id=str(project_id))
    await vm.stop()


@router.post("/{node_id}/suspend",
             status_code=status.HTTP_204_NO_CONTENT,
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def suspend_virtualbox_node(project_id: UUID, node_id: UUID):
    """
    Suspend a VirtualBox node.
    """

    vbox_manager = VirtualBox.instance()
    vm = vbox_manager.get_node(str(node_id), project_id=str(project_id))
    await vm.suspend()


@router.post("/{node_id}/resume",
             status_code=status.HTTP_204_NO_CONTENT,
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def resume_virtualbox_node(project_id: UUID, node_id: UUID):
    """
    Resume a VirtualBox node.
    """

    vbox_manager = VirtualBox.instance()
    vm = vbox_manager.get_node(str(node_id), project_id=str(project_id))
    await vm.resume()


@router.post("/{node_id}/reload",
             status_code=status.HTTP_204_NO_CONTENT,
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def reload_virtualbox_node(project_id: UUID, node_id: UUID):
    """
    Reload a VirtualBox node.
    """

    vbox_manager = VirtualBox.instance()
    vm = vbox_manager.get_node(str(node_id), project_id=str(project_id))
    await vm.reload()


@router.post("/{node_id}/adapters/{adapter_number}/ports/{port_number}/nio",
             status_code=status.HTTP_201_CREATED,
             response_model=schemas.UDPNIO,
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def create_nio(project_id: UUID, node_id: UUID, adapter_number: int, port_number: int, nio_data: schemas.UDPNIO):
    """
    Add a NIO (Network Input/Output) to the node.
    The port number on the VirtualBox node is always 0.
    """

    vbox_manager = VirtualBox.instance()
    vm = vbox_manager.get_node(str(node_id), project_id=str(project_id))
    nio = vbox_manager.create_nio(jsonable_encoder(nio_data, exclude_unset=True))
    await vm.adapter_add_nio_binding(adapter_number, nio)
    return nio.__json__()


@router.put("/{node_id}/adapters/{adapter_number}/ports/{port_number}/nio",
            status_code=status.HTTP_201_CREATED,
            response_model=schemas.UDPNIO,
            responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def update_nio(project_id: UUID, node_id: UUID, adapter_number: int, port_number: int, nio_data: schemas.UDPNIO):
    """
    Update a NIO (Network Input/Output) on the node.
    The port number on the VirtualBox node is always 0.
    """

    virtualbox_manager = VirtualBox.instance()
    vm = virtualbox_manager.get_node(str(node_id), project_id=str(project_id))
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
    The port number on the VirtualBox node is always 0.
    """

    vbox_manager = VirtualBox.instance()
    vm = vbox_manager.get_node(str(node_id), project_id=str(project_id))
    await vm.adapter_remove_nio_binding(adapter_number)


@router.post("/{node_id}/adapters/{adapter_number}/ports/{port_number}/start_capture",
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def start_capture(project_id: UUID, node_id: UUID, adapter_number: int, port_number: int, node_capture_data: schemas.NodeCapture):
    """
    Start a packet capture on the node.
    The port number on the VirtualBox node is always 0.
    """

    vbox_manager = VirtualBox.instance()
    vm = vbox_manager.get_node(str(node_id), project_id=str(project_id))
    pcap_file_path = os.path.join(vm.project.capture_working_directory(), node_capture_data.capture_file_name)
    await vm.start_capture(adapter_number, pcap_file_path)
    return {"pcap_file_path": str(pcap_file_path)}


@router.post("/{node_id}/adapters/{adapter_number}/ports/{port_number}/stop_capture",
             status_code=status.HTTP_204_NO_CONTENT,
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def stop_capture(project_id: UUID, node_id: UUID, adapter_number: int, port_number: int):
    """
    Stop a packet capture on the node.
    The port number on the VirtualBox node is always 0.
    """

    vbox_manager = VirtualBox.instance()
    vm = vbox_manager.get_node(str(node_id), project_id=str(project_id))
    await vm.stop_capture(adapter_number)


@router.post("/{node_id}/console/reset",
             status_code=status.HTTP_204_NO_CONTENT,
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def reset_console(project_id: UUID, node_id: UUID):

    virtualbox_manager = VirtualBox.instance()
    vm = virtualbox_manager.get_node(str(node_id), project_id=str(project_id))
    await vm.reset_console()


@router.get("/{node_id}/adapters/{adapter_number}/ports/{port_number}/pcap",
            responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or node"}})
async def stream_pcap_file(project_id: UUID, node_id: UUID, adapter_number: int, port_number: int):
    """
    Stream the pcap capture file.
    The port number on the VirtualBox node is always 0.
    """

    virtualbox_manager = VirtualBox.instance()
    vm = virtualbox_manager.get_node(str(node_id), project_id=str(project_id))
    nio = vm.get_nio(adapter_number)
    stream = virtualbox_manager.stream_pcap_file(nio, vm.project.id)
    return StreamingResponse(stream, media_type="application/vnd.tcpdump.pcap")


# @Route.get(
#     r"/projects/{project_id}/virtualbox/nodes/{node_id}/console/ws",
#     description="WebSocket for console",
#     parameters={
#         "project_id": "Project UUID",
#         "node_id": "Node UUID",
#     })
# async def console_ws(request, response):
#
#     virtualbox_manager = VirtualBox.instance()
#     vm = virtualbox_manager.get_node(request.match_info["node_id"], project_id=request.match_info["project_id"])
#     return await vm.start_websocket_console(request)
