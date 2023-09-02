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

from sqlalchemy import Column, String, Boolean, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship

from .base import BaseTable, generate_uuid, GUID

import logging

log = logging.getLogger(__name__)


class ACE(BaseTable):

    __tablename__ = "acl"

    ace_id = Column(GUID, primary_key=True, default=generate_uuid)
    ace_type: str = Column(String)
    path = Column(String)
    propagate = Column(Boolean, default=True)
    allowed = Column(Boolean, default=True)
    user_id = Column(GUID, ForeignKey('users.user_id', ondelete="CASCADE"))
    user = relationship("User", back_populates="acl_entries")
    group_id = Column(GUID, ForeignKey('user_groups.user_group_id', ondelete="CASCADE"))
    group = relationship("UserGroup", back_populates="acl_entries")
    role_id = Column(GUID, ForeignKey('roles.role_id', ondelete="CASCADE"))
    role = relationship("Role", back_populates="acl_entries")

    __table_args__ = (
        CheckConstraint("(user_id IS NOT NULL AND ace_type = 'user') OR (group_id IS NOT NULL AND ace_type = 'group')"),
    )
