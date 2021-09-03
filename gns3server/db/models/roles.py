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
    name = Column(String, unique=True, index=True)
    description = Column(String)
    is_builtin = Column(Boolean, default=False)
    permissions = relationship("Permission", secondary=permission_role_link, back_populates="roles")
    groups = relationship("UserGroup", secondary=role_group_link, back_populates="roles")


@event.listens_for(Role.__table__, 'after_create')
def create_default_roles(target, connection, **kw):

    default_roles = [
        {"name": "Administrator", "description": "Administrator role", "is_builtin": True},
        {"name": "User", "description": "User role", "is_builtin": True},
    ]

    stmt = target.insert().values(default_roles)
    connection.execute(stmt)
    connection.commit()
    log.debug("The default roles have been created in the database")


@event.listens_for(role_group_link, 'after_create')
def add_admin_to_group(target, connection, **kw):

    from .users import UserGroup
    user_groups_table = UserGroup.__table__
    roles_table = Role.__table__

    # Add roles to built-in user groups
    groups_to_roles = {"Administrators": "Administrator", "Users": "User"}
    for user_group, role in groups_to_roles.items():
        stmt = user_groups_table.select().where(user_groups_table.c.name == user_group)
        result = connection.execute(stmt)
        user_group_id = result.first().user_group_id
        stmt = roles_table.select().where(roles_table.c.name == role)
        result = connection.execute(stmt)
        role_id = result.first().role_id
        stmt = target.insert().values(role_id=role_id, user_group_id=user_group_id)
        connection.execute(stmt)

    connection.commit()
