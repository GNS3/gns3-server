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

from sqlalchemy import Column, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from .base import BaseTable, generate_uuid, GUID

import logging

log = logging.getLogger(__name__)


class ResourcePool(BaseTable):

    __tablename__ = "resource_pools"

    resource_id = Column(GUID, primary_key=True)
    resource_type = Column(String)

    # Create a self-referential relationship to represent a hierarchy of resources
    parent_id = Column(GUID, ForeignKey("resources.resource_id", ondelete="CASCADE"))
    children = relationship(
        "Resource",
        remote_side=[resource_id],
        cascade="all, delete-orphan",
        single_parent=True
    )
