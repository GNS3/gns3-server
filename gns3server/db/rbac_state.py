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
One semantic is stronger here: a user-level ACE covering a path decides
the check alone, whatever role it carries, so a group grant can never
widen a reduced user-level role (this is what freezes a distributed
project copy for its recipient).
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
        self._user_names: Dict[UUID, str] = {}
        self._superadmin_ids: Set[UUID] = set()
        self._aces: List[AceEntry] = []
        self._project_resource_ids: Set[str] = set()
        # pool id (str) -> project resource ids (str)
        self._pool_projects: Dict[str, Set[str]] = {}
        # group id -> MCP tool names whitelisted for that group (a group
        # missing from the dict has no whitelist: every tool is allowed)
        self._mcp_tool_whitelists: Dict[UUID, Set[str]] = {}

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
        self._user_names = {}
        self._superadmin_ids = set()
        self._aces = []
        self._project_resource_ids = set()
        self._pool_projects = {}
        self._mcp_tool_whitelists = {}

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

        # user id -> username: owner ACEs carry no marker, they are identified
        # by matching the ACE user against the project creator's username.
        # User uses legacy Column declarations (like ACE), so go through the
        # plain dict for typed access
        users_result = await db_session.execute(select(models.User))
        user_names: Dict[UUID, str] = {}
        superadmin_ids: Set[UUID] = set()
        for user in users_result.scalars().all():
            values = user.asdict()
            user_names[values["user_id"]] = values["username"]
            if values["is_superadmin"]:
                superadmin_ids.add(values["user_id"])

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

        # group id -> whitelisted MCP tool names (absent = no whitelist). A
        # sentinel row with an empty tool name marks a configured-but-empty
        # whitelist (hide every tool): the key exists, the set stays empty.
        whitelist_result = await db_session.execute(select(models.MCPToolWhitelist))
        mcp_tool_whitelists: Dict[UUID, Set[str]] = {}
        for entry in whitelist_result.scalars().all():
            names = mcp_tool_whitelists.setdefault(entry.user_group_id, set())
            if entry.tool_name:
                names.add(entry.tool_name)

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
        self._user_names = user_names
        self._superadmin_ids = superadmin_ids
        self._aces = aces
        self._project_resource_ids = project_resource_ids
        self._pool_projects = pool_projects
        self._mcp_tool_whitelists = mcp_tool_whitelists
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

    def _all_user_aces(self, user_id: UUID) -> List[AceEntry]:
        """
        Every ACE assigned to the user itself, whatever its role carries: a
        user-level ACE covering a path decides the check alone, so all of
        them are candidates when looking for the deciding one.
        """

        return [ace for ace in self._aces if ace.user_id == user_id]

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

    @staticmethod
    def _deciding_user_ace(path: str, aces: Iterable[AceEntry]) -> Optional[AceEntry]:
        """
        The user-level ACE that decides a check on the path, or None.

        Deepest path first, an allow only covers the exact path or propagates:
        whatever role it carries, that ACE speaks for the user on this path
        and replaces every group-level ACE (a reduced role must not be widen
        by a group grant, a deny must not be bypassed either).
        """

        parsed_url = urlparse(path)
        original_path = path
        path_components = parsed_url.path.split("/")
        for i in range(len(path_components), 0, -1):
            candidate = "/".join(path_components[:i])
            if not candidate:
                candidate = "/"
            for ace in aces:
                if ace.path == candidate and (candidate == original_path or ace.propagate):
                    return ace
        return None

    def effective_role_id(self, user_id: UUID, path: str, privilege_name: str) -> Optional[UUID]:
        """
        Role id of the ACE that decides a privilege check for the user.

        A user-level ACE covering the path decides alone, exactly like in
        user_has_privilege. Returns None when the check is denied or when no
        ACE matches.
        """

        deciding_ace = self._deciding_user_ace(path, self._all_user_aces(user_id))
        if deciding_ace is not None:
            if deciding_ace.allowed and privilege_name in self._role_privileges.get(deciding_ace.role_id, ()):
                return deciding_ace.role_id
            return None  # the user-level ACE speaks for the user: the check is denied

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

        * A user-level ACE covering the path decides the check alone, whatever
          role it carries: a group grant cannot widen a reduced user-level
          role, and a user-level deny cannot be bypassed by a group either.
        * Privileges for groups apply when the user is member of that group.
        * Privileges on deeper levels replace those inherited from an upper level.
        """

        path_is_in_pool = any(path.startswith(f"/projects/{resource_id}") for resource_id in self._project_resource_ids)

        # a user-level ACE covering the path replaces everything else
        deciding_ace = self._deciding_user_ace(path, self._all_user_aces(user_id))
        if deciding_ace is not None:
            return deciding_ace.allowed and privilege_name in self._role_privileges.get(deciding_ace.role_id, ())

        # no user-level ACE covers the path: a user-level resource pool can
        # still grant it, before the group-level ACEs are considered
        user_aces = self._user_aces(user_id, privilege_name)
        try:
            if path_is_in_pool and self._pool_grants_path(user_aces, path):
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

    def group_privilege_names(self, group_id: UUID) -> Set[str]:
        """
        Names of all privileges granted to a group through the roles carried
        by its allowed ACEs. Same flattened view as user_privilege_names,
        scoped to a single group: this is the candidate set an admin sees
        when configuring the group's MCP tool whitelist.
        """

        names: Set[str] = set()
        for ace in self._aces:
            if ace.allowed and ace.group_id == group_id:
                names.update(self._role_privileges.get(ace.role_id, ()))
        return names

    def group_mcp_tools(self, group_id: UUID) -> Optional[Set[str]]:
        """
        Whitelisted MCP tool names for a group, or None when the group has
        no whitelist configured (every tool stays allowed).
        """

        whitelist = self._mcp_tool_whitelists.get(group_id)
        return set(whitelist) if whitelist is not None else None

    def group_mcp_bypass(self, group_id: UUID) -> bool:
        """
        Whether a whitelist for this group cannot affect anyone right now:
        the group has no member that is not a superadmin (superadmins bypass
        the whitelist entirely, and an empty group has nobody to restrict).
        The config stays allowed: adding a regular member later makes it
        effective again.
        """

        members = self._group_members.get(group_id, set())
        return all(user_id in self._superadmin_ids for user_id in members)

    def user_mcp_tool_whitelist(self, user_id: UUID) -> Optional[Set[str]]:
        """
        Effective MCP tool whitelist for a user: the union of the
        whitelists of the groups the user belongs to. A group without a
        configured whitelist does not restrict its members, so as soon as
        one of the user's groups is unconfigured the result is None (no
        restriction). Users in no group at all are unrestricted too.
        """

        groups = {group_id for group_id, members in self._group_members.items() if user_id in members}
        configured = [self._mcp_tool_whitelists[g] for g in groups if g in self._mcp_tool_whitelists]
        if len(configured) < len(groups):
            return None
        return set().union(*configured) if configured else None

    def _direct_project_ids(
        self, user_aces_all: List[AceEntry], group_aces: List[AceEntry], privilege_name: str, all_project_ids: List[str]
    ) -> Tuple[Set[str], Set[str]]:
        """
        Projects the user can access via a direct ACE on /projects/<id>.

        A user-level ACE covering the project path decides alone, even when
        its role lacks the privilege: the group ACEs are only consulted for
        projects without a user-level ACE. Returns the accessible ids and
        the ids decided by a user-level ACE (out of reach for pools too).
        """

        direct_ace_ids = set()
        user_decided = set()

        # --- User ACE: direct path check ---
        for pid in all_project_ids:
            path = f"/projects/{pid}"
            deciding_ace = self._deciding_user_ace(path, user_aces_all)
            if deciding_ace is not None:
                user_decided.add(pid)
                if deciding_ace.allowed and privilege_name in self._role_privileges.get(deciding_ace.role_id, ()):
                    direct_ace_ids.add(pid)
                continue

            # --- Group ACE: direct path check (only without a user-level ACE) ---
            try:
                if self._check_path_with_aces(path, group_aces):
                    direct_ace_ids.add(pid)
            except PermissionError:
                pass

        return direct_ace_ids, user_decided

    def _pooled_project_ids(
        self, user_aces: List[AceEntry], group_aces: List[AceEntry], user_decided: Set[str]
    ) -> Set[str]:
        """
        Projects the user can access because they sit in a resource pool
        referenced by an allowed ACE: user pools first, then group pools.
        Projects decided by a user-level ACE are left alone.
        """

        # --- User ACE: pool check ---
        user_pool_ids = {ace.path.split("/")[2] for ace in user_aces if ace.path.startswith("/pools/") and ace.allowed}

        pool_accessible_ids = set()
        for pool_id, project_ids in self._pool_projects.items():
            if pool_id in user_pool_ids:
                for pid in project_ids:
                    if pid not in user_decided:
                        pool_accessible_ids.add(pid)

        # --- Group ACE: pool check ---
        group_pool_ids = {
            ace.path.split("/")[2] for ace in group_aces if ace.path.startswith("/pools/") and ace.allowed
        }

        for pool_id, project_ids in self._pool_projects.items():
            if pool_id in group_pool_ids:
                for pid in project_ids:
                    if pid not in user_decided and pid not in pool_accessible_ids:
                        pool_accessible_ids.add(pid)

        return pool_accessible_ids

    def accessible_project_ids(
        self, user_id: UUID, privilege_name: str, all_project_ids: List[str]
    ) -> Tuple[Set[str], Set[str]]:
        """
        Batch check which projects a user can access via direct ACE or resource pools.

        A user-level ACE on the project path decides alone (see
        user_has_privilege); group ACEs apply only to projects without one.

        Returns:
            (direct_ace_ids, pool_accessible_ids) where:
            - direct_ace_ids: projects the user has a direct ACE on (needs created_by filter)
            - pool_accessible_ids: projects in resource pools the user can access (no created_by filter)
        """

        user_aces_all = self._all_user_aces(user_id)
        user_aces = self._user_aces(user_id, privilege_name)
        group_aces = self._group_aces(user_id, privilege_name)

        direct_ace_ids, user_decided = self._direct_project_ids(
            user_aces_all, group_aces, privilege_name, all_project_ids
        )
        pool_accessible_ids = self._pooled_project_ids(user_aces, group_aces, user_decided)
        return direct_ace_ids, pool_accessible_ids

    def project_share_counts(self, owners: Dict[str, Optional[str]]) -> Dict[str, int]:
        """
        Count the share ACEs of the given projects.

        ``owners`` maps project ids to the username of their creator. A share
        is any ACE on /projects/<id> except the owner ACE of the creator (the
        same definition as the /projects/<id>/shares endpoint); a group share
        counts as one share. Projects without a resolvable owner have no owner
        ACE, so every ACE on their path counts. Returns only the projects with
        at least one share.
        """

        ids_by_name = {username: user_id for user_id, username in self._user_names.items()}
        entries = {}
        for project_id, username in owners.items():
            owner_user_id = ids_by_name.get(username) if username else None
            entries[f"/projects/{project_id}"] = (project_id, owner_user_id)

        counts: Dict[str, int] = {}
        for ace in self._aces:
            entry = entries.get(ace.path)
            if entry is None:
                continue
            project_id, owner_user_id = entry
            if ace.user_id is not None and ace.user_id == owner_user_id:
                continue  # the owner ACE is not a share
            counts[project_id] = counts.get(project_id, 0) + 1
        return counts
