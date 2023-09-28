#!/usr/bin/env python
#
# Copyright (C) 2023 GNS3 Technologies Inc.
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


class ResourcePoolsRepository(BaseRepository):

    def __init__(self, db_session: AsyncSession) -> None:

        super().__init__(db_session)

    async def get_resource(self, resource_id: UUID) -> Optional[models.Resource]:
        """
        Get a resource by its ID.
        """

        query = select(models.Resource).where(models.Resource.resource_id == resource_id)
        result = await self._db_session.execute(query)
        return result.scalars().first()

    async def get_resources(self) -> List[models.Resource]:
        """
        Get all resources.
        """

        query = select(models.Resource)
        result = await self._db_session.execute(query)
        return result.scalars().all()

    async def create_resource(self, resource: schemas.ResourceCreate) -> models.Resource:
        """
        Create a new resource.
        """

        db_resource = models.Resource(
            resource_id=resource.resource_id,
            resource_type=resource.resource_type,
            name=resource.name
        )
        self._db_session.add(db_resource)
        await self._db_session.commit()
        await self._db_session.refresh(db_resource)
        return db_resource

    async def delete_resource(self, resource_id: UUID) -> bool:
        """
        Delete a resource.
        """

        query = delete(models.Resource).where(models.Resource.resource_id == resource_id)
        result = await self._db_session.execute(query)
        await self._db_session.commit()
        return result.rowcount > 0

    async def get_resource_memberships(self, resource_id: UUID) -> List[models.UserGroup]:
        """
        Get all resource memberships in resource pools.
        """

        query = select(models.ResourcePool).\
            join(models.ResourcePool.resources).\
            filter(models.Resource.resource_id == resource_id)

        result = await self._db_session.execute(query)
        return result.scalars().all()

    async def get_resource_pool(self, resource_pool_id: UUID) -> Optional[models.ResourcePool]:
        """
        Get a resource pool by its ID.
        """

        query = select(models.ResourcePool).where(models.ResourcePool.resource_pool_id == resource_pool_id)
        result = await self._db_session.execute(query)
        return result.scalars().first()

    async def get_resource_pool_by_name(self, name: str) -> Optional[models.ResourcePool]:
        """
        Get a resource pool by its name.
        """

        query = select(models.ResourcePool).where(models.ResourcePool.name == name)
        result = await self._db_session.execute(query)
        return result.scalars().first()

    async def get_resource_pools(self) -> List[models.ResourcePool]:
        """
        Get all resource pools.
        """

        query = select(models.ResourcePool)
        result = await self._db_session.execute(query)
        return result.scalars().all()

    async def create_resource_pool(self, resource_pool: schemas.ResourcePoolCreate) -> models.ResourcePool:
        """
        Create a new resource pool.
        """

        db_resource_pool = models.ResourcePool(name=resource_pool.name)
        self._db_session.add(db_resource_pool)
        await self._db_session.commit()
        await self._db_session.refresh(db_resource_pool)
        return db_resource_pool

    async def update_resource_pool(
            self,
            resource_pool_id: UUID,
            resource_pool_update: schemas.ResourcePoolUpdate
    ) -> Optional[models.ResourcePool]:
        """
        Update a resource pool.
        """

        update_values = resource_pool_update.model_dump(exclude_unset=True)
        query = update(models.ResourcePool).\
            where(models.ResourcePool.resource_pool_id == resource_pool_id).\
            values(update_values)

        await self._db_session.execute(query)
        await self._db_session.commit()
        resource_pool_db = await self.get_resource_pool(resource_pool_id)
        if resource_pool_db:
            await self._db_session.refresh(resource_pool_db)  # force refresh of updated_at value
        return resource_pool_db

    async def delete_resource_pool(self, resource_pool_id: UUID) -> bool:
        """
        Delete a resource pool.
        """

        query = delete(models.ResourcePool).where(models.ResourcePool.resource_pool_id == resource_pool_id)
        result = await self._db_session.execute(query)
        await self._db_session.commit()
        return result.rowcount > 0

    async def add_resource_to_pool(
            self,
            resource_pool_id: UUID,
            resource: models.Resource
    ) -> Union[None, models.ResourcePool]:
        """
        Add a resource to a resource pool.
        """

        query = select(models.ResourcePool).\
            options(selectinload(models.ResourcePool.resources)).\
            where(models.ResourcePool.resource_pool_id == resource_pool_id)
        result = await self._db_session.execute(query)
        resource_pool_db = result.scalars().first()
        if not resource_pool_db:
            return None

        resource_pool_db.resources.append(resource)
        await self._db_session.commit()
        await self._db_session.refresh(resource_pool_db)
        return resource_pool_db

    async def remove_resource_from_pool(
            self,
            resource_pool_id: UUID,
            resource: models.Resource
    ) -> Union[None, models.ResourcePool]:
        """
        Remove a resource from a resource pool.
        """

        query = select(models.ResourcePool).\
            options(selectinload(models.ResourcePool.resources)).\
            where(models.ResourcePool.resource_pool_id == resource_pool_id)
        result = await self._db_session.execute(query)
        resource_pool_db = result.scalars().first()
        if not resource_pool_db:
            return None

        resource_pool_db.resources.remove(resource)
        await self._db_session.commit()
        await self._db_session.refresh(resource_pool_db)
        return resource_pool_db

    async def get_pool_resources(self, resource_pool_id: UUID) -> List[models.Resource]:
        """
        Get all resources from a resource pool.
        """

        query = select(models.Resource).\
            join(models.Resource.resource_pools).\
            filter(models.ResourcePool.resource_pool_id == resource_pool_id)

        result = await self._db_session.execute(query)
        return result.scalars().all()
