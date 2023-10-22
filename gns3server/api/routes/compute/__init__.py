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


from fastapi import FastAPI, Request, Depends
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from gns3server.controller.gns3vm.gns3_vm_error import GNS3VMError
from gns3server.compute.error import ImageMissingError, NodeError
from gns3server.compute.ubridge.ubridge_error import UbridgeError

from .dependencies.authentication import compute_authentication

from gns3server.compute.compute_error import (
    ComputeError,
    ComputeNotFoundError,
    ComputeTimeoutError,
    ComputeForbiddenError,
    ComputeUnauthorizedError,
)

from . import capabilities
from . import compute
from . import projects
from . import notifications
from . import images
from . import atm_switch_nodes
from . import cloud_nodes
from . import docker_nodes
from . import dynamips_nodes
from . import ethernet_hub_nodes
from . import ethernet_switch_nodes
from . import frame_relay_switch_nodes
from . import iou_nodes
from . import nat_nodes
from . import qemu_nodes
from . import virtualbox_nodes
from . import vmware_nodes
from . import vpcs_nodes

import logging

log = logging.getLogger(__name__)


compute_api = FastAPI(
    title="GNS3 compute API",
    description="This page describes the private compute API for GNS3. PLEASE DO NOT USE DIRECTLY!",
    version="v3",
)

compute_api.state.controller_host = None


@compute_api.exception_handler(ComputeError)
async def compute_error_handler(request: Request, exc: ComputeError):
    log.error(f"Compute error: {exc}")
    return JSONResponse(
        status_code=409,
        content={"message": str(exc)},
    )


@compute_api.exception_handler(ComputeTimeoutError)
async def compute_timeout_error_handler(request: Request, exc: ComputeTimeoutError):
    log.error(f"Compute timeout error: {exc}")
    return JSONResponse(
        status_code=408,
        content={"message": str(exc)},
    )


@compute_api.exception_handler(ComputeUnauthorizedError)
async def compute_unauthorized_error_handler(request: Request, exc: ComputeUnauthorizedError):
    log.error(f"Compute unauthorized error: {exc}")
    return JSONResponse(
        status_code=401,
        content={"message": str(exc)},
    )


@compute_api.exception_handler(ComputeForbiddenError)
async def compute_forbidden_error_handler(request: Request, exc: ComputeForbiddenError):
    log.error(f"Compute forbidden error: {exc}")
    return JSONResponse(
        status_code=403,
        content={"message": str(exc)},
    )


@compute_api.exception_handler(ComputeNotFoundError)
async def compute_not_found_error_handler(request: Request, exc: ComputeNotFoundError):
    log.error(f"Compute not found error: {exc}")
    return JSONResponse(
        status_code=404,
        content={"message": str(exc)},
    )


@compute_api.exception_handler(GNS3VMError)
async def compute_gns3vm_error_handler(request: Request, exc: GNS3VMError):
    log.error(f"Compute GNS3 VM error: {exc}")
    return JSONResponse(
        status_code=409,
        content={"message": str(exc)},
    )


@compute_api.exception_handler(ImageMissingError)
async def image_missing_error_handler(request: Request, exc: ImageMissingError):
    log.error(f"Compute image missing error: {exc}")
    return JSONResponse(
        status_code=409,
        content={"message": str(exc), "image": exc.image, "exception": exc.__class__.__name__},
    )


@compute_api.exception_handler(NodeError)
async def node_error_handler(request: Request, exc: NodeError):
    log.error(f"Compute node error: {exc}")
    return JSONResponse(
        status_code=409,
        content={"message": str(exc), "exception": exc.__class__.__name__},
    )


@compute_api.exception_handler(UbridgeError)
async def ubridge_error_handler(request: Request, exc: UbridgeError):
    log.error(f"Compute uBridge error: {exc}")
    return JSONResponse(
        status_code=409,
        content={"message": str(exc), "exception": exc.__class__.__name__},
    )


# make sure the content key is "message", not "detail" per default
@compute_api.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"message": exc.detail},
    )


compute_api.include_router(
    capabilities.router,
    dependencies=[Depends(compute_authentication)],
    tags=["Capabilities"]
)

compute_api.include_router(
    compute.router,
    dependencies=[Depends(compute_authentication)],
    tags=["Compute"]
)

compute_api.include_router(
    notifications.router,
    tags=["Notifications"]
)

compute_api.include_router(
    projects.router,
    dependencies=[Depends(compute_authentication)],
    tags=["Projects"]
)

compute_api.include_router(
    images.router,
    dependencies=[Depends(compute_authentication)],
    tags=["Images"]
)

compute_api.include_router(
    atm_switch_nodes.router,
    dependencies=[Depends(compute_authentication)],
    prefix="/projects/{project_id}/atm_switch/nodes",
    tags=["ATM switch"]
)
compute_api.include_router(
    cloud_nodes.router,
    dependencies=[Depends(compute_authentication)],
    prefix="/projects/{project_id}/cloud/nodes",
    tags=["Cloud nodes"]
)

compute_api.include_router(
    docker_nodes.router,
    prefix="/projects/{project_id}/docker/nodes",
    tags=["Docker nodes"]
)

compute_api.include_router(
    dynamips_nodes.router,
    prefix="/projects/{project_id}/dynamips/nodes",
    tags=["Dynamips nodes"]
)

compute_api.include_router(
    ethernet_hub_nodes.router,
    dependencies=[Depends(compute_authentication)],
    prefix="/projects/{project_id}/ethernet_hub/nodes",
    tags=["Ethernet hub nodes"]
)

compute_api.include_router(
    ethernet_switch_nodes.router,
    dependencies=[Depends(compute_authentication)],
    prefix="/projects/{project_id}/ethernet_switch/nodes",
    tags=["Ethernet switch nodes"]
)

compute_api.include_router(
    frame_relay_switch_nodes.router,
    dependencies=[Depends(compute_authentication)],
    prefix="/projects/{project_id}/frame_relay_switch/nodes",
    tags=["Frame Relay switch nodes"]
)

compute_api.include_router(
    iou_nodes.router,
    prefix="/projects/{project_id}/iou/nodes",
    tags=["IOU nodes"])

compute_api.include_router(
    nat_nodes.router,
    dependencies=[Depends(compute_authentication)],
    prefix="/projects/{project_id}/nat/nodes",
    tags=["NAT nodes"]
)

compute_api.include_router(
    qemu_nodes.router,
    prefix="/projects/{project_id}/qemu/nodes",
    tags=["Qemu nodes"]
)

compute_api.include_router(
    virtualbox_nodes.router,
    prefix="/projects/{project_id}/virtualbox/nodes",
    tags=["VirtualBox nodes"]
)

compute_api.include_router(
    vmware_nodes.router,
    prefix="/projects/{project_id}/vmware/nodes",
    tags=["VMware nodes"]
)

compute_api.include_router(
    vpcs_nodes.router,
    prefix="/projects/{project_id}/vpcs/nodes",
    tags=["VPCS nodes"]
)
