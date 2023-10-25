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
API routes for Docker nodes.
"""

import os

from fastapi import APIRouter, WebSocket, Depends, Body, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from uuid import UUID
from typing import Union

from gns3server import schemas
from gns3server.compute.docker import Docker
from gns3server.compute.docker.docker_vm import DockerVM

from .dependencies.authentication import compute_authentication, ws_compute_authentication

responses = {404: {"model": schemas.ErrorMessage, "description": "Could not find project or Docker node"}}

router = APIRouter(responses=responses)


def dep_node(project_id: UUID, node_id: UUID) -> DockerVM:
    """
    Dependency to retrieve a node.
    """

    docker_manager = Docker.instance()
    node = docker_manager.get_node(str(node_id), project_id=str(project_id))
    return node


@router.post(
    "",
    response_model=schemas.Docker,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": schemas.ErrorMessage, "description": "Could not create Docker node"}},
    dependencies=[Depends(compute_authentication)]
)
async def create_docker_node(project_id: UUID, node_data: schemas.DockerCreate) -> schemas.Docker:
    """
    Create a new Docker node.
    """

    docker_manager = Docker.instance()
    node_data = jsonable_encoder(node_data, exclude_unset=True)
    container = await docker_manager.create_node(
        node_data.pop("name"),
        str(project_id),
        node_data.get("node_id"),
        image=node_data.pop("image"),
        start_command=node_data.get("start_command"),
        environment=node_data.get("environment"),
        adapters=node_data.get("adapters"),
        console=node_data.get("console"),
        console_type=node_data.get("console_type"),
        console_resolution=node_data.get("console_resolution", "1024x768"),
        console_http_port=node_data.get("console_http_port", 80),
        console_http_path=node_data.get("console_http_path", "/"),
        aux=node_data.get("aux"),
        aux_type=node_data.pop("aux_type", "none"),
        extra_hosts=node_data.get("extra_hosts"),
        extra_volumes=node_data.get("extra_volumes"),
        memory=node_data.get("memory", 0),
        cpus=node_data.get("cpus", 0),
    )
    for name, value in node_data.items():
        if name != "node_id":
            if hasattr(container, name) and getattr(container, name) != value:
                setattr(container, name, value)

    return container.asdict()


@router.get(
    "/{node_id}",
    response_model=schemas.Docker,
    dependencies=[Depends(compute_authentication)]
)
def get_docker_node(node: DockerVM = Depends(dep_node)) -> schemas.Docker:
    """
    Return a Docker node.
    """

    return node.asdict()


@router.put(
    "/{node_id}",
    response_model=schemas.Docker,
    dependencies=[Depends(compute_authentication)]
)
async def update_docker_node(node_data: schemas.DockerUpdate, node: DockerVM = Depends(dep_node)) -> schemas.Docker:
    """
    Update a Docker node.
    """

    props = [
        "name",
        "console",
        "console_type",
        "aux",
        "aux_type",
        "console_resolution",
        "console_http_port",
        "console_http_path",
        "start_command",
        "environment",
        "adapters",
        "extra_hosts",
        "extra_volumes",
        "memory",
        "cpus",
    ]

    changed = False
    node_data = jsonable_encoder(node_data, exclude_unset=True)
    for prop in props:
        if prop in node_data and node_data[prop] != getattr(node, prop):
            setattr(node, prop, node_data[prop])
            changed = True
    # We don't call container.update for nothing because it will restart the container
    if changed:
        await node.update()
    node.updated()
    return node.asdict()


@router.post(
    "/{node_id}/start",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(compute_authentication)]
)
async def start_docker_node(node: DockerVM = Depends(dep_node)) -> None:
    """
    Start a Docker node.
    """

    await node.start()


@router.post(
    "/{node_id}/stop",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(compute_authentication)]
)
async def stop_docker_node(node: DockerVM = Depends(dep_node)) -> None:
    """
    Stop a Docker node.
    """

    await node.stop()


@router.post(
    "/{node_id}/suspend",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(compute_authentication)]
)
async def suspend_docker_node(node: DockerVM = Depends(dep_node)) -> None:
    """
    Suspend a Docker node.
    """

    await node.pause()


@router.post(
    "/{node_id}/reload",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(compute_authentication)]
)
async def reload_docker_node(node: DockerVM = Depends(dep_node)) -> None:
    """
    Reload a Docker node.
    """

    await node.restart()


@router.post(
    "/{node_id}/pause",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(compute_authentication)]
)
async def pause_docker_node(node: DockerVM = Depends(dep_node)) -> None:
    """
    Pause a Docker node.
    """

    await node.pause()


@router.post(
    "/{node_id}/unpause",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(compute_authentication)]
)
async def unpause_docker_node(node: DockerVM = Depends(dep_node)) -> None:
    """
    Unpause a Docker node.
    """

    await node.unpause()


@router.delete(
    "/{node_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(compute_authentication)]
)
async def delete_docker_node(node: DockerVM = Depends(dep_node)) -> None:
    """
    Delete a Docker node.
    """

    await node.delete()


@router.post(
    "/{node_id}/duplicate",
    response_model=schemas.Docker,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(compute_authentication)]
)
async def duplicate_docker_node(
        destination_node_id: UUID = Body(..., embed=True),
        node: DockerVM = Depends(dep_node)
) -> schemas.Docker:
    """
    Duplicate a Docker node.
    """

    new_node = await Docker.instance().duplicate_node(node.id, str(destination_node_id))
    return new_node.asdict()


@router.post(
    "/{node_id}/adapters/{adapter_number}/ports/{port_number}/nio",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.UDPNIO,
    dependencies=[Depends(compute_authentication)]
)
async def create_docker_node_nio(
    adapter_number: int, port_number: int, nio_data: schemas.UDPNIO, node: DockerVM = Depends(dep_node)
) -> schemas.UDPNIO:
    """
    Add a NIO (Network Input/Output) to the node.
    The port number on the Docker node is always 0.
    """

    nio = Docker.instance().create_nio(jsonable_encoder(nio_data, exclude_unset=True))
    await node.adapter_add_nio_binding(adapter_number, nio)
    return nio.asdict()


@router.put(
    "/{node_id}/adapters/{adapter_number}/ports/{port_number}/nio",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.UDPNIO,
    dependencies=[Depends(compute_authentication)]
)
async def update_docker_node_nio(
    adapter_number: int, port_number: int, nio_data: schemas.UDPNIO, node: DockerVM = Depends(dep_node)
) -> schemas.UDPNIO:
    """
    Update a NIO (Network Input/Output) on the node.
    The port number on the Docker node is always 0.
    """

    nio = node.get_nio(adapter_number)
    if nio_data.filters:
        nio.filters = nio_data.filters
    await node.adapter_update_nio_binding(adapter_number, nio)
    return nio.asdict()


@router.delete(
    "/{node_id}/adapters/{adapter_number}/ports/{port_number}/nio",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(compute_authentication)]
)
async def delete_docker_node_nio(
        adapter_number: int,
        port_number: int,
        node: DockerVM = Depends(dep_node)
) -> None:
    """
    Delete a NIO (Network Input/Output) from the node.
    The port number on the Docker node is always 0.
    """

    await node.adapter_remove_nio_binding(adapter_number)


@router.post(
    "/{node_id}/adapters/{adapter_number}/ports/{port_number}/capture/start",
    dependencies=[Depends(compute_authentication)]
)
async def start_docker_node_capture(
        adapter_number: int,
        port_number: int,
        node_capture_data: schemas.NodeCapture,
        node: DockerVM = Depends(dep_node)
) -> dict:
    """
    Start a packet capture on the node.
    The port number on the Docker node is always 0.
    """

    pcap_file_path = os.path.join(node.project.capture_working_directory(), node_capture_data.capture_file_name)
    await node.start_capture(adapter_number, pcap_file_path)
    return {"pcap_file_path": str(pcap_file_path)}


@router.post(
    "/{node_id}/adapters/{adapter_number}/ports/{port_number}/capture/stop",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(compute_authentication)]
)
async def stop_docker_node_capture(
        adapter_number: int,
        port_number: int,
        node: DockerVM = Depends(dep_node)
) -> None:
    """
    Stop a packet capture on the node.
    The port number on the Docker node is always 0.
    """

    await node.stop_capture(adapter_number)


@router.get(
    "/{node_id}/adapters/{adapter_number}/ports/{port_number}/capture/stream",
    dependencies=[Depends(compute_authentication)]
)
async def stream_pcap_file(
        adapter_number: int,
        port_number: int,
        node: DockerVM = Depends(dep_node)
) -> StreamingResponse:
    """
    Stream the pcap capture file.
    The port number on the Docker node is always 0.
    """

    nio = node.get_nio(adapter_number)
    stream = Docker.instance().stream_pcap_file(nio, node.project.id)
    return StreamingResponse(stream, media_type="application/vnd.tcpdump.pcap")


@router.websocket("/{node_id}/console/ws")
async def console_ws(
        websocket: Union[None, WebSocket] = Depends(ws_compute_authentication),
        node: DockerVM = Depends(dep_node)
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
async def reset_console(node: DockerVM = Depends(dep_node)) -> None:

    await node.reset_console()
