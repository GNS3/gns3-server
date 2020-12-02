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

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from uuid import UUID
from typing import List

from gns3server import schemas
from gns3server.controller.controller_error import ControllerBadRequestError, ControllerNotFoundError
from gns3server.db.repositories.users import UsersRepository
from gns3server.services import auth_service

from .dependencies.authentication import get_current_active_user

import logging
log = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=List[schemas.User])
async def get_users(user_repo: UsersRepository = Depends()) -> List[schemas.User]:
    """
    Get all users.
    """

    users = await user_repo.get_users()
    return users


@router.post("", response_model=schemas.User, status_code=status.HTTP_201_CREATED)
async def create_user(new_user: schemas.UserCreate, user_repo: UsersRepository = Depends()) -> schemas.User:
    """
    Create a new user.
    """

    if await user_repo.get_user_by_username(new_user.username):
        raise ControllerBadRequestError(f"Username '{new_user.username}' is already registered")

    if new_user.email and await user_repo.get_user_by_email(new_user.email):
        raise ControllerBadRequestError(f"Email '{new_user.email}' is already registered")

    return await user_repo.create_user(new_user)


@router.get("/{user_id}", response_model=schemas.User)
async def get_user(user_id: UUID, user_repo: UsersRepository = Depends()) -> schemas.User:
    """
    Get an user.
    """

    user = await user_repo.get_user(user_id)
    if not user:
        raise ControllerNotFoundError(f"User '{user_id}' not found")
    return user


@router.put("/{user_id}", response_model=schemas.User)
async def update_user(user_id: UUID,
                      update_user: schemas.UserUpdate,
                      user_repo: UsersRepository = Depends()) -> schemas.User:
    """
    Update an user.
    """

    user = await user_repo.update_user(user_id, update_user)
    if not user:
        raise ControllerNotFoundError(f"User '{user_id}' not found")
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: UUID, user_repo: UsersRepository = Depends()):
    """
    Delete an user.
    """

    success = await user_repo.delete_user(user_id)
    if not success:
        raise ControllerNotFoundError(f"User '{user_id}' not found")


@router.post("/login", response_model=schemas.Token)
async def login(user_repo: UsersRepository = Depends(),
                form_data: OAuth2PasswordRequestForm = Depends()) -> schemas.Token:
    """
    User login.
    """

    user = await user_repo.authenticate_user(username=form_data.username, password=form_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Authentication was unsuccessful.",
                            headers={"WWW-Authenticate": "Bearer"})

    token = schemas.Token(access_token=auth_service.create_access_token(user.username), token_type="bearer")
    return token


@router.get("/users/me/", response_model=schemas.User)
async def get_current_active_user(current_user: schemas.User = Depends(get_current_active_user)) -> schemas.User:
    """
    Get the current active user.
    """

    return current_user
