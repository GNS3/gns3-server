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

from sqlalchemy import Table, Boolean, Column, String, DateTime, ForeignKey, event
from sqlalchemy.orm import relationship

from .base import Base, BaseTable, generate_uuid, GUID

from gns3server.config import Config
from gns3server.services import auth_service

import logging

log = logging.getLogger(__name__)

user_group_map = Table(
    "user_group_map",
    Base.metadata,
    Column("user_id", GUID, ForeignKey("users.user_id", ondelete="CASCADE")),
    Column("user_group_id", GUID, ForeignKey("user_groups.user_group_id", ondelete="CASCADE"))
)


class User(BaseTable):

    __tablename__ = "users"

    user_id = Column(GUID, primary_key=True, default=generate_uuid)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    full_name = Column(String)
    hashed_password = Column(String)
    last_login = Column(DateTime)
    is_active = Column(Boolean, default=True)
    is_superadmin = Column(Boolean, default=False)
    groups = relationship("UserGroup", secondary=user_group_map, back_populates="users")
    acl_entries = relationship("ACE")


@event.listens_for(User.__table__, 'after_create')
def create_default_super_admin(target, connection, **kw):

    config = Config.instance().settings
    default_admin_username = config.Controller.default_admin_username
    default_admin_password = config.Controller.default_admin_password.get_secret_value()
    hashed_password = auth_service.hash_password(default_admin_password)
    stmt = target.insert().values(
        username=default_admin_username,
        full_name="Super Administrator",
        hashed_password=hashed_password,
        is_superadmin=True
    )
    connection.execute(stmt)
    connection.commit()
    log.debug("The default super admin account has been created in the database")


class UserGroup(BaseTable):

    __tablename__ = "user_groups"

    user_group_id = Column(GUID, primary_key=True, default=generate_uuid)
    name = Column(String, unique=True, index=True)
    is_builtin = Column(Boolean, default=False)
    users = relationship("User", secondary=user_group_map, back_populates="groups")
    acl_entries = relationship("ACE")


@event.listens_for(UserGroup.__table__, 'after_create')
def create_default_user_groups(target, connection, **kw):

    default_groups = [
        {"name": "Administrators", "is_builtin": True},
        {"name": "Users", "is_builtin": True}
    ]

    stmt = target.insert().values(default_groups)
    connection.execute(stmt)
    connection.commit()
    log.debug("The default user groups have been created in the database")
