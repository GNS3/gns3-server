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

import re

from fastapi import Request, WebSocket, Depends, HTTPException
from gns3server import schemas
from gns3server.db.repositories.rbac import RbacRepository
from .authentication import get_current_active_user, get_current_active_user_from_websocket
from .database import get_repository

import logging

log = logging.getLogger()


def has_privilege(
        privilege_name: str
):
    async def get_user_and_check_privilege(
            request: Request,
            current_user: schemas.User = Depends(get_current_active_user),
            rbac_repo: RbacRepository = Depends(get_repository(RbacRepository))
    ):
        if not current_user.is_superadmin:
            path = re.sub(r"^/v[0-9]", "", request.url.path)  # remove the prefix (e.g. "/v3") from URL path
            log.debug(f"Checking user {current_user.username} has privilege {privilege_name} on '{path}'")
            if not await rbac_repo.check_user_has_privilege(current_user.user_id, path, privilege_name):
                raise HTTPException(status_code=403, detail=f"Permission denied (privilege {privilege_name} is required)")
        return current_user
    return get_user_and_check_privilege


def has_privilege_on_websocket(
        privilege_name: str
):
    async def get_user_and_check_privilege(
            websocket: WebSocket,
            current_user: schemas.User = Depends(get_current_active_user_from_websocket),
            rbac_repo: RbacRepository = Depends(get_repository(RbacRepository))
    ):
        if not current_user.is_superadmin:
            path = re.sub(r"^/v[0-9]", "", websocket.url.path)  # remove the prefix (e.g. "/v3") from URL path
            log.debug(f"Checking user {current_user.username} has privilege {privilege_name} on '{path}'")
            if not await rbac_repo.check_user_has_privilege(current_user.user_id, path, privilege_name):
                raise HTTPException(status_code=403, detail=f"Permission denied (privilege {privilege_name} is required)")
        return current_user
    return get_user_and_check_privilege

# class PrivilegeChecker:
#
#     def __init__(self, required_privilege: str) -> None:
#         self._required_privilege = required_privilege
#
#     async def __call__(
#             self,
#             current_user: schemas.User = Depends(get_current_active_user),
#             rbac_repo: RbacRepository = Depends(get_repository(RbacRepository))
#     ) -> bool:
#
#         if not await rbac_repo.check_user_has_privilege(current_user.user_id, "/projects", self._required_privilege):
#             raise HTTPException(status_code=403, detail=f"Permission denied (privilege {self._required_privilege} is required)")
#         return True

# Depends(PrivilegeChecker("Project.Audit"))
