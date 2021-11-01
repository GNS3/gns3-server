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

from sqlalchemy import Table, Column, String, ForeignKey, event
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
    description = Column(String)
    methods = Column(ListType)
    path = Column(String)
    action = Column(String)
    user_id = Column(GUID, ForeignKey('users.user_id', ondelete="CASCADE"))
    roles = relationship("Role", secondary=permission_role_link, back_populates="permissions")


@event.listens_for(Permission.__table__, 'after_create')
def create_default_roles(target, connection, **kw):

    default_permissions = [
        {
            "description": "Allow access to all endpoints",
            "methods": ["GET", "POST", "PUT", "DELETE"],
            "path": "/",
            "action": "ALLOW"
        },
        {
            "description": "Allow to receive controller notifications",
            "methods": ["GET"],
            "path": "/notifications",
            "action": "ALLOW"
        },
        {
            "description": "Allow to create and list projects",
            "methods": ["GET", "POST"],
            "path": "/projects",
            "action": "ALLOW"
        },
        {
            "description": "Allow to create and list templates",
            "methods": ["GET", "POST"],
            "path": "/templates",
            "action": "ALLOW"
        },
        {
            "description": "Allow to list computes",
            "methods": ["GET"],
            "path": "/computes/*",
            "action": "ALLOW"
        },
        {
            "description": "Allow access to all symbol endpoints",
            "methods": ["GET", "POST"],
            "path": "/symbols/*",
            "action": "ALLOW"
        },
    ]

    stmt = target.insert().values(default_permissions)
    connection.execute(stmt)
    connection.commit()
    log.debug("The default permissions have been created in the database")


@event.listens_for(permission_role_link, 'after_create')
def add_permissions_to_role(target, connection, **kw):

    from .roles import Role
    roles_table = Role.__table__
    stmt = roles_table.select().where(roles_table.c.name == "Administrator")
    result = connection.execute(stmt)
    role_id = result.first().role_id

    permissions_table = Permission.__table__
    stmt = permissions_table.select().where(permissions_table.c.path == "/")
    result = connection.execute(stmt)
    permission_id = result.first().permission_id

    # add root path to the "Administrator" role
    stmt = target.insert().values(permission_id=permission_id, role_id=role_id)
    connection.execute(stmt)

    stmt = roles_table.select().where(roles_table.c.name == "User")
    result = connection.execute(stmt)
    role_id = result.first().role_id

    # add minimum required paths to the "User" role
    for path in ("/notifications", "/projects", "/templates", "/computes/*", "/symbols/*"):
        stmt = permissions_table.select().where(permissions_table.c.path == path)
        result = connection.execute(stmt)
        permission_id = result.first().permission_id
        stmt = target.insert().values(permission_id=permission_id, role_id=role_id)
        connection.execute(stmt)

    connection.commit()
