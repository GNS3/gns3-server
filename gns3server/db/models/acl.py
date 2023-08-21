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

from sqlalchemy import Column, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from .base import BaseTable, generate_uuid, GUID

import logging

log = logging.getLogger(__name__)


class ACL(BaseTable):

    __tablename__ = "acl"

    acl_id = Column(GUID, primary_key=True, default=generate_uuid)
    allowed = Column(Boolean, default=True)
    user_id = Column(GUID, ForeignKey('users.user_id', ondelete="CASCADE"))
    user = relationship("User", back_populates="acl_entries")
    group_id = Column(GUID, ForeignKey('user_groups.user_group_id', ondelete="CASCADE"))
    group = relationship("UserGroup", back_populates="acl_entries")
    resource_id = Column(GUID, ForeignKey('resources.resource_id', ondelete="CASCADE"))
    resource = relationship("Resource", back_populates="acl_entries")
    role_id = Column(GUID, ForeignKey('roles.role_id', ondelete="CASCADE"))
    role = relationship("Role", back_populates="acl_entries")
