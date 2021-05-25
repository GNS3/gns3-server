#!/usr/bin/env python
#
# Copyright (C) 2021 GNS3 Technologies Inc.
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
API routes for permissions.
"""

from fastapi import APIRouter, Depends, status
from uuid import UUID
from typing import List

from gns3server import schemas
from gns3server.controller.controller_error import (
    ControllerBadRequestError,
    ControllerNotFoundError,
    ControllerForbiddenError,
)

from gns3server.db.repositories.rbac import RbacRepository
from .dependencies.database import get_repository

import logging

log = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=List[schemas.Permission])
async def get_permissions(
        rbac_repo: RbacRepository = Depends(get_repository(RbacRepository))
) -> List[schemas.Permission]:
    """
    Get all permissions.
    """

    return await rbac_repo.get_permissions()


@router.post("", response_model=schemas.Permission, status_code=status.HTTP_201_CREATED)
async def create_permission(
        permission_create: schemas.PermissionCreate,
        rbac_repo: RbacRepository = Depends(get_repository(RbacRepository))
) -> schemas.Permission:
    """
    Create a new permission.
    """

    # if await rbac_repo.get_role_by_path(role_create.name):
    #     raise ControllerBadRequestError(f"Role '{role_create.name}' already exists")

    return await rbac_repo.create_permission(permission_create)


@router.get("/{permission_id}", response_model=schemas.Permission)
async def get_permission(
        permission_id: UUID,
        rbac_repo: RbacRepository = Depends(get_repository(RbacRepository)),
) -> schemas.Permission:
    """
    Get a permission.
    """

    permission = await rbac_repo.get_permission(permission_id)
    if not permission:
        raise ControllerNotFoundError(f"Permission '{permission_id}' not found")
    return permission


@router.put("/{permission_id}", response_model=schemas.Permission)
async def update_permission(
        permission_id: UUID,
        permission_update: schemas.PermissionUpdate,
        rbac_repo: RbacRepository = Depends(get_repository(RbacRepository))
) -> schemas.Permission:
    """
    Update a permission.
    """

    permission = await rbac_repo.get_permission(permission_id)
    if not permission:
        raise ControllerNotFoundError(f"Permission '{permission_id}' not found")

    #if not user_group.is_updatable:
    #    raise ControllerForbiddenError(f"User group '{user_group_id}' cannot be updated")

    return await rbac_repo.update_permission(permission_id, permission_update)


@router.delete("/{permission_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_permission(
    permission_id: UUID,
    rbac_repo: RbacRepository = Depends(get_repository(RbacRepository)),
) -> None:
    """
    Delete a permission.
    """

    permission = await rbac_repo.get_permission(permission_id)
    if not permission:
        raise ControllerNotFoundError(f"Permission '{permission_id}' not found")

    #if not user_group.is_updatable:
    #    raise ControllerForbiddenError(f"User group '{user_group_id}' cannot be deleted")

    success = await rbac_repo.delete_permission(permission_id)
    if not success:
        raise ControllerNotFoundError(f"Permission '{permission_id}' could not be deleted")
