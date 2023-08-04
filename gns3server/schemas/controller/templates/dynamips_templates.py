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

from . import Category, TemplateBase

from gns3server.schemas.compute.dynamips_nodes import (
    DynamipsConsoleType,
    DynamipsPlatform,
    DynamipsAdapters,
    DynamipsWics,
    DynamipsNPE,
    DynamipsMidplane,
)

from pydantic import Field
from typing import Optional
from enum import Enum


class DynamipsTemplate(TemplateBase):

    category: Optional[Category] = "router"
    default_name_format: Optional[str] = "R{0}"
    symbol: Optional[str] = "router"
    platform: DynamipsPlatform = Field(..., description="Cisco router platform")
    image: str = Field(..., description="Path to the IOS image")
    exec_area: Optional[int] = Field(64, description="Exec area value")
    mmap: Optional[bool] = Field(True, description="MMAP feature")
    mac_addr: Optional[str] = Field(
        "", description="Base MAC address", pattern="^([0-9a-fA-F]{4}\\.){2}[0-9a-fA-F]{4}$|^$"
    )
    system_id: Optional[str] = Field("FTX0945W0MY", description="System ID")
    startup_config: Optional[str] = Field("ios_base_startup-config.txt", description="IOS startup configuration file")
    private_config: Optional[str] = Field("", description="IOS private configuration file")
    idlepc: Optional[str] = Field("", description="Idle-PC value", pattern="^(0x[0-9a-fA-F]+)?$|^$")
    idlemax: Optional[int] = Field(500, description="Idlemax value")
    idlesleep: Optional[int] = Field(30, description="Idlesleep value")
    disk0: Optional[int] = Field(0, description="Disk0 size in MB")
    disk1: Optional[int] = Field(0, description="Disk1 size in MB")
    auto_delete_disks: Optional[bool] = Field(False, description="Automatically delete nvram and disk files")
    console_type: Optional[DynamipsConsoleType] = Field("telnet", description="Console type")
    console_auto_start: Optional[bool] = Field(
        False, description="Automatically start the console when the node has started"
    )
    aux_type: Optional[DynamipsConsoleType] = Field("none", description="Auxiliary console type")
    slot0: Optional[DynamipsAdapters] = Field(None, description="Network module slot 0")
    slot1: Optional[DynamipsAdapters] = Field(None, description="Network module slot 1")
    slot2: Optional[DynamipsAdapters] = Field(None, description="Network module slot 2")
    slot3: Optional[DynamipsAdapters] = Field(None, description="Network module slot 3")
    slot4: Optional[DynamipsAdapters] = Field(None, description="Network module slot 4")
    slot5: Optional[DynamipsAdapters] = Field(None, description="Network module slot 5")
    slot6: Optional[DynamipsAdapters] = Field(None, description="Network module slot 6")
    wic0: Optional[DynamipsWics] = Field(None, description="Network module WIC slot 0")
    wic1: Optional[DynamipsWics] = Field(None, description="Network module WIC slot 1")
    wic2: Optional[DynamipsWics] = Field(None, description="Network module WIC slot 2")


class C7200DynamipsTemplate(DynamipsTemplate):

    ram: Optional[int] = Field(512, description="Amount of RAM in MB")
    nvram: Optional[int] = Field(512, description="Amount of NVRAM in KB")
    npe: Optional[DynamipsNPE] = Field("npe-400", description="NPE model")
    midplane: Optional[DynamipsMidplane] = Field("vxr", description="Midplane model")
    sparsemem: Optional[bool] = Field(True, description="Sparse memory feature")


class C7200DynamipsTemplateUpdate(C7200DynamipsTemplate):

    platform: Optional[DynamipsPlatform] = Field(None, description="Cisco router platform")
    image: Optional[str] = Field(None, description="Path to the IOS image")


class C3725DynamipsTemplate(DynamipsTemplate):

    ram: Optional[int] = Field(128, description="Amount of RAM in MB")
    nvram: Optional[int] = Field(256, description="Amount of NVRAM in KB")
    iomem: Optional[int] = Field(5, ge=0, le=100, description="I/O memory percentage")
    sparsemem: Optional[bool] = Field(True, description="Sparse memory feature")


class C3725DynamipsTemplateUpdate(C3725DynamipsTemplate):

    platform: Optional[DynamipsPlatform] = Field(None, description="Cisco router platform")
    image: Optional[str] = Field(None, description="Path to the IOS image")


class C3745DynamipsTemplate(DynamipsTemplate):

    ram: Optional[int] = Field(256, description="Amount of RAM in MB")
    nvram: Optional[int] = Field(256, description="Amount of NVRAM in KB")
    iomem: Optional[int] = Field(5, ge=0, le=100, description="I/O memory percentage")
    sparsemem: Optional[bool] = Field(True, description="Sparse memory feature")


class C3745DynamipsTemplateUpdate(C3745DynamipsTemplate):

    platform: Optional[DynamipsPlatform] = Field(None, description="Cisco router platform")
    image: Optional[str] = Field(None, description="Path to the IOS image")


class C3600ChassisType(str, Enum):

    chassis_3620 = "3620"
    chassis_3640 = "3640"
    chassis_3660 = "3660"


class C3600DynamipsTemplate(DynamipsTemplate):

    chassis: Optional[C3600ChassisType] = Field("c3660", description="Chassis type")
    ram: Optional[int] = Field(192, description="Amount of RAM in MB")
    nvram: Optional[int] = Field(128, description="Amount of NVRAM in KB")
    iomem: Optional[int] = Field(5, ge=0, le=100, description="I/O memory percentage")
    sparsemem: Optional[bool] = Field(True, description="Sparse memory feature")


class C3600DynamipsTemplateUpdate(C3600DynamipsTemplate):

    platform: Optional[DynamipsPlatform] = Field(None, description="Cisco router platform")
    image: Optional[str] = Field(None, description="Path to the IOS image")


class C2691DynamipsTemplate(DynamipsTemplate):

    ram: Optional[int] = Field(192, description="Amount of RAM in MB")
    nvram: Optional[int] = Field(256, description="Amount of NVRAM in KB")
    iomem: Optional[int] = Field(5, ge=0, le=100, description="I/O memory percentage")
    sparsemem: Optional[bool] = Field(True, description="Sparse memory feature")


class C2691DynamipsTemplateUpdate(C2691DynamipsTemplate):

    platform: Optional[DynamipsPlatform] = Field(None, description="Cisco router platform")
    image: Optional[str] = Field(None, description="Path to the IOS image")


class C2600ChassisType(str, Enum):

    chassis_2610 = "2610"
    chassis_2620 = "2620"
    chassis_2610xm = "2610XM"
    chassis_2620xm = "2620XM"
    chassis_2650xm = "2650XM"
    chassis_2621 = "2621"
    chassis_2611xm = "2611XM"
    chassis_2621xm = "2621XM"
    chassis_2651xm = "2651XM"


class C2600DynamipsTemplate(DynamipsTemplate):

    chassis: Optional[C2600ChassisType] = Field("2651XM", description="Chassis type")
    ram: Optional[int] = Field(160, description="Amount of RAM in MB")
    nvram: Optional[int] = Field(128, description="Amount of NVRAM in KB")
    iomem: Optional[int] = Field(15, ge=0, le=100, description="I/O memory percentage")
    sparsemem: Optional[bool] = Field(True, description="Sparse memory feature")


class C2600DynamipsTemplateUpdate(C2600DynamipsTemplate):

    platform: Optional[DynamipsPlatform] = Field(None, description="Cisco router platform")
    image: Optional[str] = Field(None, description="Path to the IOS image")


class C1700ChassisType(str, Enum):

    chassis_1720 = "1720"
    chassis_1721 = "1721"
    chassis_1750 = "1750"
    chassis_1751 = "1751"
    chassis_1760 = "1760"


class C1700DynamipsTemplate(DynamipsTemplate):

    chassis: Optional[C1700ChassisType] = Field("1760", description="Chassis type")
    ram: Optional[int] = Field(160, description="Amount of RAM in MB")
    nvram: Optional[int] = Field(128, description="Amount of NVRAM in KB")
    iomem: Optional[int] = Field(15, ge=0, le=100, description="I/O memory percentage")
    sparsemem: Optional[bool] = Field(False, description="Sparse memory feature")


class C1700DynamipsTemplateUpdate(C1700DynamipsTemplate):

    platform: Optional[DynamipsPlatform] = Field(None, description="Cisco router platform")
    image: Optional[str] = Field(None, description="Path to the IOS image")
