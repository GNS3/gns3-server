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

from pydantic import ConfigDict, BaseModel, Field
from enum import Enum

from .base import DateTimeModelMixin


class ImageType(str, Enum):

    qemu = "qemu"
    ios = "ios"
    iou = "iou"


class ImageBase(BaseModel):
    """
    Common image properties.
    """

    filename: str = Field(..., description="Image filename")
    path: str = Field(..., description="Image path")
    image_type: ImageType = Field(..., description="Image type")
    image_size: int = Field(..., description="Image size in bytes")
    checksum: str = Field(..., description="Checksum value")
    checksum_algorithm: str = Field(..., description="Checksum algorithm")


class Image(DateTimeModelMixin, ImageBase):
    model_config = ConfigDict(from_attributes=True)
