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
In-memory snapshot of the RBAC state.

The controller keeps its whole runtime state (projects, computes,
notifications) in process memory: a second controller instance is not a
supported setup. This module applies the same idea to the RBAC tables.
All roles, ACEs, group memberships and resource pool memberships are
loaded once into a process-wide snapshot, permission checks then run
against the snapshot instead of querying the database on every request.

The database stays the source of truth. Every repository method that
writes an RBAC table marks the snapshot as dirty, and the next read
rebuilds it from the database. Rebuilding is a handful of small SELECTs
and only happens after (human frequency) administrative writes, so the
checks keep their exact semantics while dropping from several queries
per request (including a full resource scan) to an in-memory lookup.

The evaluation methods replicate the semantics of the previous
database-backed implementation, quirks included (path reverse traversal,
deny raising PermissionError, pool checks with the "/pool" prefix, group
ACEs in natural order while user ACEs are sorted by descending path).
"""

import logging
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Set, Tuple
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import gns3server.db.models as models

log = logging.getLogger(__name__)

# Sentinels returned by _check_path_role: the path is denied by a matching
# deny ACE, or no ACE matched at all.
_ACE_DENIED = object()
_ACE_NO_MATCH = object()


@dataclass(frozen=True)
class AceEntry:
    """
    A flattened ACE: the ACE row itself plus the ids it matches.
    """

    path: str
    propagate: bool
    allowed: bool
    user_id: Optional[UUID]
    group_id: Optional[UUID]
    role_id: UUID


class RbacState:
    """
    Process-wide snapshot of the RBAC tables.

    The snapshot is loaded lazily on first use and rebuilt after any
    RBAC write (mark_dirty). It must be reset when the database is
    recreated (tests) via reset().
    """

    _instance: Optional["RbacState"] = None

    def __init__(self) -> None:

        self._loaded: bool = False
        self._dirty: bool = False
        self._role_privileges: Dict[UUID, Set[str]] = {}
        self._group_members: Dict[UUID, Set[UUID]] = {}
        self._aces: List[AceEntry] = []
        self._project_resource_ids: Set[str] = set()
        # pool id (str) -> project resource ids (str)
        self._pool_projects: Dict[str, Set[str]] = {}

    @classmethod
    def instance(cls) -> "RbacState":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def reset(self) -> None:
        """
        Drop the snapshot: the next read reloads it from the database.
        Called when the database is recreated (tests) or at startup.
        """

        self._loaded = False
        self._dirty = False
        self._role_privileges = {}
        self._group_members = {}
        self._aces = []
        self._project_resource_ids = set()
        self._pool_projects = {}

    def mark_dirty(self) -> None:
        """
        Flag the snapshot as outdated. Repository write methods call
        this after touching an RBAC table; no I/O is done here.
        """

        self._dirty = True

    @property
    def needs_reload(self) -> bool:
        """
        Whether the next read must rebuild the snapshot from the database.
        Long-lived consumers (notification streams) poll this to pick up
        administrative changes without holding a database session open.
        """

        return not self._loaded or self._dirty

    async def reload(self, db_session: AsyncSession) -> None:
        """
        Rebuild the snapshot from the database, whatever its state.
        """

        # clear the flag before loading: if a write marks the snapshot
        # dirty again while the queries are awaited, the next read
        # triggers another reload
        self._dirty = False

        # role id -> privilege names
        roles_result = await db_session.execute(select(models.Role).options(selectinload(models.Role.privileges)))
        role_privileges: Dict[UUID, Set[str]] = {}
        for role in roles_result.scalars().all():
            role_privileges[role.role_id] = {privilege.name for privilege in role.privileges}

        # group id -> member user ids
        result = await db_session.execute(select(models.UserGroup).options(selectinload(models.UserGroup.users)))
        group_members: Dict[UUID, Set[UUID]] = {}
        for group in result.scalars().all():
            group_members[group.user_group_id] = {user.user_id for user in group.users}

        # ACEs, in natural database order (group ACE evaluation order relies on it)
        aces_result = await db_session.execute(select(models.ACE))
        aces: List[AceEntry] = []
        for ace in aces_result.scalars().all():
            # ACE uses legacy Column declarations, so typed attribute access
            # on instances is not available: go through the plain dict
            values = ace.asdict()
            aces.append(
                AceEntry(
                    path=values["path"],
                    propagate=values["propagate"],
                    allowed=values["allowed"],
                    user_id=values["user_id"],
                    group_id=values["group_id"],
                    role_id=values["role_id"],
                )
            )

        # all registered project resources, pooled or not: the pool gate in
        # user_has_privilege checks paths against every project resource
        resources_result = await db_session.execute(
            select(models.Resource)
            .options(selectinload(models.Resource.resource_pools))
            .filter(models.Resource.resource_type == "project")
        )
        project_resource_ids: Set[str] = set()
        pool_projects: Dict[str, Set[str]] = {}
        for resource in resources_result.scalars().all():
            project_resource_ids.add(str(resource.resource_id))
            for pool in resource.resource_pools:
                pool_projects.setdefault(str(pool.resource_pool_id), set()).add(str(resource.resource_id))

        self._role_privileges = role_privileges
        self._group_members = group_members
        self._aces = aces
        self._project_resource_ids = project_resource_ids
        self._pool_projects = pool_projects
        self._loaded = True
        log.debug(f"RBAC snapshot reloaded: {len(aces)} ACE(s), {len(role_privileges)} role(s)")

    async def ensure_loaded(self, db_session: AsyncSession) -> None:
        """
        Rebuild the snapshot if it has never been loaded or is dirty.
        """

        if self.needs_reload:
            await self.reload(db_session)

    #
    # Evaluation methods below are pure: no database access.
    #

    def _user_aces(self, user_id: UUID, privilege_name: str) -> List[AceEntry]:
        """
        ACEs assigned to the user itself granting the privilege,
        sorted by descending path (same order as the SQL implementation).
        """

        aces = [
            ace
            for ace in self._aces
            if ace.user_id == user_id and privilege_name in self._role_privileges.get(ace.role_id, ())
        ]
        return sorted(aces, key=lambda ace: ace.path, reverse=True)

    def _group_aces(self, user_id: UUID, privilege_name: str) -> List[AceEntry]:
        """
        ACEs assigned to the groups the user belongs to granting the
        privilege, in natural order (same order as the SQL implementation).
        """

        groups = {group_id for group_id, members in self._group_members.items() if user_id in members}
        return [
            ace
            for ace in self._aces
            if ace.group_id is not None
            and ace.group_id in groups
            and privilege_name in self._role_privileges.get(ace.role_id, ())
        ]

    @staticmethod
    def _check_path_with_aces(path: str, aces: Iterable[AceEntry]) -> bool:
        """
        Compare path with existing ACEs to check if the user has the required privilege on that path.
        """

        parsed_url = urlparse(path)
        original_path = path
        path_components = parsed_url.path.split("/")
        # traverse the path in reverse order
        for i in range(len(path_components), 0, -1):
            path = "/".join(path_components[:i])
            if not path:
                path = "/"
            for ace in aces:
                if ace.path == path:
                    if not ace.allowed:
                        raise PermissionError(f"Permission denied for {path}")
                    if path == original_path or ace.propagate:
                        return True  # only allow if the path is the original path or the ACE is set to propagate
        return False

    @staticmethod
    def _check_path_role(path: str, aces: Iterable[AceEntry]):
        """
        Role id of the ACE that decides the path, or one of the module
        sentinels when the path is denied or no ACE matches.

        Mirrors _check_path_with_aces (deepest path first, a deny wins over
        an allow, an allow only applies to the exact path or when the ACE
        propagates) and is used to grant a resource creator the same role
        that allowed the creation, applied to the new resource path.
        """

        parsed_url = urlparse(path)
        original_path = path
        path_components = parsed_url.path.split("/")
        for i in range(len(path_components), 0, -1):
            candidate = "/".join(path_components[:i])
            if not candidate:
                candidate = "/"
            for ace in aces:
                if ace.path == candidate:
                    if not ace.allowed:
                        return _ACE_DENIED
                    if candidate == original_path or ace.propagate:
                        return ace.role_id
        return _ACE_NO_MATCH

    def effective_role_id(self, user_id: UUID, path: str, privilege_name: str) -> Optional[UUID]:
        """
        Role id of the ACE that decides a privilege check for the user.

        User ACEs are evaluated before group ACEs, exactly like
        user_has_privilege. Returns None when the check is denied or when no
        ACE matches.
        """

        role_id = self._check_path_role(path, self._user_aces(user_id, privilege_name))
        if role_id is _ACE_NO_MATCH:
            role_id = self._check_path_role(path, self._group_aces(user_id, privilege_name))
        if role_id is _ACE_NO_MATCH or role_id is _ACE_DENIED:
            return None
        return role_id

    def _pool_grants_path(self, aces: Iterable[AceEntry], path: str) -> bool:
        """
        Whether any pool referenced by the given ACEs contains a project
        matching the path (the previous implementation returned the list
        of matching resources; only its truthiness was used).
        """

        for ace in aces:
            if ace.path.startswith("/pool"):
                pool_id = ace.path.split("/")[2]
                for project_id in self._pool_projects.get(pool_id, ()):
                    if path.startswith(f"/projects/{project_id}"):
                        return True
        return False

    def user_has_privilege(self, user_id: UUID, path: str, privilege_name: str) -> bool:
        """
        Check the user has a privilege on a path.

        Resource paths form a file system like tree and privileges can be inherited by paths down that tree
        (the propagate field is True by default)

        The following inheritance rules are used:

        * Privileges for individual users always replace group privileges.
        * Privileges for groups apply when the user is member of that group.
        * Privileges on deeper levels replace those inherited from an upper level.
        """

        path_is_in_pool = any(path.startswith(f"/projects/{resource_id}") for resource_id in self._project_resource_ids)

        user_aces = self._user_aces(user_id, privilege_name)
        try:
            # Check regular ACEs first
            if self._check_path_with_aces(path, user_aces):
                # the user has an ACE matching the path and privilege, there is no need to check group ACEs
                return True
            # Then check resource pool ACEs
            if path_is_in_pool:
                if self._pool_grants_path(user_aces, path):
                    return True
        except PermissionError:
            return False

        group_aces = self._group_aces(user_id, privilege_name)
        try:
            # Check regular ACEs first
            if self._check_path_with_aces(path, group_aces):
                return True
            # Then check resource pool ACEs
            if path_is_in_pool:
                if self._pool_grants_path(group_aces, path):
                    return True
        except PermissionError:
            return False
        return False

    def user_privilege_names(self, user_id: UUID) -> Set[str]:
        """
        Names of all privileges granted to a user through its roles, via
        ACEs on the user itself and on the groups the user belongs to.
        Flattened view that ignores resource paths.
        """

        groups = {group_id for group_id, members in self._group_members.items() if user_id in members}
        names: Set[str] = set()
        for ace in self._aces:
            if not ace.allowed:
                continue
            if ace.user_id == user_id or (ace.group_id is not None and ace.group_id in groups):
                names.update(self._role_privileges.get(ace.role_id, ()))
        return names

    def _direct_project_ids(
        self, user_aces: List[AceEntry], group_aces: List[AceEntry], all_project_ids: List[str]
    ) -> Tuple[Set[str], Set[str]]:
        """
        Projects the user can access via a direct ACE on /projects/<id>:
        user ACEs first (a deny puts the project aside as denied), then
        group ACEs skipping already accessible or denied projects.
        """

        direct_ace_ids = set()
        user_denied = set()

        # --- User ACE: direct path check ---
        for pid in all_project_ids:
            path = f"/projects/{pid}"
            try:
                if self._check_path_with_aces(path, user_aces):
                    direct_ace_ids.add(pid)
            except PermissionError:
                user_denied.add(pid)

        # --- Group ACE: direct path check (skip already accessible or denied) ---
        for pid in all_project_ids:
            if pid in direct_ace_ids or pid in user_denied:
                continue
            path = f"/projects/{pid}"
            try:
                if self._check_path_with_aces(path, group_aces):
                    direct_ace_ids.add(pid)
            except PermissionError:
                pass

        return direct_ace_ids, user_denied

    def _pooled_project_ids(
        self, user_aces: List[AceEntry], group_aces: List[AceEntry], user_denied: Set[str]
    ) -> Set[str]:
        """
        Projects the user can access because they sit in a resource pool
        referenced by an allowed ACE: user pools first, then group pools.
        """

        # --- User ACE: pool check ---
        user_pool_ids = {ace.path.split("/")[2] for ace in user_aces if ace.path.startswith("/pools/") and ace.allowed}

        pool_accessible_ids = set()
        for pool_id, project_ids in self._pool_projects.items():
            if pool_id in user_pool_ids:
                for pid in project_ids:
                    if pid not in user_denied:
                        pool_accessible_ids.add(pid)

        # --- Group ACE: pool check ---
        group_pool_ids = {
            ace.path.split("/")[2] for ace in group_aces if ace.path.startswith("/pools/") and ace.allowed
        }

        for pool_id, project_ids in self._pool_projects.items():
            if pool_id in group_pool_ids:
                for pid in project_ids:
                    if pid not in user_denied and pid not in pool_accessible_ids:
                        pool_accessible_ids.add(pid)

        return pool_accessible_ids

    def accessible_project_ids(
        self, user_id: UUID, privilege_name: str, all_project_ids: List[str]
    ) -> Tuple[Set[str], Set[str]]:
        """
        Batch check which projects a user can access via direct ACE or resource pools.

        Returns:
            (direct_ace_ids, pool_accessible_ids) where:
            - direct_ace_ids: projects the user has a direct ACE on (needs created_by filter)
            - pool_accessible_ids: projects in resource pools the user can access (no created_by filter)
        """

        user_aces = self._user_aces(user_id, privilege_name)
        group_aces = self._group_aces(user_id, privilege_name)

        direct_ace_ids, user_denied = self._direct_project_ids(user_aces, group_aces, all_project_ids)
        pool_accessible_ids = self._pooled_project_ids(user_aces, group_aces, user_denied)
        return direct_ace_ids, pool_accessible_ids
