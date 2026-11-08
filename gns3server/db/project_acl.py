#
# Copyright (C) 2026 GNS3 Technologies Inc.
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
#

"""
Ownership ACEs for projects.

The default ACE granting the "User" role to the "Users" group on /projects
does not propagate, so a project is only accessible through an ACE on its own
path. When a project is created, an owner ACE is added for its creator:

* ``created_by`` resolves to an existing user: a user ACE on
  ``/projects/<project_id>`` carrying the role that allowed the creation
  (falling back to the built-in "User" role);
* ``created_by`` is empty or the user no longer exists: no ACE is created and
  the project stays accessible to superadmins only.

The helper is idempotent: an existing owner ACE (whatever its role) is never
replaced, and an ACE an administrator customized is left untouched.
"""

import logging
from typing import Dict, Iterable, Optional, Tuple, Union, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import gns3server.db.models as models
from gns3server import schemas
from gns3server.db.repositories.rbac import RbacRepository
from gns3server.db.repositories.users import UsersRepository

log = logging.getLogger(__name__)

PROJECTS_PATH = "/projects"
FALLBACK_ROLE_NAME = "User"


def project_ace_path(project_id: Union[str, UUID]) -> str:
    return f"{PROJECTS_PATH}/{project_id}"


async def _owner_role_id(rbac_repo: RbacRepository, user_id: UUID) -> Optional[UUID]:
    """
    Role carried by the ACE that lets the user create projects, so the owner
    ACE keeps the same rights on the new project. Falls back to the built-in
    "User" role (covers superadmins, who bypass the ACE checks).
    """

    role_id = await rbac_repo.get_effective_role_id(user_id, PROJECTS_PATH, "Project.Allocate")
    if role_id is not None:
        return role_id
    role = await rbac_repo.get_role_by_name(FALLBACK_ROLE_NAME)
    return role.role_id if role is not None else None


async def _has_user_ace(db_session: AsyncSession, path: str, user_id: UUID) -> bool:
    result = await db_session.execute(select(models.ACE).where(models.ACE.path == path, models.ACE.user_id == user_id))
    return result.first() is not None


async def ensure_project_owner_ace(
    db_session: AsyncSession, project_id: Union[str, UUID], created_by: Optional[str]
) -> bool:
    """
    Create the owner ACE of a project when it is missing.

    Returns True when an ACE was created. Projects without a resolvable owner
    (created_by is None or the user no longer exists) get no ACE and stay
    restricted to superadmins.
    """

    if not created_by:
        log.debug(f"Project '{project_id}' has no owner: it stays restricted to superadmins")
        return False

    user = await UsersRepository(db_session).get_user_by_username(created_by)
    if user is None:
        log.warning(f"Project '{project_id}' owner '{created_by}' no longer exists: it stays restricted to superadmins")
        return False
    user_id = cast(UUID, user.user_id)

    path = project_ace_path(project_id)
    if await _has_user_ace(db_session, path, user_id):
        return False

    rbac_repo = RbacRepository(db_session)
    role_id = await _owner_role_id(rbac_repo, user_id)
    if role_id is None:
        log.error(f"Could not determine a role for the owner '{created_by}' of project '{project_id}'")
        return False

    await rbac_repo.create_ace(
        schemas.ACECreate(
            path=path,
            ace_type="user",
            propagate=True,
            allowed=True,
            user_id=user_id,
            role_id=role_id,
        )
    )
    log.debug(f"Created the owner ACE on '{path}' for user '{created_by}'")
    return True


async def ensure_all_project_aces(
    db_session: AsyncSession, projects: Iterable[Tuple[Union[str, UUID], Optional[str]]]
) -> int:
    """
    Create every missing owner ACE in a single transaction.

    ``projects`` is an iterable of (project_id, created_by) pairs. Returns the
    number of ACEs created.
    """

    owners: Dict[str, str] = {}
    for project_id, created_by in projects:
        if created_by:
            owners[project_ace_path(project_id)] = created_by
    if not owners:
        return 0

    result = await db_session.execute(select(models.User).where(models.User.username.in_(set(owners.values()))))
    users_by_name = {user.username: user for user in result.scalars()}

    result = await db_session.execute(select(models.ACE).where(models.ACE.path.in_(list(owners))))
    existing = set()
    for ace in result.scalars():
        values = ace.asdict()
        if values["user_id"] is not None:
            existing.add((values["path"], values["user_id"]))

    rbac_repo = RbacRepository(db_session)
    role_cache: Dict[UUID, Optional[UUID]] = {}
    new_aces = []
    for path, username in owners.items():
        user = users_by_name.get(username)
        if user is None:
            log.warning(
                f"Project owner '{username}' for '{path}' no longer exists: the project stays restricted to superadmins"
            )
            continue
        user_id = cast(UUID, user.user_id)
        if (path, user_id) in existing:
            continue
        if user_id not in role_cache:
            role_cache[user_id] = await _owner_role_id(rbac_repo, user_id)
        role_id = role_cache[user_id]
        if role_id is None:
            log.error(f"Could not determine a role for the owner '{username}' of '{path}'")
            continue
        new_aces.append(
            schemas.ACECreate(
                path=path,
                ace_type="user",
                propagate=True,
                allowed=True,
                user_id=user_id,
                role_id=role_id,
            )
        )

    if new_aces:
        await rbac_repo.create_aces(new_aces)
        log.info(f"Created {len(new_aces)} project owner ACE(s)")
    return len(new_aces)
