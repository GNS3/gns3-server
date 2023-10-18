#!/usr/bin/env python
#
# Copyright (C) 2023 GNS3 Technologies Inc.
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
API routes for resource pools.
"""

from fastapi import APIRouter, Depends, status
from uuid import UUID
from typing import List

from gns3server import schemas
from gns3server.controller.controller_error import (
    ControllerError,
    ControllerBadRequestError,
    ControllerNotFoundError
)

from gns3server.controller import Controller
from gns3server.db.repositories.rbac import RbacRepository
from gns3server.db.repositories.pools import ResourcePoolsRepository

from .dependencies.rbac import has_privilege
from .dependencies.database import get_repository

import logging

log = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "",
    response_model=List[schemas.ResourcePool],
    dependencies=[Depends(has_privilege("Pool.Audit"))]
)
async def get_resource_pools(
        pools_repo: ResourcePoolsRepository = Depends(get_repository(ResourcePoolsRepository))
) -> List[schemas.ResourcePool]:
    """
    Get all resource pools.

    Required privilege: Pool.Audit
    """

    return await pools_repo.get_resource_pools()


@router.post(
    "",
    response_model=schemas.ResourcePool,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(has_privilege("Pool.Allocate"))]
)
async def create_resource_pool(
        resource_pool_create: schemas.ResourcePoolCreate,
        pools_repo: ResourcePoolsRepository = Depends(get_repository(ResourcePoolsRepository))
) -> schemas.ResourcePool:
    """
    Create a new resource pool

    Required privilege: Pool.Allocate
    """

    if await pools_repo.get_resource_pool_by_name(resource_pool_create.name):
       raise ControllerBadRequestError(f"Resource pool '{resource_pool_create.name}' already exists")

    return await pools_repo.create_resource_pool(resource_pool_create)


@router.get(
    "/{resource_pool_id}",
    response_model=schemas.ResourcePool,
    dependencies=[Depends(has_privilege("Pool.Audit"))]
)
async def get_resource_pool(
        resource_pool_id: UUID,
        pools_repo: ResourcePoolsRepository = Depends(get_repository(ResourcePoolsRepository))
) -> schemas.ResourcePool:
    """
    Get a resource pool.

    Required privilege: Pool.Audit
    """

    resource_pool = await pools_repo.get_resource_pool(resource_pool_id)
    if not resource_pool:
        raise ControllerNotFoundError(f"Resource pool '{resource_pool_id}' not found")
    return resource_pool


@router.put(
    "/{resource_pool_id}",
    response_model=schemas.ResourcePool,
    dependencies=[Depends(has_privilege("Pool.Modify"))]
)
async def update_resource_pool(
        resource_pool_id: UUID,
        resource_pool_update: schemas.ResourcePoolUpdate,
        pools_repo: ResourcePoolsRepository = Depends(get_repository(ResourcePoolsRepository))
) -> schemas.ResourcePool:
    """
    Update a resource pool.

    Required privilege: Pool.Modify
    """

    resource_pool = await pools_repo.get_resource_pool(resource_pool_id)
    if not resource_pool:
        raise ControllerNotFoundError(f"Resource pool '{resource_pool_id}' not found")

    return await pools_repo.update_resource_pool(resource_pool_id, resource_pool_update)


@router.delete(
    "/{resource_pool_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(has_privilege("Pool.Allocate"))]
)
async def delete_resource_pool(
        resource_pool_id: UUID,
        pools_repo: ResourcePoolsRepository = Depends(get_repository(ResourcePoolsRepository)),
        rbac_repo: RbacRepository = Depends(get_repository(RbacRepository))
) -> None:
    """
    Delete a resource pool.

    Required privilege: Pool.Allocate
    """

    resource_pool = await pools_repo.get_resource_pool(resource_pool_id)
    if not resource_pool:
        raise ControllerNotFoundError(f"Resource pool '{resource_pool_id}' not found")

    success = await pools_repo.delete_resource_pool(resource_pool_id)
    if not success:
        raise ControllerError(f"Resource pool '{resource_pool_id}' could not be deleted")
    await rbac_repo.delete_all_ace_starting_with_path(f"/pools/{resource_pool_id}")


@router.get(
    "/{resource_pool_id}/resources",
    response_model=List[schemas.Resource],
    dependencies=[Depends(has_privilege("Pool.Audit"))]
)
async def get_pool_resources(
        resource_pool_id: UUID,
        pools_repo: ResourcePoolsRepository = Depends(get_repository(ResourcePoolsRepository)),
) -> List[schemas.Resource]:
    """
    Get all resource in a pool.

    Required privilege: Pool.Audit
    """

    return await pools_repo.get_pool_resources(resource_pool_id)


@router.put(
    "/{resource_pool_id}/resources/{resource_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(has_privilege("Pool.Modify"))]
)
async def add_resource_to_pool(
        resource_pool_id: UUID,
        resource_id: UUID,
        pools_repo: ResourcePoolsRepository = Depends(get_repository(ResourcePoolsRepository)),
) -> None:
    """
    Add resource to a resource pool.

    Required privilege: Pool.Modify
    """

    resource_pool = await pools_repo.get_resource_pool(resource_pool_id)
    if not resource_pool:
        raise ControllerNotFoundError(f"Resource pool '{resource_pool_id}' not found")

    # TODO: consider if a resource can belong to multiple pools
    resources = await pools_repo.get_pool_resources(resource_pool_id)
    for resource in resources:
        if resource.resource_id == resource_id:
            raise ControllerBadRequestError(f"Resource '{resource_id}' is already in '{resource_pool.name}'")

    # we only support projects in resource pools for now
    project = Controller.instance().get_project(str(resource_id))

    resource = await pools_repo.get_resource(resource_id)
    if not resource:
        # the resource is not in the database yet, create it
        resource_create = schemas.ResourceCreate(resource_id=resource_id, resource_type="project", name=project.name)
        resource = await pools_repo.create_resource(resource_create)

    await pools_repo.add_resource_to_pool(resource_pool_id, resource)


@router.delete(
    "/{resource_pool_id}/resources/{resource_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(has_privilege("Pool.Modify"))]
)
async def remove_resource_from_pool(
    resource_pool_id: UUID,
    resource_id: UUID,
    pools_repo: ResourcePoolsRepository = Depends(get_repository(ResourcePoolsRepository)),
) -> None:
    """
    Remove resource from a resource pool.

    Required privilege: Pool.Modify
    """

    resource = await pools_repo.get_resource(resource_id)
    if not resource:
        raise ControllerNotFoundError(f"Resource '{resource_id}' not found")

    resource_pool = await pools_repo.remove_resource_from_pool(resource_pool_id, resource)
    if not resource_pool:
        raise ControllerNotFoundError(f"Resource pool '{resource_pool_id}' not found")

    # TODO: consider if a resource can belong to multiple pools
    success = await pools_repo.delete_resource(resource.resource_id)
    if not success:
        raise ControllerError(f"Resource '{resource_id}' could not be deleted")
