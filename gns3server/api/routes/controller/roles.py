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

from fastapi import APIRouter, Depends, status
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
from .dependencies.rbac import has_privilege

import logging

log = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "",
    response_model=List[schemas.Role],
    dependencies=[Depends(has_privilege("Role.Audit"))]
)
async def get_roles(
        rbac_repo: RbacRepository = Depends(get_repository(RbacRepository))
) -> List[schemas.Role]:
    """
    Get all roles.

    Required privilege: Role.Audit
    """

    return await rbac_repo.get_roles()


@router.post(
    "",
    response_model=schemas.Role,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(has_privilege("Role.Allocate"))]
)
async def create_role(
        role_create: schemas.RoleCreate,
        rbac_repo: RbacRepository = Depends(get_repository(RbacRepository))
) -> schemas.Role:
    """
    Create a new role.

    Required privilege: Role.Allocate
    """

    if await rbac_repo.get_role_by_name(role_create.name):
        raise ControllerBadRequestError(f"Role '{role_create.name}' already exists")

    return await rbac_repo.create_role(role_create)


@router.get(
    "/{role_id}",
    response_model=schemas.Role,
    dependencies=[Depends(has_privilege("Role.Audit"))]
)
async def get_role(
        role_id: UUID,
        rbac_repo: RbacRepository = Depends(get_repository(RbacRepository)),
) -> schemas.Role:
    """
    Get a role.

    Required privilege: Role.Audit
    """

    role = await rbac_repo.get_role(role_id)
    if not role:
        raise ControllerNotFoundError(f"Role '{role_id}' not found")
    return role


@router.put(
    "/{role_id}",
    response_model=schemas.Role,
    dependencies=[Depends(has_privilege("Role.Modify"))]
)
async def update_role(
        role_id: UUID,
        role_update: schemas.RoleUpdate,
        rbac_repo: RbacRepository = Depends(get_repository(RbacRepository))
) -> schemas.Role:
    """
    Update a role.

    Required privilege: Role.Modify
    """

    role = await rbac_repo.get_role(role_id)
    if not role:
        raise ControllerNotFoundError(f"Role '{role_id}' not found")

    if role.is_builtin:
        raise ControllerForbiddenError(f"Built-in role '{role_id}' cannot be updated")

    return await rbac_repo.update_role(role_id, role_update)


@router.delete(
    "/{role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(has_privilege("Role.Allocate"))]
)
async def delete_role(
    role_id: UUID,
    rbac_repo: RbacRepository = Depends(get_repository(RbacRepository)),
) -> None:
    """
    Delete a role.

    Required privilege: Role.Allocate
    """

    role = await rbac_repo.get_role(role_id)
    if not role:
        raise ControllerNotFoundError(f"Role '{role_id}' not found")

    if role.is_builtin:
        raise ControllerForbiddenError(f"Built-in role '{role_id}' cannot be deleted")

    success = await rbac_repo.delete_role(role_id)
    if not success:
        raise ControllerError(f"Role '{role_id}' could not be deleted")
    await rbac_repo.delete_all_ace_starting_with_path(f"/roles/{role_id}")


@router.get(
    "/{role_id}/privileges",
    response_model=List[schemas.Privilege],
    dependencies=[Depends(has_privilege("Role.Audit"))]
)
async def get_role_privileges(
        role_id: UUID,
        rbac_repo: RbacRepository = Depends(get_repository(RbacRepository))
) -> List[schemas.Privilege]:
    """
    Get all role privileges.

    Required privilege: Role.Audit
    """

    return await rbac_repo.get_role_privileges(role_id)


@router.put(
    "/{role_id}/privileges/{privilege_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(has_privilege("Role.Modify"))]
)
async def add_privilege_to_role(
        role_id: UUID,
        privilege_id: UUID,
        rbac_repo: RbacRepository = Depends(get_repository(RbacRepository))
) -> None:
    """
    Add a privilege to a role.

    Required privilege: Role.Modify
    """

    privilege = await rbac_repo.get_privilege(privilege_id)
    if not privilege:
        raise ControllerNotFoundError(f"Privilege '{privilege_id}' not found")

    role = await rbac_repo.add_privilege_to_role(role_id, privilege)
    if not role:
        raise ControllerNotFoundError(f"Role '{role_id}' not found")


@router.delete(
    "/{role_id}/privileges/{privilege_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(has_privilege("Role.Modify"))]
)
async def remove_privilege_from_role(
    role_id: UUID,
    privilege_id: UUID,
    rbac_repo: RbacRepository = Depends(get_repository(RbacRepository)),
) -> None:
    """
    Remove privilege from a role.

    Required privilege: Role.Modify
    """

    privilege = await rbac_repo.get_privilege(privilege_id)
    if not privilege:
        raise ControllerNotFoundError(f"Privilege '{privilege_id}' not found")

    role = await rbac_repo.remove_privilege_from_role(role_id, privilege)
    if not role:
        raise ControllerNotFoundError(f"Role '{role_id}' not found")
