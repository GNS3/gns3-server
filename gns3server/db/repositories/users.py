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
from typing import Optional, List
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import engine
from .base import BaseRepository

import gns3server.db.models as models
from gns3server import schemas
from gns3server.services import auth_service


class UsersRepository(BaseRepository):

    def __init__(self) -> None:

        super().__init__()
        self._auth_service = auth_service

    async def get_user(self, user_id: UUID) -> Optional[models.User]:

        async with AsyncSession(engine) as session:
            result = await session.execute(select(models.User).where(models.User.user_id == user_id))
            return result.scalars().first()

    async def get_user_by_username(self, username: str) -> Optional[models.User]:

        async with AsyncSession(engine) as session:
            result = await session.execute(select(models.User).where(models.User.username == username))
            return result.scalars().first()

    async def get_user_by_email(self, email: str) -> Optional[models.User]:

        async with AsyncSession(engine) as session:
            result = await session.execute(select(models.User).where(models.User.email == email))
            return result.scalars().first()

    async def get_users(self) -> List[models.User]:

        async with AsyncSession(engine) as session:
            result = await session.execute(select(models.User))
            return result.scalars().all()

    async def create_user(self, user: schemas.UserCreate) -> models.User:

        async with AsyncSession(engine) as session:
            hashed_password = self._auth_service.hash_password(user.password)
            db_user = models.User(username=user.username,
                                  email=user.email,
                                  full_name=user.full_name,
                                  hashed_password=hashed_password)
            session.add(db_user)
            await session.commit()
            await session.refresh(db_user)
            return db_user

    async def update_user(self, user_id: UUID, user_update: schemas.UserUpdate) -> Optional[models.User]:

        async with AsyncSession(engine) as session:

            update_values = user_update.dict(exclude_unset=True)
            password = update_values.pop("password", None)
            if password:
                update_values["hashed_password"] = self._auth_service.hash_password(password=password)

            print(update_values)
            query = update(models.User) \
                .where(models.User.user_id == user_id) \
                .values(update_values)

            await session.execute(query)
            await session.commit()
            return await self.get_user(user_id)

    async def delete_user(self, user_id: UUID) -> bool:

        async with AsyncSession(engine) as session:
            query = delete(models.User).where(models.User.user_id == user_id)
            result = await session.execute(query)
            await session.commit()
            return result.rowcount > 0
            #except:
            #    await session.rollback()

    async def authenticate_user(self, username: str, password: str) -> Optional[models.User]:

        user = await self.get_user_by_username(username)
        if not user:
            return None
        if not self._auth_service.verify_password(password, user.hashed_password):
            return None
        return user
