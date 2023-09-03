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


class ErrorMessage(BaseModel):
    """
    Error message.
    """

    message: str


class NodeStatus(str, Enum):
    """
    Supported node statuses.
    """

    stopped = "stopped"
    started = "started"
    suspended = "suspended"


class CustomAdapter(BaseModel):
    """
    Custom adapter data.
    """

    adapter_number: int
    port_name: Optional[str] = None
    adapter_type: Optional[str] = None
    mac_address: Optional[str] = Field(None, pattern="^([0-9a-fA-F]{2}[:]){5}([0-9a-fA-F]{2})$")


class ConsoleType(str, Enum):
    """
    Supported console types.
    """

    vnc = "vnc"
    telnet = "telnet"
    http = "http"
    https = "https"
    spice = "spice"
    spice_agent = "spice+agent"
    none = "none"


class AuxType(str, Enum):
    """
    Supported auxiliary console types.
    """

    telnet = "telnet"
    none = "none"
