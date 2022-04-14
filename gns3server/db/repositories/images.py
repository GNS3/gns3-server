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

import os

from typing import Optional, List
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from .base import BaseRepository

import gns3server.db.models as models

import logging

log = logging.getLogger(__name__)


class ImagesRepository(BaseRepository):

    def __init__(self, db_session: AsyncSession) -> None:

        super().__init__(db_session)

    async def get_image(self, image_path: str) -> Optional[models.Image]:
        """
        Get an image by its path.
        """

        image_dir, image_name = os.path.split(image_path)
        if image_dir:
            query = select(models.Image).\
                where(models.Image.filename == image_name, models.Image.path.endswith(image_path))
        else:
            query = select(models.Image).where(models.Image.filename == image_name)
        result = await self._db_session.execute(query)
        return result.scalars().one_or_none()

    async def get_image_by_checksum(self, checksum: str) -> Optional[models.Image]:
        """
        Get an image by its checksum.
        """

        query = select(models.Image).where(models.Image.checksum == checksum)
        result = await self._db_session.execute(query)
        return result.scalars().first()

    async def get_images(self, image_type=None) -> List[models.Image]:
        """
        Get all images.
        """

        if image_type:
            query = select(models.Image).where(models.Image.image_type == image_type)
        else:
            query = select(models.Image)
        result = await self._db_session.execute(query)
        return result.scalars().all()

    async def get_image_templates(self, image_id: int) -> Optional[List[models.Template]]:
        """
        Get all templates that an image belongs to.
        """

        query = select(models.Template).\
            join(models.Template.images).\
            filter(models.Image.image_id == image_id)

        result = await self._db_session.execute(query)
        return result.scalars().all()

    async def add_image(self, image_name, image_type, image_size, path, checksum, checksum_algorithm) -> models.Image:
        """
        Create a new image.
        """

        db_image = models.Image(
            image_id=None,
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

    async def delete_image(self, image_path: str) -> bool:
        """
        Delete an image.
        """

        image_dir, image_name = os.path.split(image_path)
        if image_dir:
            query = delete(models.Image).\
                where(models.Image.filename == image_name, models.Image.path.endswith(image_path)).\
                execution_options(synchronize_session=False)
        else:
            query = delete(models.Image).where(models.Image.filename == image_name)
        result = await self._db_session.execute(query)
        await self._db_session.commit()
        return result.rowcount > 0

    async def prune_images(self) -> int:
        """
        Prune images not attached to any template.
        """

        query = select(models.Image).\
            filter(~models.Image.templates.any())
        result = await self._db_session.execute(query)
        images = result.scalars().all()
        images_deleted = 0
        for image in images:
            try:
                log.debug(f"Deleting image '{image.path}'")
                os.remove(image.path)
            except OSError:
                log.warning(f"Could not delete image file {image.path}")
            if await self.delete_image(image.filename):
                images_deleted += 1
        log.info(f"{images_deleted} image(s) have been deleted")
        return images_deleted
