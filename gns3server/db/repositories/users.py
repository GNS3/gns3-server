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
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .base import BaseRepository

import gns3server.db.models as models
from gns3server import schemas
from gns3server.services import auth_service

import logging

log = logging.getLogger(__name__)


class UsersRepository(BaseRepository):

    def __init__(self, db_session: AsyncSession) -> None:

        super().__init__(db_session)
        self._auth_service = auth_service

    async def get_user(self, user_id: UUID) -> Optional[models.User]:
        """
        Get a user by its ID.
        """

        query = select(models.User).where(models.User.user_id == user_id)
        result = await self._db_session.execute(query)
        return result.scalars().first()

    async def get_user_by_username(self, username: str) -> Optional[models.User]:
        """
        Get a user by its name.
        """

        query = select(models.User).where(models.User.username == username)
        result = await self._db_session.execute(query)
        return result.scalars().first()

    async def get_user_by_email(self, email: str) -> Optional[models.User]:
        """
        Get a user by its email.
        """

        query = select(models.User).where(models.User.email == email)
        result = await self._db_session.execute(query)
        return result.scalars().first()

    async def get_users(self) -> List[models.User]:
        """
        Get all users.
        """

        query = select(models.User)
        result = await self._db_session.execute(query)
        return result.scalars().all()

    async def create_user(self, user: schemas.UserCreate) -> models.User:
        """
        Create a new user.
        """

        hashed_password = self._auth_service.hash_password(user.password.get_secret_value())
        db_user = models.User(
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            hashed_password=hashed_password
        )
        self._db_session.add(db_user)
        await self._db_session.commit()
        await self._db_session.refresh(db_user)
        return db_user

    async def update_user(self, user_id: UUID, user_update: schemas.UserUpdate) -> Optional[models.User]:
        """
        Update a user.
        """

        update_values = user_update.model_dump(exclude_unset=True)
        password = update_values.pop("password", None)
        if password:
            update_values["hashed_password"] = self._auth_service.hash_password(password=password.get_secret_value())

        query = update(models.User).\
            where(models.User.user_id == user_id).\
            values(update_values)

        await self._db_session.execute(query)
        await self._db_session.commit()
        user_db = await self.get_user(user_id)
        if user_db:
            await self._db_session.refresh(user_db)  # force refresh of updated_at value
        return user_db

    async def delete_user(self, user_id: UUID) -> bool:
        """
        Delete a user.
        """

        query = delete(models.User).where(models.User.user_id == user_id)
        result = await self._db_session.execute(query)
        await self._db_session.commit()
        return result.rowcount > 0

    async def authenticate_user(self, username: str, password: str) -> Optional[models.User]:
        """
        Authenticate user.
        """

        user = await self.get_user_by_username(username)
        if not user:
            return None
        # Allow user to be authenticated if hashed password in the db is null
        # this is useful for manual password recovery like:
        # sqlite3 gns3_controller.db "UPDATE users SET hashed_password = null WHERE username = 'admin';"
        if user.hashed_password is None:
            log.warning(f"User '{username}' has been authenticated without a password "
                        f"configured. Please set a new password.")
            return user
        if not self._auth_service.verify_password(password, user.hashed_password):
            return None

        # Backup the updated_at value
        updated_at = user.updated_at
        user.last_login = func.current_timestamp()
        await self._db_session.commit()
        # Restore the original updated_at value
        # so it is not affected by the last login update
        user.updated_at = updated_at
        await self._db_session.commit()
        return user

    async def get_user_memberships(self, user_id: UUID) -> List[models.UserGroup]:
        """
        Get all user memberships (user groups).
        """

        query = select(models.UserGroup).\
            join(models.UserGroup.users).\
            filter(models.User.user_id == user_id)

        result = await self._db_session.execute(query)
        return result.scalars().all()

    async def get_user_group(self, user_group_id: UUID) -> Optional[models.UserGroup]:
        """
        Get a user group by its ID.
        """

        query = select(models.UserGroup).where(models.UserGroup.user_group_id == user_group_id)
        result = await self._db_session.execute(query)
        return result.scalars().first()

    async def get_user_group_by_name(self, name: str) -> Optional[models.UserGroup]:
        """
        Get a user group by its name.
        """

        query = select(models.UserGroup).where(models.UserGroup.name == name)
        result = await self._db_session.execute(query)
        return result.scalars().first()

    async def get_user_groups(self) -> List[models.UserGroup]:
        """
        Get all user groups.
        """

        query = select(models.UserGroup)
        result = await self._db_session.execute(query)
        return result.scalars().all()

    async def create_user_group(self, user_group: schemas.UserGroupCreate) -> models.UserGroup:
        """
        Create a new user group.
        """

        db_user_group = models.UserGroup(name=user_group.name)
        self._db_session.add(db_user_group)
        await self._db_session.commit()
        await self._db_session.refresh(db_user_group)
        return db_user_group

    async def update_user_group(
            self,
            user_group_id: UUID,
            user_group_update: schemas.UserGroupUpdate
    ) -> Optional[models.UserGroup]:
        """
        Update a user group.
        """

        update_values = user_group_update.model_dump(exclude_unset=True)
        query = update(models.UserGroup).\
            where(models.UserGroup.user_group_id == user_group_id).\
            values(update_values)

        await self._db_session.execute(query)
        await self._db_session.commit()
        user_group_db = await self.get_user_group(user_group_id)
        if user_group_db:
            await self._db_session.refresh(user_group_db)  # force refresh of updated_at value
        return user_group_db

    async def delete_user_group(self, user_group_id: UUID) -> bool:
        """
        Delete a user group.
        """

        query = delete(models.UserGroup).where(models.UserGroup.user_group_id == user_group_id)
        result = await self._db_session.execute(query)
        await self._db_session.commit()
        return result.rowcount > 0

    async def add_member_to_user_group(
            self,
            user_group_id: UUID,
            user: models.User
    ) -> Union[None, models.UserGroup]:
        """
        Add a member to a user group.
        """

        query = select(models.UserGroup).\
            options(selectinload(models.UserGroup.users)).\
            where(models.UserGroup.user_group_id == user_group_id)
        result = await self._db_session.execute(query)
        user_group_db = result.scalars().first()
        if not user_group_db:
            return None

        user_group_db.users.append(user)
        await self._db_session.commit()
        await self._db_session.refresh(user_group_db)
        return user_group_db

    async def remove_member_from_user_group(
            self,
            user_group_id: UUID,
            user: models.User
    ) -> Union[None, models.UserGroup]:
        """
        Remove a member from a user group.
        """

        query = select(models.UserGroup).\
            options(selectinload(models.UserGroup.users)).\
            where(models.UserGroup.user_group_id == user_group_id)
        result = await self._db_session.execute(query)
        user_group_db = result.scalars().first()
        if not user_group_db:
            return None

        user_group_db.users.remove(user)
        await self._db_session.commit()
        await self._db_session.refresh(user_group_db)
        return user_group_db

    async def get_user_group_members(self, user_group_id: UUID) -> List[models.User]:
        """
        Get all members from a user group.
        """

        query = select(models.User).\
            join(models.User.groups).\
            filter(models.UserGroup.user_group_id == user_group_id)

        result = await self._db_session.execute(query)
        return result.scalars().all()
