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

from sqlalchemy import Table, Column, String, ForeignKey
from sqlalchemy.orm import relationship

from .base import Base, BaseTable, generate_uuid, GUID

import logging

log = logging.getLogger(__name__)


resource_pool_map = Table(
    "resource_pool_map",
    Base.metadata,
    Column("resource_id", GUID, ForeignKey("resources.resource_id", ondelete="CASCADE")),
    Column("resource_pool_id", GUID, ForeignKey("resource_pools.resource_pool_id", ondelete="CASCADE"))
)


class Resource(BaseTable):

    __tablename__ = "resources"

    resource_id = Column(GUID, primary_key=True)
    name = Column(String, unique=True, index=True)
    resource_type = Column(String)
    resource_pools = relationship("ResourcePool", secondary=resource_pool_map, back_populates="resources")


class ResourcePool(BaseTable):

    __tablename__ = "resource_pools"

    resource_pool_id = Column(GUID, primary_key=True, default=generate_uuid)
    name = Column(String, unique=True, index=True)
    resources = relationship("Resource", secondary=resource_pool_map, back_populates="resource_pools")
