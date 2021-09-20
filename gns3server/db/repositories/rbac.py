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
from sqlalchemy import select, update, delete, null
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .base import BaseRepository

import gns3server.db.models as models
from gns3server.schemas.controller.rbac import HTTPMethods, PermissionAction
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
            options(selectinload(models.Role.permissions)).\
            where(models.Role.role_id == role_id)
        result = await self._db_session.execute(query)
        return result.scalars().first()

    async def get_role_by_name(self, name: str) -> Optional[models.Role]:
        """
        Get a role by its name.
        """

        query = select(models.Role).\
            options(selectinload(models.Role.permissions)).\
            where(models.Role.name == name)
        #query = select(models.Role).where(models.Role.name == name)
        result = await self._db_session.execute(query)
        return result.scalars().first()

    async def get_roles(self) -> List[models.Role]:
        """
        Get all roles.
        """

        query = select(models.Role).options(selectinload(models.Role.permissions))
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
        #await self._db_session.refresh(db_role)
        return await self.get_role(db_role.role_id)

    async def update_role(
            self,
            role_id: UUID,
            role_update: schemas.RoleUpdate
    ) -> Optional[models.Role]:
        """
        Update a role.
        """

        update_values = role_update.dict(exclude_unset=True)
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

    async def add_permission_to_role(
            self,
            role_id: UUID,
            permission: models.Permission
    ) -> Union[None, models.Role]:
        """
        Add a permission to a role.
        """

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
        """
        Remove a permission from a role.
        """

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
        """
        Get all the role permissions.
        """

        query = select(models.Permission).\
            join(models.Permission.roles).\
            filter(models.Role.role_id == role_id)

        result = await self._db_session.execute(query)
        return result.scalars().all()

    async def get_permission(self, permission_id: UUID) -> Optional[models.Permission]:
        """
        Get a permission by its ID.
        """

        query = select(models.Permission).where(models.Permission.permission_id == permission_id)
        result = await self._db_session.execute(query)
        return result.scalars().first()

    async def get_permission_by_path(self, path: str) -> Optional[models.Permission]:
        """
        Get a permission by its path.
        """

        query = select(models.Permission).where(models.Permission.path == path)
        result = await self._db_session.execute(query)
        return result.scalars().first()

    async def get_permissions(self) -> List[models.Permission]:
        """
        Get all permissions.
        """

        query = select(models.Permission).\
            order_by(models.Permission.path.desc())
        result = await self._db_session.execute(query)
        return result.scalars().all()

    async def check_permission_exists(self, permission_create: schemas.PermissionCreate) -> bool:
        """
        Check if a permission exists.
        """

        query = select(models.Permission).\
            where(models.Permission.methods == permission_create.methods,
                  models.Permission.path == permission_create.path,
                  models.Permission.action == permission_create.action)
        result = await self._db_session.execute(query)
        return result.scalars().first() is not None

    async def create_permission(self, permission_create: schemas.PermissionCreate) -> models.Permission:
        """
        Create a new permission.
        """

        db_permission = models.Permission(
            description=permission_create.description,
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
        """
        Update a permission.
        """

        update_values = permission_update.dict(exclude_unset=True)
        query = update(models.Permission).\
            where(models.Permission.permission_id == permission_id).\
            values(update_values)

        await self._db_session.execute(query)
        await self._db_session.commit()
        permission_db = await self.get_permission(permission_id)
        if permission_db:
            await self._db_session.refresh(permission_db)  # force refresh of updated_at value
        return permission_db

    async def delete_permission(self, permission_id: UUID) -> bool:
        """
        Delete a permission.
        """

        query = delete(models.Permission).where(models.Permission.permission_id == permission_id)
        result = await self._db_session.execute(query)
        await self._db_session.commit()
        return result.rowcount > 0

    async def prune_permissions(self) -> int:
        """
        Prune orphaned permissions.
        """

        query = select(models.Permission).\
            filter((~models.Permission.roles.any()) & (models.Permission.user_id == null()))
        result = await self._db_session.execute(query)
        permissions = result.scalars().all()
        permissions_deleted = 0
        for permission in permissions:
            if await self.delete_permission(permission.permission_id):
                permissions_deleted += 1
        log.info(f"{permissions_deleted} orphaned permissions have been deleted")
        return permissions_deleted

    def _match_permission(
            self,
            permissions: List[models.Permission],
            method: str,
            path: str
    ) -> Union[None, models.Permission]:
        """
        Match the methods and path with a permission.
        """

        for permission in permissions:
            log.debug(f"RBAC: checking permission {permission.methods} {permission.path} {permission.action}")
            if method not in permission.methods:
                continue
            if permission.path.endswith("/*") and path.startswith(permission.path[:-2]):
                return permission
            elif permission.path == path:
                return permission

    async def get_user_permissions(self, user_id: UUID):
        """
        Get all permissions from an user.
        """

        query = select(models.Permission).\
            join(models.User.permissions).\
            filter(models.User.user_id == user_id).\
            order_by(models.Permission.path.desc())

        result = await self._db_session.execute(query)
        return result.scalars().all()

    async def add_permission_to_user(
            self,
            user_id: UUID,
            permission: models.Permission
    ) -> Union[None, models.User]:
        """
        Add a permission to an user.
        """

        query = select(models.User).\
            options(selectinload(models.User.permissions)).\
            where(models.User.user_id == user_id)
        result = await self._db_session.execute(query)
        user_db = result.scalars().first()
        if not user_db:
            return None

        user_db.permissions.append(permission)
        await self._db_session.commit()
        await self._db_session.refresh(user_db)
        return user_db

    async def remove_permission_from_user(
            self,
            user_id: UUID,
            permission: models.Permission
    ) -> Union[None, models.User]:
        """
        Remove a permission from a role.
        """

        query = select(models.User).\
            options(selectinload(models.User.permissions)).\
            where(models.User.user_id == user_id)
        result = await self._db_session.execute(query)
        user_db = result.scalars().first()
        if not user_db:
            return None

        user_db.permissions.remove(permission)
        await self._db_session.commit()
        await self._db_session.refresh(user_db)
        return user_db

    async def add_permission_to_user_with_path(self, user_id: UUID, path: str) -> Union[None, models.User]:
        """
        Add a permission to an user.
        """

        # Create a new permission with full rights on path
        new_permission = schemas.PermissionCreate(
            description=f"Allow access to {path}",
            methods=[HTTPMethods.get, HTTPMethods.head, HTTPMethods.post, HTTPMethods.put, HTTPMethods.delete],
            path=path,
            action=PermissionAction.allow
        )
        permission_db = await self.create_permission(new_permission)

        # Add the permission to the user
        query = select(models.User).\
            options(selectinload(models.User.permissions)).\
            where(models.User.user_id == user_id)

        result = await self._db_session.execute(query)
        user_db = result.scalars().first()
        if not user_db:
            return None

        user_db.permissions.append(permission_db)
        await self._db_session.commit()
        await self._db_session.refresh(user_db)
        return user_db

    async def delete_all_permissions_with_path(self, path: str) -> None:
        """
        Delete all permissions with path.
        """

        query = delete(models.Permission).\
            where(models.Permission.path.startswith(path)).\
            execution_options(synchronize_session=False)
        result = await self._db_session.execute(query)
        log.debug(f"{result.rowcount} permission(s) have been deleted")

    async def check_user_is_authorized(self, user_id: UUID, method: str, path: str) -> bool:
        """
        Check if an user is authorized to access a resource.
        """

        query = select(models.Permission).\
            join(models.Permission.roles).\
            join(models.Role.groups).\
            join(models.UserGroup.users).\
            filter(models.User.user_id == user_id).\
            order_by(models.Permission.path.desc())

        result = await self._db_session.execute(query)
        permissions = result.scalars().all()
        log.debug(f"RBAC: checking authorization for user '{user_id}' on {method} '{path}'")
        matched_permission = self._match_permission(permissions, method, path)
        if matched_permission:
            log.debug(f"RBAC: matched role permission {matched_permission.methods} "
                      f"{matched_permission.path} {matched_permission.action}")
            if matched_permission.action == "DENY":
                return False
            return True

        log.debug(f"RBAC: could not find a role permission, checking user permissions...")
        permissions = await self.get_user_permissions(user_id)
        matched_permission = self._match_permission(permissions, method, path)
        if matched_permission:
            log.debug(f"RBAC: matched user permission {matched_permission.methods} "
                      f"{matched_permission.path} {matched_permission.action}")
            if matched_permission.action == "DENY":
                return False
            return True

        return False
