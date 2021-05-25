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

from sqlalchemy import Table, Column, String, ForeignKey, Boolean
from sqlalchemy.orm import relationship

from .base import Base, BaseTable, generate_uuid, GUID, ListType

import logging

log = logging.getLogger(__name__)


permission_role_link = Table(
    "permissions_roles_link",
    Base.metadata,
    Column("permission_id", GUID, ForeignKey("permissions.permission_id", ondelete="CASCADE")),
    Column("role_id", GUID, ForeignKey("roles.role_id", ondelete="CASCADE"))

)


class Permission(BaseTable):

    __tablename__ = "permissions"

    permission_id = Column(GUID, primary_key=True, default=generate_uuid)
    methods = Column(ListType)
    path = Column(String)
    action = Column(String)
    roles = relationship("Role", secondary=permission_role_link, back_populates="permissions")
