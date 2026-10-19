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

import re
from enum import Enum
from typing import List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ..common import NodeStatus
from ..update import PartialUpdateModel

LINUX_TAP_NAME_PATTERN = r"^[a-zA-Z0-9_.:-]{1,15}$"


class HostInterfaceType(StrEnum):
    ethernet = "ethernet"
    tap = "tap"


class IPAddressFamily(StrEnum):
    ipv4 = "ipv4"
    ipv6 = "ipv6"


class InterfaceStatus(StrEnum):
    up = "up"
    down = "down"


class HostInterfaceIPAddress(BaseModel):
    """
    An IP address (with optional netmask) bound to a host interface.
    """

    family: IPAddressFamily = Field(..., description="Address family (ipv4 or ipv6)")
    address: str = Field(..., description="IP address")
    netmask: Optional[str] = Field(None, description="Network mask, if available")


class HostInterface(BaseModel):
    """
    Interface on this host.
    """

    name: str = Field(..., description="Interface name")
    type: HostInterfaceType = Field(..., description="Interface type")
    special: bool = Field(..., description="Whether the interface is non standard")
    is_bridge: bool = Field(False, description="Whether this is a Linux bridge")
    ip_addresses: List[HostInterfaceIPAddress] = Field(
        default_factory=list, description="All IPv4 and IPv6 addresses on this interface"
    )
    status: InterfaceStatus = Field(InterfaceStatus.down, description="Interface status (up or down)")
    speed: int = Field(0, description="Interface speed in Mbit/s (0 if unknown)")
    mtu: int = Field(0, description="Interface MTU")
    flags: List[str] = Field(default_factory=list, description="Interface flags")


class EthernetType(StrEnum):
    ethernet = "ethernet"


class EthernetPort(BaseModel):
    """
    Ethernet port properties.
    """

    name: str
    port_number: int
    type: EthernetType
    interface: str


class TAPType(StrEnum):
    tap = "tap"


class TAPPort(BaseModel):
    """
    TAP port properties.
    """

    name: str
    port_number: int
    type: TAPType
    interface: str
    bridge: Optional[str] = Field(
        None,
        min_length=1,
        max_length=15,
        pattern=LINUX_TAP_NAME_PATTERN,
        description="Existing Linux bridge to attach the TAP to",
    )

    @model_validator(mode="after")
    def validate_bridged_interface(self):
        if self.bridge and not re.fullmatch(LINUX_TAP_NAME_PATTERN, self.interface):
            raise ValueError("A bridged TAP name must be 1-15 letters, digits, underscores, dots, colons or hyphens")
        return self


class UDPType(StrEnum):
    udp = "udp"


class UDPPort(BaseModel):
    """
    UDP tunnel port properties.
    """

    name: str
    port_number: int
    type: UDPType
    lport: int = Field(..., gt=0, le=65535, description="Local port")
    rhost: str = Field(..., description="Remote host")
    rport: int = Field(..., gt=0, le=65535, description="Remote port")


class CloudConsoleType(StrEnum):
    telnet = "telnet"
    ssh = "ssh"
    vnc = "vnc"
    spice = "spice"
    http = "http"
    https = "https"
    none = "none"


class CloudBase(BaseModel):
    """
    Common cloud node properties.
    """

    name: Optional[str] = None
    node_id: Optional[UUID] = None
    usage: Optional[str] = None
    remote_console_host: Optional[str] = Field(None, description="Remote console host or IP")
    remote_console_port: Optional[int] = Field(None, gt=0, le=65535, description="Console TCP port")
    remote_console_type: Optional[CloudConsoleType] = Field(None, description="Console type")
    remote_console_http_path: Optional[str] = Field(None, description="Path of the remote web interface")
    ports_mapping: Optional[List[Union[EthernetPort, TAPPort, UDPPort]]] = Field(
        None, description="List of port mappings"
    )
    interfaces: Optional[List[HostInterface]] = Field(None, description="List of interfaces")


class CloudCreate(CloudBase):
    """
    Properties to create a cloud node.
    """

    name: str


class CloudUpdate(PartialUpdateModel, CloudBase):
    """
    Properties to update a cloud node.
    """

    update_excluded_fields = ("node_id",)

    name: Optional[str] = None


class Cloud(CloudBase):
    name: str
    project_id: UUID
    node_id: UUID
    ports_mapping: List[Union[EthernetPort, TAPPort, UDPPort]]
    status: NodeStatus = Field(..., description="Cloud node status (read only)")
