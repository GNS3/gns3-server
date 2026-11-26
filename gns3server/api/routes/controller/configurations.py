"""Node configuration export/download and project startup configuration sets.

Small request bodies (node export options) use the default bounded route;
set documents and archives use the larger startup-route budget.
"""

import asyncio
import io
import zipfile
from pathlib import PurePosixPath
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response

from gns3server.api.configuration_route import ConfigurationRoute
from gns3server.controller.configurations import (
    console_driver,
    driver_for,
    launch_capture,
    launch_live_apply,
    request_export,
    state,
    store_export,
    validate_live_recipe,
    validate_startup_entry,
    wipe_configurations,
)
from gns3server.db.repositories.rbac import RbacRepository
from gns3server.schemas.configurations import (
    CONSOLE_DEVICE_TYPES,
    STARTUP_ENGINES,
    ApplyRequest,
    ArchiveImport,
    BulkSelectionUpdate,
    CaptureRequest,
    Engine,
    ExportOptions,
    ExportResult,
    Selection,
    SetName,
    Source,
    StartupConfigurationState,
    StartupDocument,
    WipeRequest,
    compatible_device_type,
)
from gns3server.services.configurations.console.platforms import get_platform
from gns3server.services.configurations.sets import archive
from gns3server.services.configurations.sets.selections import SelectionStore, default_selection_changes
from gns3server.services.configurations.sets.store import StartupStore, store_lock
from gns3server.services.configurations.shared.errors import ConfigurationError
from gns3server.services.configurations.shared.safe_io import run_file_io

from .dependencies.authentication import get_current_active_user
from .dependencies.database import get_repository
from .nodes import dep_node
from .projects import dep_project


class StartupRoute(ConfigurationRoute):
    max_request_bytes = 34 * 1024 * 1024


class BulkRoute(ConfigurationRoute):
    # Room for the longest node list of a bulk request.
    max_request_bytes = 512 * 1024


router = APIRouter(route_class=ConfigurationRoute)
bulk_router = APIRouter(route_class=BulkRoute)
startup_router = APIRouter(route_class=StartupRoute)


def require_open(project):
    """A closed project has no loaded nodes: per-node access cannot be checked and no entry can be told apart
    from one of a deleted node, so its sets are neither shown nor changed."""
    if project.status != "opened":
        raise HTTPException(status_code=409, detail="project_closed")


def require_changeable(project):
    require_open(project)
    # A frozen template's copies take these files along.
    project.check_mutable("changing startup configurations")


async def loaded(project):
    """Wait for a project that is still loading, so that no node is mistaken for a deleted one."""
    await project.wait_loaded()


def eligible_nodes(project):
    return {node_id for node_id, node in project.nodes.items() if node.node_type in STARTUP_ENGINES}


async def access(project, user, repository, node_ids=(), *, write=False, console=False):
    if user.is_superadmin:
        return
    checks = [(f"/projects/{project.id}", "Project.Modify" if write else "Project.Audit")]
    for node_id in node_ids:
        checks.append((f"/projects/{project.id}/nodes/{node_id}", "Node.Modify" if write else "Node.Audit"))
        if console:
            checks.append((f"/projects/{project.id}/nodes/{node_id}", "Node.Console"))
    for path, privilege in checks:
        if not await repository.check_user_has_privilege(user.user_id, path, privilege):
            raise HTTPException(status_code=403, detail="configuration_access_denied")


def editor_state(project, document, eligible):
    assignments = SelectionStore(project).selections()
    return StartupConfigurationState(
        **document.model_dump(),
        selection_revision=assignments["revision"],
        selections={node_id: source for node_id, source in assignments["nodes"].items() if node_id in eligible},
    )


def read_editor_state(project, eligible):
    with store_lock(project):
        return editor_state(project, StartupStore(project).read(), eligible)


@router.get("/startup-configurations", response_model=StartupConfigurationState)
async def get_sets(
    project=Depends(dep_project),
    user=Depends(get_current_active_user),
    repository=Depends(get_repository(RbacRepository)),
):
    await loaded(project)
    node_ids = eligible_nodes(project)
    await access(project, user, repository, node_ids)
    require_open(project)
    document = await run_file_io(read_editor_state, project, node_ids)
    return document.model_copy(
        update={
            "sets": tuple(
                s.model_copy(
                    update={"nodes": {node_id: entry for node_id, entry in s.nodes.items() if str(node_id) in node_ids}}
                )
                for s in document.sets
            )
        }
    )


def require_eligible_nodes(project, node_ids, eligible):
    """The ids must name nodes of the project (404) whose type the feature supports (422)."""
    if any(node_id not in project.nodes for node_id in node_ids):
        raise HTTPException(status_code=404, detail="configuration_node_not_found")
    if any(node_id not in eligible for node_id in node_ids):
        raise HTTPException(status_code=422, detail="configuration_engine_unsupported")


def selection_changes(document, previous, assignments, node_ids):
    """Validate the editor's assignments before either manifest is changed."""
    if document.selections is None:
        return {}
    updates = {}
    if assignments["revision"] != document.selection_revision:
        raise ConfigurationError("startup_configurations_changed")
    sets = {s.id: s for s in document.sets}
    for identifier, selection in document.selections.items():
        node_id = str(identifier)
        if node_id not in node_ids:
            raise HTTPException(status_code=422, detail="configuration_node_not_found")
        if selection.kind == "set" and selection.set_id not in sets:
            # Deleting a set disables its assignments, including nodes
            # without an entry in the set currently displayed by the editor.
            if assignments["nodes"].get(node_id) != selection.model_dump(mode="json"):
                raise ConfigurationError("configuration_set_not_found")
            selection = Selection()
        if assignments["nodes"].get(node_id) != selection.model_dump(mode="json"):
            updates[node_id] = selection
    for node_id, value in assignments["nodes"].items():
        source = Selection.model_validate(value)
        if source.kind == "set" and source.set_id not in sets and node_id not in updates:
            updates[node_id] = Selection()
    if previous.selected not in sets:
        for node_id in node_ids:
            if node_id not in assignments["nodes"] and UUID(node_id) not in document.selections:
                updates[node_id] = Selection()
    return updates


@startup_router.put("/startup-configurations", response_model=StartupConfigurationState)
async def put_sets(
    document: StartupConfigurationState,
    project=Depends(dep_project),
    user=Depends(get_current_active_user),
    repository=Depends(get_repository(RbacRepository)),
):
    await loaded(project)
    node_ids = eligible_nodes(project)
    # Authorize before validating: node ids must not be probeable without access.
    await access(project, user, repository, node_ids, write=True, console=True)
    require_changeable(project)
    if any(str(node_id) not in node_ids for s in document.sets for node_id in s.nodes):
        raise HTTPException(status_code=422, detail="configuration_node_not_found")
    if any(
        not compatible_device_type(project.nodes[str(node_id)].node_type, entry.device_type)
        for s in document.sets
        for node_id, entry in s.nodes.items()
    ):
        raise HTTPException(status_code=422, detail="configuration_apply_unsupported")
    return await run_file_io(save_editor_state, project, document, node_ids)


def require_startable(node, entry):
    """An entry that the node's next start would apply has to pass that start's own check."""
    if entry is not None and entry.enabled and entry.content.strip():
        validate_startup_entry(node, entry)


def effective_entry(document, selection, node_id):
    """The entry a node starts with under this choice; without a choice it follows the project's selected set."""
    if selection is not None and selection.kind == "none":
        return None
    set_id = selection.set_id if selection is not None else document.selected
    chosen = next((s for s in document.sets if s.id == set_id), None)
    return chosen.nodes.get(UUID(node_id)) if chosen is not None else None


def save_editor_state(project, document, node_ids):
    store = StartupStore(project)
    assignments_store = SelectionStore(project)
    plain = StartupDocument.model_validate(document.model_dump(exclude={"selections", "selection_revision"}))
    # One lock hold from the first read to the last write (the lock is re-entrant, nothing here awaits):
    # no other writer can change the assignments between saving the sets and applying the choices.
    with store_lock(project):
        previous = store.read()
        assignments = assignments_store.selections()
        updates = selection_changes(document, previous, assignments, node_ids)
        if document.selections is None:
            updates = default_selection_changes(previous, plain, assignments)
        # Only what this save changes for a node is checked: an old entry must not block unrelated edits.
        for node_id in node_ids:
            stored = assignments["nodes"].get(node_id)
            stored = Selection.model_validate(stored) if stored is not None else None
            after = effective_entry(plain, updates.get(node_id, stored), node_id)
            if after != effective_entry(previous, stored, node_id):
                require_startable(project.nodes[node_id], after)
        updated = assignments_store.prepare_updates(updates, assignments["revision"]) if updates else None
        saved = store.write(plain, revision=document.revision, assignments=updated)
        return editor_state(project, saved, node_ids)


def set_summary(document, selected):
    return {
        "id": selected.id,
        "name": selected.name,
        "selected": selected.id == document.selected,
        "entries": len(selected.nodes),
    }


@router.post("/startup-configurations/sets", status_code=201)
async def create_set(
    request: SetName,
    project=Depends(dep_project),
    user=Depends(get_current_active_user),
    repository=Depends(get_repository(RbacRepository)),
):
    await loaded(project)
    await access(project, user, repository, eligible_nodes(project), write=True, console=True)
    require_changeable(project)
    document, selected = StartupStore(project).create_set(
        request.name, revision=request.revision, select=request.select
    )
    return {"revision": document.revision, "set": set_summary(document, selected)}


@bulk_router.post("/startup-configurations/wipe")
async def wipe_nodes(
    request: WipeRequest,
    project=Depends(dep_project),
    user=Depends(get_current_active_user),
    repository=Depends(get_repository(RbacRepository)),
):
    if project.status != "opened":
        raise HTTPException(status_code=409, detail="project_closed")
    eligible = eligible_nodes(project)
    node_ids = sorted(eligible) if request.all else list(dict.fromkeys(str(node_id) for node_id in request.node_ids))
    await access(project, user, repository, node_ids, write=True, console=True)
    # A wipe deletes the nodes' overlay disks, which the copies of a frozen template point at.
    project.check_mutable("wiping nodes")
    require_eligible_nodes(project, node_ids, eligible)
    stopped: list[str] = []
    results = await wipe_configurations(project, node_ids, stopped=stopped)
    # "stopped" lists the nodes that were running and were stopped to be wiped.
    return {"nodes": results, "stopped": stopped}


@bulk_router.post("/startup-configurations/capture", status_code=202)
async def capture_set(
    request: CaptureRequest,
    project=Depends(dep_project),
    user=Depends(get_current_active_user),
    repository=Depends(get_repository(RbacRepository)),
):
    if project.status != "opened":
        raise HTTPException(status_code=409, detail="project_closed")
    eligible = eligible_nodes(project)
    node_ids = list(dict.fromkeys(str(node_id) for node_id in request.node_ids)) or list(eligible)
    await access(project, user, repository, node_ids, write=True, console=True)
    require_changeable(project)
    StartupStore(project).set(request.set_id)
    require_eligible_nodes(project, node_ids, eligible)
    return launch_capture(project, request.set_id, node_ids)


def read_revisions(project):
    with store_lock(project):
        return StartupStore(project).revision(), SelectionStore(project).revision()


def assign_selection(project, node_ids, selection, revision):
    """Give every node the same choice under one lock and revision; nothing is changed when one of them cannot take it."""
    with store_lock(project):
        without_startup = []
        if selection.kind == "set":
            _, selected = StartupStore(project).set(selection.set_id)
            for node_id in node_ids:
                entry = selected.nodes.get(UUID(node_id))
                if entry and not compatible_device_type(project.nodes[node_id].node_type, entry.device_type):
                    raise HTTPException(status_code=422, detail="configuration_apply_unsupported")
                require_startable(project.nodes[node_id], entry)
                if entry is None or not entry.enabled or not entry.content.strip():
                    without_startup.append(node_id)
        store = SelectionStore(project)
        value = store.assign_many({node_id: selection for node_id in node_ids}, revision)
        return {"revision": value["revision"], "node_ids": node_ids, "without_startup": without_startup}


@bulk_router.put("/startup-configurations/selections")
async def put_selections(
    request: BulkSelectionUpdate,
    project=Depends(dep_project),
    user=Depends(get_current_active_user),
    repository=Depends(get_repository(RbacRepository)),
):
    """Assign a set to some nodes, or clear their startup, without the rights to the other nodes of the project."""
    if project.status != "opened":
        raise HTTPException(status_code=409, detail="project_closed")
    node_ids = list(dict.fromkeys(str(node_id) for node_id in request.node_ids))
    # An assignment can lead to console replay at boot, so it needs the same privileges as the per-node route.
    await access(project, user, repository, node_ids, write=True, console=request.selection.kind != "none")
    require_changeable(project)
    require_eligible_nodes(project, node_ids, eligible_nodes(project))
    return await run_file_io(assign_selection, project, node_ids, request.selection, request.revision)


@router.get("/startup-configurations/status")
async def get_status(
    project=Depends(dep_project),
    user=Depends(get_current_active_user),
    repository=Depends(get_repository(RbacRepository)),
):
    await access(project, user, repository, eligible_nodes(project))
    data = state(project)
    revision, selection_revision = await run_file_io(read_revisions, project)
    return {
        "jobs": list(data["jobs"].values()),
        "nodes": data["nodes"],
        "revision": revision,
        "selection_revision": selection_revision,
    }


@router.post("/nodes/{node_id}/configuration-apply", status_code=202)
async def apply_saved_configuration(
    request: ApplyRequest,
    node=Depends(dep_node),
    user=Depends(get_current_active_user),
    repository=Depends(get_repository(RbacRepository)),
):
    await access(node.project, user, repository, [node.id], write=True, console=True)
    require_changeable(node.project)
    if node.project.status != "opened":
        raise HTTPException(status_code=409, detail="project_closed")
    if node.locked:
        raise HTTPException(status_code=409, detail="node_locked")
    if node.status != "started":
        raise HTTPException(status_code=409, detail="start_required")
    document, selected = StartupStore(node.project).set(request.set_id)
    if document.revision != request.revision:
        raise HTTPException(status_code=409, detail="startup_configurations_changed")
    entry = selected.nodes.get(UUID(node.id))
    if entry is None or not entry.content.strip():
        raise HTTPException(status_code=404, detail="configuration_not_found")
    if (
        not compatible_device_type(node.node_type, entry.device_type)
        or entry.device_type not in CONSOLE_DEVICE_TYPES
        or not get_platform(entry.device_type).restorable
    ):
        raise HTTPException(status_code=409, detail="configuration_apply_unsupported")
    validate_live_recipe(node, entry)
    return launch_live_apply(node, selected.id, entry)


@router.get("/startup-configurations/sets/{set_id}/export", response_class=Response)
async def export_set_archive(
    set_id: UUID,
    revision: int | None = Query(None, ge=0),
    project=Depends(dep_project),
    user=Depends(get_current_active_user),
    repository=Depends(get_repository(RbacRepository)),
):
    await loaded(project)
    await access(project, user, repository, eligible_nodes(project))
    require_open(project)
    filename, payload = await asyncio.to_thread(archive.build, project, set_id, revision)
    return Response(
        payload,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename, safe='')}",
            "X-Configuration-Content": "may-contain-secrets",
        },
    )


@startup_router.post("/startup-configurations/import", status_code=201)
async def import_set_archive(
    request: ArchiveImport,
    project=Depends(dep_project),
    user=Depends(get_current_active_user),
    repository=Depends(get_repository(RbacRepository)),
):
    # Nothing of the upload is decoded for a user who cannot change the project.
    await access(project, user, repository, write=True)
    if project.status != "opened":
        raise HTTPException(status_code=409, detail="project_closed")
    project.check_mutable("importing startup configurations")
    # Validate the archive before authorizing or writing anything. Node IDs are
    # canonical; names in the archive are only hints.
    manifest = await asyncio.to_thread(archive.read, request.payload())
    await access(project, user, repository, archive.targets(project, request, manifest), write=True)
    plan = await asyncio.to_thread(archive.prepare_import, project, request, manifest)
    # Authorize the plan that will actually be committed, including changes to inherited choices.
    await access(project, user, repository, plan.targets, write=True)
    if plan.affected_nodes:
        await access(project, user, repository, sorted(plan.affected_nodes), write=True, console=True)
    return await run_file_io(archive.commit_import, project, plan)


def download(result: ExportResult):
    if len(result.files) == 1:
        file = result.files[0]
        data = file.content
        filename = PurePosixPath(file.filename).name
        media_type = "application/octet-stream"
    else:
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as bundle_zip:
            for file in result.files:
                bundle_zip.writestr(file.filename, file.content)
        data = output.getvalue()
        filename, media_type = f"configuration-{result.node_id}.zip", "application/zip"
    return Response(
        data,
        media_type=media_type,
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename, safe='')}",
            "X-Configuration-Source": result.source.value,
        },
    )


async def export_access(node, user, repository, *, save_to_set):
    """Reading a configuration needs audit access; saving it into the project's set needs modify access as well."""
    await access(node.project, user, repository, [node.id])
    if save_to_set:
        await access(node.project, user, repository, [node.id], write=True)


def selected_export_entry(node):
    document = StartupStore(node.project).read()
    selected = next(item for item in document.sets if item.id == document.selected)
    return selected.id, selected.nodes.get(UUID(node.id))


@router.post("/nodes/{node_id}/configuration-export", response_class=Response)
async def export_configuration(
    options: ExportOptions = Body(default=ExportOptions()),
    save_to_set: bool = Query(default=False),
    node=Depends(dep_node),
    user=Depends(get_current_active_user),
    repository=Depends(get_repository(RbacRepository)),
):
    await export_access(node, user, repository, save_to_set=save_to_set)
    if save_to_set:
        require_changeable(node.project)
    if options.source == Source.save_then_capture:
        # Saving first changes what the guest boots from.
        await access(node.project, user, repository, [node.id], write=True)
    try:
        engine = Engine(node.node_type)
    except ValueError:
        raise HTTPException(status_code=501, detail="configuration_engine_unsupported") from None
    running = options.source in (Source.running, Source.save_then_capture) or (
        options.source is None and engine == Engine.qemu
    )
    if running:
        if not user.is_superadmin and not await repository.check_user_has_privilege(
            user.user_id, f"/projects/{node.project.id}/nodes/{node.id}", "Node.Console"
        ):
            raise HTTPException(status_code=403, detail="configuration_access_denied")
        if engine == Engine.qemu:
            console_driver(node.netmiko_device_type)
        driver = console_driver(options.device_type or node.netmiko_device_type)
        options = options.model_copy(update={"device_type": driver})
    if not running and node.status == "started" and engine == Engine.docker and driver_for(node) == "frr":
        await access(node.project, user, repository, [node.id], console=True)
    saved = None
    if save_to_set:
        options = options.model_copy(update={"backup": True})
        saved = await run_file_io(selected_export_entry, node)
    result = await request_export(node, options)
    if (result.project_id, result.node_id, result.engine) != (UUID(node.project.id), UUID(node.id), engine):
        raise HTTPException(status_code=502, detail="configuration_compute_identity_mismatch")
    expected = (
        {options.source}
        if options.source is not None
        else (
            {Source.running}
            if engine == Engine.qemu
            else {Source.saved_startup, Source.saved_files}
            if engine == Engine.docker
            else {Source.saved_startup}
        )
    )
    if result.source not in expected:
        raise HTTPException(status_code=502, detail="configuration_source_mismatch")
    if saved is not None:
        await run_file_io(store_export, node, result, options.device_type if running else driver_for(node), saved)
    return await asyncio.to_thread(download, result)
