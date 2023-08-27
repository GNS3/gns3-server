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
API routes for ACL.
"""

import re

from fastapi import APIRouter, Depends, Request, status
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


@router.get("", response_model=List[schemas.ACE])
async def get_aces(
        rbac_repo: RbacRepository = Depends(get_repository(RbacRepository))
) -> List[schemas.ACE]:
    """
    Get all ACL entries.
    """

    return await rbac_repo.get_aces()


@router.post("", response_model=schemas.ACE, status_code=status.HTTP_201_CREATED)
async def create_ace(
        request: Request,
        ace_create: schemas.ACECreate,
        current_user: schemas.User = Depends(get_current_active_user),
        rbac_repo: RbacRepository = Depends(get_repository(RbacRepository))
) -> schemas.ACE:
    """
    Create a new ACL entry.
    """

    for route in request.app.routes:
        if isinstance(route, APIRoute):

            # remove the prefix (e.g. "/v3") from the route path
            route_path = re.sub(r"^/v[0-9]", "", route.path)
            # replace route path ID parameters by a UUID regex
            route_path = re.sub(r"{\w+_id}", "[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", route_path)
            # replace remaining route path parameters by a word matching regex
            route_path = re.sub(r"/{[\w:]+}", r"/\\w+", route_path)

            if re.fullmatch(route_path, ace_create.path):
                log.info("Creating ACE for route path", ace_create.path, route_path)
                return await rbac_repo.create_ace(ace_create)

    raise ControllerBadRequestError(f"Path '{ace_create.path}' doesn't match any existing endpoint")


@router.get("/{ace_id}", response_model=schemas.ACE)
async def get_ace(
        ace_id: UUID,
        rbac_repo: RbacRepository = Depends(get_repository(RbacRepository)),
) -> schemas.ACE:
    """
    Get an ACL entry.
    """

    ace = await rbac_repo.get_ace(ace_id)
    if not ace:
        raise ControllerNotFoundError(f"ACL entry '{ace_id}' not found")
    return ace


@router.put("/{ace_id}", response_model=schemas.ACE)
async def update_ace(
        ace_id: UUID,
        ace_update: schemas.ACEUpdate,
        rbac_repo: RbacRepository = Depends(get_repository(RbacRepository))
) -> schemas.ACE:
    """
    Update an ACL entry.
    """

    ace = await rbac_repo.get_ace(ace_id)
    if not ace:
        raise ControllerNotFoundError(f"ACL entry '{ace_id}' not found")

    return await rbac_repo.update_ace(ace_id, ace_update)


@router.delete("/{ace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ace(
    ace_id: UUID,
    rbac_repo: RbacRepository = Depends(get_repository(RbacRepository)),
) -> None:
    """
    Delete an ACL entry.
    """

    ace = await rbac_repo.get_ace(ace_id)
    if not ace:
        raise ControllerNotFoundError(f"ACL entry '{ace_id}' not found")

    success = await rbac_repo.delete_ace(ace_id)
    if not success:
        raise ControllerNotFoundError(f"ACL entry '{ace_id}' could not be deleted")


# @router.post("/prune", status_code=status.HTTP_204_NO_CONTENT)
# async def prune_permissions(
#         rbac_repo: RbacRepository = Depends(get_repository(RbacRepository))
# ) -> None:
#     """
#     Prune orphaned permissions.
#     """
#
#     await rbac_repo.prune_permissions()
