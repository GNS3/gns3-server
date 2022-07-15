#!/usr/bin/env python
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
    Example: curl http://host:port/v3/users/login -H "Content-Type: application/x-www-form-urlencoded" -d "username=admin&password=admin"
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
    Example: curl http://host:port/v3/users/authenticate -d '{"username": "admin", "password": "admin"}' -H "Content-Type: application/json"
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


@router.get("", response_model=List[schemas.User], dependencies=[Depends(get_current_active_user)])
async def get_users(
        users_repo: UsersRepository = Depends(get_repository(UsersRepository))
) -> List[schemas.User]:
    """
    Get all users.
    """

    return await users_repo.get_users()


@router.post(
    "",
    response_model=schemas.User,
    dependencies=[Depends(get_current_active_user)],
    status_code=status.HTTP_201_CREATED
)
async def create_user(
        user_create: schemas.UserCreate,
        users_repo: UsersRepository = Depends(get_repository(UsersRepository))
) -> schemas.User:
    """
    Create a new user.
    """

    if await users_repo.get_user_by_username(user_create.username):
        raise ControllerBadRequestError(f"Username '{user_create.username}' is already registered")

    if user_create.email and await users_repo.get_user_by_email(user_create.email):
        raise ControllerBadRequestError(f"Email '{user_create.email}' is already registered")

    return await users_repo.create_user(user_create)


@router.get("/{user_id}", dependencies=[Depends(get_current_active_user)], response_model=schemas.User)
async def get_user(
        user_id: UUID,
        users_repo: UsersRepository = Depends(get_repository(UsersRepository)),
) -> schemas.User:
    """
    Get an user.
    """

    user = await users_repo.get_user(user_id)
    if not user:
        raise ControllerNotFoundError(f"User '{user_id}' not found")
    return user


@router.put("/{user_id}", dependencies=[Depends(get_current_active_user)], response_model=schemas.User)
async def update_user(
        user_id: UUID,
        user_update: schemas.UserUpdate,
        users_repo: UsersRepository = Depends(get_repository(UsersRepository))
) -> schemas.User:
    """
    Update an user.
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
    dependencies=[Depends(get_current_active_user)],
    status_code=status.HTTP_204_NO_CONTENT
)
async def delete_user(
    user_id: UUID,
    users_repo: UsersRepository = Depends(get_repository(UsersRepository)),
) -> None:
    """
    Delete an user.
    """

    user = await users_repo.get_user(user_id)
    if not user:
        raise ControllerNotFoundError(f"User '{user_id}' not found")

    if user.is_superadmin:
        raise ControllerForbiddenError("The super admin cannot be deleted")

    success = await users_repo.delete_user(user_id)
    if not success:
        raise ControllerError(f"User '{user_id}' could not be deleted")


@router.get(
    "/{user_id}/groups",
    dependencies=[Depends(get_current_active_user)],
    response_model=List[schemas.UserGroup]
)
async def get_user_memberships(
        user_id: UUID,
        users_repo: UsersRepository = Depends(get_repository(UsersRepository))
) -> List[schemas.UserGroup]:
    """
    Get user memberships.
    """

    return await users_repo.get_user_memberships(user_id)


@router.get(
    "/{user_id}/permissions",
    dependencies=[Depends(get_current_active_user)],
    response_model=List[schemas.Permission]
)
async def get_user_permissions(
        user_id: UUID,
        rbac_repo: RbacRepository = Depends(get_repository(RbacRepository))
) -> List[schemas.Permission]:
    """
    Get user permissions.
    """

    return await rbac_repo.get_user_permissions(user_id)


@router.put(
    "/{user_id}/permissions/{permission_id}",
    dependencies=[Depends(get_current_active_user)],
    status_code=status.HTTP_204_NO_CONTENT
)
async def add_permission_to_user(
        user_id: UUID,
        permission_id: UUID,
        rbac_repo: RbacRepository = Depends(get_repository(RbacRepository))
) -> None:
    """
    Add a permission to an user.
    """

    permission = await rbac_repo.get_permission(permission_id)
    if not permission:
        raise ControllerNotFoundError(f"Permission '{permission_id}' not found")

    user = await rbac_repo.add_permission_to_user(user_id, permission)
    if not user:
        raise ControllerNotFoundError(f"User '{user_id}' not found")


@router.delete(
    "/{user_id}/permissions/{permission_id}",
    dependencies=[Depends(get_current_active_user)],
    status_code=status.HTTP_204_NO_CONTENT
)
async def remove_permission_from_user(
    user_id: UUID,
    permission_id: UUID,
    rbac_repo: RbacRepository = Depends(get_repository(RbacRepository)),
) -> None:
    """
    Remove permission from an user.
    """

    permission = await rbac_repo.get_permission(permission_id)
    if not permission:
        raise ControllerNotFoundError(f"Permission '{permission_id}' not found")

    user = await rbac_repo.remove_permission_from_user(user_id, permission)
    if not user:
        raise ControllerNotFoundError(f"User '{user_id}' not found")
