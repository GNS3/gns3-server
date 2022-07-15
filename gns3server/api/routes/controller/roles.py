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
API routes for roles.
"""

from fastapi import APIRouter, Depends, Response, status
from uuid import UUID
from typing import List

from gns3server import schemas
from gns3server.controller.controller_error import (
    ControllerError,
    ControllerBadRequestError,
    ControllerNotFoundError,
    ControllerForbiddenError,
)

from gns3server.db.repositories.rbac import RbacRepository
from .dependencies.database import get_repository

import logging

log = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=List[schemas.Role])
async def get_roles(
        rbac_repo: RbacRepository = Depends(get_repository(RbacRepository))
) -> List[schemas.Role]:
    """
    Get all roles.
    """

    return await rbac_repo.get_roles()


@router.post("", response_model=schemas.Role, status_code=status.HTTP_201_CREATED)
async def create_role(
        role_create: schemas.RoleCreate,
        rbac_repo: RbacRepository = Depends(get_repository(RbacRepository))
) -> schemas.Role:
    """
    Create a new role.
    """

    if await rbac_repo.get_role_by_name(role_create.name):
        raise ControllerBadRequestError(f"Role '{role_create.name}' already exists")

    return await rbac_repo.create_role(role_create)


@router.get("/{role_id}", response_model=schemas.Role)
async def get_role(
        role_id: UUID,
        rbac_repo: RbacRepository = Depends(get_repository(RbacRepository)),
) -> schemas.Role:
    """
    Get a role.
    """

    role = await rbac_repo.get_role(role_id)
    if not role:
        raise ControllerNotFoundError(f"Role '{role_id}' not found")
    return role


@router.put("/{role_id}", response_model=schemas.Role)
async def update_role(
        role_id: UUID,
        role_update: schemas.RoleUpdate,
        rbac_repo: RbacRepository = Depends(get_repository(RbacRepository))
) -> schemas.Role:
    """
    Update a role.
    """

    role = await rbac_repo.get_role(role_id)
    if not role:
        raise ControllerNotFoundError(f"Role '{role_id}' not found")

    if role.is_builtin:
        raise ControllerForbiddenError(f"Built-in role '{role_id}' cannot be updated")

    return await rbac_repo.update_role(role_id, role_update)


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: UUID,
    rbac_repo: RbacRepository = Depends(get_repository(RbacRepository)),
) -> None:
    """
    Delete a role.
    """

    role = await rbac_repo.get_role(role_id)
    if not role:
        raise ControllerNotFoundError(f"Role '{role_id}' not found")

    if role.is_builtin:
        raise ControllerForbiddenError(f"Built-in role '{role_id}' cannot be deleted")

    success = await rbac_repo.delete_role(role_id)
    if not success:
        raise ControllerError(f"Role '{role_id}' could not be deleted")


@router.get("/{role_id}/permissions", response_model=List[schemas.Permission])
async def get_role_permissions(
        role_id: UUID,
        rbac_repo: RbacRepository = Depends(get_repository(RbacRepository))
) -> List[schemas.Permission]:
    """
    Get all role permissions.
    """

    return await rbac_repo.get_role_permissions(role_id)


@router.put(
    "/{role_id}/permissions/{permission_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
async def add_permission_to_role(
        role_id: UUID,
        permission_id: UUID,
        rbac_repo: RbacRepository = Depends(get_repository(RbacRepository))
) -> None:
    """
    Add a permission to a role.
    """

    permission = await rbac_repo.get_permission(permission_id)
    if not permission:
        raise ControllerNotFoundError(f"Permission '{permission_id}' not found")

    role = await rbac_repo.add_permission_to_role(role_id, permission)
    if not role:
        raise ControllerNotFoundError(f"Role '{role_id}' not found")


@router.delete(
    "/{role_id}/permissions/{permission_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
async def remove_permission_from_role(
    role_id: UUID,
    permission_id: UUID,
    rbac_repo: RbacRepository = Depends(get_repository(RbacRepository)),
) -> None:
    """
    Remove member from an user group.
    """

    permission = await rbac_repo.get_permission(permission_id)
    if not permission:
        raise ControllerNotFoundError(f"Permission '{permission_id}' not found")

    role = await rbac_repo.remove_permission_from_role(role_id, permission)
    if not role:
        raise ControllerNotFoundError(f"Role '{role_id}' not found")
