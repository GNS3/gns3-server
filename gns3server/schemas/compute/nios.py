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
    suspend: Optional[bool] = Field(None, description="Suspend the NIO")
    filters: Optional[dict] = Field(None, description="Packet filters")
    markers: Optional[dict] = Field(None, description="Traffic-insight markers")


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


class MarkerToggle(BaseModel):
    """
    Body for the per-marker enable/disable toggle endpoint: flips a running
    uBridge marker filter with ``enable_packet_filter on|off`` (no NIO rebuild,
    so the pcap identity and emitted counter are preserved).
    """

    enabled: bool


class MarkerRebuild(BaseModel):
    """
    Body for the per-marker rebuild endpoint: re-install a single uBridge marker
    filter with new BPF/tag/direction via ``delete_packet_filter`` + add (NOT a
    bridge-wide reset), so sibling markers keep their pcaps open. The marker's
    own pcap is reopened by uBridge on re-add (new capture session for the new
    BPF), which is expected.
    """

    bpf: str
    tag: Optional[int] = None
    direction: Optional[str] = None
    enabled: bool = True
    link_id: str = ""


class BatchNIOEntry(BaseModel):
    """
    A single NIO binding to create as part of a project-wide batch.
    """

    node_id: str = Field(..., description="Node the NIO is attached to")
    adapter_number: int = Field(0, ge=0, description="Adapter number")
    port_number: int = Field(0, ge=0, description="Port number")
    nio: UDPNIO = Field(..., description="NIO settings")


class BatchNIOCreate(BaseModel):
    """
    Body for the project-wide batch NIO endpoint: create many NIO bindings in a
    single request (used during project open) to avoid one HTTP round-trip per
    NIO between controller and compute.
    """

    nios: List[BatchNIOEntry] = Field(..., description="NIO bindings to create")
