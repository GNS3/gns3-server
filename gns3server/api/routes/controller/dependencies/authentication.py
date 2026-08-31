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

import asyncio
import hashlib
import logging
import bcrypt

from fastapi import Request, Query, Depends, HTTPException, WebSocket, status
from fastapi.security import OAuth2PasswordBearer
from typing import Optional
from uuid import UUID

from gns3server import schemas
import gns3server.db.models as models
from gns3server.db.repositories.api_keys import ApiKeysRepository
from gns3server.db.repositories.users import UsersRepository
from gns3server.db.repositories.rbac import RbacRepository
from gns3server.schemas.controller.tokens import TokenData
from gns3server.services import auth_service, access_ticket_service
from gns3server.services.access_tickets import TICKET_PREFIX
from .database import get_repository

log = logging.getLogger(__name__)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v3/access/users/login", auto_error=False)


def _reject_refresh_token(token_data) -> None:
    """Reject tokens with type == 'refresh' — they must not grant API access."""

    if token_data.token_use == "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh tokens cannot be used for API access",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_user_from_token(
        request: Request,
        bearer_token: str = Depends(oauth2_scheme),
        user_repo: UsersRepository = Depends(get_repository(UsersRepository)),
        api_keys_repo: ApiKeysRepository = Depends(get_repository(ApiKeysRepository)),
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

    if token.startswith(TICKET_PREFIX):
        # Access tickets ("gns3t_…"): short-lived credentials bound to one
        # exact resource path, minted by the MCP download tools (capture
        # files, symbols). redeem_for_path() confines the ticket to that
        # path, so it cannot be replayed against any other resource.
        ticket = access_ticket_service.redeem_for_path(token, request.url.path)
        if ticket is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired access ticket",
                headers={"WWW-Authenticate": "Bearer"},
            )
        token_data = TokenData(
            username=ticket.username,
            token_version=ticket.token_version,
            token_use="access",
        )
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
                detail=f"Token has been revoked for '{token_data.username}'",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user

    # API Key authentication — format: gns3_<api_key_id>_<random_secret>
    # Direct lookup by UUID avoids O(n) scan of all keys.
    if token.startswith("gns3_"):
        parts = token.split("_", 2)
        if len(parts) != 3:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key format")
        try:
            key_id = UUID(parts[1])
        except ValueError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key format")
        secret = parts[2]
        db_key = await api_keys_repo.get_api_key(key_id)
        if not db_key or db_key.revoked:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
        if not await asyncio.to_thread(bcrypt.checkpw, secret.encode(), db_key.key_hash.encode()):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
        await api_keys_repo.update_last_used(db_key.api_key_id)
        user = await user_repo.get_user(db_key.user_id)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not an active user",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user

    # JWT authentication
    token_data = auth_service.get_token_data(token)
    _reject_refresh_token(token_data)
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
            detail=f"Token has been revoked for '{token_data.username}'",
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

    # Extract requested subprotocols from headers for proper WebSocket negotiation
    # This is critical for protocols like xpra that require specific subprotocols
    scope = websocket.scope
    headers = dict(scope.get("headers", []))
    requested_protocols_header = headers.get(b"sec-websocket-protocol", b"")
    requested_protocols = [p.decode().strip() for p in requested_protocols_header.split(b",") if p.strip()]

    # Accept the connection with the first requested subprotocol (if any)
    subprotocol = requested_protocols[0] if requested_protocols else None
    await websocket.accept(subprotocol=subprotocol)

    try:
        if token.startswith(TICKET_PREFIX):
            # Node-bound access tickets ("gns3t_…"): short-lived credentials
            # for one node's console endpoints, minted by the node_console
            # MCP tool. redeem() confines them to the route matching their
            # binding, so they cannot authenticate the notification/wireshark
            # sockets that share this dependency.
            ticket = access_ticket_service.redeem(token, websocket.path_params)
            if ticket is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired console ticket",
                )
            token_data = TokenData(
                username=ticket.username,
                token_version=ticket.token_version,
                token_use="access",
            )
        else:
            token_data = auth_service.get_token_data(token)
        _reject_refresh_token(token_data)
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
                detail=f"'{token_data.username}' is not an active user"
            )

        return user

    except HTTPException as e:
        # Fingerprint the received token so clients can compare it against the fingerprint
        # returned when the token was issued (e.g. token_sha256_prefix from the
        # node_console_info MCP tool) and detect copy corruption on their side.
        token_sha256_prefix = hashlib.sha256(token.encode()).hexdigest()[:8]
        err_msg = (
            f"Could not authenticate while connecting to controller WebSocket: {e.detail} "
            f"(received token sha256 prefix: {token_sha256_prefix})"
        )
        websocket_error = {"action": "log.error", "event": {"message": err_msg}}
        await websocket.send_json(websocket_error)
        log.error(err_msg)
        return await websocket.close(code=1008)

