#!/usr/bin/env python
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

from uuid import UUID
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

        query = select(models.Role).\
            options(selectinload(models.Role.permissions)).\
            where(models.Role.role_id == role_id)
        result = await self._db_session.execute(query)
        return result.scalars().first()

    async def get_role_by_name(self, name: str) -> Optional[models.Role]:

        query = select(models.Role).\
            options(selectinload(models.Role.permissions)).\
            where(models.Role.name == name)
        #query = select(models.Role).where(models.Role.name == name)
        result = await self._db_session.execute(query)
        return result.scalars().first()

    async def get_roles(self) -> List[models.Role]:

        query = select(models.Role).options(selectinload(models.Role.permissions))
        result = await self._db_session.execute(query)
        return result.scalars().all()

    async def create_role(self, role_create: schemas.RoleCreate) -> models.Role:

        db_role = models.Role(
            name=role_create.name,
            description=role_create.description,
        )
        self._db_session.add(db_role)
        await self._db_session.commit()
        #await self._db_session.refresh(db_role)
        return await self.get_role(db_role.role_id)

    async def update_role(
            self,
            role_id: UUID,
            role_update: schemas.RoleUpdate
    ) -> Optional[models.Role]:

        update_values = role_update.dict(exclude_unset=True)
        query = update(models.Role).where(models.Role.role_id == role_id).values(update_values)

        await self._db_session.execute(query)
        await self._db_session.commit()
        return await self.get_role(role_id)

    async def delete_role(self, role_id: UUID) -> bool:

        query = delete(models.Role).where(models.Role.role_id == role_id)
        result = await self._db_session.execute(query)
        await self._db_session.commit()
        return result.rowcount > 0

    async def add_permission_to_role(
            self,
            role_id: UUID,
            permission: models.Permission
    ) -> Union[None, models.Role]:

        query = select(models.Role).\
            options(selectinload(models.Role.permissions)).\
            where(models.Role.role_id == role_id)
        result = await self._db_session.execute(query)
        role_db = result.scalars().first()
        if not role_db:
            return None

        role_db.permissions.append(permission)
        await self._db_session.commit()
        await self._db_session.refresh(role_db)
        return role_db

    async def remove_permission_from_role(
            self,
            role_id: UUID,
            permission: models.Permission
    ) -> Union[None, models.Role]:

        query = select(models.Role).\
            options(selectinload(models.Role.permissions)).\
            where(models.Role.role_id == role_id)
        result = await self._db_session.execute(query)
        role_db = result.scalars().first()
        if not role_db:
            return None

        role_db.permissions.remove(permission)
        await self._db_session.commit()
        await self._db_session.refresh(role_db)
        return role_db

    async def get_role_permissions(self, role_id: UUID) -> List[models.Permission]:

        query = select(models.Permission).\
            join(models.Permission.roles).\
            filter(models.Role.role_id == role_id)

        result = await self._db_session.execute(query)
        return result.scalars().all()

    async def get_permission(self, permission_id: UUID) -> Optional[models.Permission]:

        query = select(models.Permission).where(models.Permission.permission_id == permission_id)
        result = await self._db_session.execute(query)
        return result.scalars().first()

    async def get_permission_by_path(self, path: str) -> Optional[models.Permission]:

        query = select(models.Permission).where(models.Permission.path == path)
        result = await self._db_session.execute(query)
        return result.scalars().first()

    async def get_permissions(self) -> List[models.Permission]:

        query = select(models.Permission)
        result = await self._db_session.execute(query)
        return result.scalars().all()

    async def create_permission(self, permission_create: schemas.PermissionCreate) -> models.Permission:

        create_values = permission_create.dict(exclude_unset=True)
        # action = create_values.pop("action", "deny")
        # is_allowed = False
        # if action == "allow":
        #     is_allowed = True

        db_permission = models.Permission(
            methods=permission_create.methods,
            path=permission_create.path,
            action=permission_create.action,
        )
        self._db_session.add(db_permission)

        await self._db_session.commit()
        await self._db_session.refresh(db_permission)
        return db_permission

    async def update_permission(
            self,
            permission_id: UUID,
            permission_update: schemas.PermissionUpdate
    ) -> Optional[models.Permission]:

        update_values = permission_update.dict(exclude_unset=True)
        query = update(models.Permission).where(models.Permission.permission_id == permission_id).values(update_values)

        await self._db_session.execute(query)
        await self._db_session.commit()
        return await self.get_permission(permission_id)

    async def delete_permission(self, permission_id: UUID) -> bool:

        query = delete(models.Permission).where(models.Permission.permission_id == permission_id)
        result = await self._db_session.execute(query)
        await self._db_session.commit()
        return result.rowcount > 0
