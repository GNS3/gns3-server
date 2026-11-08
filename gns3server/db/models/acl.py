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

import logging

from sqlalchemy import Boolean, CheckConstraint, Column, ForeignKey, String, event
from sqlalchemy.orm import relationship

from .base import GUID, BaseTable, generate_uuid

log = logging.getLogger(__name__)


class ACE(BaseTable):
    __tablename__ = "acl"

    ace_id = Column(GUID, primary_key=True, default=generate_uuid)
    ace_type = Column(String)
    path = Column(String)
    propagate = Column(Boolean, default=True)
    allowed = Column(Boolean, default=True)
    user_id = Column(GUID, ForeignKey("users.user_id", ondelete="CASCADE"))
    user = relationship("User", back_populates="acl_entries")
    group_id = Column(GUID, ForeignKey("user_groups.user_group_id", ondelete="CASCADE"))
    group = relationship("UserGroup", back_populates="acl_entries")
    role_id = Column(GUID, ForeignKey("roles.role_id", ondelete="CASCADE"))
    role = relationship("Role", back_populates="acl_entries")

    __table_args__ = (
        CheckConstraint("(user_id IS NOT NULL AND ace_type = 'user') OR (group_id IS NOT NULL AND ace_type = 'group')"),
    )


@event.listens_for(ACE.__table__, "after_create")
def create_default_aces(target, connection, **kw):

    from .roles import Role
    from .users import UserGroup

    roles_table = Role.__table__
    stmt = roles_table.select().where(roles_table.c.name == "User")
    role_id = connection.execute(stmt).first().role_id

    user_groups_table = UserGroup.__table__
    stmt = user_groups_table.select().where(user_groups_table.c.name == "Users")
    group_id = connection.execute(stmt).first().user_group_id

    # Grant the "User" role to the "Users" group on each top-level resource path
    # covered by that role, so new users can work out of the box (new users are
    # added to the "Users" group). One ACE per resource path instead of a single
    # ACE on "/": each entry can be tightened (e.g. "/projects/<uuid>") or
    # removed on its own, without deny entries carved out of a blanket grant.
    default_paths = ("/projects", "/templates", "/computes", "/symbols", "/appliances", "/images", "/access/users")
    for path in default_paths:
        stmt = target.insert().values(
            ace_type="group",
            path=path,
            propagate=True,
            allowed=True,
            role_id=role_id,
            group_id=group_id,
        )
        connection.execute(stmt)
    connection.commit()
    log.debug("The default ACEs granting the 'User' role to the 'Users' group have been created")
