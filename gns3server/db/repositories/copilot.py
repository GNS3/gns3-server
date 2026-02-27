#!/usr/bin/env python
#
# Copyright (C) 2025 GNS3 Technologies Inc.
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
from typing import Optional
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from .base import BaseRepository

import gns3server.db.models as models
from gns3server import schemas

import logging

log = logging.getLogger(__name__)


class CopilotRepository(BaseRepository):
    """
    Repository for managing copilot configurations.
    """

    def __init__(self, db_session: AsyncSession) -> None:
        super().__init__(db_session)

    async def get_copilot_config(self, user_id: UUID) -> Optional[models.CopilotConfig]:
        """
        Get copilot configuration for a user.
        """
        query = select(models.CopilotConfig).where(models.CopilotConfig.user_id == user_id)
        result = await self._db_session.execute(query)
        return result.scalars().first()

    async def create_copilot_config(self, config: schemas.CopilotConfigCreate, user_id: UUID) -> models.CopilotConfig:
        """
        Create a new copilot configuration for a user.
        """
        db_config = models.CopilotConfig(
            user_id=user_id,
            provider=config.provider,
            model_name=config.model_name,
            api_key=config.api_key,
            base_url=config.base_url,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            enabled=config.enabled
        )
        self._db_session.add(db_config)
        await self._db_session.commit()
        await self._db_session.refresh(db_config)
        return db_config

    async def update_copilot_config(
        self,
        user_id: UUID,
        config_update: schemas.CopilotConfigUpdate
    ) -> Optional[models.CopilotConfig]:
        """
        Update copilot configuration for a user.
        """
        update_values = config_update.model_dump(exclude_unset=True)
        if not update_values:
            return await self.get_copilot_config(user_id)

        query = update(models.CopilotConfig).\
            where(models.CopilotConfig.user_id == user_id).\
            values(update_values)

        await self._db_session.execute(query)
        await self._db_session.commit()
        return await self.get_copilot_config(user_id)

    async def delete_copilot_config(self, user_id: UUID) -> bool:
        """
        Delete copilot configuration for a user.
        """
        query = delete(models.CopilotConfig).where(models.CopilotConfig.user_id == user_id)
        result = await self._db_session.execute(query)
        await self._db_session.commit()
        return result.rowcount > 0
