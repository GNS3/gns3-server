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


class WhenExit(str, Enum):
    """
    What to do with the VM when GNS3 VM exits.
    """

    stop = "stop"
    suspend = "suspend"
    keep = "keep"


class Engine(str, Enum):
    """
    "The engine to use for the GNS3 VM.
    """

    vmware = "vmware"
    virtualbox = "virtualbox"
    hyperv = "hyper-v"
    none = "none"


class GNS3VM(BaseModel):
    """
    GNS3 VM data.
    """

    enable: Optional[bool] = Field(None, description="Enable/disable the GNS3 VM")
    vmname: Optional[str] = Field(None, description="GNS3 VM name")
    when_exit: Optional[WhenExit] = Field(None, description="Action when the GNS3 VM exits")
    headless: Optional[bool] = Field(None, description="Start the GNS3 VM GUI or not")
    engine: Optional[Engine] = Field(None, description="The engine to use for the GNS3 VM")
    allocate_vcpus_ram: Optional[bool] = Field(None, description="Allocate vCPUS and RAM settings")
    vcpus: Optional[int] = Field(None, description="Number of CPUs to allocate for the GNS3 VM")
    ram: Optional[int] = Field(None, description="Amount of memory to allocate for the GNS3 VM")
    port: Optional[int] = Field(None, gt=0, le=65535)
