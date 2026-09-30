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

from sqlalchemy import JSON, BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import GUID, Base, BaseTable

image_template_map = Table(
    "image_template_map",
    Base.metadata,
    Column("image_id", Integer, ForeignKey("images.image_id", ondelete="CASCADE")),
    Column("template_id", GUID, ForeignKey("templates.template_id", ondelete="CASCADE")),
)


class Image(BaseTable):
    __tablename__ = "images"

    image_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String, index=True)
    path: Mapped[str] = mapped_column(String, unique=True, nullable=True)
    image_type = Column(String)
    image_size = Column(BigInteger)
    checksum = Column(String, index=True)
    checksum_algorithm = Column(String)
    availability = Column(String, nullable=False, default="unknown", server_default="unknown")
    file_fingerprint = Column(String)
    last_seen_at = Column(DateTime)
    last_verified_at = Column(DateTime)
    last_error = Column(String)
    templates = relationship("Template", secondary=image_template_map, back_populates="images")


class ImageSyncJob(BaseTable):
    __tablename__ = "image_sync_jobs"

    job_id = Column(String, primary_key=True)
    status = Column(String, nullable=False)
    dry_run = Column(Boolean, nullable=False)
    force_checksum = Column(Boolean, nullable=False)
    finished_at = Column(DateTime)
    counts = Column(JSON, nullable=False)
    errors = Column(JSON, nullable=False)
