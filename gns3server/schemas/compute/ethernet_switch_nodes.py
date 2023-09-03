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

from pydantic import BaseModel, Field, model_validator
from typing import Optional, List
from uuid import UUID
from enum import Enum

from ..common import NodeStatus


class EthernetSwitchPortType(str, Enum):

    access = "access"
    dot1q = "dot1q"
    qinq = "qinq"


class EthernetSwitchEtherType(str, Enum):

    ethertype_8021q = "0x8100"
    ethertype_qinq = "0x88A8"
    ethertype_8021q9100 = "0x9100"
    ethertype_8021q9200 = "0x9200"


class EthernetSwitchPort(BaseModel):

    name: str
    port_number: int
    type: EthernetSwitchPortType = Field(..., description="Port type")
    vlan: int = Field(..., ge=1, le=4094, description="VLAN number")
    ethertype: Optional[EthernetSwitchEtherType] = Field("0x8100", description="QinQ Ethertype")

    @model_validator(mode="after")
    def check_ethertype(self) -> "EthernetSwitchPort":

        if self.ethertype != EthernetSwitchEtherType.ethertype_8021q and self.type != EthernetSwitchPortType.qinq:
            raise ValueError("Ethertype is only for QinQ port type")
        return self


class TelnetConsoleType(str, Enum):
    """
    Supported console types.
    """

    telnet = "telnet"
    none = "none"


class EthernetSwitchBase(BaseModel):
    """
    Common Ethernet switch properties.
    """

    name: Optional[str] = None
    node_id: Optional[UUID] = None
    usage: Optional[str] = None
    ports_mapping: Optional[List[EthernetSwitchPort]] = None
    console: Optional[int] = Field(None, gt=0, le=65535, description="Console TCP port")
    console_type: Optional[TelnetConsoleType] = Field(None, description="Console type")


class EthernetSwitchCreate(EthernetSwitchBase):
    """
    Properties to create an Ethernet switch node.
    """

    name: str


class EthernetSwitchUpdate(EthernetSwitchBase):
    """
    Properties to update an Ethernet hub node.
    """

    pass


class EthernetSwitch(EthernetSwitchBase):

    name: str
    node_id: UUID
    project_id: UUID
    ports_mapping: List[EthernetSwitchPort]
    status: NodeStatus
