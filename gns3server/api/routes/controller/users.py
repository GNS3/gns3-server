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

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm

import gns3server.db.models as models
from gns3server import schemas
from gns3server.controller import Controller
from gns3server.controller.controller_error import (
    ControllerBadRequestError,
    ControllerError,
    ControllerForbiddenError,
    ControllerNotFoundError,
)
from gns3server.controller.quota_usage import count_usage
from gns3server.db.repositories.rbac import RbacRepository
from gns3server.db.repositories.users import UsersRepository
from gns3server.db.user_quota_state import UserQuotaState
from gns3server.services import auth_service
from gns3server.services.login_rate_limiter import login_rate_limiter

from .dependencies.authentication import get_current_active_user
from .dependencies.database import get_repository
from .dependencies.rbac import has_privilege

log = logging.getLogger(__name__)

router = APIRouter()

# The preferences document is client-controlled storage: cap it so a single
# user cannot grow the controller database without bound.
MAX_PREFERENCES_SIZE_BYTES = 256 * 1024


@router.post("/login", response_model=schemas.Token)
async def login(
    request: Request,
    users_repo: UsersRepository = Depends(get_repository(UsersRepository)),
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> schemas.Token:
    """
    Default user login method using forms (x-www-form-urlencoded).
    Example: curl -X POST http://host:port/v3/access/users/login -H "Content-Type: application/x-www-form-urlencoded" -d "username=admin&password=admin"
    """

    client_ip = request.client.host if request.client else "127.0.0.1"
    is_limited, retry_after = login_rate_limiter.is_rate_limited(form_data.username, client_ip)
    if is_limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    user = await users_repo.authenticate_user(username=form_data.username, password=form_data.password)
    if not user:
        login_rate_limiter.record_failure(form_data.username, client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication was unsuccessful.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    login_rate_limiter.reset(form_data.username, client_ip)
    return auth_service.create_token_response(user)


@router.post("/authenticate", response_model=schemas.Token)
async def authenticate(
    request: Request,
    user_credentials: schemas.Credentials,
    users_repo: UsersRepository = Depends(get_repository(UsersRepository)),
) -> schemas.Token:
    """
    Alternative authentication method using json.
    Example: curl -X POST http://host:port/v3/access/users/authenticate -d '{"username": "admin", "password": "admin"}' -H "Content-Type: application/json"
    """

    client_ip = request.client.host if request.client else "127.0.0.1"
    is_limited, retry_after = login_rate_limiter.is_rate_limited(user_credentials.username, client_ip)
    if is_limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    user = await users_repo.authenticate_user(username=user_credentials.username, password=user_credentials.password)
    if not user:
        login_rate_limiter.record_failure(user_credentials.username, client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication was unsuccessful.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    login_rate_limiter.reset(user_credentials.username, client_ip)
    return auth_service.create_token_response(user)


@router.post("/refresh", response_model=schemas.Token)
async def refresh_access_token(
    request: schemas.RefreshTokenRequest,
    users_repo: UsersRepository = Depends(get_repository(UsersRepository)),
) -> schemas.Token:
    """
    Exchange a refresh token for a new access token.

    Public endpoint — the refresh token itself proves identity. Respects the
    user's token_version, so logout (which increments it) invalidates all
    outstanding refresh tokens. Refresh tokens are stateless JWTs with a
    longer expiry (default 30 days). Stolen tokens remain valid until their
    `exp` or until logout — no replay protection without a server-side table.
    """

    token_data = auth_service.get_token_data(request.refresh_token)
    if token_data.token_use != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = await users_repo.get_user_by_username(token_data.username)
    if user is None or not user.is_active:
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

    return auth_service.create_token_response(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    current_user: schemas.User = Depends(get_current_active_user),
    users_repo: UsersRepository = Depends(get_repository(UsersRepository)),
) -> None:
    """
    Logout the current user by revoking all existing tokens.
    """

    await users_repo.logout_user(current_user.user_id)


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
    users_repo: UsersRepository = Depends(get_repository(UsersRepository)),
) -> Optional[models.User]:
    """
    Update the current active user.
    """

    if current_user.auth_source == "ldap" and user_update.password:
        raise ControllerBadRequestError("Password cannot be changed for directory-authenticated users")

    if user_update.email and await users_repo.get_user_by_email(user_update.email):
        raise ControllerBadRequestError(f"Email '{user_update.email}' is already registered")

    return await users_repo.update_user(current_user.user_id, user_update)


@router.get("/me/privileges", response_model=schemas.UserPrivileges)
async def get_logged_in_user_privileges(
    current_user: schemas.User = Depends(get_current_active_user),
    rbac_repo: RbacRepository = Depends(get_repository(RbacRepository)),
) -> schemas.UserPrivileges:
    """
    Get the effective privileges of the current active user.

    The privileges are the union of everything granted by the roles assigned
    to the user (directly or through group membership), flattened across all
    resource paths. This is meant for rendering purposes (e.g. showing or
    hiding parts of the UI): the server remains the authority for permission
    checks and can still deny a privilege on a specific resource path.

    Example: curl -X GET http://host:port/v3/access/users/me/privileges -H "Authorization: Bearer <token>"
    """

    if current_user.is_superadmin:
        privileges = sorted(privilege.name for privilege in await rbac_repo.get_privileges())
        return schemas.UserPrivileges(is_superadmin=True, privileges=privileges)

    privilege_names = await rbac_repo.get_user_privileges(current_user.user_id)
    return schemas.UserPrivileges(is_superadmin=False, privileges=sorted(privilege_names))


@router.get(
    "/me/group-members",
    response_model=schemas.UserGroupMembersResponse,
    dependencies=[Depends(has_privilege("User.GroupMembers"))],
)
async def get_logged_in_user_group_members(
    current_user: schemas.User = Depends(get_current_active_user),
    users_repo: UsersRepository = Depends(get_repository(UsersRepository)),
) -> schemas.UserGroupMembersResponse:
    """
    List the members of every user group of the current user, as usernames
    only. This is what a share or distribution dialog offers as candidate
    recipients: a user sees the members of their own groups, never the whole
    user base (that stays User.Audit).

    Example: curl -X GET http://host:port/v3/access/users/me/group-members -H "Authorization: Bearer <token>"
    """

    groups = await users_repo.get_user_memberships(current_user.user_id)
    entries = []
    for group in sorted(groups, key=lambda group: str(group.name)):
        members = sorted(str(user.username) for user in await users_repo.get_user_group_members(group.user_group_id))
        entries.append(schemas.UserGroupMembers(group_name=str(group.name), members=members))
    return schemas.UserGroupMembersResponse(groups=entries)


@router.get("/me/quotas", response_model=schemas.UserQuotaUsage)
async def get_logged_in_user_quotas(
    current_user: schemas.User = Depends(get_current_active_user),
) -> schemas.UserQuotaUsage:
    """
    Get the effective node quotas of the current user along with the current
    usage across all the projects they own. A NULL limit means unlimited
    (superadmins are never limited). The usage only counts the node types
    that consume resources (Ethernet switches, hubs, clouds and NATs are
    not counted).

    Meant for rendering purposes (e.g. a quota bar in the web UI).

    Example: curl -X GET http://host:port/v3/access/users/me/quotas -H "Authorization: Bearer <token>"
    """

    assert current_user.username is not None  # an authenticated user always has a name
    # the usage follows the stable owner id: a deleted user's projects must
    # not count for a user created later under the same name
    user_id = str(current_user.user_id)
    if current_user.is_superadmin:
        current_nodes, current_running_nodes = count_usage(current_user.username, user_id)
        return schemas.UserQuotaUsage(current_nodes=current_nodes, current_running_nodes=current_running_nodes)

    limits = UserQuotaState.instance().get(current_user.username)
    current_nodes, current_running_nodes = count_usage(current_user.username, user_id)
    if limits is None:
        return schemas.UserQuotaUsage(current_nodes=current_nodes, current_running_nodes=current_running_nodes)
    return schemas.UserQuotaUsage(
        max_nodes=limits.max_nodes,
        max_running_nodes=limits.max_running_nodes,
        current_nodes=current_nodes,
        current_running_nodes=current_running_nodes,
    )


@router.get("/me/preferences", response_model=schemas.UserPreferences)
async def get_logged_in_user_preferences(
    current_user: schemas.User = Depends(get_current_active_user),
    users_repo: UsersRepository = Depends(get_repository(UsersRepository)),
) -> schemas.UserPreferences:
    """
    Get the preferences document of the current user.

    The document is an arbitrary JSON object owned by the client (e.g. the web UI
    stores its per-user settings there so they follow the user across machines).
    The server stores it as-is and does not interpret its contents. Returns an
    empty object when no preferences have been saved yet.

    Example: curl -X GET http://host:port/v3/access/users/me/preferences -H "Authorization: Bearer <token>"
    """

    db_prefs = await users_repo.get_user_preferences(current_user.user_id)
    if db_prefs is None:
        return schemas.UserPreferences()
    return schemas.UserPreferences(preferences=db_prefs.preferences, updated_at=db_prefs.updated_at)


@router.put("/me/preferences", response_model=schemas.UserPreferences)
async def update_logged_in_user_preferences(
    request: Request,
    current_user: schemas.User = Depends(get_current_active_user),
    users_repo: UsersRepository = Depends(get_repository(UsersRepository)),
    preferences: Dict[str, Any] = Body(...),
) -> schemas.UserPreferences:
    """
    Replace the preferences document of the current user.

    The request body is the document itself (a JSON object) and replaces any
    previously saved document as a whole (last write wins). Clients should keep
    the document small (it is capped at 256 KiB) and carry their own schema
    version inside it. Credentials must not be stored there.

    Example: curl -X PUT http://host:port/v3/access/users/me/preferences -H "Authorization: Bearer <token>" -H "Content-Type: application/json" -d '{"version": 1, "theme": "dark"}'
    """

    body = await request.body()
    if len(body) > MAX_PREFERENCES_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Preferences document is too large (maximum {MAX_PREFERENCES_SIZE_BYTES} bytes)",
        )

    db_prefs = await users_repo.save_user_preferences(current_user.user_id, preferences)
    return schemas.UserPreferences(preferences=db_prefs.preferences, updated_at=db_prefs.updated_at)


@router.delete("/me/preferences", status_code=status.HTTP_204_NO_CONTENT)
async def reset_logged_in_user_preferences(
    current_user: schemas.User = Depends(get_current_active_user),
    users_repo: UsersRepository = Depends(get_repository(UsersRepository)),
) -> None:
    """
    Reset the preferences document of the current user.

    Example: curl -X DELETE http://host:port/v3/access/users/me/preferences -H "Authorization: Bearer <token>"
    """

    await users_repo.delete_user_preferences(current_user.user_id)


@router.get("", response_model=List[schemas.User], dependencies=[Depends(has_privilege("User.Audit"))])
async def get_users(users_repo: UsersRepository = Depends(get_repository(UsersRepository))) -> List[models.User]:
    """
    Get all users.

    Required privilege: User.Audit
    """

    return await users_repo.get_users()


@router.post(
    "",
    response_model=schemas.User,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(has_privilege("User.Allocate"))],
)
async def create_user(
    user_create: schemas.UserCreate, users_repo: UsersRepository = Depends(get_repository(UsersRepository))
) -> models.User:
    """
    Create a new user.

    Required privilege: User.Allocate
    """

    if await users_repo.get_user_by_username_case_insensitive(user_create.username):
        raise ControllerBadRequestError(f"Username '{user_create.username}' is already registered")

    if user_create.email and await users_repo.get_user_by_email(user_create.email):
        raise ControllerBadRequestError(f"Email '{user_create.email}' is already registered")

    if not await users_repo.get_user_group(user_create.user_group_id):
        raise ControllerNotFoundError(f"User group '{user_create.user_group_id}' not found")

    return await users_repo.create_user(user_create)


@router.get("/{user_id}", response_model=schemas.User, dependencies=[Depends(has_privilege("User.Audit"))])
async def get_user(
    user_id: UUID,
    users_repo: UsersRepository = Depends(get_repository(UsersRepository)),
) -> models.User:
    """
    Get a user.

    Required privilege: User.Audit
    """

    user = await users_repo.get_user(user_id)
    if not user:
        raise ControllerNotFoundError(f"User '{user_id}' not found")
    return user


@router.put("/{user_id}", response_model=schemas.User, dependencies=[Depends(has_privilege("User.Modify"))])
async def update_user(
    user_id: UUID,
    user_update: schemas.UserUpdate,
    users_repo: UsersRepository = Depends(get_repository(UsersRepository)),
) -> Optional[models.User]:
    """
    Update a user.

    Required privilege: User.Modify
    """

    user = await users_repo.get_user(user_id)
    if not user:
        raise ControllerNotFoundError(f"User '{user_id}' not found")

    if user_update.username and user_update.username != user.username:
        # Ownership and quotas are keyed by the username (projects keep
        # created_by as a string): a rename would cut the user off from
        # their projects, so it is refused. Sending the current username
        # is a no-op and stays allowed.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The username cannot be changed",
        )

    if user_update.email and await users_repo.get_user_by_email(user_update.email):
        raise ControllerBadRequestError(f"Email '{user_update.email}' is already registered")

    existing_user = await users_repo.get_user(user_id)
    if not existing_user:
        raise ControllerNotFoundError(f"User '{user_id}' not found")

    extra_values = {}
    if existing_user.auth_source == "ldap" and user_update.password:
        from gns3server.config import Config

        if Config.instance().settings.LDAP.enabled:
            raise ControllerBadRequestError("Password cannot be changed for directory-authenticated users")
        extra_values["auth_source"] = "local"

    user = await users_repo.update_user(user_id, user_update, **extra_values)
    return user


@router.delete(
    "/{user_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(has_privilege("User.Allocate"))]
)
async def delete_user(
    user_id: UUID,
    users_repo: UsersRepository = Depends(get_repository(UsersRepository)),
    rbac_repo: RbacRepository = Depends(get_repository(RbacRepository)),
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

    # Projects owned by the user lose their owner ACE when the user row is
    # deleted (the ACE is removed by the foreign key cascade): warn so an
    # administrator can grant access again through an explicit ACE.
    owned_projects = [p.name for p in Controller.instance().projects.values() if p.created_by == user.username]

    success = await users_repo.delete_user(user_id)
    if not success:
        raise ControllerError(f"User '{user_id}' could not be deleted")
    await rbac_repo.delete_all_ace_starting_with_path(f"/access/users/{user_id}")
    if owned_projects:
        log.warning(
            f"Deleted user '{user.username}' owned project(s) {', '.join(owned_projects)}: "
            "they are now restricted to superadmins until an ACE is granted again"
        )


@router.get(
    "/{user_id}/groups", response_model=List[schemas.UserGroup], dependencies=[Depends(has_privilege("Group.Audit"))]
)
async def get_user_memberships(
    user_id: UUID, users_repo: UsersRepository = Depends(get_repository(UsersRepository))
) -> List[models.UserGroup]:
    """
    Get user memberships.

    Required privilege: Group.Audit
    """

    return await users_repo.get_user_memberships(user_id)
