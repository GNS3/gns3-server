#
# Copyright (C) 2026 GNS3 Technologies Inc.
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
#

import logging

from sqlalchemy import JSON, Boolean, Column, Integer, String, Text

from .base import GUID, BaseTable, generate_uuid

log = logging.getLogger(__name__)


class DistributionRecord(BaseTable):
    """
    Persisted state of one project distribution job: who distributed the
    project, to which recipients (one result per copy), and how far the job
    got. The live state of a running job lives in the in-memory registry
    (gns3server.controller.distribution); this table is the durable record
    that survives controller restarts and backs the distribution history.

    Projects are file-based and have no database row, so project_id carries
    no foreign key.
    """

    __tablename__ = "distribution_records"

    distribution_id = Column(GUID, primary_key=True, default=generate_uuid)
    project_id = Column(GUID, nullable=False, index=True)
    name = Column(String)
    created_by = Column(String, nullable=False)
    total = Column(Integer, nullable=False, default=0)
    status = Column(String, nullable=False, default="running")
    error = Column(Text, nullable=True)
    # set by a cancel request: the copy in flight completes, the remaining
    # recipients are skipped (cancelling never cuts a copy in half)
    cancel_requested = Column(Boolean, nullable=False, default=False)
    # one entry per recipient: {"username": ..., "project": ..., "error": ...}
    results = Column(JSON, nullable=False, default=list)
