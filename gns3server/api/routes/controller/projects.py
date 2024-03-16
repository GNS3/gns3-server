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
API routes for projects.
"""

import os
import asyncio
import tempfile
import aiofiles
import time
import urllib.parse
import gns3server.utils.zipfile_zstd as zipfile

import logging

log = logging.getLogger()

from fastapi import APIRouter, Depends, Request, Body, HTTPException, status, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse, FileResponse
from websockets.exceptions import ConnectionClosed, WebSocketException
from typing import List, Optional
from uuid import UUID

from gns3server import schemas
from gns3server.controller import Controller
from gns3server.controller.project import Project
from gns3server.controller.controller_error import ControllerError, ControllerBadRequestError
from gns3server.controller.import_project import import_project as import_controller_project
from gns3server.controller.export_project import export_project as export_controller_project
from gns3server.utils.asyncio import aiozipstream
from gns3server.utils.path import is_safe_path
from gns3server.db.repositories.templates import TemplatesRepository
from gns3server.db.repositories.rbac import RbacRepository
from gns3server.db.repositories.pools import ResourcePoolsRepository
from gns3server.services.templates import TemplatesService

from .dependencies.rbac import has_privilege, has_privilege_on_websocket
from .dependencies.authentication import get_current_active_user
from .dependencies.database import get_repository

responses = {404: {"model": schemas.ErrorMessage, "description": "Could not find project"}}

router = APIRouter(responses=responses)


def dep_project(project_id: UUID) -> Project:
    """
    Dependency to retrieve a project.
    """

    project = Controller.instance().get_project(str(project_id))
    return project


@router.get(
    "",
    response_model=List[schemas.Project],
    response_model_exclude_unset=True
)
async def get_projects(
        current_user: schemas.User = Depends(get_current_active_user),
        rbac_repo: RbacRepository = Depends(get_repository(RbacRepository)),
        pools_repo: ResourcePoolsRepository = Depends(get_repository(ResourcePoolsRepository))
) -> List[schemas.Project]:
    """
    Return all projects.

    Required privilege: Project.Audit
    """

    controller = Controller.instance()
    projects = []

    if current_user.is_superadmin:
        # super admin sees all projects
        return [p.asdict() for p in controller.projects.values()]
    elif await rbac_repo.check_user_has_privilege(current_user.user_id, "/projects", "Project.Audit"):
        # user with Project.Audit privilege on '/projects' sees all projects except those in resource pools
        project_ids_in_pools = [str(r.resource_id) for r in await pools_repo.get_resources() if r.resource_type == "project"]
        projects.extend([p.asdict() for p in controller.projects.values() if p.id not in project_ids_in_pools])

    # user with Project.Audit privilege on resource pools sees the projects in these pools
    user_pool_resources = await rbac_repo.get_user_pool_resources(current_user.user_id, "Project.Audit")
    project_ids_in_pools = [str(r.resource_id) for r in user_pool_resources if r.resource_type == "project"]
    projects.extend([p.asdict() for p in controller.projects.values() if p.id in project_ids_in_pools])

    return projects


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.Project,
    response_model_exclude_unset=True,
    responses={409: {"model": schemas.ErrorMessage, "description": "Could not create project"}},
    dependencies=[Depends(has_privilege("Project.Allocate"))]
)
async def create_project(
        project_data: schemas.ProjectCreate,
) -> schemas.Project:
    """
    Create a new project.

    Required privilege: Project.Allocate
    """

    controller = Controller.instance()
    project = await controller.add_project(**jsonable_encoder(project_data, exclude_unset=True))
    return project.asdict()


@router.get("/{project_id}", response_model=schemas.Project, dependencies=[Depends(has_privilege("Project.Audit"))])
def get_project(project: Project = Depends(dep_project)) -> schemas.Project:
    """
    Return a project.

    Required privilege: Project.Audit
    """

    return project.asdict()


@router.put(
    "/{project_id}",
    response_model=schemas.Project,
    response_model_exclude_unset=True,
    dependencies=[Depends(has_privilege("Project.Modify"))]
)
async def update_project(
        project_data: schemas.ProjectUpdate,
        project: Project = Depends(dep_project)
) -> schemas.Project:
    """
    Update a project.

    Required privilege: Project.Modify
    """

    await project.update(**jsonable_encoder(project_data, exclude_unset=True))
    return project.asdict()


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(has_privilege("Project.Allocate"))]
)
async def delete_project(
        project: Project = Depends(dep_project),
        rbac_repo: RbacRepository = Depends(get_repository(RbacRepository)),
) -> None:
    """
    Delete a project.

    Required privilege: Project.Allocate
    """

    controller = Controller.instance()
    await project.delete()
    controller.remove_project(project)
    await rbac_repo.delete_all_ace_starting_with_path(f"/projects/{project.id}")


@router.get("/{project_id}/stats", dependencies=[Depends(has_privilege("Project.Audit"))])
def get_project_stats(project: Project = Depends(dep_project)) -> dict:
    """
    Return a project statistics.

    Required privilege: Project.Audit
    """

    return project.stats()


@router.post(
    "/{project_id}/close",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={**responses, 409: {"model": schemas.ErrorMessage, "description": "Could not close project"}},
    dependencies=[Depends(has_privilege("Project.Allocate"))]
)
async def close_project(project: Project = Depends(dep_project)) -> None:
    """
    Close a project.

    Required privilege: Project.Allocate
    """

    await project.close()


@router.post(
    "/{project_id}/open",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.Project,
    responses={**responses, 409: {"model": schemas.ErrorMessage, "description": "Could not open project"}},
    dependencies=[Depends(has_privilege("Project.Allocate"))]
)
async def open_project(project: Project = Depends(dep_project)) -> schemas.Project:
    """
    Open a project.

    Required privilege: Project.Allocate
    """

    await project.open()
    return project.asdict()


@router.post(
    "/load",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.Project,
    responses={**responses, 409: {"model": schemas.ErrorMessage, "description": "Could not load project"}},
    dependencies=[Depends(has_privilege("Project.Allocate"))]
)
async def load_project(path: str = Body(..., embed=True)) -> schemas.Project:
    """
    Load a project (local server only).

    Required privilege: Project.Allocate
    """

    controller = Controller.instance()
    dot_gns3_file = path
    project = await controller.load_project(dot_gns3_file)
    return project.asdict()


@router.get("/{project_id}/notifications", dependencies=[Depends(has_privilege("Project.Audit"))])
async def project_http_notifications(project_id: UUID) -> StreamingResponse:
    """
    Receive project notifications about the controller from HTTP stream.

    Required privilege: Project.Audit
    """

    from gns3server.api.server import app
    controller = Controller.instance()
    project = controller.get_project(str(project_id))

    log.info(f"New client has connected to the notification stream for project ID '{project.id}' (HTTP stream method)")

    async def event_stream():

        try:
            with controller.notification.project_queue(project.id) as queue:
                while not app.state.exiting:
                    msg = await queue.get_json(5)
                    yield f"{msg}\n".encode("utf-8")
        finally:
            log.info(f"Client has disconnected from notification for project ID '{project.id}' (HTTP stream method)")
            if project.auto_close:
                # To avoid trouble with client connecting disconnecting we sleep few seconds before checking
                # if someone else is not connected
                await asyncio.sleep(5)
                if not controller.notification.project_has_listeners(project.id):
                    log.info(f"Project '{project.id}' is automatically closing due to no client listening")
                    await project.close()

    return StreamingResponse(event_stream(), media_type="application/json")


@router.websocket("/{project_id}/notifications/ws")
async def project_ws_notifications(
        project_id: UUID,
        websocket: WebSocket,
        current_user: schemas.User = Depends(has_privilege_on_websocket("Project.Audit"))
) -> None:
    """
    Receive project notifications about the controller from WebSocket.

    Required privilege: Project.Audit
    """

    if current_user is None:
        return

    controller = Controller.instance()
    project = controller.get_project(str(project_id))

    log.info(f"New client has connected to the notification stream for project ID '{project.id}' (WebSocket method)")
    try:
        with controller.notification.project_queue(project.id) as queue:
            while True:
                notification = await queue.get_json(5)
                await websocket.send_text(notification)
    except (ConnectionClosed, WebSocketDisconnect):
        log.info(f"Client has disconnected from notification stream for project ID '{project.id}' (WebSocket method)")
    except WebSocketException as e:
        log.warning(f"Error while sending to project event to WebSocket client: {e}")
    finally:
        if project.auto_close:
            # To avoid trouble with client connecting disconnecting we sleep few seconds before checking
            # if someone else is not connected
            await asyncio.sleep(5)
            if not controller.notification.project_has_listeners(project.id):
                log.info(f"Project '{project.id}' is automatically closing due to no client listening")
                await project.close()


@router.get("/{project_id}/export", dependencies=[Depends(has_privilege("Project.Audit"))])
async def export_project(
    project: Project = Depends(dep_project),
    include_snapshots: bool = False,
    include_images: bool = False,
    reset_mac_addresses: bool = False,
    compression: schemas.ProjectCompression = "zstd",
    compression_level: int = None,
) -> StreamingResponse:
    """
    Export a project as a portable archive.

    Required privilege: Project.Audit
    """

    compression_query = compression.lower()
    if compression_query == "zip":
        compression = zipfile.ZIP_DEFLATED
        if compression_level is not None and (compression_level < 0 or compression_level > 9):
            raise ControllerBadRequestError("Compression level must be between 0 and 9 for ZIP compression")
    elif compression_query == "none":
        compression = zipfile.ZIP_STORED
    elif compression_query == "bzip2":
        compression = zipfile.ZIP_BZIP2
        if compression_level is not None and (compression_level < 1 or compression_level > 9):
            raise ControllerBadRequestError("Compression level must be between 1 and 9 for BZIP2 compression")
    elif compression_query == "lzma":
        compression = zipfile.ZIP_LZMA
    elif compression_query == "zstd":
        compression = zipfile.ZIP_ZSTANDARD
        if compression_level is not None and (compression_level < 1 or compression_level > 22):
            raise ControllerBadRequestError("Compression level must be between 1 and 22 for Zstandard compression")

    if compression_level is not None and compression_query in ("none", "lzma"):
        raise ControllerBadRequestError(f"Compression level is not supported for '{compression_query}' compression method")

    try:
        begin = time.time()
        # use the parent directory as a temporary working dir
        working_dir = os.path.abspath(os.path.join(project.path, os.pardir))

        async def streamer():
            log.info(f"Exporting project '{project.name}' with '{compression_query}' compression "
                     f"(level {compression_level})")
            with tempfile.TemporaryDirectory(dir=working_dir) as tmpdir:
                with aiozipstream.ZipFile(compression=compression, compresslevel=compression_level) as zstream:
                    await export_controller_project(
                        zstream,
                        project,
                        tmpdir,
                        include_snapshots=include_snapshots,
                        include_images=include_images,
                        reset_mac_addresses=reset_mac_addresses,
                    )
                    async for chunk in zstream:
                        yield chunk

            log.info(f"Project '{project.name}' exported in {time.time() - begin:.4f} seconds")

    # Will be raised if you have no space left or permission issue on your temporary directory
    # RuntimeError: something was wrong during the zip process
    except (ValueError, OSError, RuntimeError) as e:
        raise ConnectionError(f"Cannot export project: {e}")

    headers = {"CONTENT-DISPOSITION": f'attachment; filename="{project.name}.gns3project"'}
    return StreamingResponse(streamer(), media_type="application/gns3project", headers=headers)


@router.post(
    "/{project_id}/import",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.Project,
    dependencies=[Depends(has_privilege("Project.Allocate"))]
)
async def import_project(
        project_id: UUID,
        request: Request,
        name: Optional[str] = None
) -> schemas.Project:
    """
    Import a project from a portable archive.

    Required privilege: Project.Allocate
    """

    controller = Controller.instance()
    # We write the content to a temporary location and then we extract it all.
    # It could be more optimal to stream this but it is not implemented in Python.
    try:
        begin = time.time()
        working_dir = controller.projects_directory()
        with tempfile.TemporaryDirectory(dir=working_dir) as tmpdir:
            temp_project_path = os.path.join(tmpdir, "project.zip")
            async with aiofiles.open(temp_project_path, "wb") as f:
                async for chunk in request.stream():
                    await f.write(chunk)
            with open(temp_project_path, "rb") as f:
                project = await import_controller_project(controller, str(project_id), f, name=name)

        log.info(f"Project '{project.name}' imported in {time.time() - begin:.4f} seconds")
    except OSError as e:
        raise ControllerError(f"Could not import the project: {e}")
    return project.asdict()


@router.post(
    "/{project_id}/duplicate",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.Project,
    responses={**responses, 409: {"model": schemas.ErrorMessage, "description": "Could not duplicate project"}},
    dependencies=[Depends(has_privilege("Project.Allocate"))]
)
async def duplicate_project(
        project_data: schemas.ProjectDuplicate,
        project: Project = Depends(dep_project)
) -> schemas.Project:
    """
    Duplicate a project.

    Required privilege: Project.Allocate
    """

    reset_mac_addresses = project_data.reset_mac_addresses
    new_project = await project.duplicate(
        name=project_data.name, reset_mac_addresses=reset_mac_addresses
    )
    return new_project.asdict()


@router.get("/{project_id}/locked", dependencies=[Depends(has_privilege("Project.Audit"))])
async def locked_project(project: Project = Depends(dep_project)) -> bool:
    """
    Returns whether a project is locked or not.

    Required privilege: Project.Audit
    """

    return project.locked


@router.post(
    "/{project_id}/lock",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(has_privilege("Project.Modify"))]
)
async def lock_project(project: Project = Depends(dep_project)) -> None:
    """
    Lock all drawings and nodes in a given project.

    Required privilege: Project.Audit
    """

    project.lock()


@router.post(
    "/{project_id}/unlock",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(has_privilege("Project.Modify"))]
)
async def unlock_project(project: Project = Depends(dep_project)) -> None:
    """
    Unlock all drawings and nodes in a given project.

    Required privilege: Project.Modify
    """

    project.unlock()


@router.get("/{project_id}/files/{file_path:path}", dependencies=[Depends(has_privilege("Project.Audit"))])
async def get_file(file_path: str, project: Project = Depends(dep_project)) -> FileResponse:
    """
    Return a file from a project.

    Required privilege: Project.Audit
    """

    file_path = urllib.parse.unquote(file_path)
    path = os.path.normpath(file_path)

    # Raise error if user try to escape
    if not is_safe_path(path, project.path):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    path = os.path.join(project.path, path)
    if not os.path.exists(path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    return FileResponse(path, media_type="application/octet-stream")


@router.post(
    "/{project_id}/files/{file_path:path}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(has_privilege("Project.Modify"))]
)
async def write_file(file_path: str, request: Request, project: Project = Depends(dep_project)) -> None:
    """
    Write a file to a project.

    Required privilege: Project.Modify
    """

    file_path = urllib.parse.unquote(file_path)
    path = os.path.normpath(file_path)

    # Raise error if user try to escape
    if not is_safe_path(path, project.path):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    path = os.path.join(project.path, path)

    try:
        async with aiofiles.open(path, "wb+") as f:
            async for chunk in request.stream():
                await f.write(chunk)
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    except PermissionError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    except OSError as e:
        raise ControllerError(str(e))


@router.post(
    "/{project_id}/templates/{template_id}",
    response_model=schemas.Node,
    status_code=status.HTTP_201_CREATED,
    responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or template"}},
    dependencies=[Depends(has_privilege("Node.Allocate"))]
)
async def create_node_from_template(
    project_id: UUID,
    template_id: UUID,
    template_usage: schemas.TemplateUsage,
    templates_repo: TemplatesRepository = Depends(get_repository(TemplatesRepository)),
) -> schemas.Node:
    """
    Create a new node from a template.

    Required privilege: Node.Allocate
    """

    template = await TemplatesService(templates_repo).get_template(template_id)
    controller = Controller.instance()
    project = controller.get_project(str(project_id))
    node = await project.add_node_from_template(
        template, x=template_usage.x, y=template_usage.y, compute_id=template_usage.compute_id
    )
    return node.asdict()
