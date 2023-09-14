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
API routes for user groups.
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

from gns3server.db.repositories.users import UsersRepository
from gns3server.db.repositories.rbac import RbacRepository

from .dependencies.rbac import has_privilege
from .dependencies.database import get_repository

import logging

log = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "",
    response_model=List[schemas.UserGroup],
    dependencies=[Depends(has_privilege("Group.Audit"))]
)
async def get_user_groups(
        users_repo: UsersRepository = Depends(get_repository(UsersRepository))
) -> List[schemas.UserGroup]:
    """
    Get all user groups.

    Required privilege: Group.Audit
    """

    return await users_repo.get_user_groups()


@router.post(
    "",
    response_model=schemas.UserGroup,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(has_privilege("Group.Allocate"))]
)
async def create_user_group(
        user_group_create: schemas.UserGroupCreate,
        users_repo: UsersRepository = Depends(get_repository(UsersRepository))
) -> schemas.UserGroup:
    """
    Create a new user group.

    Required privilege: Group.Allocate
    """

    if await users_repo.get_user_group_by_name(user_group_create.name):
        raise ControllerBadRequestError(f"User group '{user_group_create.name}' already exists")

    return await users_repo.create_user_group(user_group_create)


@router.get(
    "/{user_group_id}",
    response_model=schemas.UserGroup,
    dependencies=[Depends(has_privilege("Group.Audit"))]
)
async def get_user_group(
        user_group_id: UUID,
        users_repo: UsersRepository = Depends(get_repository(UsersRepository)),
) -> schemas.UserGroup:
    """
    Get a user group.

    Required privilege: Group.Audit
    """

    user_group = await users_repo.get_user_group(user_group_id)
    if not user_group:
        raise ControllerNotFoundError(f"User group '{user_group_id}' not found")
    return user_group


@router.put(
    "/{user_group_id}",
    response_model=schemas.UserGroup,
    dependencies=[Depends(has_privilege("Group.Modify"))]
)
async def update_user_group(
        user_group_id: UUID,
        user_group_update: schemas.UserGroupUpdate,
        users_repo: UsersRepository = Depends(get_repository(UsersRepository))
) -> schemas.UserGroup:
    """
    Update a user group.

    Required privilege: Group.Modify
    """
    user_group = await users_repo.get_user_group(user_group_id)
    if not user_group:
        raise ControllerNotFoundError(f"User group '{user_group_id}' not found")

    if user_group.is_builtin:
        raise ControllerForbiddenError(f"Built-in user group '{user_group_id}' cannot be updated")

    return await users_repo.update_user_group(user_group_id, user_group_update)


@router.delete(
    "/{user_group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(has_privilege("Group.Allocate"))]
)
async def delete_user_group(
        user_group_id: UUID,
        users_repo: UsersRepository = Depends(get_repository(UsersRepository)),
        rbac_repo: RbacRepository = Depends(get_repository(RbacRepository))
) -> None:
    """
    Delete a user group.

    Required privilege: Group.Allocate
    """

    user_group = await users_repo.get_user_group(user_group_id)
    if not user_group:
        raise ControllerNotFoundError(f"User group '{user_group_id}' not found")

    if user_group.is_builtin:
        raise ControllerForbiddenError(f"Built-in user group '{user_group_id}' cannot be deleted")

    success = await users_repo.delete_user_group(user_group_id)
    if not success:
        raise ControllerError(f"User group '{user_group_id}' could not be deleted")
    await rbac_repo.delete_all_ace_starting_with_path(f"/groups/{user_group_id}")


@router.get(
    "/{user_group_id}/members",
    response_model=List[schemas.User],
    dependencies=[Depends(has_privilege("Group.Audit"))]
)
async def get_user_group_members(
        user_group_id: UUID,
        users_repo: UsersRepository = Depends(get_repository(UsersRepository))
) -> List[schemas.User]:
    """
    Get all user group members.

    Required privilege: Group.Audit
    """

    return await users_repo.get_user_group_members(user_group_id)


@router.put(
    "/{user_group_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(has_privilege("Group.Modify"))]
)
async def add_member_to_group(
        user_group_id: UUID,
        user_id: UUID,
        users_repo: UsersRepository = Depends(get_repository(UsersRepository))
) -> None:
    """
    Add member to a user group.

    Required privilege: Group.Modify
    """

    user = await users_repo.get_user(user_id)
    if not user:
        raise ControllerNotFoundError(f"User '{user_id}' not found")

    user_groups = await users_repo.get_user_memberships(user_id)
    for group in user_groups:
        if group.user_group_id == user_group_id:
            raise ControllerBadRequestError(f"Username '{user.username}' is already member of group '{group.name}'")

    user_group = await users_repo.add_member_to_user_group(user_group_id, user)
    if not user_group:
        raise ControllerNotFoundError(f"User group '{user_group_id}' not found")


@router.delete(
    "/{user_group_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(has_privilege("Group.Modify"))]
)
async def remove_member_from_group(
    user_group_id: UUID,
    user_id: UUID,
    users_repo: UsersRepository = Depends(get_repository(UsersRepository)),
) -> None:
    """
    Remove member from a user group.

    Required privilege: Group.Modify
    """

    user = await users_repo.get_user(user_id)
    if not user:
        raise ControllerNotFoundError(f"User '{user_id}' not found")

    user_group = await users_repo.remove_member_from_user_group(user_group_id, user)
    if not user_group:
        raise ControllerNotFoundError(f"User group '{user_group_id}' not found")
