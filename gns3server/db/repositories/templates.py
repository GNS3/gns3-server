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

from uuid import UUID
from typing import List, Union, Optional
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.session import make_transient

from .base import BaseRepository

import gns3server.db.models as models
from gns3server import schemas

TEMPLATE_TYPE_TO_MODEL = {
    "cloud": models.CloudTemplate,
    "docker": models.DockerTemplate,
    "dynamips": models.DynamipsTemplate,
    "ethernet_hub": models.EthernetHubTemplate,
    "ethernet_switch": models.EthernetSwitchTemplate,
    "iou": models.IOUTemplate,
    "qemu": models.QemuTemplate,
    "virtualbox": models.VirtualBoxTemplate,
    "vmware": models.VMwareTemplate,
    "vpcs": models.VPCSTemplate,
}


class TemplatesRepository(BaseRepository):

    def __init__(self, db_session: AsyncSession) -> None:

        super().__init__(db_session)

    async def get_template(self, template_id: UUID) -> Union[None, models.Template]:

        query = select(models.Template).\
            options(selectinload(models.Template.images)).\
            where(models.Template.template_id == template_id)
        result = await self._db_session.execute(query)
        return result.scalars().first()

    async def get_template_by_name_and_version(self, name: str, version: str) -> Union[None, models.Template]:

        query = select(models.Template).\
            options(selectinload(models.Template.images)).\
            where(models.Template.name == name, models.Template.version == version)
        result = await self._db_session.execute(query)
        return result.scalars().first()

    async def get_templates(self) -> List[models.Template]:

        query = select(models.Template).options(selectinload(models.Template.images))
        result = await self._db_session.execute(query)
        return result.scalars().all()

    async def create_template(self, template_type: str, template_settings: dict) -> models.Template:

        model = TEMPLATE_TYPE_TO_MODEL[template_type]
        db_template = model(**template_settings)
        self._db_session.add(db_template)
        await self._db_session.commit()
        await self._db_session.refresh(db_template)
        return db_template

    async def update_template(self, db_template: models.Template, template_settings: dict) -> schemas.Template:

        # update the fields directly because update() query couldn't work
        for key, value in template_settings.items():
            setattr(db_template, key, value)
        await self._db_session.commit()
        await self._db_session.refresh(db_template)  # force refresh of updated_at value
        return db_template

    async def delete_template(self, template_id: UUID) -> bool:

        query = delete(models.Template).where(models.Template.template_id == template_id)
        result = await self._db_session.execute(query)
        await self._db_session.commit()
        return result.rowcount > 0

    async def duplicate_template(self, template_id: UUID) -> Optional[schemas.Template]:

        query = select(models.Template).\
            options(selectinload(models.Template.images)).\
            where(models.Template.template_id == template_id)
        db_template = (await self._db_session.execute(query)).scalars().first()
        if db_template:
            # duplicate db object with new primary key (template_id)
            self._db_session.expunge(db_template)
            make_transient(db_template)
            db_template.template_id = None
            self._db_session.add(db_template)
            await self._db_session.commit()
            await self._db_session.refresh(db_template)
        return db_template

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

    async def add_image_to_template(
            self,
            template_id: UUID,
            image: models.Image
    ) -> Union[None, models.Template]:
        """
        Add an image to template.
        """

        query = select(models.Template).\
            options(selectinload(models.Template.images)).\
            where(models.Template.template_id == template_id)
        result = await self._db_session.execute(query)
        template_in_db = result.scalars().first()
        if not template_in_db:
            return None

        template_in_db.images.append(image)
        await self._db_session.commit()
        await self._db_session.refresh(template_in_db)
        return template_in_db

    async def remove_image_from_template(
            self,
            template_id: UUID,
            image: models.Image
    ) -> Union[None, models.Template]:
        """
        Remove an image from a template.
        """

        query = select(models.Template).\
            options(selectinload(models.Template.images)).\
            where(models.Template.template_id == template_id)
        result = await self._db_session.execute(query)
        template_in_db = result.scalars().first()
        if not template_in_db:
            return None

        if image in template_in_db.images:
            template_in_db.images.remove(image)
            await self._db_session.commit()
            await self._db_session.refresh(template_in_db)
        return template_in_db
