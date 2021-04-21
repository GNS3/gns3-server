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
from typing import Optional
from uuid import UUID

from ..common import NodeStatus


class ATMSwitchBase(BaseModel):
    """
    Common ATM switch properties.
    """

    name: str = None
    node_id: UUID = None
    usage: Optional[str] = None
    mappings: Optional[dict] = None


class ATMSwitchCreate(ATMSwitchBase):
    """
    Properties to create an ATM switch node.
    """

    node_id: Optional[UUID] = None


class ATMSwitchUpdate(ATMSwitchBase):
    """
    Properties to update an ATM switch node.
    """

    name: Optional[str] = None
    node_id: Optional[UUID] = None


class ATMSwitch(ATMSwitchBase):

    project_id: UUID
    status: Optional[NodeStatus] = None
