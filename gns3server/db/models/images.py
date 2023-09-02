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

from sqlalchemy import Table, Column, String, ForeignKey, BigInteger, Integer
from sqlalchemy.orm import relationship

from .base import Base, BaseTable, GUID


image_template_map = Table(
    "image_template_map",
    Base.metadata,
    Column("image_id", Integer, ForeignKey("images.image_id", ondelete="CASCADE")),
    Column("template_id", GUID, ForeignKey("templates.template_id", ondelete="CASCADE"))
)


class Image(BaseTable):

    __tablename__ = "images"

    image_id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String, index=True)
    path = Column(String, unique=True)
    image_type = Column(String)
    image_size = Column(BigInteger)
    checksum = Column(String, index=True)
    checksum_algorithm = Column(String)
    templates = relationship("Template", secondary=image_template_map, back_populates="images")
