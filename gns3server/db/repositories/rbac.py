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

import logging
from typing import List, Optional, Set, Union, cast
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import gns3server.db.models as models
from gns3server import schemas
from gns3server.db.rbac_state import RbacState

from .base import BaseRepository

log = logging.getLogger(__name__)


class RbacRepository(BaseRepository):
    def __init__(self, db_session: AsyncSession) -> None:

        super().__init__(db_session)
        self._rbac_state = RbacState.instance()

    async def get_role(self, role_id: UUID) -> Optional[models.Role]:
        """
        Get a role by its ID.
        """

        query = select(models.Role).options(selectinload(models.Role.privileges)).where(models.Role.role_id == role_id)
        result = await self._db_session.execute(query)
        return result.scalars().first()

    async def get_role_by_name(self, name: str) -> Optional[models.Role]:
        """
        Get a role by its name.
        """

        query = select(models.Role).options(selectinload(models.Role.privileges)).where(models.Role.name == name)
        result = await self._db_session.execute(query)
        return result.scalars().first()

    async def get_roles(self) -> List[models.Role]:
        """
        Get all roles.
        """

        query = select(models.Role).options(selectinload(models.Role.privileges))
        result = await self._db_session.execute(query)
        return list(result.scalars().all())

    async def create_role(self, role_create: schemas.RoleCreate) -> Optional[models.Role]:
        """
        Create a new role.
        """

        db_role = models.Role(
            name=role_create.name,
            description=role_create.description,
        )
        self._db_session.add(db_role)
        await self._db_session.commit()
        self._rbac_state.mark_dirty()
        return await self.get_role(db_role.role_id)

    async def update_role(self, role_id: UUID, role_update: schemas.RoleUpdate) -> Optional[models.Role]:
        """
        Update a role.
        """

        update_values = role_update.model_dump(exclude_unset=True)
        query = update(models.Role).where(models.Role.role_id == role_id).values(update_values)

        await self._db_session.execute(query)
        await self._db_session.commit()
        self._rbac_state.mark_dirty()
        role_db = await self.get_role(role_id)
        if role_db:
            await self._db_session.refresh(role_db)  # force refresh of updated_at value
        return role_db

    async def delete_role(self, role_id: UUID) -> bool:
        """
        Delete a role.
        """

        query = delete(models.Role).where(models.Role.role_id == role_id)
        result = await self._db_session.execute(query)
        await self._db_session.commit()
        self._rbac_state.mark_dirty()
        return cast(CursorResult, result).rowcount > 0

    async def add_privilege_to_role(self, role_id: UUID, privilege: models.Privilege) -> Union[None, models.Role]:
        """
        Add a privilege to a role.
        """

        query = select(models.Role).options(selectinload(models.Role.privileges)).where(models.Role.role_id == role_id)
        result = await self._db_session.execute(query)
        role_db = result.scalars().first()
        if not role_db:
            return None

        """
         Skip add new privilege if already added for this role.
        """
        for p in role_db.privileges:
            if p.privilege_id == privilege.privilege_id:
                return role_db

        role_db.privileges.append(privilege)
        await self._db_session.commit()
        self._rbac_state.mark_dirty()
        await self._db_session.refresh(role_db)
        return role_db

    async def remove_privilege_from_role(self, role_id: UUID, privilege: models.Privilege) -> Union[None, models.Role]:
        """
        Remove a privilege from a role.
        """

        query = select(models.Role).options(selectinload(models.Role.privileges)).where(models.Role.role_id == role_id)
        result = await self._db_session.execute(query)
        role_db = result.scalars().first()
        if not role_db:
            return None

        role_db.privileges.remove(privilege)
        await self._db_session.commit()
        self._rbac_state.mark_dirty()
        await self._db_session.refresh(role_db)
        return role_db

    async def get_role_privileges(self, role_id: UUID) -> List[models.Privilege]:
        """
        Get all the role privileges.
        """

        query = select(models.Privilege).join(models.Privilege.roles).filter(models.Role.role_id == role_id)

        result = await self._db_session.execute(query)
        return list(result.scalars().all())

    async def get_privilege(self, privilege_id: UUID) -> Optional[models.Privilege]:
        """
        Get a privilege by its ID.
        """

        query = select(models.Privilege).where(models.Privilege.privilege_id == privilege_id)
        result = await self._db_session.execute(query)
        return result.scalars().first()

    async def get_privilege_by_name(self, name: str) -> Optional[models.Privilege]:
        """
        Get a privilege by its name.
        """

        query = select(models.Privilege).where(models.Privilege.name == name)
        result = await self._db_session.execute(query)
        return result.scalars().first()

    async def get_privileges(self) -> List[models.Privilege]:
        """
        Get all privileges.
        """

        query = select(models.Privilege)
        result = await self._db_session.execute(query)
        return list(result.scalars().all())

    async def get_user_privileges(self, user_id: UUID) -> Set[str]:
        """
        Get the names of all privileges granted to a user through its roles,
        via ACEs on the user itself and on the groups the user belongs to.

        This is a flattened view that ignores resource paths: the authoritative
        check remains check_user_has_privilege(), which takes paths into account.
        """

        await self._rbac_state.ensure_loaded(self._db_session)
        return self._rbac_state.user_privilege_names(user_id)

    async def get_ace(self, ace_id: UUID) -> Optional[models.ACE]:
        """
        Get an ACE by its ID.
        """

        query = select(models.ACE).where(models.ACE.ace_id == ace_id)
        result = await self._db_session.execute(query)
        return result.scalars().first()

    async def get_ace_by_path(self, path: str) -> Optional[models.ACE]:
        """
        Get an ACE by its path.
        """

        query = select(models.ACE).where(models.ACE.path == path)
        result = await self._db_session.execute(query)
        return result.scalars().first()

    async def get_aces(self) -> List[models.ACE]:
        """
        Get all ACEs.
        """

        query = select(models.ACE)
        result = await self._db_session.execute(query)
        return list(result.scalars().all())

    async def get_aces_for_path(self, path: str) -> List[models.ACE]:
        """
        Get all ACEs for a specific path (exact match or starting with path).

        This method includes related user, group, and role information.
        """

        query = (
            select(models.ACE)
            .where((models.ACE.path == path) | (models.ACE.path.startswith(path + "/")))
            .options(selectinload(models.ACE.user), selectinload(models.ACE.group), selectinload(models.ACE.role))
        )
        result = await self._db_session.execute(query)
        return list(result.scalars().all())

    async def check_ace_exists(self, path: str) -> bool:
        """
        Check if an ACE exists.
        """

        query = select(models.ACE).where(models.ACE.path == path)
        result = await self._db_session.execute(query)
        return result.scalars().first() is not None

    async def create_ace(self, ace_create: schemas.ACECreate) -> models.ACE:
        """
        Create a new ACE
        """

        create_values = ace_create.model_dump(exclude_unset=True)
        db_ace = models.ACE(**create_values)
        self._db_session.add(db_ace)
        await self._db_session.commit()
        self._rbac_state.mark_dirty()
        await self._db_session.refresh(db_ace)
        return db_ace

    async def update_ace(self, ace_id: UUID, ace_update: schemas.ACEUpdate) -> Optional[models.ACE]:
        """
        Update an ACE
        """

        update_values = ace_update.model_dump(exclude_unset=True)
        query = update(models.ACE).where(models.ACE.ace_id == ace_id).values(update_values)

        await self._db_session.execute(query)
        await self._db_session.commit()
        self._rbac_state.mark_dirty()
        ace_db = await self.get_ace(ace_id)
        if ace_db:
            await self._db_session.refresh(ace_db)  # force refresh of updated_at value
        return ace_db

    async def delete_ace(self, ace_id: UUID) -> bool:
        """
        Delete an ACE
        """

        query = delete(models.ACE).where(models.ACE.ace_id == ace_id)
        result = await self._db_session.execute(query)
        await self._db_session.commit()
        self._rbac_state.mark_dirty()
        return cast(CursorResult, result).rowcount > 0

    async def delete_all_ace_starting_with_path(self, path: str) -> None:
        """
        Delete all ACEs starting with path.
        """

        query = delete(models.ACE).where(models.ACE.path.startswith(path)).execution_options(synchronize_session=False)
        result = await self._db_session.execute(query)
        await self._db_session.commit()
        self._rbac_state.mark_dirty()
        log.debug(f"{cast(CursorResult, result).rowcount} ACE(s) have been deleted")

    async def get_accessible_project_ids(self, user_id: UUID, privilege_name: str, all_project_ids: List[str]):
        """
        Batch check which projects a user can access via direct ACE or resource pools.

        Returns:
            (direct_ace_ids, pool_accessible_ids) where:
            - direct_ace_ids: projects the user has a direct ACE on (needs created_by filter)
            - pool_accessible_ids: projects in resource pools the user can access (no created_by filter)
        """

        await self._rbac_state.ensure_loaded(self._db_session)
        return self._rbac_state.accessible_project_ids(user_id, privilege_name, all_project_ids)

    async def check_user_has_privilege(self, user_id: UUID, path: str, privilege_name: str) -> bool:
        """
        Resource paths form a file system like tree and privileges can be inherited by paths down that tree
        (the propagate field is True by default)

        The following inheritance rules are used:

        * Privileges for individual users always replace group privileges.
        * Privileges for groups apply when the user is member of that group.
        * Privileges on deeper levels replace those inherited from an upper level.

        The check runs against the in-memory RBAC snapshot (rebuilt after
        any RBAC write), see gns3server.db.rbac_state.
        """

        await self._rbac_state.ensure_loaded(self._db_session)
        return self._rbac_state.user_has_privilege(user_id, path, privilege_name)
