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
API routes for computes.
"""

from fastapi import APIRouter, Depends, status
from typing import Any, List, Union, Optional
from uuid import UUID

from gns3server.controller import Controller
from gns3server.db.repositories.computes import ComputesRepository
from gns3server.db.repositories.rbac import RbacRepository
from gns3server.services.computes import ComputesService
from gns3server import schemas

from .dependencies.database import get_repository
from .dependencies.rbac import has_privilege

responses = {404: {"model": schemas.ErrorMessage, "description": "Compute not found"}}

router = APIRouter(responses=responses)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.Compute,
    responses={
        404: {"model": schemas.ErrorMessage, "description": "Could not connect to compute"},
        409: {"model": schemas.ErrorMessage, "description": "Could not create compute"},
        401: {"model": schemas.ErrorMessage, "description": "Invalid authentication for compute"},
    },
    dependencies=[Depends(has_privilege("Compute.Allocate"))]
)
async def create_compute(
    compute_create: schemas.ComputeCreate,
    computes_repo: ComputesRepository = Depends(get_repository(ComputesRepository)),
    connect: Optional[bool] = False
) -> schemas.Compute:
    """
    Create a new compute on the controller.

    Required privilege: Compute.Allocate
    """

    return await ComputesService(computes_repo).create_compute(compute_create, connect)


@router.post(
    "/{compute_id}/connect",
    status_code=status.HTTP_204_NO_CONTENT,
    #dependencies=[Depends(has_privilege("Compute.Audit"))]  # FIXME: this is a temporary workaround due to a bug in the web-ui
)
async def connect_compute(compute_id: Union[str, UUID]) -> None:
    """
    Connect to compute on the controller.

    Required privilege: Compute.Audit
    """

    compute = Controller.instance().get_compute(str(compute_id))
    if not compute.connected:
        await compute.connect(report_failed_connection=True)


@router.get(
    "/{compute_id}",
    response_model=schemas.Compute,
    response_model_exclude_unset=True,
    #dependencies=[Depends(has_privilege("Compute.Audit"))]  # FIXME: this is a temporary workaround due to a bug in the web-ui
)
async def get_compute(
    compute_id: Union[str, UUID], computes_repo: ComputesRepository = Depends(get_repository(ComputesRepository))
) -> schemas.Compute:
    """
    Return a compute from the controller.

    Required privilege: Compute.Audit
    """

    return await ComputesService(computes_repo).get_compute(compute_id)


@router.get(
    "",
    response_model=List[schemas.Compute],
    response_model_exclude_unset=True,
    #dependencies=[Depends(has_privilege("Compute.Audit"))]  # FIXME: this is a temporary workaround due to a bug in the web-ui
)
async def get_computes(
    computes_repo: ComputesRepository = Depends(get_repository(ComputesRepository)),
) -> List[schemas.Compute]:
    """
    Return all computes known by the controller.

    Required privilege: Compute.Audit
    """

    return await ComputesService(computes_repo).get_computes()


@router.put(
    "/{compute_id}",
    response_model=schemas.Compute,
    response_model_exclude_unset=True,
    dependencies=[Depends(has_privilege("Compute.Modify"))]
)
async def update_compute(
    compute_id: Union[str, UUID],
    compute_update: schemas.ComputeUpdate,
    computes_repo: ComputesRepository = Depends(get_repository(ComputesRepository)),
) -> schemas.Compute:
    """
    Update a compute on the controller.

    Required privilege: Compute.Modify
    """

    return await ComputesService(computes_repo).update_compute(compute_id, compute_update)


@router.delete(
    "/{compute_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(has_privilege("Compute.Allocate"))]
)
async def delete_compute(
        compute_id: Union[str, UUID],
        computes_repo: ComputesRepository = Depends(get_repository(ComputesRepository)),
        rbac_repo: RbacRepository = Depends(get_repository(RbacRepository)),
) -> None:
    """
    Delete a compute from the controller.

    Required privilege: Compute.Allocate
    """

    await ComputesService(computes_repo).delete_compute(compute_id)
    await rbac_repo.delete_all_ace_starting_with_path(f"/computes/{compute_id}")


@router.get("/{compute_id}/docker/images", response_model=List[schemas.ComputeDockerImage])
async def docker_get_images(compute_id: Union[str, UUID]) -> List[schemas.ComputeDockerImage]:
    """
    Get Docker images from a compute.
    """

    compute = Controller.instance().get_compute(str(compute_id))
    result = await compute.forward("GET", "docker", "images")
    return result


@router.get("/{compute_id}/virtualbox/vms", response_model=List[schemas.ComputeVirtualBoxVM])
async def virtualbox_vms(compute_id: Union[str, UUID]) -> List[schemas.ComputeVirtualBoxVM]:
    """
    Get VirtualBox VMs from a compute.
    """

    compute = Controller.instance().get_compute(str(compute_id))
    result = await compute.forward("GET", "virtualbox", "vms")
    return result


@router.get("/{compute_id}/vmware/vms", response_model=List[schemas.ComputeVMwareVM])
async def vmware_vms(compute_id: Union[str, UUID]) -> List[schemas.ComputeVMwareVM]:
    """
    Get VMware VMs from a compute.
    """

    compute = Controller.instance().get_compute(str(compute_id))
    result = await compute.forward("GET", "vmware", "vms")
    return result


@router.post("/{compute_id}/dynamips/auto_idlepc")
async def dynamips_autoidlepc(compute_id: Union[str, UUID], auto_idle_pc: schemas.AutoIdlePC) -> str:
    """
    Find a suitable Idle-PC value for a given IOS image. This may take a few minutes.
    """

    controller = Controller.instance()
    return await controller.autoidlepc(str(compute_id), auto_idle_pc.platform, auto_idle_pc.image, auto_idle_pc.ram)


@router.get("/{compute_id}/{emulator}/{endpoint_path:path}", deprecated=True)
async def forward_get(compute_id: Union[str, UUID], emulator: str, endpoint_path: str) -> Any:
    """
    Forward a GET request to a compute.
    Read the full compute API documentation for available routes.
    """

    compute = Controller.instance().get_compute(str(compute_id))
    result = await compute.forward("GET", emulator, endpoint_path)
    return result


@router.post("/{compute_id}/{emulator}/{endpoint_path:path}", deprecated=True)
async def forward_post(compute_id: Union[str, UUID], emulator: str, endpoint_path: str, compute_data: dict) -> Any:
    """
    Forward a POST request to a compute.
    Read the full compute API documentation for available routes.
    """

    compute = Controller.instance().get_compute(str(compute_id))
    return await compute.forward("POST", emulator, endpoint_path, data=compute_data)


@router.put("/{compute_id}/{emulator}/{endpoint_path:path}", deprecated=True)
async def forward_put(compute_id: Union[str, UUID], emulator: str, endpoint_path: str, compute_data: dict) -> Any:
    """
    Forward a PUT request to a compute.
    Read the full compute API documentation for available routes.
    """

    compute = Controller.instance().get_compute(str(compute_id))
    return await compute.forward("PUT", emulator, endpoint_path, data=compute_data)
