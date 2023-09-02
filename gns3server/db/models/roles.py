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

from sqlalchemy import Column, String, Boolean, event
from sqlalchemy.orm import relationship

from .base import BaseTable, generate_uuid, GUID
from .privileges import privilege_role_map

import logging

log = logging.getLogger(__name__)


class Role(BaseTable):

    __tablename__ = "roles"

    role_id = Column(GUID, primary_key=True, default=generate_uuid)
    name = Column(String, unique=True, index=True)
    description = Column(String)
    is_builtin = Column(Boolean, default=False)
    privileges = relationship("Privilege", secondary=privilege_role_map, back_populates="roles")
    acl_entries = relationship("ACE")


@event.listens_for(Role.__table__, 'after_create')
def create_default_roles(target, connection, **kw):

    default_roles = [
        {"name": "Administrator", "description": "Administrator role", "is_builtin": True},
        {"name": "User", "description": "User role", "is_builtin": True},
        {"name": "Auditor", "description": "Role with read only access", "is_builtin": True},
        {"name": "Template manager", "description": "Role to manage templates", "is_builtin": True},
        {"name": "User manager", "description": "Role to manage users and groups", "is_builtin": True},
        {"name": "ACL manager", "description": "Role to manage other roles and the ACL", "is_builtin": True},
        {"name": "No Access", "description": "Role with no privileges (used to forbid access)", "is_builtin": True}
    ]

    stmt = target.insert().values(default_roles)
    connection.execute(stmt)
    connection.commit()
    log.debug("The default roles have been created in the database")
