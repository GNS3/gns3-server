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


from fastapi import Request, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from gns3server import schemas
from gns3server.db.repositories.users import UsersRepository
from gns3server.db.repositories.rbac import RbacRepository
from gns3server.services import auth_service
from .database import get_repository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v3/users/login")


async def get_user_from_token(
    token: str = Depends(oauth2_scheme), user_repo: UsersRepository = Depends(get_repository(UsersRepository))
) -> schemas.User:

    username = auth_service.get_username_from_token(token)
    user = await user_repo.get_user_by_username(username)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
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

    # remove the prefix (e.g. "/v3") from URL path
    if request.url.path.startswith("/v3"):
        path = request.url.path[len("/v3"):]
    else:
        path = request.url.path

    authorized = await rbac_repo.check_user_is_authorized(current_user.user_id, request.method, path)
    if not authorized:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"User is not authorized '{current_user.user_id}' on {request.method} '{path}'",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return current_user
