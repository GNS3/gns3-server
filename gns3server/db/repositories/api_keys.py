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

from uuid import UUID
from typing import Optional, List
from datetime import datetime, timezone
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .base import BaseRepository
import gns3server.db.models as models

import logging

log = logging.getLogger(__name__)


class ApiKeysRepository(BaseRepository):

    def __init__(self, db_session: AsyncSession) -> None:
        super().__init__(db_session)

    async def create_api_key(
        self, api_key_id: UUID, user_id: UUID, name: str, key_hash: str, key_prefix: str
    ) -> models.ApiKey:
        db_api_key = models.ApiKey(
            api_key_id=api_key_id,
            user_id=user_id,
            name=name,
            key_hash=key_hash,
            key_prefix=key_prefix,
        )
        self._db_session.add(db_api_key)
        await self._db_session.commit()
        await self._db_session.refresh(db_api_key)
        return db_api_key

    async def get_api_key(self, api_key_id: UUID) -> Optional[models.ApiKey]:
        query = select(models.ApiKey).where(models.ApiKey.api_key_id == api_key_id)
        result = await self._db_session.execute(query)
        return result.scalars().first()

    async def get_api_keys_by_user(self, user_id: UUID) -> List[models.ApiKey]:
        query = (
            select(models.ApiKey)
            .where(models.ApiKey.user_id == user_id)
            .order_by(models.ApiKey.created_at.desc())
        )
        result = await self._db_session.execute(query)
        return list(result.scalars().all())

    async def get_api_key_by_hash(self, key_hash: str) -> Optional[models.ApiKey]:
        query = select(models.ApiKey).where(models.ApiKey.key_hash == key_hash)
        result = await self._db_session.execute(query)
        return result.scalars().first()

    async def revoke_api_key(self, api_key_id: UUID) -> bool:
        query = (
            update(models.ApiKey)
            .where(models.ApiKey.api_key_id == api_key_id)
            .values(revoked=True)
        )
        result = await self._db_session.execute(query)
        await self._db_session.commit()
        return result.rowcount > 0

    async def restore_api_key(self, api_key_id: UUID) -> bool:
        query = (
            update(models.ApiKey)
            .where(models.ApiKey.api_key_id == api_key_id)
            .values(revoked=False)
        )
        result = await self._db_session.execute(query)
        await self._db_session.commit()
        return result.rowcount > 0

    async def update_last_used(self, api_key_id: UUID) -> None:
        query = (
            update(models.ApiKey)
            .where(models.ApiKey.api_key_id == api_key_id)
            .values(last_used_at=func.now())
        )
        await self._db_session.execute(query)
        await self._db_session.commit()

    async def delete_api_key(self, api_key_id: UUID) -> bool:
        query = delete(models.ApiKey).where(models.ApiKey.api_key_id == api_key_id)
        result = await self._db_session.execute(query)
        await self._db_session.commit()
        return result.rowcount > 0
