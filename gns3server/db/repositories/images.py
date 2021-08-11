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

from typing import Optional, List
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from .base import BaseRepository

import gns3server.db.models as models


class ImagesRepository(BaseRepository):

    def __init__(self, db_session: AsyncSession) -> None:

        super().__init__(db_session)

    async def get_image(self, image_name: str) -> Optional[models.Image]:

        query = select(models.Image).where(models.Image.filename == image_name)
        result = await self._db_session.execute(query)
        return result.scalars().first()

    async def get_images(self) -> List[models.Image]:

        query = select(models.Image)
        result = await self._db_session.execute(query)
        return result.scalars().all()

    async def get_image_templates(self, image_id: int) -> Optional[List[models.Template]]:

        query = select(models.Template).\
            join(models.Image.templates). \
            filter(models.Image.id == image_id)

        result = await self._db_session.execute(query)
        return result.scalars().all()

    async def get_image_by_checksum(self, checksum: str) -> Optional[models.Image]:

        query = select(models.Image).where(models.Image.checksum == checksum)
        result = await self._db_session.execute(query)
        return result.scalars().first()

    async def add_image(self, image_name, image_type, image_size, path, checksum, checksum_algorithm) -> models.Image:

        db_image = models.Image(
            id=None,
            filename=image_name,
            image_type=image_type,
            image_size=image_size,
            path=path,
            checksum=checksum,
            checksum_algorithm=checksum_algorithm
        )

        self._db_session.add(db_image)
        await self._db_session.commit()
        await self._db_session.refresh(db_image)
        return db_image

    async def delete_image(self, image_name: str) -> bool:

        query = delete(models.Image).where(models.Image.filename == image_name)
        result = await self._db_session.execute(query)
        await self._db_session.commit()
        return result.rowcount > 0
