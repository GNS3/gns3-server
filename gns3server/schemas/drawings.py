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


class Drawing(BaseModel):
    """
    Drawing data.
    """

    drawing_id: Optional[UUID] = None
    project_id: Optional[UUID] = None
    x: Optional[int] = None
    y: Optional[int] = None
    z: Optional[int] = None
    locked: Optional[bool] = None
    rotation: Optional[int] = Field(None, ge=-359, le=360)
    svg: Optional[str] = None
