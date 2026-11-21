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
API routes for user groups.
"""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, status

import gns3server.db.models as models
from gns3server import schemas
from gns3server.controller.controller_error import (
    ControllerBadRequestError,
    ControllerError,
    ControllerForbiddenError,
    ControllerNotFoundError,
)
from gns3server.db.repositories.rbac import RbacRepository
from gns3server.db.repositories.users import UsersRepository

from .dependencies.database import get_repository
from .dependencies.rbac import has_privilege

log = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=List[schemas.UserGroup], dependencies=[Depends(has_privilege("Group.Audit"))])
async def get_user_groups(
    users_repo: UsersRepository = Depends(get_repository(UsersRepository)),
) -> List[models.UserGroup]:
    """
    Get all user groups.

    Required privilege: Group.Audit
    """

    return await users_repo.get_user_groups()


@router.post(
    "",
    response_model=schemas.UserGroup,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(has_privilege("Group.Allocate"))],
)
async def create_user_group(
    user_group_create: schemas.UserGroupCreate, users_repo: UsersRepository = Depends(get_repository(UsersRepository))
) -> models.UserGroup:
    """
    Create a new user group.

    Required privilege: Group.Allocate
    """

    if await users_repo.get_user_group_by_name(user_group_create.name):
        raise ControllerBadRequestError(f"User group '{user_group_create.name}' already exists")

    return await users_repo.create_user_group(user_group_create)


@router.get("/{user_group_id}", response_model=schemas.UserGroup, dependencies=[Depends(has_privilege("Group.Audit"))])
async def get_user_group(
    user_group_id: UUID,
    users_repo: UsersRepository = Depends(get_repository(UsersRepository)),
) -> models.UserGroup:
    """
    Get a user group.

    Required privilege: Group.Audit
    """

    user_group = await users_repo.get_user_group(user_group_id)
    if not user_group:
        raise ControllerNotFoundError(f"User group '{user_group_id}' not found")
    return user_group


@router.put("/{user_group_id}", response_model=schemas.UserGroup, dependencies=[Depends(has_privilege("Group.Modify"))])
async def update_user_group(
    user_group_id: UUID,
    user_group_update: schemas.UserGroupUpdate,
    users_repo: UsersRepository = Depends(get_repository(UsersRepository)),
) -> Optional[models.UserGroup]:
    """
    Update a user group.

    Required privilege: Group.Modify
    """
    user_group = await users_repo.get_user_group(user_group_id)
    if not user_group:
        raise ControllerNotFoundError(f"User group '{user_group_id}' not found")

    # A built-in group cannot be renamed, but its quota defaults stay
    # editable: they are the natural place to set a limit for the default
    # "Users" group everyone is created into.
    if user_group.is_builtin and "name" in user_group_update.model_fields_set:
        raise ControllerForbiddenError(f"Built-in user group '{user_group_id}' name cannot be changed")

    return await users_repo.update_user_group(user_group_id, user_group_update)


@router.delete(
    "/{user_group_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(has_privilege("Group.Allocate"))]
)
async def delete_user_group(
    user_group_id: UUID,
    users_repo: UsersRepository = Depends(get_repository(UsersRepository)),
    rbac_repo: RbacRepository = Depends(get_repository(RbacRepository)),
) -> None:
    """
    Delete a user group.

    Required privilege: Group.Allocate
    """

    user_group = await users_repo.get_user_group(user_group_id)
    if not user_group:
        raise ControllerNotFoundError(f"User group '{user_group_id}' not found")

    if user_group.is_builtin:
        raise ControllerForbiddenError(f"Built-in user group '{user_group_id}' cannot be deleted")

    success = await users_repo.delete_user_group(user_group_id)
    if not success:
        raise ControllerError(f"User group '{user_group_id}' could not be deleted")
    await rbac_repo.delete_all_ace_starting_with_path(f"/access/groups/{user_group_id}")


@router.get(
    "/{user_group_id}/members", response_model=List[schemas.User], dependencies=[Depends(has_privilege("Group.Audit"))]
)
async def get_user_group_members(
    user_group_id: UUID, users_repo: UsersRepository = Depends(get_repository(UsersRepository))
) -> List[models.User]:
    """
    Get all user group members.

    Required privilege: Group.Audit
    """

    return await users_repo.get_user_group_members(user_group_id)


@router.put(
    "/{user_group_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(has_privilege("Group.Modify"))],
)
async def add_member_to_group(
    user_group_id: UUID, user_id: UUID, users_repo: UsersRepository = Depends(get_repository(UsersRepository))
) -> None:
    """
    Add member to a user group.

    Required privilege: Group.Modify
    """

    user = await users_repo.get_user(user_id)
    if not user:
        raise ControllerNotFoundError(f"User '{user_id}' not found")

    user_groups = await users_repo.get_user_memberships(user_id)
    for group in user_groups:
        if group.user_group_id == user_group_id:
            raise ControllerBadRequestError(f"Username '{user.username}' is already member of group '{group.name}'")

    user_group = await users_repo.add_member_to_user_group(user_group_id, user)
    if not user_group:
        raise ControllerNotFoundError(f"User group '{user_group_id}' not found")


@router.delete(
    "/{user_group_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(has_privilege("Group.Modify"))],
)
async def remove_member_from_group(
    user_group_id: UUID,
    user_id: UUID,
    users_repo: UsersRepository = Depends(get_repository(UsersRepository)),
) -> None:
    """
    Remove member from a user group.

    Required privilege: Group.Modify
    """

    user = await users_repo.get_user(user_id)
    if not user:
        raise ControllerNotFoundError(f"User '{user_id}' not found")

    user_group = await users_repo.remove_member_from_user_group(user_group_id, user)
    if not user_group:
        raise ControllerNotFoundError(f"User group '{user_group_id}' not found")


def _group_tool_candidates(group_privileges: set[str]) -> list[str]:
    """
    MCP tools the group's privileges could ever show, sorted for a stable UI.
    """

    from gns3server.agent.mcp.tool_access import TOOL_SPECS, tool_visible

    return sorted(name for name in TOOL_SPECS if tool_visible(name, frozenset(group_privileges), is_superadmin=False))


@router.get(
    "/{user_group_id}/mcp_tools",
    response_model=schemas.GroupMCPTools,
    dependencies=[Depends(has_privilege("Group.Audit"))],
)
async def get_group_mcp_tools(
    user_group_id: UUID,
    users_repo: UsersRepository = Depends(get_repository(UsersRepository)),
    rbac_repo: RbacRepository = Depends(get_repository(RbacRepository)),
) -> schemas.GroupMCPTools:
    """
    Get the MCP tool configuration of a user group.

    Returns the candidate tools (everything the group's privileges could
    ever show) and the configured whitelist, if any. The admin UI should
    offer exactly the candidates for selection.

    Required privilege: Group.Audit
    """

    if not await users_repo.get_user_group(user_group_id):
        raise ControllerNotFoundError(f"User group '{user_group_id}' not found")

    group_privileges = await rbac_repo.get_group_privileges(user_group_id)
    tools = await rbac_repo.get_group_mcp_tools(user_group_id)
    candidates = _group_tool_candidates(group_privileges)
    from gns3server.agent.mcp.tool_access import all_tool_descriptions

    descriptions = all_tool_descriptions()
    return schemas.GroupMCPTools(
        candidates=candidates,
        tools=sorted(tools) if tools is not None else None,
        bypass=await rbac_repo.get_group_mcp_bypass(user_group_id),
        descriptions={name: descriptions.get(name, "") for name in candidates},
    )


@router.put(
    "/{user_group_id}/mcp_tools",
    response_model=schemas.GroupMCPTools,
    dependencies=[Depends(has_privilege("Group.Modify"))],
)
async def update_group_mcp_tools(
    user_group_id: UUID,
    mcp_tools_update: schemas.GroupMCPToolsUpdate,
    users_repo: UsersRepository = Depends(get_repository(UsersRepository)),
    rbac_repo: RbacRepository = Depends(get_repository(RbacRepository)),
) -> schemas.GroupMCPTools:
    """
    Replace the MCP tool whitelist of a user group.

    Only candidate tools (those the group's privileges could ever show) are
    accepted: a tool outside the candidates can never appear to the group
    members anyway, so configuring it is rejected instead of silently doing
    nothing. An empty list hides every MCP tool from the group members that
    have no other group; use DELETE to lift the restriction entirely.

    Required privilege: Group.Modify
    """

    if not await users_repo.get_user_group(user_group_id):
        raise ControllerNotFoundError(f"User group '{user_group_id}' not found")

    group_privileges = await rbac_repo.get_group_privileges(user_group_id)
    candidates = _group_tool_candidates(group_privileges)
    unknown = sorted(set(mcp_tools_update.tools) - set(candidates))
    if unknown:
        raise ControllerBadRequestError(
            f"Tools are not available to user group '{user_group_id}': {', '.join(unknown)}"
        )

    await rbac_repo.set_group_mcp_tools(user_group_id, mcp_tools_update.tools)
    return schemas.GroupMCPTools(
        candidates=candidates,
        tools=sorted(set(mcp_tools_update.tools)),
        bypass=await rbac_repo.get_group_mcp_bypass(user_group_id),
    )


@router.delete(
    "/{user_group_id}/mcp_tools",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(has_privilege("Group.Modify"))],
)
async def delete_group_mcp_tools(
    user_group_id: UUID,
    users_repo: UsersRepository = Depends(get_repository(UsersRepository)),
    rbac_repo: RbacRepository = Depends(get_repository(RbacRepository)),
) -> None:
    """
    Remove the MCP tool whitelist of a user group: every tool the group's
    privileges allow becomes visible again.

    Required privilege: Group.Modify
    """

    if not await users_repo.get_user_group(user_group_id):
        raise ControllerNotFoundError(f"User group '{user_group_id}' not found")

    await rbac_repo.clear_group_mcp_tools(user_group_id)
