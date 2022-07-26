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
from enum import Enum


class UDPNIOType(str, Enum):

    udp = "nio_udp"


class UDPNIO(BaseModel):
    """
    UDP Network Input/Output properties.
    """

    type: UDPNIOType
    lport: int = Field(..., gt=0, le=65535, description="Local port")
    rhost: str = Field(..., description="Remote host")
    rport: int = Field(..., gt=0, le=65535, description="Remote port")
    suspend: Optional[int] = Field(None, description="Suspend the NIO")
    filters: Optional[dict] = Field(None, description="Packet filters")


class EthernetNIOType(str, Enum):

    ethernet = "nio_ethernet"


class EthernetNIO(BaseModel):
    """
    Generic Ethernet Network Input/Output properties.
    """

    type: EthernetNIOType
    ethernet_device: str = Field(..., description="Ethernet device name e.g. eth0")


class TAPNIOType(str, Enum):

    tap = "nio_tap"


class TAPNIO(BaseModel):
    """
    TAP Network Input/Output properties.
    """

    type: TAPNIOType
    tap_device: str = Field(..., description="TAP device name e.g. tap0")
