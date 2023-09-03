#
# Copyright (C) 2022 GNS3 Technologies Inc.
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
from enum import Enum


class QemuDiskImageFormat(str, Enum):
    """
    Supported Qemu disk image formats.
    """

    qcow2 = "qcow2"
    qcow = "qcow"
    vpc = "vpc"
    vdi = "vdi"
    vdmk = "vdmk"
    raw = "raw"


class QemuDiskImagePreallocation(str, Enum):
    """
    Supported Qemu disk image pre-allocation options.
    """

    off = "off"
    metadata = "metadata"
    falloc = "falloc"
    full = "full"


class QemuDiskImageOnOff(str, Enum):
    """
    Supported Qemu image on/off options.
    """

    on = "on"
    off = "off"


class QemuDiskImageSubformat(str, Enum):
    """
    Supported Qemu disk image sub-format options.
    """

    dynamic = "dynamic"
    fixed = "fixed"
    stream_optimized = "streamOptimized"
    two_gb_max_extent_sparse = "twoGbMaxExtentSparse"
    two_gb_max_extent_flat = "twoGbMaxExtentFlat"
    monolithic_sparse = "monolithicSparse"
    monolithic_flat = "monolithicFlat"


class QemuDiskImageAdapterType(str, Enum):
    """
    Supported Qemu disk image on/off options.
    """

    ide = "ide"
    lsilogic = "lsilogic"
    buslogic = "buslogic"
    legacy_esx = "legacyESX"


class QemuDiskImageBase(BaseModel):

    format: QemuDiskImageFormat = Field(..., description="Image format type")
    size: int = Field(..., description="Image size in Megabytes")
    preallocation: Optional[QemuDiskImagePreallocation] = None
    cluster_size: Optional[int] = None
    refcount_bits: Optional[int] = None
    lazy_refcounts: Optional[QemuDiskImageOnOff] = None
    subformat: Optional[QemuDiskImageSubformat] = None
    static: Optional[QemuDiskImageOnOff] = None
    zeroed_grain: Optional[QemuDiskImageOnOff] = None
    adapter_type: Optional[QemuDiskImageAdapterType] = None


class QemuDiskImageCreate(QemuDiskImageBase):

    pass


class QemuDiskImageUpdate(QemuDiskImageBase):

    format: Optional[QemuDiskImageFormat] = Field(None, description="Image format type")
    size: Optional[int] = Field(None, description="Image size in Megabytes")
    extend: Optional[int] = Field(None, description="Number of Megabytes to extend the image")
