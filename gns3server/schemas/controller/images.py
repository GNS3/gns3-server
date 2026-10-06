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

from datetime import datetime
from enum import Enum
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

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
    availability: Literal["unknown", "available", "missing", "unavailable", "invalid"] = "unknown"
    last_seen_at: Optional[datetime] = None
    last_verified_at: Optional[datetime] = None
    last_error: Optional[str] = None


class Image(DateTimeModelMixin, ImageBase):
    model_config = ConfigDict(from_attributes=True)


class ImageTemplateResult(BaseModel):
    status: Literal["created", "skipped"]
    name: Optional[str] = None
    reason: Optional[str] = None
    template_id: Optional[str] = None
    version: Optional[str] = None
    template_type: Optional[str] = None


class ImageUpload(Image):
    template_results: Optional[list[ImageTemplateResult]] = None


class ImageSyncRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dry_run: bool = False
    force_checksum: bool = False


class ImageSyncJob(DateTimeModelMixin):
    model_config = ConfigDict(from_attributes=True)
    job_id: str
    status: Literal["queued", "running", "completed", "partial", "failed", "cancelled", "interrupted"]
    dry_run: bool
    force_checksum: bool
    finished_at: Optional[datetime] = None
    counts: dict[str, int]
    errors: list[dict[str, str]]


class ImageCompatibilityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    checksums: list[Annotated[str, Field(pattern=r"^[a-fA-F0-9]{32}$")]] = Field(min_length=1, max_length=1000)


class ImageApplianceMatch(BaseModel):
    name: str
    version: str
    missing_images: list[str] = Field(default_factory=list)
    downloadable_images: list[str] = Field(default_factory=list)


class ImageCompatibility(BaseModel):
    checksum: str
    matches: list[ImageApplianceMatch]


class ImageCompatibilityCatalog(BaseModel):
    image_sizes: list[int]
    has_unknown_sizes: bool
