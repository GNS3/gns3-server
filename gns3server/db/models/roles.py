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

from sqlalchemy import Table, Column, String, Boolean, ForeignKey, event
from sqlalchemy.orm import relationship

from .base import Base, BaseTable, generate_uuid, GUID
from .permissions import permission_role_link

import logging

log = logging.getLogger(__name__)

role_group_link = Table(
    "roles_groups_link",
    Base.metadata,
    Column("role_id", GUID, ForeignKey("roles.role_id", ondelete="CASCADE")),
    Column("user_group_id", GUID, ForeignKey("user_groups.user_group_id", ondelete="CASCADE"))
)


class Role(BaseTable):

    __tablename__ = "roles"

    role_id = Column(GUID, primary_key=True, default=generate_uuid)
    name = Column(String)
    description = Column(String)
    is_updatable = Column(Boolean, default=True)
    permissions = relationship("Permission", secondary=permission_role_link, back_populates="roles")
    groups = relationship("UserGroup", secondary=role_group_link, back_populates="roles")


@event.listens_for(Role.__table__, 'after_create')
def create_default_roles(target, connection, **kw):

    default_roles = [
        {"name": "Administrator", "description": "Administrator role", "is_updatable": False},
        {"name": "User", "description": "User role", "is_updatable": False},
    ]

    stmt = target.insert().values(default_roles)
    connection.execute(stmt)
    connection.commit()
    log.info("The default roles have been created in the database")
