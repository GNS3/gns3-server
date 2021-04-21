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

from pydantic import BaseModel, Field
from typing import Optional, Union


class Label(BaseModel):
    """
    Label data.
    """

    text: str
    style: Optional[Union[str, None]] = Field(None, description="SVG style attribute. Apply default style if null")
    x: Optional[Union[int, None]] = Field(None, description="Relative X position of the label. Center it if null")
    y: Optional[int] = Field(None, description="Relative Y position of the label")
    rotation: Optional[int] = Field(None, ge=-359, le=360, description="Rotation of the label")
