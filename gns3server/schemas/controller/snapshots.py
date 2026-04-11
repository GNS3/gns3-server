#
# Copyright (C) 2020 GNS3 Technologies Inc.
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


from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID


class SnapshotBase(BaseModel):
    """
    Common properties for snapshot.
    """

    name: str = Field(..., description="Name of the snapshot")
    description: Optional[str] = Field(None, description="Description of the snapshot")

class SnapshotCreate(SnapshotBase):
    """
    Properties for snapshot creation.
    """

    pass


class Snapshot(SnapshotBase):

    snapshot_id: UUID
    project_id: UUID
    name: str = Field(..., description="Name of the snapshot")
    filename: str = Field(..., description="Filename of the snapshot")
    description: str = Field(..., description="Description of the snapshot")
    created_at: int = Field(..., description="Date of the snapshot (UTC timestamp)")
