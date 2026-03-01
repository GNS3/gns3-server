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
API routes for users.
"""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
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
from gns3server.services import auth_service

from .dependencies.authentication import get_current_active_user
from .dependencies.database import get_repository
from .dependencies.rbac import has_privilege

import logging

log = logging.getLogger(__name__)

router = APIRouter()


@router.post("/login", response_model=schemas.Token)
async def login(
    users_repo: UsersRepository = Depends(get_repository(UsersRepository)),
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> schemas.Token:
    """
    Default user login method using forms (x-www-form-urlencoded).
    Example: curl -X POST http://host:port/v3/access/users/login -H "Content-Type: application/x-www-form-urlencoded" -d "username=admin&password=admin"
    """

    user = await users_repo.authenticate_user(username=form_data.username, password=form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication was unsuccessful.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = schemas.Token(access_token=auth_service.create_access_token(user.username), token_type="bearer")
    return token


@router.post("/authenticate", response_model=schemas.Token)
async def authenticate(
    user_credentials: schemas.Credentials,
    users_repo: UsersRepository = Depends(get_repository(UsersRepository)),
) -> schemas.Token:
    """
    Alternative authentication method using json.
    Example: curl -X POST http://host:port/v3/access/users/authenticate -d '{"username": "admin", "password": "admin"}' -H "Content-Type: application/json"
    """

    user = await users_repo.authenticate_user(username=user_credentials.username, password=user_credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication was unsuccessful.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = schemas.Token(access_token=auth_service.create_access_token(user.username), token_type="bearer")
    return token


@router.get("/me", response_model=schemas.User)
async def get_logged_in_user(current_user: schemas.User = Depends(get_current_active_user)) -> schemas.User:
    """
    Get the current active user.
    """

    return current_user


@router.put("/me", response_model=schemas.User)
async def update_logged_in_user(
        user_update: schemas.LoggedInUserUpdate,
        current_user: schemas.User = Depends(get_current_active_user),
        users_repo: UsersRepository = Depends(get_repository(UsersRepository))
) -> schemas.User:
    """
    Update the current active user.
    """

    if user_update.email and await users_repo.get_user_by_email(user_update.email):
        raise ControllerBadRequestError(f"Email '{user_update.email}' is already registered")

    return await users_repo.update_user(current_user.user_id, user_update)


@router.get(
    "",
    response_model=List[schemas.User],
    dependencies=[Depends(has_privilege("User.Audit"))]
)
async def get_users(
        users_repo: UsersRepository = Depends(get_repository(UsersRepository))
) -> List[schemas.User]:
    """
    Get all users.

    Required privilege: User.Audit
    """

    return await users_repo.get_users()


@router.post(
    "",
    response_model=schemas.User,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(has_privilege("User.Allocate"))]
)
async def create_user(
        user_create: schemas.UserCreate,
        users_repo: UsersRepository = Depends(get_repository(UsersRepository))
) -> schemas.User:
    """
    Create a new user.

    Required privilege: User.Allocate
    """

    if await users_repo.get_user_by_username(user_create.username):
        raise ControllerBadRequestError(f"Username '{user_create.username}' is already registered")

    if user_create.email and await users_repo.get_user_by_email(user_create.email):
        raise ControllerBadRequestError(f"Email '{user_create.email}' is already registered")

    return await users_repo.create_user(user_create)


@router.get(
    "/{user_id}",
    response_model=schemas.User,
    dependencies=[Depends(has_privilege("User.Audit"))]
)
async def get_user(
        user_id: UUID,
        users_repo: UsersRepository = Depends(get_repository(UsersRepository)),
) -> schemas.User:
    """
    Get a user.

    Required privilege: User.Audit
    """

    user = await users_repo.get_user(user_id)
    if not user:
        raise ControllerNotFoundError(f"User '{user_id}' not found")
    return user


@router.put(
    "/{user_id}",
    response_model=schemas.User,
    dependencies=[Depends(has_privilege("User.Modify"))]
)
async def update_user(
        user_id: UUID,
        user_update: schemas.UserUpdate,
        users_repo: UsersRepository = Depends(get_repository(UsersRepository))
) -> schemas.User:
    """
    Update a user.

    Required privilege: User.Modify
    """

    if user_update.username and await users_repo.get_user_by_username(user_update.username):
        raise ControllerBadRequestError(f"Username '{user_update.username}' is already registered")

    if user_update.email and await users_repo.get_user_by_email(user_update.email):
        raise ControllerBadRequestError(f"Email '{user_update.email}' is already registered")

    user = await users_repo.update_user(user_id, user_update)
    if not user:
        raise ControllerNotFoundError(f"User '{user_id}' not found")
    return user


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(has_privilege("User.Allocate"))]
)
async def delete_user(
        user_id: UUID,
        users_repo: UsersRepository = Depends(get_repository(UsersRepository)),
        rbac_repo: RbacRepository = Depends(get_repository(RbacRepository))
) -> None:
    """
    Delete a user.

    Required privilege: User.Allocate
    """

    user = await users_repo.get_user(user_id)
    if not user:
        raise ControllerNotFoundError(f"User '{user_id}' not found")

    if user.is_superadmin:
        raise ControllerForbiddenError("The super admin cannot be deleted")

    success = await users_repo.delete_user(user_id)
    if not success:
        raise ControllerError(f"User '{user_id}' could not be deleted")
    await rbac_repo.delete_all_ace_starting_with_path(f"/users/{user_id}")


@router.get(
    "/{user_id}/groups",
    response_model=List[schemas.UserGroup],
    dependencies=[Depends(has_privilege("Group.Audit"))]
)
async def get_user_memberships(
        user_id: UUID,
        users_repo: UsersRepository = Depends(get_repository(UsersRepository))
) -> List[schemas.UserGroup]:
    """
    Get user memberships.

    Required privilege: Group.Audit
    """

    return await users_repo.get_user_memberships(user_id)


# User settings endpoints

@router.get("/settings", response_model=schemas.UserSettingsResponse)
async def get_user_settings(
        current_user: schemas.User = Depends(get_current_active_user),
        users_repo: UsersRepository = Depends(get_repository(UsersRepository))
) -> schemas.UserSettingsResponse:
    """
    Get all settings for the current user.
    """

    try:
        settings_db = await users_repo.get_user_settings(current_user.user_id)
        settings = {setting.key: setting.value for setting in settings_db if setting.value is not None}
        return schemas.UserSettingsResponse(user_id=current_user.user_id, settings=settings)
    except Exception as e:
        log.error(f"Failed to retrieve user settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user settings"
        )


@router.put("/settings", response_model=schemas.UserSettingsResponse)
async def update_user_settings(
        settings_update: schemas.UserSettingsUpdate,
        current_user: schemas.User = Depends(get_current_active_user),
        users_repo: UsersRepository = Depends(get_repository(UsersRepository))
) -> schemas.UserSettingsResponse:
    """
    Update all settings for the current user.

    Required keys (MODE_PROVIDER, MODEL_NAME, MODEL_API_KEY, BASE_URL, TEMPERATURE)
    will be reset to default values if not provided.
    """

    try:
        # Define required keys with default values
        required_keys = {
            "MODE_PROVIDER": "openai",
            "MODEL_NAME": "gpt-3.5-turbo",
            "MODEL_API_KEY": "",
            "BASE_URL": "https://api.openai.com/v1",
            "TEMPERATURE": "0.7"
        }

        # Merge provided settings with defaults for required keys
        settings_to_update = required_keys.copy()
        settings_to_update.update(settings_update.settings)

        await users_repo.delete_all_user_settings(current_user.user_id)
        await users_repo.set_user_settings(current_user.user_id, settings_to_update)

        return schemas.UserSettingsResponse(user_id=current_user.user_id, settings=settings_to_update)
    except Exception as e:
        log.error(f"Failed to update user settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user settings"
        )


@router.get("/settings/{key}", response_model=Dict[str, str])
async def get_user_setting(
        key: str,
        current_user: schemas.User = Depends(get_current_active_user),
        users_repo: UsersRepository = Depends(get_repository(UsersRepository))
) -> Dict[str, str]:
    """
    Get a specific setting for the current user.
    """

    setting = await users_repo.get_user_setting(current_user.user_id, key)
    if not setting or setting.value is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Setting '{key}' not found"
        )
    return {key: setting.value}


@router.put("/settings/{key}", response_model=Dict[str, str])
async def update_user_setting(
        key: str,
        setting_value: schemas.UserSettingValue,
        current_user: schemas.User = Depends(get_current_active_user),
        users_repo: UsersRepository = Depends(get_repository(UsersRepository))
) -> Dict[str, str]:
    """
    Set a specific setting for the current user.
    """

    try:
        setting = await users_repo.set_user_setting(current_user.user_id, key, setting_value.value)
        return {key: setting.value}
    except Exception as e:
        log.error(f"Failed to update user setting: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user setting"
        )


@router.delete("/settings/{key}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_setting(
        key: str,
        current_user: schemas.User = Depends(get_current_active_user),
        users_repo: UsersRepository = Depends(get_repository(UsersRepository))
) -> None:
    """
    Delete a specific setting for the current user.

    Required keys (MODE_PROVIDER, MODEL_NAME, MODEL_API_KEY, BASE_URL, TEMPERATURE)
    will be reset to default values instead of being deleted.
    """

    # Required keys with default values
    required_keys_defaults = {
        "MODE_PROVIDER": "openai",
        "MODEL_NAME": "gpt-3.5-turbo",
        "MODEL_API_KEY": "",
        "BASE_URL": "https://api.openai.com/v1",
        "TEMPERATURE": "0.7"
    }

    if key in required_keys_defaults:
        # Reset to default instead of deleting
        await users_repo.set_user_setting(current_user.user_id, key, required_keys_defaults[key])
    else:
        success = await users_repo.delete_user_setting(current_user.user_id, key)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Setting '{key}' not found"
            )


# Model profile endpoints

@router.get("/settings/model/profiles", response_model=schemas.ModelConfigsResponse)
async def get_model_profiles(
        current_user: schemas.User = Depends(get_current_active_user),
        users_repo: UsersRepository = Depends(get_repository(UsersRepository))
) -> schemas.ModelConfigsResponse:
    """
    Get all model profiles and the active profile.
    """

    try:
        configs = await users_repo.get_model_configs(current_user.user_id)
        profiles = [schemas.ModelProfile(**p) for p in configs.get("profiles", [])]
        return schemas.ModelConfigsResponse(profiles=profiles, active=configs.get("active", "default"))
    except Exception as e:
        log.error(f"Failed to retrieve model profiles: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve model profiles"
        )


@router.post("/settings/model/profiles", response_model=schemas.ModelProfile, status_code=status.HTTP_201_CREATED)
async def create_model_profile(
        profile_data: schemas.ModelProfileCreate,
        current_user: schemas.User = Depends(get_current_active_user),
        users_repo: UsersRepository = Depends(get_repository(UsersRepository))
) -> schemas.ModelProfile:
    """
    Create a new model profile.
    """

    try:
        new_profile = await users_repo.add_model_profile(
            current_user.user_id,
            profile_data.name,
            profile_data.provider,
            profile_data.model,
            profile_data.api_key,
            profile_data.base_url,
            profile_data.temperature
        )
        return schemas.ModelProfile(**new_profile)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        log.error(f"Failed to create model profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create model profile"
        )


@router.put("/settings/model/profiles/{profile_name}", response_model=schemas.ModelProfile)
async def update_model_profile(
        profile_name: str,
        profile_update: schemas.ModelProfileUpdate,
        current_user: schemas.User = Depends(get_current_active_user),
        users_repo: UsersRepository = Depends(get_repository(UsersRepository))
) -> schemas.ModelProfile:
    """
    Update an existing model profile.
    """

    try:
        # Build updates dict with only non-None values
        updates = {k: v for k, v in profile_update.model_dump().items() if v is not None}

        updated_profile = await users_repo.update_model_profile(
            current_user.user_id,
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
    except Exception as e:
        log.error(f"Failed to update model profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update model profile"
        )


@router.delete("/settings/model/profiles/{profile_name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model_profile(
        profile_name: str,
        current_user: schemas.User = Depends(get_current_active_user),
        users_repo: UsersRepository = Depends(get_repository(UsersRepository))
) -> None:
    """
    Delete a model profile.
    If deleting the active profile, another profile will be set as active.
    """

    success = await users_repo.delete_model_profile(current_user.user_id, profile_name)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Profile '{profile_name}' not found"
        )


@router.put("/settings/model/active", response_model=schemas.ModelConfigsResponse)
async def set_active_model_profile(
        request: schemas.ActiveProfileRequest,
        current_user: schemas.User = Depends(get_current_active_user),
        users_repo: UsersRepository = Depends(get_repository(UsersRepository))
) -> schemas.ModelConfigsResponse:
    """
    Set the active model profile.
    """

    success = await users_repo.set_active_model_profile(current_user.user_id, request.profile_name)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Profile '{request.profile_name}' not found"
        )

    configs = await users_repo.get_model_configs(current_user.user_id)
    profiles = [schemas.ModelProfile(**p) for p in configs.get("profiles", [])]
    return schemas.ModelConfigsResponse(profiles=profiles, active=configs.get("active", "default"))


@router.get("/settings/model/active", response_model=schemas.ModelProfile)
async def get_active_model_profile(
        current_user: schemas.User = Depends(get_current_active_user),
        users_repo: UsersRepository = Depends(get_repository(UsersRepository))
) -> schemas.ModelProfile:
    """
    Get the currently active model profile.
    """

    profile = await users_repo.get_active_model_profile(current_user.user_id)

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No model profiles configured"
        )

    return schemas.ModelProfile(**profile)
