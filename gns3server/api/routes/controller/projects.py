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

import asyncio
import logging
import os
import tempfile
import time
import urllib.parse

import aiofiles

import gns3server.utils.zipfile_zstd as zipfile

log = logging.getLogger()

from typing import Any, Dict, List, Optional, Tuple, Union, cast
from uuid import UUID

from fastapi import (
    APIRouter,
    Body,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from websockets.exceptions import ConnectionClosed, WebSocketException

import gns3server.db.models as models
from gns3server import schemas
from gns3server.api.openapi import ZIP_MEDIA_TYPE, binary_request_body, binary_response
from gns3server.api.responses import NDJSON_MEDIA_TYPE, NOTIFICATION_STREAM_RESPONSES, NDJSONResponse
from gns3server.config import Config
from gns3server.controller import Controller, marker_replay
from gns3server.controller.controller_error import (
    ControllerBadRequestError,
    ControllerError,
    ControllerForbiddenError,
    ControllerNotFoundError,
)
from gns3server.controller.distribution import Distribution, DistributionRegistry
from gns3server.controller.export_project import export_project as export_controller_project
from gns3server.controller.import_project import import_project as import_controller_project
from gns3server.controller.link import _UNSET
from gns3server.controller.marker_replay import SharkdError, SharkdMissingError
from gns3server.controller.project import Project
from gns3server.db.project_acl import ensure_project_owner_ace, project_ace_path, upsert_project_share_ace
from gns3server.db.repositories.distribution_records import DistributionRecordsRepository
from gns3server.db.repositories.pools import ResourcePoolsRepository
from gns3server.db.repositories.rbac import RbacRepository
from gns3server.db.repositories.templates import TemplatesRepository
from gns3server.db.repositories.users import UsersRepository
from gns3server.services.templates import TemplatesService
from gns3server.utils.asyncio import aiozipstream
from gns3server.utils.path import is_safe_path

from .dependencies.authentication import get_current_active_user
from .dependencies.concurrency import (
    GET_RESPONSES,
    PUT_RESPONSES,
    check_if_match,
    if_match_header,
    serialize_updates,
    set_etag,
)
from .dependencies.database import get_db_session, get_repository
from .dependencies.rbac import has_privilege, has_privilege_on_websocket

responses: dict[int | str, dict[str, Any]] = {
    404: {"model": schemas.ErrorMessage, "description": "Could not find project"}
}

router = APIRouter(responses=responses)

# the cross-project distribution history: the backing view of a distribution
# management page, independent of any one project
distributions_router = APIRouter(responses=responses)

# Role put on the owner ACE of a distributed copy, and name of the snapshot
# shipped with the copy so the recipient can reset the lab on their own.
DISTRIBUTION_DEFAULT_ROLE = "Lab member"
TEMPLATE_SNAPSHOT_NAME = "template state"


def dep_project(project_id: UUID) -> Project:
    """
    Dependency to retrieve a project.
    """

    project = Controller.instance().get_project(str(project_id))
    return project


@router.get("", response_model=List[schemas.Project], response_model_exclude_unset=True)
async def get_projects(
    current_user: schemas.User = Depends(get_current_active_user),
    rbac_repo: RbacRepository = Depends(get_repository(RbacRepository)),
    name: Optional[str] = Query(None, description="Return only projects whose name exactly matches (case-sensitive)"),
) -> List[schemas.Project]:
    """
    Return all projects.

    Required privilege: Project.Audit

    Query Parameters:
    - name: Exact, case-sensitive match on the project name.
    """

    controller = Controller.instance()
    projects = []
    seen_project_ids = set()  # track seen projects to avoid duplicates

    if current_user.is_superadmin:
        # super admin sees all projects
        visible = [p for p in controller.projects.values() if name is None or p.name == name]
        counts = await rbac_repo.get_project_share_counts({p.id: p.created_by for p in visible})
        for p in visible:
            project_dict = p.asdict()
            project_dict["share_count"] = counts.get(p.id, 0)
            projects.append(project_dict)
        return projects

    # Batch ACE + resource pool check (3 DB queries regardless of project count)
    all_project_ids = list(controller.projects.keys())
    direct_ace_ids, pool_accessible_ids = await rbac_repo.get_accessible_project_ids(
        current_user.user_id, "Project.Audit", all_project_ids
    )

    # A project is visible through its ACE (owner ACE or an explicit share) or
    # through a resource pool. There is no created_by fallback: projects without
    # an owner ACE stay restricted to superadmins.
    visible = []
    for p in controller.projects.values():
        if name is not None and p.name != name:
            continue
        if p.id in direct_ace_ids or p.id in pool_accessible_ids:
            if p.id not in seen_project_ids:
                visible.append(p)
                seen_project_ids.add(p.id)

    # Share counts are the owner's business (and superadmins'): the field is
    # left unset for everybody else and excluded from the response.
    owned = {p.id: p.created_by for p in visible if p.created_by == current_user.username}
    counts = await rbac_repo.get_project_share_counts(owned) if owned else {}
    for p in visible:
        project_dict = p.asdict()
        if p.id in owned:
            project_dict["share_count"] = counts.get(p.id, 0)
        projects.append(project_dict)

    return projects


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.Project,
    response_model_exclude_unset=True,
    responses={409: {"model": schemas.ErrorMessage, "description": "Could not create project"}},
    dependencies=[Depends(has_privilege("Project.Allocate"))],
)
async def create_project(
    project_data: schemas.ProjectCreate,
    current_user: schemas.User = Depends(get_current_active_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> schemas.Project:
    """
    Create a new project.

    Required privilege: Project.Allocate
    """

    controller = Controller.instance()
    project_dict = jsonable_encoder(project_data, exclude_unset=True)
    project_dict["created_by"] = current_user.username
    project = await controller.add_project(**project_dict)
    # The default ACE on /projects does not propagate: grant the creator access
    # to the project through an owner ACE.
    await ensure_project_owner_ace(db_session, project.id, current_user.username)
    return project.asdict()


@router.get(
    "/{project_id}",
    response_model=schemas.Project,
    responses=GET_RESPONSES,
    dependencies=[Depends(has_privilege("Project.Audit"))],
)
async def get_project(
    response: Response,
    project: Project = Depends(dep_project),
    current_user: schemas.User = Depends(get_current_active_user),
    rbac_repo: RbacRepository = Depends(get_repository(RbacRepository)),
) -> schemas.Project:
    """
    Return a project.

    Required privilege: Project.Audit. The share count is only returned to the
    project owner and superadmins.
    """

    project_dict = project.asdict()
    # the ETag covers the project itself: share_count is a per-user view on a
    # separate sub-resource (the /shares endpoints) and must not change it,
    # otherwise If-Match on PUT would fail for owners
    set_etag(response, project_dict)
    if current_user.is_superadmin or project.created_by == current_user.username:
        counts = await rbac_repo.get_project_share_counts({project.id: project.created_by})
        project_dict["share_count"] = counts.get(project.id, 0)
    return project_dict


@router.get(
    "/{project_id}/me/privileges",
    response_model=schemas.ProjectPrivileges,
    responses=GET_RESPONSES,
    dependencies=[Depends(has_privilege("Project.Audit"))],
)
async def get_logged_in_user_privileges_on_project(
    current_user: schemas.User = Depends(get_current_active_user),
    project: Project = Depends(dep_project),
    rbac_repo: RbacRepository = Depends(get_repository(RbacRepository)),
) -> schemas.ProjectPrivileges:
    """
    Get the effective privileges of the current user on this project.

    Unlike /access/users/me/privileges (flattened across all resource paths),
    each privilege is evaluated on the project's resource path, so the result
    reflects ACEs scoped to this project and resource pools containing it.
    This is meant for rendering purposes (e.g. showing or hiding buttons in
    the project view): the server remains the authority for permission checks.

    Required privilege: Project.Audit

    Example: curl -X GET http://host:port/v3/projects/{project_id}/me/privileges -H "Authorization: Bearer <token>"
    """

    if current_user.is_superadmin:
        privilege_names = sorted(privilege.name for privilege in await rbac_repo.get_privileges())
        return schemas.ProjectPrivileges(is_superadmin=True, privileges=privilege_names)

    path = f"/projects/{project.id}"
    # the flat view is the superset: only privileges granted somewhere can be
    # granted on this path, so only those need to be evaluated against it
    candidates = await rbac_repo.get_user_privileges(current_user.user_id)
    project_privileges = []
    for name in candidates:
        if await rbac_repo.check_user_has_privilege(current_user.user_id, path, name):
            project_privileges.append(name)
    return schemas.ProjectPrivileges(is_superadmin=False, privileges=sorted(project_privileges))


@router.put(
    "/{project_id}",
    response_model=schemas.Project,
    response_model_exclude_unset=True,
    responses=PUT_RESPONSES,
    dependencies=[Depends(has_privilege("Project.Modify"))],
)
async def update_project(
    project_data: schemas.ProjectUpdate,
    response: Response,
    project: Project = Depends(dep_project),
    if_match: Optional[str] = Depends(if_match_header),
) -> schemas.Project:
    """
    Update a project.

    If the If-Match header is present, the update is only applied when it matches the current ETag.

    Required privilege: Project.Modify
    """

    async with serialize_updates(f"project:{project.id}"):
        check_if_match(if_match, project.asdict())
        await project.update(**jsonable_encoder(project_data, exclude_unset=True))
    project_dict = project.asdict()
    set_etag(response, project_dict)
    return project_dict


@router.delete(
    "/{project_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(has_privilege("Project.Allocate"))]
)
async def delete_project(
    project: Project = Depends(dep_project),
    current_user: schemas.User = Depends(get_current_active_user),
    rbac_repo: RbacRepository = Depends(get_repository(RbacRepository)),
    db_session: AsyncSession = Depends(get_db_session),
) -> None:
    """
    Delete a project.

    Deleting is reserved to the project owner (its ``created_by``) and to
    superadmins: users with access through a share or a resource pool carry
    ``Project.Allocate`` (it is required to open a project) but must not be
    able to destroy a project they do not own. The owner of a distributed
    copy is its creator, so recipients can still delete their own copy.

    Required privilege: Project.Allocate, owner or superadmin
    """

    if not current_user.is_superadmin and project.created_by != current_user.username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the project owner or a superadmin can delete this project",
        )

    if project.frozen:
        # a running job has not registered its first copy yet: the
        # registered-copy check alone would let the template vanish under it
        if _running_distributions(project):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A distribution of this project is in progress: wait for it to finish before deleting it",
            )
        # the copies of a distributed template keep overlay disks pointing
        # at its files: the template cannot vanish while they exist
        live_usernames = await _live_distribution_copies(project)
        if live_usernames:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"This distributed template still has {len(live_usernames)} existing copy/copies "
                    f"(users: {', '.join(sorted(live_usernames))}): delete the copies before the template"
                ),
            )

    controller = Controller.instance()
    await project.delete()
    controller.remove_project(project)
    await rbac_repo.delete_all_ace_starting_with_path(f"/projects/{project.id}")
    # the distribution history of a deleted project is unreachable from the
    # API (every route hangs off the project): drop it with the project
    await DistributionRecordsRepository(db_session).delete_records_for_project(project.id)


@router.get(
    "/{project_id}/stats", response_model=schemas.ProjectStats, dependencies=[Depends(has_privilege("Project.Audit"))]
)
def get_project_stats(project: Project = Depends(dep_project)) -> dict:
    """
    Return a project statistics.

    Required privilege: Project.Audit
    """

    return project.stats()


@router.get(
    "/{project_id}/markers",
    response_model=Dict[str, schemas.ProjectMarker],
    response_model_exclude_unset=True,
    dependencies=[Depends(has_privilege("Project.Audit"))],
)
def get_project_markers(project: Project = Depends(dep_project)) -> dict:
    """
    Return all traffic-insight markers across every link in the project.

    Each entry is keyed ``"{link_id}/{marker_name}"`` and carries the
    marker's BPF, tag, color, enabled flag, plus its parent ``link_id``
    and capture-side ``node_id`` for frontend filtering / grouping.

    Required privilege: Project.Audit
    """

    return project.markers


async def _replay_response(awaitable):
    """Shared engine-error mapping for the replay endpoints: 501 when sharkd
    (the hard engine requirement) is unavailable, 502 when it fails. Data
    state errors (409 gate / 404 unknown tag) and filter errors (400) map
    through the global handlers before this."""

    try:
        return await awaitable
    except SharkdMissingError as e:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(e))
    except SharkdError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.get(
    "/{project_id}/markers/tags/{tag}/replay/range",
    response_model=schemas.ReplayTimeline,
    dependencies=[Depends(has_privilege("Project.Audit"))],
)
async def replay_tag_range(
    tag: int,
    filter: Optional[str] = None,
    link: Optional[str] = None,
    project: Project = Depends(dep_project),
) -> dict:
    """
    Aggregate replay timeline for a tag: merges the pcap of every marker
    carrying ``tag`` into one timestamp-ordered view. Every frame entry
    carries Wireshark-style columns (``src`` / ``dst`` / ``proto`` / ``info``
    plus coloring hints ``bg`` / ``fg``).

    The tag gate applies: every marker under the tag must be paused
    (``enabled: false``) — 409 otherwise. The response carries the timeline
    bounds, per-source stats, and the full merged frame list — deliberately
    uncapped (rendering a huge list is the client's concern; the window
    endpoint exists for incremental views).

    ``filter`` is an optional Wireshark display filter applied **before**
    counting and slicing — start / end / frame_count / frames are
    all computed on the matching frames only. An invalid expression is a 400
    carrying sharkd's original error text (for inline display in the UI
    filter bar).

    ``link`` narrows the frame stream to one capture source (link_id),
    AND-composing with ``filter``; ``sources`` always lists the tag's full
    inventory regardless. An unknown link_id yields an empty timeline (same
    shape as a zero-match filter), not a 404. Requires sharkd — 501 without
    it.

    Required privilege: Project.Audit
    """

    return await _replay_response(marker_replay.build_timeline(project, tag, filter_expr=filter, link_id=link))


@router.get(
    "/{project_id}/markers/tags/{tag}/replay/frames",
    response_model=schemas.ReplayFrames,
    dependencies=[Depends(has_privilege("Project.Audit"))],
)
async def replay_tag_frames(
    tag: int,
    ts: str,
    window_ms: int = 100,
    limit: int = 1000,
    filter: Optional[str] = None,
    link: Optional[str] = None,
    project: Project = Depends(dep_project),
) -> dict:
    """
    Frames with ts in ``[ts, ts + window_ms]`` merged across every source of
    the tag. A time with no frames is a normal successful answer:
    ``{"frames": []}``. The tag gate applies (409 while any marker captures).

    ``ts`` must be the exact string returned by the range response — never
    re-serialize it through a float. ``filter`` and ``link`` (optional
    display filter / capture-source link_id) have the same semantics as on
    the range endpoint — windows and the histogram always agree. Requires
    sharkd — 501 without it.

    Required privilege: Project.Audit
    """

    return await _replay_response(
        marker_replay.query_frames(
            project,
            tag,
            ts,
            window_ms=window_ms,
            limit=limit,
            filter_expr=filter,
            link_id=link,
        )
    )


@router.get(
    "/{project_id}/markers/tags/{tag}/replay/frame/detail",
    response_model=schemas.ReplayFrameDetail,
    response_model_exclude_unset=True,
    dependencies=[Depends(has_privilege("Project.Audit"))],
)
async def replay_tag_frame_detail(
    tag: int,
    ts: str,
    node_id: str,
    link_id: str,
    marker: str,
    frame_number: Optional[int] = None,
    project: Project = Depends(dep_project),
) -> dict:
    """
    Decode exactly one frame (lazy — invoked when the user opens a frame,
    never by the timeline itself): raw bytes for the hex view read straight
    from the pcap, protocol tree from the resident sharkd session with keys
    renamed into the REST contract (``element`` / ``label`` / ``name`` /
    ``filter_expr`` / ``pos`` + ``size`` / ``expert`` / ``generated`` /
    ``children``) — values untouched.

    ``ts`` must be the exact string from the frame list; ``node_id`` +
    ``link_id`` + ``marker`` identify the source pcap. ``frame_number``
    (optional, from the frame list entry) disambiguates same-microsecond
    frames on one link — without it the first ts match decodes. The tag gate
    applies. Requires sharkd — 501 without it.

    Required privilege: Project.Audit
    """

    return await _replay_response(
        marker_replay.decode_frame(project, tag, ts, node_id, link_id, marker, frame_number=frame_number)
    )


# ---------------------------------------------------------------------------
# Project-level marker definitions (global rules inherited by every link)
# ---------------------------------------------------------------------------


@router.get(
    "/{project_id}/marker-definitions",
    response_model=Dict[str, schemas.MarkerDefinitionWithLinks],
    response_model_exclude_unset=True,
    dependencies=[Depends(has_privilege("Project.Audit"))],
)
def get_marker_definitions(project: Project = Depends(dep_project)) -> dict:
    """
    Return all project-level marker definitions with their bound link IDs.

    Required privilege: Project.Audit
    """

    result = {}
    for name, d in project.marker_definitions.items():
        # Collect which links currently carry an inherited copy.
        bound = [
            lid
            for lid, link in project.links.items()
            if f"global-{name}" in link.markers and link.markers[f"global-{name}"].get("inherited_from") == name
        ]
        result[name] = {**d, "link_ids": bound}
    return result


@router.post(
    "/{project_id}/marker-definitions",
    response_model=schemas.MarkerDefinition,
    response_model_exclude_unset=True,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(has_privilege("Project.Marker"))],
)
async def create_marker_definition(
    def_data: schemas.MarkerDefinitionCreate, project: Project = Depends(dep_project)
) -> dict:
    """
    Create a project-level marker definition and fan out to every link.

    Required privilege: Project.Marker
    """

    if def_data.name and def_data.name.lower().startswith("global"):
        raise ControllerError('Names starting with "global" are reserved for inherited markers')
    name = def_data.name or f"def-{project.id[:8]}"
    await project.create_marker_definition(
        name=name,
        bpf=def_data.bpf,
        tag=def_data.tag,
        direction=def_data.direction,
        color=def_data.color,
        highlight_duration=def_data.highlight_duration,
        data_link_type=def_data.data_link_type,
    )
    return project.marker_definitions.get(name, {})


@router.put(
    "/{project_id}/marker-definitions/{def_name}",
    response_model=schemas.MarkerDefinition,
    response_model_exclude_unset=True,
    dependencies=[Depends(has_privilege("Project.Marker"))],
)
async def update_marker_definition(
    def_name: str, def_data: schemas.MarkerDefinitionCreate, project: Project = Depends(dep_project)
) -> dict:
    """
    Update a marker definition and sync all inherited copies on every link.

    Required privilege: Project.Marker
    """

    await project.update_marker_definition(
        name=def_name,
        bpf=def_data.bpf if def_data.bpf else None,
        tag=def_data.tag,
        direction=def_data.direction if "direction" in def_data.model_fields_set else _UNSET,
        color=def_data.color,
        highlight_duration=def_data.highlight_duration,
        data_link_type=def_data.data_link_type if "data_link_type" in def_data.model_fields_set else _UNSET,
    )
    return project.marker_definitions.get(def_name, {})


@router.post(
    "/{project_id}/marker-definitions/{def_name}/pause",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(has_privilege("Project.Marker"))],
)
async def pause_marker_definition(def_name: str, project: Project = Depends(dep_project)) -> None:
    """
    Pause a definition: toggle off every inherited ``global-{def_name}`` copy
    on every link (uBridge ``enable_packet_filter off``, instant — no NIO
    rebuild). The definition's ``paused`` flag is persisted, so links created
    later inherit it already paused.

    Required privilege: Project.Marker
    """

    await project.pause_marker_definition(def_name)


@router.post(
    "/{project_id}/marker-definitions/{def_name}/resume",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(has_privilege("Project.Marker"))],
)
async def resume_marker_definition(def_name: str, project: Project = Depends(dep_project)) -> None:
    """Resume a paused definition (toggle on every inherited copy).

    Required privilege: Project.Marker
    """

    await project.resume_marker_definition(def_name)


@router.delete(
    "/{project_id}/marker-definitions/{def_name}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(has_privilege("Project.Marker"))],
)
async def delete_marker_definition(def_name: str, project: Project = Depends(dep_project)) -> None:
    """
    Delete a marker definition and remove all inherited copies from every link.

    Required privilege: Project.Marker
    """

    await project.delete_marker_definition(def_name)


@router.post(
    "/{project_id}/close",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={**responses, 409: {"model": schemas.ErrorMessage, "description": "Could not close project"}},
    dependencies=[Depends(has_privilege("Project.Allocate"))],
)
async def close_project(project: Project = Depends(dep_project)) -> None:
    """
    Close a project.

    Required privilege: Project.Allocate
    """

    await project.close()


@router.post(
    "/{project_id}/open",
    status_code=status.HTTP_200_OK,
    response_model=schemas.Project,
    responses={**responses, 409: {"model": schemas.ErrorMessage, "description": "Could not open project"}},
    dependencies=[Depends(has_privilege("Project.Allocate"))],
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
    dependencies=[Depends(has_privilege("Server.Modify"))],
)
async def load_project(
    path: str = Body(..., embed=True),
    db_session: AsyncSession = Depends(get_db_session),
) -> schemas.Project:
    """
    Load a project (local server only).

    Required privilege: Server.Modify
    """

    if Config.instance().settings.Server.local is False:
        raise ControllerForbiddenError("You can only load a project on a local server")

    controller = Controller.instance()
    dot_gns3_file = path
    project = await controller.load_project(dot_gns3_file)
    await ensure_project_owner_ace(db_session, project.id, project.created_by)
    return project.asdict()


@router.get(
    "/{project_id}/notifications",
    dependencies=[Depends(has_privilege("Project.Audit"))],
    response_class=NDJSONResponse,
    responses=NOTIFICATION_STREAM_RESPONSES,
)
async def project_http_notifications(project_id: UUID) -> StreamingResponse:
    """
    Receive project notifications from an HTTP stream of newline delimited JSON objects (see the Notification schema).

    The same messages are available as WebSocket text frames on `/v3/projects/{project_id}/notifications/ws`.
    Marker events (`marker.match`) are not sent here, they are only available on
    `/v3/projects/{project_id}/notifications/markers/ws`.
    Project actions: `node.*`, `link.*`, `drawing.*`, `project.updated`, `snapshot.restored`, `log.*` and `ping`.

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
                    yield f"{msg}\n".encode()
        finally:
            log.info(f"Client has disconnected from notification for project ID '{project.id}' (HTTP stream method)")
            if project.auto_close:
                # To avoid trouble with client connecting disconnecting we sleep few seconds before checking
                # if someone else is not connected
                await asyncio.sleep(5)
                if not controller.notification.project_has_listeners(project.id):
                    log.info(f"Project '{project.id}' is automatically closing due to no client listening")
                    await project.close()

    return StreamingResponse(event_stream(), media_type=NDJSON_MEDIA_TYPE)


@router.websocket("/{project_id}/notifications/ws")
async def project_ws_notifications(
    project_id: UUID,
    websocket: WebSocket,
    current_user: schemas.User = Depends(has_privilege_on_websocket("Project.Audit")),
) -> None:
    """
    Receive project notifications from a WebSocket, one Notification JSON object per text frame.
    Same messages as the HTTP stream `/v3/projects/{project_id}/notifications`.

    Required privilege: Project.Audit
    """

    if current_user is None:
        return

    controller = Controller.instance()
    project = controller.get_project(str(project_id))

    log.info(f"New client has connected to the notification stream for project ID '{project.id}' (WebSocket method)")
    try:
        with controller.notification.project_queue(project.id) as queue:
            while not websocket.app.state.exiting:
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


@router.websocket("/{project_id}/notifications/markers/ws")
async def project_marker_ws_notifications(
    project_id: UUID,
    websocket: WebSocket,
    current_user: schemas.User = Depends(has_privilege_on_websocket("Project.Audit")),
) -> None:
    """
    Receive marker notifications (`marker.match`, see the Notification schema) for a project on a
    dedicated WebSocket, one JSON object per text frame, separate from the main project stream so high-frequency
    marker.matches do not block topology events (node.*/link.*).

    Required privilege: Project.Audit
    """

    if current_user is None:
        return

    controller = Controller.instance()
    project = controller.get_project(str(project_id))

    log.info(
        f"New client has connected to the marker notification stream for project ID '{project.id}' (WebSocket method)"
    )
    try:
        with controller.notification.project_marker_queue(project.id) as queue:
            while not websocket.app.state.exiting:
                notification = await queue.get_json(5)
                await websocket.send_text(notification)
    except (ConnectionClosed, WebSocketDisconnect):
        log.info(
            f"Client has disconnected from the marker notification stream for project ID '{project.id}' (WebSocket method)"
        )
    except WebSocketException as e:
        log.warning(f"Error while sending marker event to WebSocket client: {e}")


@router.get(
    "/{project_id}/export",
    response_class=StreamingResponse,
    responses={200: binary_response(ZIP_MEDIA_TYPE, "Portable project archive")},
    dependencies=[Depends(has_privilege("Project.Export"))],
)
async def export_project(
    project: Project = Depends(dep_project),
    include_snapshots: bool = False,
    include_images: bool = False,
    reset_mac_addresses: bool = False,
    keep_compute_ids: bool = False,
    compression: schemas.ProjectCompression = schemas.ProjectCompression.zstd,
    compression_level: Optional[int] = None,
) -> StreamingResponse:
    """
    Export a project as a portable archive.

    Required privilege: Project.Export
    """

    if project.distribution_master_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A distributed copy cannot be exported: its disks may be thin overlays of the template project",
        )
    if project.is_running():
        raise ControllerError("Project must be stopped in order to export it")

    compression_query = compression.lower()
    if compression_query == "zip":
        zip_compression = zipfile.ZIP_DEFLATED
        if compression_level is not None and (compression_level < 0 or compression_level > 9):
            raise ControllerBadRequestError("Compression level must be between 0 and 9 for ZIP compression")
    elif compression_query == "none":
        zip_compression = zipfile.ZIP_STORED
    elif compression_query == "bzip2":
        zip_compression = zipfile.ZIP_BZIP2
        if compression_level is not None and (compression_level < 1 or compression_level > 9):
            raise ControllerBadRequestError("Compression level must be between 1 and 9 for BZIP2 compression")
    elif compression_query == "lzma":
        zip_compression = zipfile.ZIP_LZMA
    elif compression_query == "zstd":
        zip_compression = zipfile.ZIP_ZSTANDARD
        if compression_level is not None and (compression_level < 1 or compression_level > 22):
            raise ControllerBadRequestError("Compression level must be between 1 and 22 for Zstandard compression")

    if compression_level is not None and compression_query in ("none", "lzma"):
        raise ControllerBadRequestError(
            f"Compression level is not supported for '{compression_query}' compression method"
        )

    try:
        begin = time.time()
        # use the parent directory as a temporary working dir
        working_dir = os.path.abspath(os.path.join(project.path, os.pardir))

        async def streamer():
            log.info(
                f"Exporting project '{project.name}' with '{compression_query}' compression (level {compression_level})"
            )
            with tempfile.TemporaryDirectory(dir=working_dir) as tmpdir:
                with aiozipstream.ZipFile(compression=zip_compression, compresslevel=compression_level) as zstream:
                    await export_controller_project(
                        zstream,
                        project,
                        tmpdir,
                        include_snapshots=include_snapshots,
                        include_images=include_images,
                        keep_compute_ids=keep_compute_ids,
                        reset_mac_addresses=reset_mac_addresses,
                    )
                    async for chunk in zstream:
                        yield chunk

            log.info(f"Project '{project.name}' exported in {time.time() - begin:.4f} seconds")

    # Will be raised if you have no space left or permission issue on your temporary directory
    # RuntimeError: something was wrong during the zip process
    except (ValueError, OSError, RuntimeError) as e:
        raise ConnectionError(f"Cannot export project: {e}")

    fallback = project.name.encode("ascii", "ignore").decode() or "project"
    encoded = urllib.parse.quote(project.name, safe="")
    headers = {
        "Content-Disposition": (
            f"attachment; filename=\"{fallback}.gns3project\"; filename*=UTF-8''{encoded}.gns3project"
        )
    }
    return StreamingResponse(streamer(), media_type="application/gns3project", headers=headers)


@router.post(
    "/{project_id}/import",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.Project,
    openapi_extra=binary_request_body(ZIP_MEDIA_TYPE),
)
async def import_project(
    project_id: UUID,
    request: Request,
    name: Optional[str] = None,
    current_user: schemas.User = Depends(get_current_active_user),
    rbac_repo: RbacRepository = Depends(get_repository(RbacRepository)),
    db_session: AsyncSession = Depends(get_db_session),
) -> schemas.Project:
    """
    Import a project from a portable archive.

    Required privilege: Project.Allocate
    """

    controller = Controller.instance()

    # The client picks the target project ID. A brand new project is covered by
    # the collection ACE on /projects (the default ACE does not propagate),
    # while importing on top of an existing project requires access to it.
    # Importing over an existing project destroys it, so like deletion it is
    # reserved to the project owner and to superadmins.
    existing_project = controller.projects.get(str(project_id))
    if existing_project is not None and (
        existing_project.frozen or existing_project.distribution_master_id is not None
    ):
        # importing replaces every file: it would change what the copies of a
        # frozen template see, or break the overlays of a distributed copy
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Importing over a distributed template or copy is not allowed",
        )
    if not current_user.is_superadmin:
        path = f"/projects/{project_id}" if existing_project is not None else "/projects"
        if not await rbac_repo.check_user_has_privilege(current_user.user_id, path, "Project.Allocate"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied (privilege Project.Allocate is required)",
            )
        if existing_project is not None and existing_project.created_by != current_user.username:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the project owner or a superadmin can import on top of this project",
            )

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
                project = await import_controller_project(
                    controller,
                    str(project_id),
                    f,
                    name=name,
                    user=current_user.username,
                )

        log.info(f"Project '{project.name}' imported in {time.time() - begin:.4f} seconds")
    except OSError as e:
        raise ControllerError(f"Could not import the project: {e}")
    await ensure_project_owner_ace(db_session, project.id, project.created_by)
    return project.asdict()


async def _resolve_distribution_targets(
    users_repo: UsersRepository,
    rbac_repo: RbacRepository,
    project_data: schemas.ProjectDistribute,
    current_user: schemas.User,
) -> Tuple[Optional[models.User], Optional[List[models.User]], models.Role]:
    """
    Resolve the distribution target(s) and the role of their owner ACE.

    A distribution targets a single user, a list of users or a whole group.
    The caller cannot be a recipient: a distribution hands out reduced-role
    copies to other people, someone who wants their own copy duplicates the
    project instead. Raises 404 when a user, the group or the role does not
    exist, 409 when the group is empty or a target is the caller. Everything
    is resolved before any work is done.
    """

    role_name = project_data.owner_role or DISTRIBUTION_DEFAULT_ROLE
    role = await rbac_repo.get_role_by_name(role_name)
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Role '{role_name}' does not exist")

    if project_data.target_user:
        target_user = await users_repo.get_user_by_username(project_data.target_user)
        if target_user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Target user '{project_data.target_user}' does not exist",
            )
        _reject_caller_as_target(target_user, current_user)
        return target_user, None, role

    if project_data.target_users:
        # every username must exist before the first copy is made; duplicates
        # in the list are collapsed so a user never receives two copies
        targets = []
        for username in dict.fromkeys(project_data.target_users):
            user = await users_repo.get_user_by_username(username)
            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Target user '{username}' does not exist",
                )
            targets.append(user)
        for user in targets:
            _reject_caller_as_target(user, current_user)
        return None, targets, role

    if project_data.target_group:
        group = await users_repo.get_user_group_by_name(project_data.target_group)
        if group is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Target group '{project_data.target_group}' does not exist",
            )
        members = await users_repo.get_user_group_members(group.user_group_id)
        if not members:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Target group '{project_data.target_group}' has no members",
            )
        return None, members, role

    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail="A distribution needs target_user, target_users or target_group",
    )


def _reject_caller_as_target(target: models.User, current_user: schemas.User) -> None:
    """
    A distribution hands the lab to other people: the caller asks for copies
    for them, and duplicates the project for a copy of their own.
    """

    if target.user_id == current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You cannot distribute the project to yourself: duplicate it instead",
        )


async def _distribute_project_copy(
    db_session: AsyncSession,
    project: Project,
    target: models.User,
    owner_role_id: UUID,
    name: str,
    reset_mac_addresses: Optional[bool],
    lock_topology: Optional[bool],
    overlay_from_master: bool,
    archive_path: Optional[str] = None,
) -> dict:
    """
    Duplicate a project on behalf of another user: the copy is owned by that
    user, its owner ACE carries the given (reduced) role, and it ships with a
    snapshot of the template state. With ``overlay_from_master`` the QEMU
    disks of the copy are thin overlays pointing at the template's disks
    (local computes only), so the copy costs seconds instead of a full copy.
    ``archive_path`` is the export the fallback path imports the copy from:
    the job exports the project once and every recipient reuses it.
    """

    new_project = await project.duplicate(
        name=name,
        reset_mac_addresses=reset_mac_addresses,
        user=target.username,
        overlay_from_master=overlay_from_master,
        archive_path=archive_path,
    )
    # the export/import fallback carries the topology file of the frozen
    # template verbatim: a copy is never frozen, whatever the duplication path
    if new_project.frozen:
        new_project.frozen = False
        new_project.dump()
    await ensure_project_owner_ace(db_session, new_project.id, new_project.created_by, role_id=owner_role_id)

    # Ship the copy with a snapshot of the template state so the recipient can
    # reset the lab to its initial state (Snapshot.Restore), and lock its nodes
    # and drawings when asked. The lock is advisory (a client hint): the
    # reduced owner role is the enforcement. Locking happens before the
    # snapshot, so the state a recipient restores is the locked one.
    #
    # Both checks need the copy open: the snapshot is taken through the open
    # project, and the inherited snapshots are only visible then — Project
    # __init__ does not load the snapshot config, open() does. A copy that
    # inherits a "template state" snapshot from the source keeps it instead of
    # failing on the name collision a second snapshot would raise.
    reopen = new_project.status == "closed"
    if reopen:
        await new_project.open()
    try:
        if lock_topology:
            new_project.lock()
        if TEMPLATE_SNAPSHOT_NAME not in [snapshot.name for snapshot in new_project.snapshots.values()]:
            await new_project.snapshot(TEMPLATE_SNAPSHOT_NAME)
    finally:
        if reopen:
            await new_project.close()
    return new_project.asdict()


async def _duplicable_pool_memberships(
    current_user: schemas.User,
    project: Project,
    rbac_repo: RbacRepository,
    pools_repo: ResourcePoolsRepository,
) -> List:
    """
    Pool memberships of the source project, after checking the user can
    create a copy of it somewhere: in the root (/projects) or in a pool the
    project belongs to. Superadmins always pass.
    """

    pool_memberships = await pools_repo.get_resource_memberships(project.id)

    # check if the project can be duplicated somewhere (either in a pool or in the root)
    if not current_user.is_superadmin:
        can_be_duplicated_somewhere = False
        if pool_memberships:
            for pool in pool_memberships:
                if await rbac_repo.check_user_has_privilege(
                    current_user.user_id, f"/pools/{pool.resource_pool_id}", "Project.Allocate"
                ):
                    can_be_duplicated_somewhere = True
                    break

        if not can_be_duplicated_somewhere and not await rbac_repo.check_user_has_privilege(
            current_user.user_id, "/projects", "Project.Allocate"
        ):
            log.warning(f"Project {project.name} cannot be duplicated anywhere")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    return pool_memberships


@router.post(
    "/{project_id}/duplicate",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.Project,
    responses={
        **responses,
        409: {"model": schemas.ErrorMessage, "description": "Could not duplicate project"},
    },
    dependencies=[Depends(has_privilege("Project.Duplicate"))],
)
async def duplicate_project(
    project_data: schemas.ProjectDuplicate,
    project: Project = Depends(dep_project),
    current_user: schemas.User = Depends(get_current_active_user),
    rbac_repo: RbacRepository = Depends(get_repository(RbacRepository)),
    pools_repo: ResourcePoolsRepository = Depends(get_repository(ResourcePoolsRepository)),
    db_session: AsyncSession = Depends(get_db_session),
) -> schemas.Project:
    """
    Duplicate a project: the copy belongs to the user who duplicated it.
    A distributed copy cannot be duplicated: its disks may be thin overlays
    of the template project. A frozen template can be duplicated (the copy
    is a normal independent project).

    Required privilege: Project.Duplicate, plus Project.Allocate somewhere the copy can live
    """

    if project.distribution_master_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A distributed copy cannot be duplicated: ask the template owner for a new copy instead",
        )

    pool_memberships = await _duplicable_pool_memberships(current_user, project, rbac_repo, pools_repo)

    new_project = await project.duplicate(
        name=project_data.name,
        reset_mac_addresses=project_data.reset_mac_addresses,
        user=current_user.username,
    )
    # The duplicated project is owned by the user who duplicated it.
    await ensure_project_owner_ace(db_session, new_project.id, new_project.created_by)

    # Add the new project in the same resource pools if the duplicated project belongs to any
    if pool_memberships:
        resource_create = schemas.ResourceCreate(
            resource_id=new_project.id, resource_type="project", name=new_project.name
        )
        resource = await pools_repo.create_resource(resource_create)
        for pool in pool_memberships:
            await pools_repo.add_resource_to_pool(pool.resource_pool_id, resource)

    return new_project.asdict()


async def _live_distribution_copies(project: Project) -> List[str]:
    """
    Usernames whose distributed copy of this project still exists on the
    server, across every distribution ever made from it. The copies tell it
    themselves: each one carries the id of its template, so the check does
    not depend on the distribution records (a record can be deleted, and a
    crash can drop one before it records a copy). A copy counts as gone once
    its directory no longer exists (deleted through the API or removed
    directly on disk).
    """

    controller = Controller.instance()
    live_usernames = []
    for candidate in controller.projects.values():
        if candidate.distribution_master_id is None:
            continue
        if str(candidate.distribution_master_id) != str(project.id):
            continue
        if os.path.exists(candidate.path):
            live_usernames.append(candidate.created_by or str(candidate.id))
    return live_usernames


def _running_distributions(project: Project) -> List[str]:
    """
    IDs of the distribution jobs started from this project that are still
    running. A job registers its first copy only once its files and thin
    overlays are ready: until then no project claims the template, so the
    registered-copy check alone would let it be deleted or unfrozen under
    the job.
    """

    return [
        job.distribution_id
        for job in DistributionRegistry.instance().get_for_project(str(project.id))
        if job.status in ("running", "cancelling")
    ]


def _record_live_copies(results: List[dict]) -> List[str]:
    """
    Usernames whose copy recorded in a distribution's results still exists
    on the server.
    """

    controller = Controller.instance()
    live_usernames = []
    for result in results:
        copy = result.get("project")
        if copy is None:
            continue
        try:
            copy_project = controller.get_project(str(copy["project_id"]))
        except ControllerNotFoundError:
            continue
        if os.path.exists(copy_project.path):
            live_usernames.append(str(result.get("username") or copy["project_id"]))
    return live_usernames


def _distribution_record_asdict(record: models.DistributionRecord) -> dict:
    """
    A persisted distribution record in the response shape of a live
    distribution job.
    """

    return {
        "distribution_id": record.distribution_id,
        "project_id": record.project_id,
        "name": record.name,
        "created_by": record.created_by,
        "status": record.status,
        "total": record.total,
        "completed": len(record.results or []),
        "results": _annotate_copy_existence(cast(List[dict], record.results or [])),
        "error": {"message": record.error} if record.error else None,
        "created_at": record.created_at,
    }


def _annotate_copy_existence(results: List[dict]) -> List[dict]:
    """
    Flag, per recipient, whether the distributed copy still exists on the
    server. A copy can vanish outside the API (its directory removed
    directly), so the check is against the controller's view of the projects
    directory, not a database state.
    """

    controller = Controller.instance()
    for result in results:
        copy = result.get("project")
        if copy is None:
            continue
        try:
            copy_project = controller.get_project(str(copy["project_id"]))
        except ControllerNotFoundError:
            result["project_exists"] = False
            continue
        # the directory observer takes a moment to drop a removed project
        result["project_exists"] = os.path.exists(copy_project.path)
    return results


async def _persist_distribution_job(db_session: AsyncSession, job: Distribution) -> None:
    """
    Write the current state of a distribution job through to its database
    record. The copies are the real work: a persistence failure is logged
    and never stops the job.
    """

    try:
        updated = await DistributionRecordsRepository(db_session).update_record(
            UUID(job.distribution_id), job.status, job.error, job.cancel_requested, list(job.results)
        )
        if not updated:
            log.warning(f"Distribution '{job.distribution_id}' of project '{job.project_id}' has no record to update")
    except Exception as e:
        log.error(f"Could not persist the distribution '{job.distribution_id}' of project '{job.project_id}': {e}")
        # leave the session usable for the copies still to be made
        await db_session.rollback()


async def _run_distribution(
    engine: Any,
    job: Distribution,
    project_id: str,
    recipients: List[Tuple[models.User, str]],
    owner_role_id: UUID,
    reset_mac_addresses: Optional[bool],
    lock_topology: Optional[bool],
    overlay_from_master: bool,
) -> None:
    """
    Create one copy per recipient in the background, recording a result per
    recipient as it completes. A failing recipient never stops the job. A
    cancel request stops it at the next recipient boundary: the copy in
    flight completes, the remaining recipients are skipped. Every state
    change is written through to the distribution record, so a crash leaves
    a trace of how far the job got.

    The copies are thin overlay copies on a local-only project. A project
    with remote computes falls back to export/import copies, and the project
    is exported once for the whole job: every recipient imports that archive
    instead of downloading the project files again.
    """

    registry = DistributionRegistry.instance()
    try:
        # the background task outlives the request: it needs its own session
        async with AsyncSession(engine, expire_on_commit=False) as db_session:
            project = Controller.instance().get_project(project_id)
            # the archive lives under the projects directory, like the
            # per-recipient fallback export, to avoid no space left issues
            # when '/tmp' is located on another partition
            working_dir = os.path.abspath(os.path.join(project.path, os.pardir))
            with tempfile.TemporaryDirectory(dir=working_dir) as tmpdir:
                archive_path = None
                if not overlay_from_master:
                    archive_path = os.path.join(tmpdir, "project.gns3p")
                    previous_status = project.status
                    if previous_status == "closed":
                        await project.open()
                    try:
                        await project.export_archive(archive_path)
                    finally:
                        if previous_status == "closed":
                            await project.close()
                for member, name in recipients:
                    if job.cancel_requested:
                        # nothing is in flight between two recipients: this is the
                        # safe place to stop, every copy made so far is complete
                        break
                    try:
                        copy = await _distribute_project_copy(
                            db_session,
                            project,
                            member,
                            owner_role_id,
                            name,
                            reset_mac_addresses,
                            lock_topology,
                            overlay_from_master,
                            archive_path,
                        )
                        registry.record_result(job, {"username": member.username, "project": copy, "error": None})
                    except Exception as e:
                        log.error(f"Could not distribute a copy to '{member.username}': {e}")
                        registry.record_result(
                            job, {"username": member.username, "project": None, "error": {"message": str(e)}}
                        )
                    await _persist_distribution_job(db_session, job)
                # the cancel request may also land during the very last copy: the
                # loop above ends without checking again
                if job.cancel_requested:
                    registry.cancelled(job)
                else:
                    registry.complete(job)
                await _persist_distribution_job(db_session, job)
    except Exception as e:
        registry.fail(job, str(e))
        try:
            async with AsyncSession(engine, expire_on_commit=False) as db_session:
                await _persist_distribution_job(db_session, job)
        except Exception as persist_error:
            log.error(f"Could not persist the failed distribution '{job.distribution_id}': {persist_error}")


@router.post(
    "/{project_id}/distribute",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=schemas.ProjectDistribution,
    responses={
        **responses,
        409: {"model": schemas.ErrorMessage, "description": "Could not distribute project"},
    },
    dependencies=[Depends(has_privilege("Project.Distribute"))],
)
async def distribute_project(
    project_data: schemas.ProjectDistribute,
    project: Project = Depends(dep_project),
    current_user: schemas.User = Depends(get_current_active_user),
    rbac_repo: RbacRepository = Depends(get_repository(RbacRepository)),
    pools_repo: ResourcePoolsRepository = Depends(get_repository(ResourcePoolsRepository)),
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    Distribute a project: create one copy per recipient (a single user, every
    listed user, or every member of a user group) in the background. Each
    copy is owned by its recipient, its owner ACE carries a reduced role
    (``owner_role``, the built-in "Lab member" role by default), it ships
    with a snapshot of the template state, and its nodes and drawings are
    locked by default (``lock_topology``). The copies' QEMU disks are thin
    overlays of the project's disks (a project with nodes on a remote
    compute falls back to full copies), and the project is frozen as a
    template: it cannot be modified until every copy is deleted. The caller
    cannot be a recipient (duplicate the project instead), and the owner
    role cannot carry privileges the caller does not hold on the project.
    Returns the distribution job: poll
    ``GET /projects/{project_id}/distributions/{distribution_id}``
    for the progress and the per-recipient results.

    Required privilege: Project.Distribute, plus Project.Allocate somewhere the copy can live
    """

    if project.distribution_master_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A distributed copy cannot be distributed: distribute the template project instead",
        )

    # Resolve the recipient(s) and the role of their owner ACE before the job
    # starts: a bad request must not distribute anything.
    target_user, recipients, owner_role = await _resolve_distribution_targets(
        UsersRepository(db_session), rbac_repo, project_data, current_user
    )
    await _check_share_role_width(rbac_repo, current_user, project, owner_role)
    await _duplicable_pool_memberships(current_user, project, rbac_repo, pools_repo)

    # the overlays' backing files must live on the same machine as the
    # copies: only an all-local project can be distributed the thin way
    # (has_remote_compute also works on a closed project, whose computes
    # would come back as plain dicts)
    overlay_from_master = not project.has_remote_compute()

    # freeze the template before the first copy is made: from here on its
    # content is the reference every recipient depends on
    if not project.frozen:
        project.frozen = True
        project.dump()
        project.emit_controller_notification("project.updated", project.asdict())

    # a single recipient keeps the given name, a fan-out names every copy
    # after the lab and its recipient (lab1-alice)
    targets = [target_user] if target_user is not None else recipients or []
    names = [
        (member, project_data.name if target_user is not None else f"{project_data.name}-{member.username}")
        for member in targets
    ]

    registry = DistributionRegistry.instance()
    registry.prune()
    assert current_user.username is not None  # an authenticated user always has a name
    job = registry.create(str(project.id), project_data.name, current_user.username, total=len(names))
    # the durable record is created with the job: from here on the
    # distribution is visible in the history even if the controller dies
    await DistributionRecordsRepository(db_session).create_record(
        UUID(job.distribution_id), project.id, job.name, job.created_by, job.total
    )
    job.task = asyncio.create_task(
        _run_distribution(
            # the bound engine outlives the request-scoped session
            db_session.bind,
            job,
            str(project.id),
            names,
            owner_role.role_id,
            project_data.reset_mac_addresses,
            project_data.lock_topology,
            overlay_from_master,
        )
    )
    return job.asdict()


@router.get(
    "/{project_id}/distributions",
    response_model=List[schemas.ProjectDistribution],
    dependencies=[Depends(has_privilege("Project.Audit"))],
)
async def get_project_distributions(
    project: Project = Depends(dep_project),
    current_user: schemas.User = Depends(get_current_active_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> List[dict]:
    """
    Return the distribution history of a project from the persisted records
    (the caller's own, plus every one on a project the caller owns, and
    every one for a superadmin): who distributed the project, to which
    recipients and when, across controller restarts.

    Required privilege: Project.Audit
    """

    registry = DistributionRegistry.instance()
    registry.prune()
    records_repo = DistributionRecordsRepository(db_session)
    # a record still marked running whose job is not in the live registry was
    # cut short by a controller restart: close it out before listing
    await records_repo.mark_interrupted([UUID(distribution_id) for distribution_id in registry.live_ids()])
    records = await records_repo.get_records_for_project(project.id)
    return [
        _distribution_record_asdict(record)
        for record in records
        if current_user.is_superadmin
        or record.created_by == current_user.username
        or project.created_by == current_user.username
    ]


async def _get_owned_distribution_or_record(
    project: Project,
    distribution_id: UUID,
    current_user: schemas.User,
    db_session: AsyncSession,
) -> Tuple[Optional[Distribution], Optional[models.DistributionRecord]]:
    """
    Look up one distribution of the project — the live job (fresher than the
    last write-through) or, once its job is gone, its persisted record —
    checking the caller is the user who started it, the owner of the project
    (whose project a distribution freezes, so they must always be able to
    read and clean it up), or a superadmin. Exactly one of the two returns
    is set.
    """

    def _refused() -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This distribution belongs to another user and to another user's project",
        )

    job = DistributionRegistry.instance().get(str(distribution_id))
    if job is not None and job.project_id == str(project.id):
        if (
            not current_user.is_superadmin
            and job.created_by != current_user.username
            and project.created_by != current_user.username
        ):
            raise _refused()
        return job, None

    record = await DistributionRecordsRepository(db_session).get_record(distribution_id)
    if record is None or str(record.project_id) != str(project.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Could not find this distribution")
    if (
        not current_user.is_superadmin
        and record.created_by != current_user.username
        and project.created_by != current_user.username
    ):
        raise _refused()
    return None, record


@router.get(
    "/{project_id}/distributions/{distribution_id}",
    response_model=schemas.ProjectDistribution,
    dependencies=[Depends(has_privilege("Project.Audit"))],
)
async def get_project_distribution(
    distribution_id: UUID,
    project: Project = Depends(dep_project),
    current_user: schemas.User = Depends(get_current_active_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    Return the state of one distribution job: the progress and the
    per-recipient results recorded so far. A live job is served from the
    registry; once its job is gone the persisted record is returned, so a
    distribution stays readable across controller restarts.

    Required privilege: Project.Audit
    """

    job, record = await _get_owned_distribution_or_record(project, distribution_id, current_user, db_session)
    if job is not None:
        job_dict = job.asdict()
        job_dict["results"] = _annotate_copy_existence(job_dict["results"])
        return job_dict
    assert record is not None  # one of the two is set
    return _distribution_record_asdict(record)


@router.delete(
    "/{project_id}/distributions/{distribution_id}",
    response_model=schemas.ProjectDistribution,
    responses={
        **responses,
        204: {"description": "The finished distribution was removed from the history"},
        409: {
            "model": schemas.ErrorMessage,
            "description": "The distribution is running or still has existing copies",
        },
    },
    dependencies=[Depends(has_privilege("Project.Audit"))],
)
async def cancel_project_distribution(
    distribution_id: UUID,
    project: Project = Depends(dep_project),
    current_user: schemas.User = Depends(get_current_active_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> Union[dict, Response]:
    """
    Delete a distribution. A running (or cancelling) one is cancelled: the
    copy in flight still completes, the remaining recipients are skipped,
    the job switches to "cancelling" right away and to "cancelled" once the
    current copy is done, and the job state is returned. A finished one has
    its record removed from the history (204): the copies already made are
    real projects and are not touched. A record whose copies still exist is
    refused with 409: the record is how those copies are found for a bulk
    cleanup.

    Required privilege: Project.Audit, and only the user who started the distribution,
    the project owner, or a superadmin
    """

    registry = DistributionRegistry.instance()
    job, record = await _get_owned_distribution_or_record(project, distribution_id, current_user, db_session)
    if job is not None and registry.request_cancel(job):
        job_dict = job.asdict()
        job_dict["results"] = _annotate_copy_existence(job_dict["results"])
        return job_dict

    # removing the record is how the copies stop being reachable for a bulk
    # cleanup: refuse it while a copy still exists
    results = cast(List[dict], job.results if job is not None else (record.results if record is not None else []))
    live_usernames = _record_live_copies(results)
    if live_usernames:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"This distribution still has {len(live_usernames)} existing copy/copies "
                f"(users: {', '.join(sorted(live_usernames))}): delete the copies before removing its record"
            ),
        )

    # the job already finished (or only its record is left): remove the
    # record from the history, and with it the registry entry so the job
    # does not resurface during the retention window
    registry.remove(str(distribution_id))
    await DistributionRecordsRepository(db_session).delete_record(distribution_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/{project_id}/distributions/{distribution_id}/copies",
    response_model=schemas.ProjectDistribution,
    responses={
        **responses,
        409: {
            "model": schemas.ErrorMessage,
            "description": "The distribution is still running: cancel it first",
        },
    },
    dependencies=[Depends(has_privilege("Project.Audit"))],
)
async def delete_distribution_copies(
    distribution_id: UUID,
    project: Project = Depends(dep_project),
    current_user: schemas.User = Depends(get_current_active_user),
    rbac_repo: RbacRepository = Depends(get_repository(RbacRepository)),
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    Delete every copy of this distribution that still exists on the server,
    recipient by recipient (each copy is closed and removed through the
    regular project deletion). A copy a recipient already deleted, or whose
    directory was removed directly on disk, is skipped. The distribution
    record is kept: it still tells who received a copy and when. Once every
    copy of every distribution of the project is gone the template can be
    unfrozen and modified again.

    Required privilege: Project.Audit, and only the user who started the distribution,
    the project owner, or a superadmin
    """

    registry = DistributionRegistry.instance()
    job, record = await _get_owned_distribution_or_record(project, distribution_id, current_user, db_session)
    if job is not None:
        if job.status in ("running", "cancelling"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The distribution is still running: cancel it before deleting its copies",
            )
        results = list(job.results)
    else:
        assert record is not None  # one of the two is set
        results = list(record.results or [])

    controller = Controller.instance()
    for result in results:
        copy = result.get("project")
        if copy is None:
            continue  # this recipient failed: no copy to delete
        try:
            copy_project = controller.get_project(str(copy["project_id"]))
        except ControllerNotFoundError:
            continue
        if not os.path.exists(copy_project.path):
            continue  # already gone (deleted by the recipient or on disk)
        log.info(f"Deleting the distributed copy of '{result.get('username')}' ({copy['project_id']})")
        await copy_project.delete()
        controller.remove_project(copy_project)
        await rbac_repo.delete_all_ace_starting_with_path(f"/projects/{copy_project.id}")

    # the per-recipient results keep their history: which copies existed and
    # were deleted is visible through the project_exists flags
    if job is not None:
        job_dict = job.asdict()
    else:
        assert record is not None  # one of the two is set
        job_dict = _distribution_record_asdict(record)
    job_dict["results"] = _annotate_copy_existence(job_dict["results"])
    return job_dict


def _annotate_source_project(entry: dict) -> dict:
    """
    Add the name of the distributed (source) project to a history entry, so
    the cross-project listing reads without joining the projects first. The
    name is None when the project no longer exists on the server (its
    directory was removed directly — an API deletion takes the records with
    it).
    """

    controller = Controller.instance()
    try:
        entry["project_name"] = controller.get_project(str(entry["project_id"])).name
    except ControllerNotFoundError:
        entry["project_name"] = None
    return entry


@distributions_router.get(
    "",
    response_model=List[schemas.ProjectDistribution],
    dependencies=[Depends(has_privilege("Project.Audit"))],
)
async def list_distributions(
    current_user: schemas.User = Depends(get_current_active_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> List[dict]:
    """
    Return the distribution history across every project (the caller's own,
    plus every one for a superadmin): the backing view of a distribution
    management page. Each entry carries the name of the distributed project
    (``project_name``, None when that project no longer exists on the
    server) and the per-recipient results with their ``project_exists``
    flags, so dead entries can be cleaned up knowingly.

    Required privilege: Project.Audit on /distributions
    """

    registry = DistributionRegistry.instance()
    records_repo = DistributionRecordsRepository(db_session)
    await records_repo.mark_interrupted([UUID(distribution_id) for distribution_id in registry.live_ids()])
    if current_user.is_superadmin:
        records = await records_repo.get_all_records()
    else:
        assert current_user.username is not None  # an authenticated user always has a name
        records = await records_repo.get_records_by_creator(current_user.username)
    return [_annotate_source_project(_distribution_record_asdict(record)) for record in records]


@distributions_router.delete(
    "/{distribution_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        **responses,
        409: {
            "model": schemas.ErrorMessage,
            "description": "The distribution is running, or still has existing copies",
        },
    },
    dependencies=[Depends(has_privilege("Project.Audit"))],
)
async def delete_distribution(
    distribution_id: UUID,
    current_user: schemas.User = Depends(get_current_active_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> Response:
    """
    Remove one record from the distribution history. Unlike the per-project
    endpoint this works whatever happened to the project (its directory may
    have been removed directly, leaving the record unreachable there), and a
    running distribution is refused with 409 — cancel it on its project.
    Only the user who started the distribution (or a superadmin) can remove
    its record. The copies themselves are never touched, and a record whose
    copies still exist is refused with 409: the record is how those copies
    are found for a bulk cleanup.

    Required privilege: Project.Audit on /distributions
    """

    registry = DistributionRegistry.instance()
    job = registry.get(str(distribution_id))
    if job is not None and job.status in ("running", "cancelling"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This distribution is still running: cancel it on its project",
        )

    record = await DistributionRecordsRepository(db_session).get_record(distribution_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Could not find this distribution")
    if not current_user.is_superadmin and record.created_by != current_user.username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="This distribution was started by another user"
        )
    # a finished job in the registry is fresher than its last write-through
    results = job.results if job is not None else cast(List[dict], record.results or [])
    live_usernames = _record_live_copies(results)
    if live_usernames:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"This distribution still has {len(live_usernames)} existing copy/copies "
                f"(users: {', '.join(sorted(live_usernames))}): delete the copies before removing its record"
            ),
        )

    registry.remove(str(distribution_id))
    await DistributionRecordsRepository(db_session).delete_record(distribution_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _share_result(ace: models.ACE, username: Optional[str], group_name: Optional[str], role_name: str) -> dict:
    """
    One share as returned by the share endpoints.
    """

    return {
        "ace_id": ace.ace_id,
        "username": username,
        "group_name": group_name,
        "role": role_name,
        "created_at": ace.created_at,
        "updated_at": ace.updated_at,
    }


async def _share_aces(rbac_repo: RbacRepository, project: Project) -> List[models.ACE]:
    """
    The ACEs sharing a project: every user and group ACE on the project path,
    except the owner ACE of its creator.
    """

    path = project_ace_path(project.id)
    aces = await rbac_repo.get_aces_for_path(path)
    return [
        ace
        for ace in aces
        if ace.path == path
        and not (ace.user is not None and project.created_by is not None and ace.user.username == project.created_by)
    ]


async def _resolve_share_targets(
    users_repo: UsersRepository, share_data: schemas.ProjectShare, owner_username: Optional[str]
) -> Tuple[Optional[List[models.User]], Optional[models.UserGroup]]:
    """
    Resolve the share target(s) and their role. A share targets a single user,
    a list of users or a whole group (one group ACE for all its members).
    The project owner cannot be a target: the share upsert replaces an
    existing user ACE, and on the owner it would replace the owner ACE and
    its role. Raises 404 when a user or the group does not exist, 409 when
    the group is empty or a target is the owner. Everything is resolved
    before any ACE is written.
    """

    def _reject_owner(target: models.User) -> None:
        if target.username == owner_username:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The owner of the project cannot be a share target: it would replace the owner role",
            )

    if share_data.target_user:
        user = await users_repo.get_user_by_username(share_data.target_user)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Target user '{share_data.target_user}' does not exist",
            )
        _reject_owner(user)
        return [user], None

    if share_data.target_users:
        targets = []
        for username in dict.fromkeys(share_data.target_users):
            user = await users_repo.get_user_by_username(username)
            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Target user '{username}' does not exist",
                )
            targets.append(user)
        for user in targets:
            _reject_owner(user)
        return targets, None

    if share_data.target_group:
        group = await users_repo.get_user_group_by_name(share_data.target_group)
        if group is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Target group '{share_data.target_group}' does not exist",
            )
        members = await users_repo.get_user_group_members(group.user_group_id)
        if not members:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Target group '{share_data.target_group}' has no members",
            )
        return None, group

    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail="A share needs target_user, target_users or target_group",
    )


async def _check_share_role_width(
    rbac_repo: RbacRepository, current_user: schemas.User, project: Project, role: models.Role
) -> None:
    """
    A share, or the owner role handed out with a distribution copy, cannot
    grant a role with privileges the caller does not hold on the project: in
    particular, the owner of a distributed (frozen) copy cannot unfreeze it
    by sharing it to anyone — themselves included — with a wider role.
    Superadmins can share with any role.
    """

    if current_user.is_superadmin:
        return
    path = project_ace_path(project.id)
    for privilege in role.privileges:
        if not await rbac_repo.check_user_has_privilege(current_user.user_id, path, privilege.name):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{role.name}' has privileges you do not have on this project",
            )


@router.post(
    "/{project_id}/share",
    status_code=status.HTTP_201_CREATED,
    response_model=List[schemas.ProjectShareResult],
    responses={
        **responses,
        409: {"model": schemas.ErrorMessage, "description": "Could not share project"},
    },
    dependencies=[Depends(has_privilege("Project.Share"))],
)
async def share_project(
    share_data: schemas.ProjectShare,
    project: Project = Depends(dep_project),
    current_user: schemas.User = Depends(get_current_active_user),
    rbac_repo: RbacRepository = Depends(get_repository(RbacRepository)),
    db_session: AsyncSession = Depends(get_db_session),
) -> List[dict]:
    """
    Share a project with a single user, a list of users or a whole user group:
    no copy is created, the targets get access to this very project through an
    ACE carrying ``role`` (the built-in "Lab member" role by default). Sharing
    again with the same target replaces its role. The project owner cannot be
    a target: a share updates an existing user ACE, so it would replace the
    owner ACE and its role. A share cannot grant a role with privileges the
    sharer does not hold on the project.

    Required privilege: Project.Share
    """

    role_name = share_data.role or DISTRIBUTION_DEFAULT_ROLE
    role = await rbac_repo.get_role_by_name(role_name)
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Role '{role_name}' does not exist")
    await _check_share_role_width(rbac_repo, current_user, project, role)

    users, group = await _resolve_share_targets(UsersRepository(db_session), share_data, project.created_by)

    shares = []
    if users is not None:
        for user in users:
            ace, _created = await upsert_project_share_ace(
                db_session, project.id, role.role_id, user_id=cast(UUID, user.user_id)
            )
            shares.append(_share_result(ace, user.username, None, role_name))
    else:
        assert group is not None  # one of users or group is set
        ace, _created = await upsert_project_share_ace(
            db_session, project.id, role.role_id, group_id=group.user_group_id
        )
        shares.append(_share_result(ace, None, cast(str, group.name), role_name))
    return shares


@router.get(
    "/{project_id}/shares",
    response_model=List[schemas.ProjectShareResult],
    dependencies=[Depends(has_privilege("Project.Share"))],
)
async def get_project_shares(
    project: Project = Depends(dep_project),
    rbac_repo: RbacRepository = Depends(get_repository(RbacRepository)),
) -> List[dict]:
    """
    Return who a project is shared with. The owner ACE of the creator is not a
    share and is not listed; resource pool memberships are a different
    mechanism and are not listed either.

    Required privilege: Project.Share
    """

    shares = []
    for ace in await _share_aces(rbac_repo, project):
        if ace.user is not None:
            shares.append(_share_result(ace, ace.user.username, None, ace.role.name))
        else:
            shares.append(_share_result(ace, None, ace.group.name, ace.role.name))
    return shares


@router.delete(
    "/{project_id}/shares/{ace_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        **responses,
        409: {"model": schemas.ErrorMessage, "description": "Could not delete share"},
    },
    dependencies=[Depends(has_privilege("Project.Share"))],
)
async def delete_project_share(
    ace_id: UUID,
    project: Project = Depends(dep_project),
    rbac_repo: RbacRepository = Depends(get_repository(RbacRepository)),
) -> None:
    """
    Remove one share of a project. The owner ACE of the creator cannot be
    removed this way.

    Required privilege: Project.Share
    """

    if ace_id not in {ace.ace_id for ace in await _share_aces(rbac_repo, project)}:
        raise ControllerNotFoundError(f"Share '{ace_id}' does not exist")
    await rbac_repo.delete_ace(ace_id)


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
    dependencies=[Depends(has_privilege("Project.Modify"))],
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
    dependencies=[Depends(has_privilege("Project.Modify"))],
)
async def unlock_project(project: Project = Depends(dep_project)) -> None:
    """
    Unlock all drawings and nodes in a given project.

    Required privilege: Project.Modify
    """

    project.unlock()


@router.post(
    "/{project_id}/unfreeze",
    response_model=schemas.Project,
    responses={
        **responses,
        409: {
            "model": schemas.ErrorMessage,
            "description": "The project is not frozen or distributed copies still exist",
        },
    },
    dependencies=[Depends(has_privilege("Project.Modify"))],
)
async def unfreeze_project(
    project: Project = Depends(dep_project),
    current_user: schemas.User = Depends(get_current_active_user),
) -> dict:
    """
    Unfreeze a distributed template so it can be modified (and distributed
    again) — only when every copy made from it is gone. Reserved to the
    project owner and to superadmins, like deletion: unfreezing paves the
    way to changing what future recipients will get.

    Required privilege: Project.Modify, owner or superadmin
    """

    if not project.frozen:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="This project is not a frozen distributed template"
        )
    if not current_user.is_superadmin and project.created_by != current_user.username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the project owner or a superadmin can unfreeze this project",
        )
    if _running_distributions(project):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A distribution of this project is in progress: wait for it to finish before unfreezing it",
        )
    live_usernames = await _live_distribution_copies(project)
    if live_usernames:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"This distributed template still has {len(live_usernames)} existing copy/copies "
                f"(users: {', '.join(sorted(live_usernames))}): delete the copies before unfreezing"
            ),
        )
    project.frozen = False
    project.dump()
    project.emit_controller_notification("project.updated", project.asdict())
    return project.asdict()


@router.get(
    "/{project_id}/files/{file_path:path}",
    response_class=FileResponse,
    responses={200: binary_response(description="File content")},
    dependencies=[Depends(has_privilege("Project.Audit"))],
)
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


@router.get(
    "/{project_id}/gns3file",
    response_class=FileResponse,
    responses={
        200: {
            "description": "Project topology file",
            "content": {"application/json": {"schema": {"type": "object"}}},
        }
    },
    dependencies=[Depends(has_privilege("Project.Audit"))],
)
async def get_project_gns3_file(project: Project = Depends(dep_project)) -> FileResponse:
    """
    Return the .gns3 topology file of a project.

    Required privilege: Project.Audit
    """

    path = project.topology_file
    if not os.path.exists(path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    return FileResponse(path, media_type="application/json")


@router.post(
    "/{project_id}/files/{file_path:path}",
    status_code=status.HTTP_204_NO_CONTENT,
    openapi_extra=binary_request_body(),
    dependencies=[Depends(has_privilege("Project.Modify"))],
)
async def write_file(file_path: str, request: Request, project: Project = Depends(dep_project)) -> None:
    """
    Write a file to a project.

    Required privilege: Project.Modify
    """

    # a frozen template's files include the base disks the overlay disks of
    # its copies point at: writing one would break every copy
    project.check_mutable("writing project files")

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
    dependencies=[Depends(has_privilege("Node.Allocate"))],
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
        template, x=template_usage.x, y=template_usage.y, name=template_usage.name, compute_id=template_usage.compute_id
    )
    return node.asdict()
