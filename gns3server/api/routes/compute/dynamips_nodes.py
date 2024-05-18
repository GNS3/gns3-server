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
API routes for Dynamips nodes.
"""

import os

from fastapi import APIRouter, WebSocket, Body, Depends, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from typing import List, Union
from uuid import UUID

from gns3server.compute.dynamips import Dynamips
from gns3server.compute.dynamips.nodes.router import Router
from gns3server import schemas

from .dependencies.authentication import compute_authentication, ws_compute_authentication

responses = {404: {"model": schemas.ErrorMessage, "description": "Could not find project or Dynamips node"}}

router = APIRouter(responses=responses)


DEFAULT_CHASSIS = {"c1700": "1720", "c2600": "2610", "c3600": "3640"}


def dep_node(project_id: UUID, node_id: UUID) -> Router:
    """
    Dependency to retrieve a node.
    """

    dynamips_manager = Dynamips.instance()
    node = dynamips_manager.get_node(str(node_id), project_id=str(project_id))
    return node


@router.post(
    "",
    response_model=schemas.Dynamips,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": schemas.ErrorMessage, "description": "Could not create Dynamips node"}},
    dependencies=[Depends(compute_authentication)]
)
async def create_router(project_id: UUID, node_data: schemas.DynamipsCreate) -> schemas.Dynamips:
    """
    Create a new Dynamips router.
    """

    dynamips_manager = Dynamips.instance()
    platform = node_data.platform
    print(node_data.chassis, platform in DEFAULT_CHASSIS)
    if not node_data.chassis and platform in DEFAULT_CHASSIS:
        chassis = DEFAULT_CHASSIS[platform]
    else:
        chassis = node_data.chassis
    node_data = jsonable_encoder(node_data, exclude_unset=True)
    vm = await dynamips_manager.create_node(
        node_data.pop("name"),
        str(project_id),
        node_data.get("node_id"),
        dynamips_id=node_data.get("dynamips_id"),
        platform=platform,
        console=node_data.get("console"),
        console_type=node_data.get("console_type", "telnet"),
        aux=node_data.get("aux"),
        aux_type=node_data.pop("aux_type", "none"),
        chassis=chassis,
        node_type="dynamips",
    )
    await dynamips_manager.update_vm_settings(vm, node_data)
    return vm.asdict()


@router.get(
    "/{node_id}",
    response_model=schemas.Dynamips,
    dependencies=[Depends(compute_authentication)]
)
def get_router(node: Router = Depends(dep_node)) -> schemas.Dynamips:
    """
    Return Dynamips router.
    """

    return node.asdict()


@router.put(
    "/{node_id}",
    response_model=schemas.Dynamips,
    dependencies=[Depends(compute_authentication)]
)
async def update_router(node_data: schemas.DynamipsUpdate, node: Router = Depends(dep_node)) -> schemas.Dynamips:
    """
    Update a Dynamips router.
    """

    await Dynamips.instance().update_vm_settings(node, jsonable_encoder(node_data, exclude_unset=True))
    node.updated()
    return node.asdict()


@router.delete(
    "/{node_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(compute_authentication)]
)
async def delete_router(node: Router = Depends(dep_node)) -> None:
    """
    Delete a Dynamips router.
    """

    await Dynamips.instance().delete_node(node.id)


@router.post(
    "/{node_id}/start",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(compute_authentication)]
)
async def start_router(node: Router = Depends(dep_node)) -> None:
    """
    Start a Dynamips router.
    """

    try:
        await Dynamips.instance().ghost_ios_support(node)
    except GeneratorExit:
        pass
    await node.start()


@router.post(
    "/{node_id}/stop",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(compute_authentication)]
)
async def stop_router(node: Router = Depends(dep_node)) -> None:
    """
    Stop a Dynamips router.
    """

    await node.stop()


@router.post(
    "/{node_id}/suspend",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(compute_authentication)]
)
async def suspend_router(node: Router = Depends(dep_node)) -> None:

    await node.suspend()


@router.post(
    "/{node_id}/resume",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(compute_authentication)]
)
async def resume_router(node: Router = Depends(dep_node)) -> None:
    """
    Resume a suspended Dynamips router.
    """

    await node.resume()


@router.post(
    "/{node_id}/reload",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(compute_authentication)]
)
async def reload_router(node: Router = Depends(dep_node)) -> None:
    """
    Reload a suspended Dynamips router.
    """

    await node.reload()


@router.post(
    "/{node_id}/adapters/{adapter_number}/ports/{port_number}/nio",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.UDPNIO,
    dependencies=[Depends(compute_authentication)]
)
async def create_nio(
        adapter_number: int,
        port_number: int,
        nio_data: schemas.UDPNIO,
        node: Router = Depends(dep_node)
) -> schemas.UDPNIO:
    """
    Add a NIO (Network Input/Output) to the node.
    """

    nio = await Dynamips.instance().create_nio(node, jsonable_encoder(nio_data, exclude_unset=True))
    await node.slot_add_nio_binding(adapter_number, port_number, nio)
    return nio.asdict()


@router.put(
    "/{node_id}/adapters/{adapter_number}/ports/{port_number}/nio",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.UDPNIO,
    dependencies=[Depends(compute_authentication)]
)
async def update_nio(
        adapter_number: int,
        port_number: int,
        nio_data: schemas.UDPNIO,
        node: Router = Depends(dep_node)
) -> schemas.UDPNIO:
    """
    Update a NIO (Network Input/Output) on the node.
    """

    nio = node.get_nio(adapter_number, port_number)
    if nio_data.filters:
        nio.filters = nio_data.filters
    await node.slot_update_nio_binding(adapter_number, port_number, nio)
    return nio.asdict()


@router.delete(
    "/{node_id}/adapters/{adapter_number}/ports/{port_number}/nio",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(compute_authentication)]
)
async def delete_nio(adapter_number: int, port_number: int, node: Router = Depends(dep_node)) -> None:
    """
    Delete a NIO (Network Input/Output) from the node.
    """

    nio = await node.slot_remove_nio_binding(adapter_number, port_number)
    await nio.delete()


@router.post(
    "/{node_id}/adapters/{adapter_number}/ports/{port_number}/capture/start",
    dependencies=[Depends(compute_authentication)]
)
async def start_capture(
        adapter_number: int,
        port_number: int,
        node_capture_data: schemas.NodeCapture,
        node: Router = Depends(dep_node)
) -> dict:
    """
    Start a packet capture on the node.
    """

    pcap_file_path = os.path.join(node.project.capture_working_directory(), node_capture_data.capture_file_name)
    await node.start_capture(adapter_number, port_number, pcap_file_path, node_capture_data.data_link_type)
    return {"pcap_file_path": pcap_file_path}


@router.post(
    "/{node_id}/adapters/{adapter_number}/ports/{port_number}/capture/stop",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(compute_authentication)]
)
async def stop_capture(adapter_number: int, port_number: int, node: Router = Depends(dep_node)) -> None:
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
        node: Router = Depends(dep_node)
) -> StreamingResponse:
    """
    Stream the pcap capture file.
    """

    nio = node.get_nio(adapter_number, port_number)
    stream = Dynamips.instance().stream_pcap_file(nio, node.project.id)
    return StreamingResponse(stream, media_type="application/vnd.tcpdump.pcap")


@router.get(
    "/{node_id}/idlepc_proposals",
    dependencies=[Depends(compute_authentication)]
)
async def get_idlepcs(node: Router = Depends(dep_node)) -> List[str]:
    """
    Retrieve Dynamips idle-pc proposals
    """

    await node.set_idlepc("0x0")
    return await node.get_idle_pc_prop()


@router.get(
    "/{node_id}/auto_idlepc",
    dependencies=[Depends(compute_authentication)]
)
async def get_auto_idlepc(node: Router = Depends(dep_node)) -> dict:
    """
    Get an automatically guessed best idle-pc value.
    """

    idlepc = await Dynamips.instance().auto_idlepc(node)
    return {"idlepc": idlepc}


@router.post(
    "/{node_id}/duplicate",
    response_model=schemas.Dynamips,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(compute_authentication)]
)
async def duplicate_router(destination_node_id: UUID = Body(..., embed=True), node: Router = Depends(dep_node)) -> schemas.Dynamips:
    """
    Duplicate a router.
    """

    new_node = await Dynamips.instance().duplicate_node(node.id, str(destination_node_id))
    return new_node.asdict()


@router.websocket("/{node_id}/console/ws")
async def console_ws(
        websocket: Union[None, WebSocket] = Depends(ws_compute_authentication),
        node: Router = Depends(dep_node)

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
async def reset_console(node: Router = Depends(dep_node)) -> None:

    await node.reset_console()
