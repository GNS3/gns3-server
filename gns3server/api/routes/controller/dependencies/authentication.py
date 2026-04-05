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

import logging

from fastapi import Request, Query, Depends, HTTPException, WebSocket, status
from fastapi.security import OAuth2PasswordBearer
from typing import Optional

from gns3server import schemas
from gns3server.db.repositories.users import UsersRepository
from gns3server.db.repositories.rbac import RbacRepository
from gns3server.services import auth_service
from .database import get_repository

log = logging.getLogger(__name__)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v3/access/users/login", auto_error=False)


async def get_user_from_token(
        bearer_token: str = Depends(oauth2_scheme),
        user_repo: UsersRepository = Depends(get_repository(UsersRepository)),
        token: Optional[str] = Query(None, include_in_schema=False)
) -> schemas.User:

    if bearer_token:
        # bearer token is used first, then any token passed as a URL parameter
        token = bearer_token

    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_data = auth_service.get_token_data(token)
    user = await user_repo.get_user_by_username(token_data.username)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if token_data.token_version != user.token_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_current_active_user(
        request: Request,
        current_user: schemas.User = Depends(get_user_from_token),
        rbac_repo: RbacRepository = Depends(get_repository(RbacRepository))
) -> schemas.User:

    # Super admin is always authorized
    if current_user.is_superadmin:
        return current_user

    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not an active user",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return current_user


async def get_current_active_user_from_websocket(
        websocket: WebSocket,
        token: str = Query(...),
        user_repo: UsersRepository = Depends(get_repository(UsersRepository)),
) -> Optional[schemas.User]:

    await websocket.accept()

    try:
        token_data = auth_service.get_token_data(token)
        user = await user_repo.get_user_by_username(token_data.username)

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Could not validate credentials for '{token_data.username}'"
            )
        if token_data.token_version != user.token_version:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Token has been revoked for '{token_data.username}'"
            )

        # Super admin is always authorized
        if user.is_superadmin:
            return user

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"'{username}' is not an active user"
            )

        return user

    except HTTPException as e:
        err_msg = f"Could not authenticate while connecting to controller WebSocket: {e.detail}"
        websocket_error = {"action": "log.error", "event": {"message": err_msg}}
        await websocket.send_json(websocket_error)
        log.error(err_msg)
        return await websocket.close(code=1008)

