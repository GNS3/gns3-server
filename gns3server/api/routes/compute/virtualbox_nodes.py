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
API routes for VirtualBox nodes.
"""

import os

from fastapi import APIRouter, WebSocket, Depends, Path, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from uuid import UUID
from typing import Union

from gns3server import schemas
from gns3server.compute.virtualbox import VirtualBox
from gns3server.compute.virtualbox.virtualbox_error import VirtualBoxError
from gns3server.compute.virtualbox.virtualbox_vm import VirtualBoxVM

from .dependencies.authentication import compute_authentication, ws_compute_authentication

responses = {404: {"model": schemas.ErrorMessage, "description": "Could not find project or VirtualBox node"}}

router = APIRouter(responses=responses, deprecated=True)


def dep_node(project_id: UUID, node_id: UUID) -> VirtualBoxVM:
    """
    Dependency to retrieve a node.
    """

    vbox_manager = VirtualBox.instance()
    node = vbox_manager.get_node(str(node_id), project_id=str(project_id))
    return node


@router.post(
    "",
    response_model=schemas.VirtualBox,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": schemas.ErrorMessage, "description": "Could not create VirtualBox node"}},
    dependencies=[Depends(compute_authentication)]
)
async def create_virtualbox_node(project_id: UUID, node_data: schemas.VirtualBoxCreate) -> schemas.VirtualBox:
    """
    Create a new VirtualBox node.
    """

    vbox_manager = VirtualBox.instance()
    node_data = jsonable_encoder(node_data, exclude_unset=True)
    vm = await vbox_manager.create_node(
        node_data.pop("name"),
        str(project_id),
        node_data.get("node_id"),
        node_data.pop("vmname"),
        linked_clone=node_data.pop("linked_clone", False),
        console=node_data.get("console", None),
        console_type=node_data.get("console_type", "telnet"),
        adapters=node_data.get("adapters", 0),
    )

    if "ram" in node_data:
        ram = node_data.pop("ram")
        if ram != vm.ram:
            await vm.set_ram(ram)

    for name, value in node_data.items():
        if name != "node_id":
            if hasattr(vm, name) and getattr(vm, name) != value:
                setattr(vm, name, value)

    return vm.asdict()


@router.get(
    "/{node_id}",
    response_model=schemas.VirtualBox,
    dependencies=[Depends(compute_authentication)]
)
def get_virtualbox_node(node: VirtualBoxVM = Depends(dep_node)) -> schemas.VirtualBox:
    """
    Return a VirtualBox node.
    """

    return node.asdict()


@router.put(
    "/{node_id}",
    response_model=schemas.VirtualBox,
    dependencies=[Depends(compute_authentication)]
)
async def update_virtualbox_node(
        node_data: schemas.VirtualBoxUpdate,
        node: VirtualBoxVM = Depends(dep_node)
) -> schemas.VirtualBox:
    """
    Update a VirtualBox node.
    """

    node_data = jsonable_encoder(node_data, exclude_unset=True)
    if "name" in node_data:
        name = node_data.pop("name")
        vmname = node_data.pop("vmname", None)
        if name != node.name:
            oldname = node.name
            node.name = name
            if node.linked_clone:
                try:
                    await node.set_vmname(node.name)
                except VirtualBoxError as e:  # In case of error we rollback (we can't change the name when running)
                    node.name = oldname
                    node.updated()
                    raise e

    if "adapters" in node_data:
        adapters = node_data.pop("adapters")
        if adapters != node.adapters:
            await node.set_adapters(adapters)

    if "ram" in node_data:
        ram = node_data.pop("ram")
        if ram != node.ram:
            await node.set_ram(ram)

    # update the console first to avoid issue if updating console type
    node.console = node_data.pop("console", node.console)

    for name, value in node_data.items():
        if hasattr(node, name) and getattr(node, name) != value:
            setattr(node, name, value)

    node.updated()
    return node.asdict()


@router.delete(
    "/{node_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(compute_authentication)]
)
async def delete_virtualbox_node(node: VirtualBoxVM = Depends(dep_node)) -> None:
    """
    Delete a VirtualBox node.
    """

    await VirtualBox.instance().delete_node(node.id)


@router.post(
    "/{node_id}/start",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(compute_authentication)]
)
async def start_virtualbox_node(node: VirtualBoxVM = Depends(dep_node)) -> None:
    """
    Start a VirtualBox node.
    """

    await node.start()


@router.post(
    "/{node_id}/stop",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(compute_authentication)]
)
async def stop_virtualbox_node(node: VirtualBoxVM = Depends(dep_node)) -> None:
    """
    Stop a VirtualBox node.
    """

    await node.stop()


@router.post(
    "/{node_id}/suspend",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(compute_authentication)]
)
async def suspend_virtualbox_node(node: VirtualBoxVM = Depends(dep_node)) -> None:
    """
    Suspend a VirtualBox node.
    """

    await node.suspend()


@router.post(
    "/{node_id}/resume",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(compute_authentication)]
)
async def resume_virtualbox_node(node: VirtualBoxVM = Depends(dep_node)) -> None:
    """
    Resume a VirtualBox node.
    """

    await node.resume()


@router.post(
    "/{node_id}/reload",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(compute_authentication)]
)
async def reload_virtualbox_node(node: VirtualBoxVM = Depends(dep_node)) -> None:
    """
    Reload a VirtualBox node.
    """

    await node.reload()


@router.post(
    "/{node_id}/adapters/{adapter_number}/ports/{port_number}/nio",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.UDPNIO,
    dependencies=[Depends(compute_authentication)]
)
async def create_virtualbox_node_nio(
        *,
        adapter_number: int,
        port_number: int = Path(..., ge=0, le=0),
        nio_data: schemas.UDPNIO,
        node: VirtualBoxVM = Depends(dep_node)
) -> schemas.UDPNIO:
    """
    Add a NIO (Network Input/Output) to the node.
    The port number on the VirtualBox node is always 0.
    """

    nio = VirtualBox.instance().create_nio(jsonable_encoder(nio_data, exclude_unset=True))
    await node.adapter_add_nio_binding(adapter_number, nio)
    return nio.asdict()


@router.put(
    "/{node_id}/adapters/{adapter_number}/ports/{port_number}/nio",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.UDPNIO,
    dependencies=[Depends(compute_authentication)]
)
async def update_virtualbox_node_nio(
        *,
        adapter_number: int,
        port_number: int = Path(..., ge=0, le=0),
        nio_data: schemas.UDPNIO,
        node: VirtualBoxVM = Depends(dep_node)
) -> schemas.UDPNIO:
    """
    Update a NIO (Network Input/Output) on the node.
    The port number on the VirtualBox node is always 0.
    """

    nio = node.get_nio(adapter_number)
    if nio_data.filters:
        nio.filters = nio_data.filters
    if nio_data.suspend:
        nio.suspend = nio_data.suspend
    await node.adapter_update_nio_binding(adapter_number, nio)
    return nio.asdict()


@router.delete(
    "/{node_id}/adapters/{adapter_number}/ports/{port_number}/nio",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(compute_authentication)]
)
async def delete_virtualbox_node_nio(
        adapter_number: int,
        port_number: int = Path(..., ge=0, le=0),
        node: VirtualBoxVM = Depends(dep_node)
) -> None:
    """
    Delete a NIO (Network Input/Output) from the node.
    The port number on the VirtualBox node is always 0.
    """

    await node.adapter_remove_nio_binding(adapter_number)


@router.post(
    "/{node_id}/adapters/{adapter_number}/ports/{port_number}/capture/start",
    dependencies=[Depends(compute_authentication)]
)
async def start_virtualbox_node_capture(
        *,
        adapter_number: int,
        port_number: int = Path(..., ge=0, le=0),
        node_capture_data: schemas.NodeCapture,
        node: VirtualBoxVM = Depends(dep_node),
) -> dict:
    """
    Start a packet capture on the node.
    The port number on the VirtualBox node is always 0.
    """

    pcap_file_path = os.path.join(node.project.capture_working_directory(), node_capture_data.capture_file_name)
    await node.start_capture(adapter_number, pcap_file_path)
    return {"pcap_file_path": str(pcap_file_path)}


@router.post(
    "/{node_id}/adapters/{adapter_number}/ports/{port_number}/capture/stop",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(compute_authentication)]
)
async def stop_virtualbox_node_capture(
        adapter_number: int,
        port_number: int = Path(..., ge=0, le=0),
        node: VirtualBoxVM = Depends(dep_node)
) -> None:
    """
    Stop a packet capture on the node.
    The port number on the VirtualBox node is always 0.
    """

    await node.stop_capture(adapter_number)


@router.get(
    "/{node_id}/adapters/{adapter_number}/ports/{port_number}/capture/stream",
    dependencies=[Depends(compute_authentication)]
)
async def stream_pcap_file(
        adapter_number: int,
        port_number: int = Path(..., ge=0, le=0),
        node: VirtualBoxVM = Depends(dep_node)
) -> StreamingResponse:
    """
    Stream the pcap capture file.
    The port number on the VirtualBox node is always 0.
    """

    nio = node.get_nio(adapter_number)
    stream = VirtualBox.instance().stream_pcap_file(nio, node.project.id)
    return StreamingResponse(stream, media_type="application/vnd.tcpdump.pcap")


@router.websocket(
    "/{node_id}/console/ws"
)
async def console_ws(
        websocket: Union[None, WebSocket] = Depends(ws_compute_authentication),
        node: VirtualBoxVM = Depends(dep_node)
) -> None:
    """
    Console WebSocket.
    """

    await node.start_websocket_console(websocket)


@router.post(
    "/{node_id}/console/reset",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(compute_authentication)]
)
async def reset_console(node: VirtualBoxVM = Depends(dep_node)) -> None:

    await node.reset_console()

