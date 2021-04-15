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

from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID

from ..common import NodeStatus


class EthernetHubPort(BaseModel):

    name: str
    port_number: int


class EthernetHubBase(BaseModel):
    """
    Common Ethernet hub properties.
    """

    name: Optional[str] = None
    node_id: Optional[UUID] = None
    usage: Optional[str] = None
    ports_mapping: Optional[List[EthernetHubPort]] = None


class EthernetHubCreate(EthernetHubBase):
    """
    Properties to create an Ethernet hub node.
    """

    name: str


class EthernetHubUpdate(EthernetHubBase):
    """
    Properties to update an Ethernet hub node.
    """

    pass


class EthernetHub(EthernetHubBase):

    name: str
    node_id: UUID
    project_id: UUID
    ports_mapping: List[EthernetHubPort]
    status: NodeStatus
