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

import re

from fastapi import APIRouter, Depends, Response, Request, status
from fastapi.routing import APIRoute
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
from .dependencies.authentication import get_current_active_user

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
        request: Request,
        permission_create: schemas.PermissionCreate,
        current_user: schemas.User = Depends(get_current_active_user),
        rbac_repo: RbacRepository = Depends(get_repository(RbacRepository))
) -> schemas.Permission:
    """
    Create a new permission.
    """

    # TODO: should we prevent having multiple permissions with same methods/path?
    #if await rbac_repo.check_permission_exists(permission_create):
    #    raise ControllerBadRequestError(f"Permission '{permission_create.methods} {permission_create.path} "
    #                                    f"{permission_create.action}' already exists")

    for route in request.app.routes:
        if isinstance(route, APIRoute):

            # remove the prefix (e.g. "/v3") from the route path
            route_path = re.sub(r"^/v[0-9]", "", route.path)
            # replace route path ID parameters by an UUID regex
            route_path = re.sub(r"{\w+_id}", "[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", route_path)
            # replace remaining route path parameters by an word matching regex
            route_path = re.sub(r"/{[\w:]+}", r"/\\w+", route_path)

            # the permission can match multiple routes
            if permission_create.path.endswith("/*"):
                route_path += r"/.*"

            if re.fullmatch(route_path, permission_create.path):
                for method in permission_create.methods:
                    if method in list(route.methods):
                        # check user has the right to add the permission (i.e has already to right on the path)
                        if not await rbac_repo.check_user_is_authorized(current_user.user_id, method, permission_create.path):
                            raise ControllerForbiddenError(f"User '{current_user.username}' doesn't have the rights to "
                                                           f"add a permission on {method} {permission_create.path} or "
                                                           f"the endpoint doesn't exist")
                        return await rbac_repo.create_permission(permission_create)

    raise ControllerBadRequestError(f"Permission '{permission_create.methods} {permission_create.path}' "
                                    f"doesn't match any existing endpoint")


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

    success = await rbac_repo.delete_permission(permission_id)
    if not success:
        raise ControllerNotFoundError(f"Permission '{permission_id}' could not be deleted")


@router.post("/prune", status_code=status.HTTP_204_NO_CONTENT)
async def prune_permissions(
        rbac_repo: RbacRepository = Depends(get_repository(RbacRepository))
) -> None:
    """
    Prune orphaned permissions.
    """

    await rbac_repo.prune_permissions()
