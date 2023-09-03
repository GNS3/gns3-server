#!/usr/bin/env python
#
# Copyright (C) 2021 GNS3 Technologies Inc.
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

from .base import BaseRepository

import gns3server.db.models as models
from gns3server import schemas


class ComputesRepository(BaseRepository):

    def __init__(self, db_session: AsyncSession) -> None:

        super().__init__(db_session)

    async def get_compute(self, compute_id: UUID) -> Optional[models.Compute]:

        query = select(models.Compute).where(models.Compute.compute_id == compute_id)
        result = await self._db_session.execute(query)
        return result.scalars().first()

    async def get_compute_by_name(self, name: str) -> Optional[models.Compute]:

        query = select(models.Compute).where(models.Compute.name == name)
        result = await self._db_session.execute(query)
        return result.scalars().first()

    async def get_computes(self) -> List[models.Compute]:

        query = select(models.Compute)
        result = await self._db_session.execute(query)
        return result.scalars().all()

    async def create_compute(self, compute_create: schemas.ComputeCreate) -> models.Compute:

        db_compute = models.Compute(
            compute_id=compute_create.compute_id,
            name=compute_create.name,
            protocol=compute_create.protocol,
            host=compute_create.host,
            port=compute_create.port,
            user=compute_create.user,
            password=compute_create.password.get_secret_value(),
        )
        self._db_session.add(db_compute)
        await self._db_session.commit()
        await self._db_session.refresh(db_compute)
        return db_compute

    async def update_compute(self, compute_id: UUID, compute_update: schemas.ComputeUpdate) -> Optional[models.Compute]:

        update_values = compute_update.model_dump(exclude_unset=True)

        password = compute_update.password
        if password:
            update_values["password"] = password.get_secret_value()

        query = update(models.Compute).\
            where(models.Compute.compute_id == compute_id).\
            values(update_values)

        await self._db_session.execute(query)
        await self._db_session.commit()
        compute_db = await self.get_compute(compute_id)
        if compute_db:
            await self._db_session.refresh(compute_db)  # force refresh of updated_at value
        return compute_db

    async def delete_compute(self, compute_id: UUID) -> bool:

        query = delete(models.Compute).where(models.Compute.compute_id == compute_id)
        result = await self._db_session.execute(query)
        await self._db_session.commit()
        return result.rowcount > 0
