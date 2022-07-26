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
from typing import Optional, Union, List
from enum import Enum
from uuid import UUID

from ..common import NodeStatus


class HostInterfaceType(str, Enum):

    ethernet = "ethernet"
    tap = "tap"


class HostInterface(BaseModel):
    """
    Interface on this host.
    """

    name: str = Field(..., description="Interface name")
    type: HostInterfaceType = Field(..., description="Interface type")
    special: bool = Field(..., description="Whether the interface is non standard")


class EthernetType(str, Enum):
    ethernet = "ethernet"


class EthernetPort(BaseModel):
    """
    Ethernet port properties.
    """

    name: str
    port_number: int
    type: EthernetType
    interface: str


class TAPType(str, Enum):
    tap = "tap"


class TAPPort(BaseModel):
    """
    TAP port properties.
    """

    name: str
    port_number: int
    type: TAPType
    interface: str


class UDPType(str, Enum):
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


class CloudConsoleType(str, Enum):

    telnet = "telnet"
    vnc = "vnc"
    spice = "spice"
    http = "http"
    https = "https"
    none = "none"


class CloudBase(BaseModel):
    """
    Common cloud node properties.
    """

    name: str
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

    pass


class CloudUpdate(CloudBase):
    """
    Properties to update a cloud node.
    """

    name: Optional[str] = None


class Cloud(CloudBase):

    project_id: UUID
    node_id: UUID
    ports_mapping: List[Union[EthernetPort, TAPPort, UDPPort]]
    status: NodeStatus = Field(..., description="Cloud node status (read only)")
