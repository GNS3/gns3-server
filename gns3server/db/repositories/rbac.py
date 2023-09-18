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

from uuid import UUID
from urllib.parse import urlparse
from typing import Optional, List, Union
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .base import BaseRepository

import gns3server.db.models as models
from gns3server import schemas

import logging

log = logging.getLogger(__name__)


class RbacRepository(BaseRepository):

    def __init__(self, db_session: AsyncSession) -> None:

        super().__init__(db_session)

    async def get_role(self, role_id: UUID) -> Optional[models.Role]:
        """
        Get a role by its ID.
        """

        query = select(models.Role).\
            options(selectinload(models.Role.privileges)).\
            where(models.Role.role_id == role_id)
        result = await self._db_session.execute(query)
        return result.scalars().first()

    async def get_role_by_name(self, name: str) -> Optional[models.Role]:
        """
        Get a role by its name.
        """

        query = select(models.Role).\
            options(selectinload(models.Role.privileges)).\
            where(models.Role.name == name)
        result = await self._db_session.execute(query)
        return result.scalars().first()

    async def get_roles(self) -> List[models.Role]:
        """
        Get all roles.
        """

        query = select(models.Role).options(selectinload(models.Role.privileges))
        result = await self._db_session.execute(query)
        return result.scalars().all()

    async def create_role(self, role_create: schemas.RoleCreate) -> models.Role:
        """
        Create a new role.
        """

        db_role = models.Role(
            name=role_create.name,
            description=role_create.description,
        )
        self._db_session.add(db_role)
        await self._db_session.commit()
        return await self.get_role(db_role.role_id)

    async def update_role(
            self,
            role_id: UUID,
            role_update: schemas.RoleUpdate
    ) -> Optional[models.Role]:
        """
        Update a role.
        """

        update_values = role_update.model_dump(exclude_unset=True)
        query = update(models.Role).\
            where(models.Role.role_id == role_id).\
            values(update_values)

        await self._db_session.execute(query)
        await self._db_session.commit()
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
        return result.rowcount > 0

    async def add_privilege_to_role(
            self,
            role_id: UUID,
            privilege: models.Privilege
    ) -> Union[None, models.Role]:
        """
        Add a privilege to a role.
        """

        query = select(models.Role).\
            options(selectinload(models.Role.privileges)).\
            where(models.Role.role_id == role_id)
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
        await self._db_session.refresh(role_db)
        return role_db

    async def remove_privilege_from_role(
            self,
            role_id: UUID,
            privilege: models.Privilege
    ) -> Union[None, models.Role]:
        """
        Remove a privilege from a role.
        """

        query = select(models.Role).\
            options(selectinload(models.Role.privileges)).\
            where(models.Role.role_id == role_id)
        result = await self._db_session.execute(query)
        role_db = result.scalars().first()
        if not role_db:
            return None

        role_db.privileges.remove(privilege)
        await self._db_session.commit()
        await self._db_session.refresh(role_db)
        return role_db

    async def get_role_privileges(self, role_id: UUID) -> List[models.Privilege]:
        """
        Get all the role privileges.
        """

        query = select(models.Privilege).\
            join(models.Privilege.roles).\
            filter(models.Role.role_id == role_id)

        result = await self._db_session.execute(query)
        return result.scalars().all()

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
        return result.scalars().all()

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
        return result.scalars().all()

    async def check_ace_exists(self, path: str) -> bool:
        """
        Check if an ACE exists.
        """

        query = select(models.ACE).\
            where(models.ACE.path == path)
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
        await self._db_session.refresh(db_ace)
        return db_ace

    async def update_ace(
            self,
            ace_id: UUID,
            ace_update: schemas.ACEUpdate
    ) -> Optional[models.ACE]:
        """
        Update an ACE
        """

        update_values = ace_update.model_dump(exclude_unset=True)
        query = update(models.ACE).\
            where(models.ACE.ace_id == ace_id).\
            values(update_values)

        await self._db_session.execute(query)
        await self._db_session.commit()
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
        return result.rowcount > 0

    async def delete_all_ace_starting_with_path(self, path: str) -> None:
        """
        Delete all ACEs starting with path.
        """

        query = delete(models.ACE).\
            where(models.ACE.path.startswith(path)).\
            execution_options(synchronize_session=False)
        result = await self._db_session.execute(query)
        log.debug(f"{result.rowcount} ACE(s) have been deleted")

    @staticmethod
    def _check_path_with_aces(path: str, aces) -> bool:
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
            for ace_path, ace_propagate, ace_allowed, ace_privilege in aces:
                if ace_path == path:
                    if not ace_allowed:
                        raise PermissionError(f"Permission denied for {path}")
                    if path == original_path or ace_propagate:
                        return True  # only allow if the path is the original path or the ACE is set to propagate
        return False

    async def _get_resources_in_pools(self, aces, path: str = None) -> List[models.Resource]:
        """
        Get all resources in pools.
        """

        pool_resources = []
        for ace_path, ace_propagate, ace_allowed, ace_privilege in aces:
            if ace_path.startswith("/pool"):
                resource_pool_id = ace_path.split("/")[2]
                query = select(models.Resource). \
                    join(models.Resource.resource_pools). \
                    filter(models.ResourcePool.resource_pool_id == resource_pool_id)

                result = await self._db_session.execute(query)
                resources = result.scalars().all()

                for resource in resources:
                    # we only support projects in resource pools for now
                    if resource.resource_type == "project":
                        if path:
                            if path.startswith(f"/projects/{resource.resource_id}"):
                                pool_resources.append(resource)
                        else:
                            pool_resources.append(resource)
        return pool_resources

    async def _get_user_aces(self, user_id: UUID, privilege_name: str):
        """
        Retrieve all user ACEs matching the user_id and privilege name.
        """

        query = select(models.ACE.path, models.ACE.propagate, models.ACE.allowed, models.Privilege.name).\
            join(models.Privilege.roles).\
            join(models.Role.acl_entries).\
            join(models.ACE.user). \
            filter(models.User.user_id == user_id).\
            filter(models.Privilege.name == privilege_name).\
            order_by(models.ACE.path.desc())

        result = await self._db_session.execute(query)
        return result.all()

    async def _get_group_aces(self, user_id: UUID, privilege_name: str):
        """
        Retrieve all group ACEs matching the user_id and privilege name.
        """

        query = select(models.ACE.path, models.ACE.propagate, models.ACE.allowed, models.Privilege.name). \
            join(models.Privilege.roles). \
            join(models.Role.acl_entries). \
            join(models.ACE.group). \
            join(models.UserGroup.users).\
            filter(models.User.user_id == user_id). \
            filter(models.Privilege.name == privilege_name)

        result = await self._db_session.execute(query)
        return result.all()

    async def get_user_pool_resources(self, user_id: UUID, privilege_name: str) -> List[models.Resource]:
        """
        Get all resources in pools belonging to a user and groups
        """

        user_aces = await self._get_user_aces(user_id, privilege_name)
        pool_resources = await self._get_resources_in_pools(user_aces)
        group_aces = await self._get_group_aces(user_id, privilege_name)
        pool_resources.extend(await self._get_resources_in_pools(group_aces))
        return list(set(pool_resources))

    async def check_user_has_privilege(self, user_id: UUID, path: str, privilege_name: str) -> bool:
        """
        Resource paths form a file system like tree and privileges can be inherited by paths down that tree
        (the propagate field is True by default)

        The following inheritance rules are used:

        * Privileges for individual users always replace group privileges.
        * Privileges for groups apply when the user is member of that group.
        * Privileges on deeper levels replace those inherited from an upper level.
        """

        query = select(models.Resource)
        result = await self._db_session.execute(query)
        resources = result.scalars().all()
        projects_in_pools = [f"/projects/{r.resource_id}" for r in resources if r.resource_type == "project"]
        path_is_in_pool = False
        for project_in_pool in projects_in_pools:
            if path.startswith(project_in_pool):
                path_is_in_pool = True
                break

        aces = await self._get_user_aces(user_id, privilege_name)
        try:
            if path_is_in_pool:
                if await self._get_resources_in_pools(aces, path):
                    return True
            elif self._check_path_with_aces(path, aces):
                # the user has an ACE matching the path and privilege, there is no need to check group ACEs
                return True
        except PermissionError:
            return False

        aces = await self._get_group_aces(user_id, privilege_name)
        try:
            if path_is_in_pool:
                if await self._get_resources_in_pools(aces, path):
                    return True
            elif self._check_path_with_aces(path, aces):
                return True
        except PermissionError:
            return False
        return False
