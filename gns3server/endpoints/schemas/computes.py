# -*- coding: utf-8 -*-
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
from typing import List, Optional, Union
from uuid import UUID
from enum import Enum

from .nodes import NodeType


class Protocol(str, Enum):
    """
    Protocol supported to communicate with a compute.
    """

    http = "http"
    https = "https"


class ComputeBase(BaseModel):
    """
    Data to create a compute.
    """

    compute_id: Optional[Union[str, UUID]] = None
    name: Optional[str] = None
    protocol: Protocol
    host: str
    port: int = Field(..., gt=0, le=65535)
    user: Optional[str] = None


class ComputeCreate(ComputeBase):
    """
    Data to create a compute.
    """

    password: Optional[str] = None

    class Config:
        schema_extra = {
            "example": {
                "name": "My compute",
                "host": "127.0.0.1",
                "port": 3080,
                "user": "user",
                "password": "password"
            }
        }


class ComputeUpdate(ComputeBase):
    """
    Data to update a compute.
    """

    protocol: Optional[Protocol] = None
    host: Optional[str] = None
    port: Optional[int] = Field(None, gt=0, le=65535)
    password: Optional[str] = None

    class Config:
        schema_extra = {
            "example": {
                "host": "10.0.0.1",
                "port": 8080,
            }
        }


class Capabilities(BaseModel):
    """
    Capabilities supported by a compute.
    """

    version: str = Field(..., description="Compute version number")
    node_types: List[NodeType] = Field(..., description="Node types supported by the compute")
    platform: str = Field(..., description="Platform where the compute is running (Linux, Windows or macOS)")
    cpus: int = Field(..., description="Number of CPUs on this compute")
    memory: int = Field(..., description="Amount of memory on this compute")
    disk_size: int = Field(..., description="Disk size on this compute")


class Compute(ComputeBase):
    """
    Data returned for a compute.
    """

    compute_id: Union[str, UUID]
    name: str
    connected: bool = Field(..., description="Whether the controller is connected to the compute or not")
    cpu_usage_percent: float = Field(..., description="CPU usage of the compute", ge=0, le=100)
    memory_usage_percent: float = Field(..., description="Memory usage of the compute", ge=0, le=100)
    disk_usage_percent: float = Field(..., description="Disk usage of the compute", ge=0, le=100)
    last_error: Optional[str] = Field(None, description="Last error found on the compute")
    capabilities: Capabilities


class AutoIdlePC(BaseModel):
    """
    Data for auto Idle-PC request.
    """

    platform: str = Field(..., description="Cisco platform")
    image: str = Field(..., description="Image path")
    ram: int = Field(..., description="Amount of RAM in MB")

    class Config:
        schema_extra = {
            "example": {
                "platform": "c7200",
                "image": "/path/to/c7200_image.bin",
                "ram": 256
            }
        }
