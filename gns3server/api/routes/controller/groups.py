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

from fastapi import APIRouter, Depends, HTTPException, status
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


# Model profile endpoints for user groups

@router.get(
    "/{user_group_id}/profiles",
    response_model=schemas.ModelConfigsResponse,
    dependencies=[Depends(has_privilege("Group.Audit"))]
)
async def get_group_model_profiles(
        user_group_id: UUID,
        users_repo: UsersRepository = Depends(get_repository(UsersRepository))
) -> schemas.ModelConfigsResponse:
    """
    Get all model profiles and the active profile for a user group.
    Includes the version for optimistic locking.

    Required privilege: Group.Audit
    """

    try:
        configs = await users_repo.get_group_model_configs(user_group_id)
        profiles = [schemas.ModelProfile(**p) for p in configs.get("profiles", [])]
        version = await users_repo._get_group_model_configs_version(user_group_id)
        return schemas.ModelConfigsResponse(
            profiles=profiles,
            active=configs.get("active", "default"),
            version=version or 0
        )
    except Exception as e:
        log.error(f"Failed to retrieve group model profiles: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve model profiles"
        )


@router.post(
    "/{user_group_id}/profiles",
    response_model=schemas.ModelProfile,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(has_privilege("Group.Modify"))]
)
async def create_group_model_profile(
        user_group_id: UUID,
        profile_data: schemas.ModelProfileCreate,
        users_repo: UsersRepository = Depends(get_repository(UsersRepository))
) -> schemas.ModelProfile:
    """
    Create a new model profile for a user group.

    Required privilege: Group.Modify
    """

    # Check if group exists
    user_group = await users_repo.get_user_group(user_group_id)
    if not user_group:
        raise ControllerNotFoundError(f"User group '{user_group_id}' not found")

    try:
        # Convert profile_data to dict to include extra fields
        profile_dict = profile_data.model_dump()
        new_profile = await users_repo.add_group_model_profile(user_group_id, profile_dict)
        return schemas.ModelProfile(**new_profile)
    except ValueError as e:
        # Handle both validation errors and optimistic lock errors
        if "Concurrent modification" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e)
            )
        raise ControllerBadRequestError(str(e))
    except Exception as e:
        log.error(f"Failed to create group model profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create model profile"
        )


@router.get(
    "/{user_group_id}/profiles/active",
    response_model=schemas.ModelProfile,
    dependencies=[Depends(has_privilege("Group.Audit"))]
)
async def get_active_group_model_profile(
        user_group_id: UUID,
        users_repo: UsersRepository = Depends(get_repository(UsersRepository))
) -> schemas.ModelProfile:
    """
    Get the currently active model profile for a user group.

    Required privilege: Group.Audit
    """

    profile = await users_repo.get_active_group_model_profile(user_group_id)

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No model profiles configured"
        )

    return schemas.ModelProfile(**profile)


@router.put(
    "/{user_group_id}/profiles/active",
    response_model=schemas.ModelConfigsResponse,
    dependencies=[Depends(has_privilege("Group.Modify"))]
)
async def set_active_group_model_profile(
        user_group_id: UUID,
        request: schemas.ActiveProfileRequest,
        users_repo: UsersRepository = Depends(get_repository(UsersRepository))
) -> schemas.ModelConfigsResponse:
    """
    Set the active model profile for a user group.
    If expected_version is provided, it will be validated for optimistic locking.

    Required privilege: Group.Modify
    """

    # Check if group exists
    user_group = await users_repo.get_user_group(user_group_id)
    if not user_group:
        raise ControllerNotFoundError(f"User group '{user_group_id}' not found")

    try:
        success = await users_repo.set_active_group_model_profile(user_group_id, request.profile_name)
    except ValueError as e:
        # Optimistic lock error
        if "Concurrent modification" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e)
            )
        raise

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Profile '{request.profile_name}' not found"
        )

    configs = await users_repo.get_group_model_configs(user_group_id)
    profiles = [schemas.ModelProfile(**p) for p in configs.get("profiles", [])]
    version = await users_repo._get_group_model_configs_version(user_group_id)
    return schemas.ModelConfigsResponse(
        profiles=profiles,
        active=configs.get("active", "default"),
        version=version or 0
    )


@router.put(
    "/{user_group_id}/profiles/{profile_name}",
    response_model=schemas.ModelProfile,
    dependencies=[Depends(has_privilege("Group.Modify"))]
)
async def update_group_model_profile(
        user_group_id: UUID,
        profile_name: str,
        profile_update: schemas.ModelProfileUpdate,
        users_repo: UsersRepository = Depends(get_repository(UsersRepository))
) -> schemas.ModelProfile:
    """
    Update an existing model profile for a user group.

    Required privilege: Group.Modify
    """

    # Check if group exists
    user_group = await users_repo.get_user_group(user_group_id)
    if not user_group:
        raise ControllerNotFoundError(f"User group '{user_group_id}' not found")

    try:
        # Build updates dict with only non-None values
        updates = {k: v for k, v in profile_update.model_dump().items() if v is not None}

        updated_profile = await users_repo.update_group_model_profile(
            user_group_id,
            profile_name,
            updates
        )

        if not updated_profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Profile '{profile_name}' not found"
            )

        return schemas.ModelProfile(**updated_profile)
    except HTTPException:
        raise
    except ValueError as e:
        # Handle optimistic lock errors
        if "Concurrent modification" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e)
            )
        raise ControllerBadRequestError(str(e))
    except Exception as e:
        log.error(f"Failed to update group model profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update model profile"
        )


@router.delete(
    "/{user_group_id}/profiles/{profile_name}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(has_privilege("Group.Modify"))]
)
async def delete_group_model_profile(
        user_group_id: UUID,
        profile_name: str,
        users_repo: UsersRepository = Depends(get_repository(UsersRepository))
) -> None:
    """
    Delete a model profile from a user group.
    If deleting the active profile, another profile will be set as active.

    Required privilege: Group.Modify
    """

    # Check if group exists
    user_group = await users_repo.get_user_group(user_group_id)
    if not user_group:
        raise ControllerNotFoundError(f"User group '{user_group_id}' not found")

    try:
        success = await users_repo.delete_group_model_profile(user_group_id, profile_name)
    except ValueError as e:
        # Handle optimistic lock errors
        if "Concurrent modification" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e)
            )
        raise ControllerBadRequestError(str(e))

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Profile '{profile_name}' not found"
        )
