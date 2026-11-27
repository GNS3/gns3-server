"""Authenticated configuration export, apply and wipe on the owning compute."""

import asyncio
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Request

from gns3server.api.configuration_route import ConfigurationRoute
from gns3server.compute import MODULES
from gns3server.compute.configurations import ConfigurationService
from gns3server.schemas.configurations import (
    ApplyOptions,
    Engine,
    ExportOptions,
    ExportResult,
    MediaRequest,
    RuntimeState,
)
from gns3server.services.configurations.boot_media.staging import preflight_media, reconcile_staged
from gns3server.services.configurations.shared.errors import ConfigurationError
from gns3server.services.configurations.shared.node_lease import node_lease
from gns3server.services.configurations.shared.startup_journal import runtime

from .dependencies.authentication import compute_authentication

router = APIRouter(route_class=ConfigurationRoute, dependencies=[Depends(compute_authentication)])


def dep_configuration_node(project_id: UUID, node_id: UUID, node_type: Engine):
    for manager in MODULES:
        if manager.__name__.lower() == node_type.value:
            return manager.instance().get_node(str(node_id), project_id=str(project_id))
    raise HTTPException(status_code=404, detail="Node engine is not installed")


@router.post("/projects/{project_id}/{node_type}/nodes/{node_id}/configuration-export", response_model=ExportResult)
async def export_compute_configuration(
    node_type: Engine, options: ExportOptions = Body(default=ExportOptions()), node=Depends(dep_configuration_node)
):
    async with node_lease(node):
        return await ConfigurationService(node, node_type).export(options)


class ApplyRoute(ConfigurationRoute):
    max_request_bytes = 13 * 1024 * 1024


startup_router = APIRouter(route_class=ApplyRoute, dependencies=[Depends(compute_authentication)])


@startup_router.get(
    "/projects/{project_id}/{node_type}/nodes/{node_id}/configuration-startup-state", response_model=RuntimeState
)
async def configuration_startup_state(node_type: Engine, node=Depends(dep_configuration_node)):
    """Read the boot lifecycle without requiring a native startup profile."""
    async with node_lease(node):
        if node_type == Engine.qemu and getattr(node, "status", None) == "stopped":
            reconcile_staged(node)
        value = runtime(node)
    # The journal also records what the compute prepared for the node; the controller only needs its lifecycle.
    return {key: value[key] for key in RuntimeState.model_fields}


@startup_router.post("/projects/{project_id}/{node_type}/nodes/{node_id}/configuration-wipe", status_code=204)
async def wipe_configuration(node_type: Engine, node=Depends(dep_configuration_node)):
    async with node_lease(node):
        await ConfigurationService(node, node_type).wipe()


@startup_router.post("/projects/{project_id}/{node_type}/nodes/{node_id}/configuration-wipe/preflight", status_code=204)
async def preflight_wipe_configuration(node_type: Engine, node=Depends(dep_configuration_node)):
    async with node_lease(node):
        await ConfigurationService(node, node_type).preflight_wipe()


@startup_router.post("/projects/{project_id}/{node_type}/nodes/{node_id}/configuration-withdraw", status_code=204)
async def withdraw_configuration(node_type: Engine, node=Depends(dep_configuration_node)):
    """Take back a startup preparation that was never launched."""
    async with node_lease(node):
        await ConfigurationService(node, node_type).withdraw()


async def cancel_when_disconnected(request, work, poll_seconds=1.0):
    """Run ``work``, cancelling it when the controller gives up on the request.

    A console replay holds the node for minutes; a Stop, close or delete must not have to wait for it.
    """
    task = asyncio.ensure_future(work)
    try:
        while True:
            done, _ = await asyncio.wait({task}, timeout=poll_seconds)
            if done:
                return task.result()
            if await request.is_disconnected():
                raise ConfigurationError("runtime_changed_during_capture")
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


@startup_router.post("/projects/{project_id}/{node_type}/nodes/{node_id}/configuration-apply", status_code=204)
async def apply_configuration(
    request: Request, options: ApplyOptions, node_type: Engine, node=Depends(dep_configuration_node)
):
    async def apply_under_lease():
        if node_type == Engine.qemu and options.wait_ready and not options.running:
            # A boot can take minutes. Passive prompt observation must not hold the
            # node's lifecycle lease and block Configure. The console supervisor
            # acquires it after readiness and revalidates startup delivery there.
            await ConfigurationService(node, node_type).apply(options)
            return
        async with node_lease(node):
            await ConfigurationService(node, node_type).apply(options)

    await cancel_when_disconnected(request, apply_under_lease())


@startup_router.post("/projects/{project_id}/{node_type}/nodes/{node_id}/configuration-media")
async def stage_configuration_media(
    http_request: Request, request: MediaRequest, node_type: Engine, node=Depends(dep_configuration_node)
):
    """Stage native boot media for the next boot; ``staged`` is false when nothing will be delivered."""

    async def stage():
        async with node_lease(node):
            return {"staged": await ConfigurationService(node, node_type).stage_media(request)}

    # Preparing a disk can take minutes; a Stop abandons the start and with it this request.
    return await cancel_when_disconnected(http_request, stage())


@startup_router.post(
    "/projects/{project_id}/{node_type}/nodes/{node_id}/configuration-media/preflight", status_code=204
)
async def preflight_configuration_media(request: MediaRequest, node_type: Engine, node=Depends(dep_configuration_node)):
    if node_type != Engine.qemu or request.content is None:
        raise ConfigurationError("configuration_apply_unsupported")
    password = request.admin_password.get_secret_value() if request.admin_password is not None else None
    async with node_lease(node):
        await preflight_media(node, request.profile, request.content, password)
