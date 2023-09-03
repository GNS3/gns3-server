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
from typing import Optional, List
from enum import Enum
from uuid import UUID

from ..common import NodeStatus


class DynamipsPlatform(str, Enum):
    """
    Supported Dynamips Platforms.
    """

    c7200 = "c7200"
    c3725 = "c3725"
    c3745 = "c3745"
    c3600 = "c3600"
    c2691 = "c2691"
    c2600 = "c2600"
    c1700 = "c1700"


class DynamipsAdapters(str, Enum):
    """
    Supported Dynamips Network Modules.
    """

    c7200_io_2fe = "C7200-IO-2FE"
    c7200_io_fe = "C7200-IO-FE"
    c7200_io_ge_e = "C7200-IO-GE-E"
    nm_16esw = "NM-16ESW"
    nm_1e = "NM-1E"
    nm_1fe_tx = "NM-1FE-TX"
    nm_4e = "NM-4E"
    nm_4t = "NM-4T"
    pa_2fe_tx = "PA-2FE-TX"
    pa_4e = "PA-4E"
    pa_4t_plus = "PA-4T+"
    pa_8e = "PA-8E"
    pa_8t = "PA-8T"
    pa_a1 = "PA-A1"
    pa_fe_tx = "PA-FE-TX"
    pa_ge = "PA-GE"
    pa_pos_oc3 = "PA-POS-OC3"
    c2600_mb_2fe = "C2600-MB-2FE"
    c2600_mb_1e = "C2600-MB-1E"
    c1700_mb_1fe = "C1700-MB-1FE"
    c2600_mb_2e = "C2600-MB-2E"
    c2600_mb_1fe = "C2600-MB-1FE"
    c1700_mb_wic1 = "C1700-MB-WIC1"
    gt96100_fe = "GT96100-FE"
    leopard_2fe = "Leopard-2FE"
    _ = ""


class DynamipsWics(str, Enum):
    """
    Supported Dynamips WICs.
    """

    wic_1enet = "WIC-1ENET"
    wic_1t = "WIC-1T"
    wic_2t = "WIC-2T"
    _ = ""


class DynamipsConsoleType(str, Enum):
    """
    Supported Dynamips console types.
    """

    telnet = "telnet"
    none = "none"


class DynamipsNPE(str, Enum):
    """
    Supported Dynamips NPE models.
    """

    npe_100 = "npe-100"
    npe_150 = "npe-150"
    npe_175 = "npe-175"
    npe_200 = "npe-200"
    npe_225 = "npe-225"
    npe_300 = "npe-300"
    npe_400 = "npe-400"
    npe_g2 = "npe-g2"


class DynamipsMidplane(str, Enum):
    """
    Supported Dynamips Midplane models.
    """

    std = "std"
    vxr = "vxr"


# TODO: improve schema for Dynamips (match platform specific options, e.g. NPE allowed only for c7200)
class DynamipsBase(BaseModel):
    """
    Common Dynamips node properties.
    """

    node_id: Optional[UUID] = None
    name: Optional[str] = None
    dynamips_id: Optional[int] = Field(None, description="Dynamips internal ID")
    platform: Optional[DynamipsPlatform] = Field(None, description="Cisco router platform")
    ram: Optional[int] = Field(None, description="Amount of RAM in MB")
    nvram: Optional[int] = Field(None, description="Amount of NVRAM in KB")
    image: Optional[str] = Field(None, description="Path to the IOS image")
    image_md5sum: Optional[str] = Field(None, description="Checksum of the IOS image")
    usage: Optional[str] = Field(None, description="How to use the Dynamips VM")
    chassis: Optional[str] = Field(None, description="Cisco router chassis model", pattern="^[0-9]{4}(XM)?$")
    startup_config_content: Optional[str] = Field(None, description="Content of IOS startup configuration file")
    private_config_content: Optional[str] = Field(None, description="Content of IOS private configuration file")
    mmap: Optional[bool] = Field(None, description="MMAP feature")
    sparsemem: Optional[bool] = Field(None, description="Sparse memory feature")
    clock_divisor: Optional[int] = Field(None, description="Clock divisor")
    idlepc: Optional[str] = Field(None, description="Idle-PC value", pattern="^(0x[0-9a-fA-F]+)?$")
    idlemax: Optional[int] = Field(None, description="Idlemax value")
    idlesleep: Optional[int] = Field(None, description="Idlesleep value")
    exec_area: Optional[int] = Field(None, description="Exec area value")
    disk0: Optional[int] = Field(None, description="Disk0 size in MB")
    disk1: Optional[int] = Field(None, description="Disk1 size in MB")
    auto_delete_disks: Optional[bool] = Field(None, description="Automatically delete nvram and disk files")
    console: Optional[int] = Field(None, gt=0, le=65535, description="Console TCP port")
    console_type: Optional[DynamipsConsoleType] = Field(None, description="Console type")
    aux: Optional[int] = Field(None, gt=0, le=65535, description="Auxiliary console TCP port")
    aux_type: Optional[DynamipsConsoleType] = Field(None, description="Auxiliary console type")
    mac_addr: Optional[str] = Field(
        None, description="Base MAC address", pattern="^([0-9a-fA-F]{4}\\.){2}[0-9a-fA-F]{4}$"
    )
    system_id: Optional[str] = Field(None, description="System ID")
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
    npe: Optional[DynamipsNPE] = Field(None, description="NPE model")
    midplane: Optional[DynamipsMidplane] = Field(None, description="Midplane model")
    sensors: Optional[List] = Field(None, description="Temperature sensors")
    power_supplies: Optional[List] = Field(None, description="Power supplies status")
    # I/O memory property for all platforms but C7200
    iomem: Optional[int] = Field(None, ge=0, le=100, description="I/O memory percentage")


class DynamipsCreate(DynamipsBase):
    """
    Properties to create a Dynamips node.
    """

    name: str
    platform: str = Field(..., description="Cisco router platform", pattern="^c[0-9]{4}$")
    image: str = Field(..., description="Path to the IOS image")
    ram: int = Field(..., description="Amount of RAM in MB")


class DynamipsUpdate(DynamipsBase):
    """
    Properties to update a Dynamips node.
    """

    pass


class Dynamips(DynamipsBase):

    name: str
    node_id: UUID
    project_id: UUID
    dynamips_id: int
    status: NodeStatus
    node_directory: Optional[str] = Field(None, description="Path to the vm working directory")
