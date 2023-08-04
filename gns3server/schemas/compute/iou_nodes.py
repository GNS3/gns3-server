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
from uuid import UUID

from ..common import NodeStatus, ConsoleType


class IOUBase(BaseModel):
    """
    Common IOU node properties.
    """

    name: str
    path: str = Field(..., description="IOU executable path")
    application_id: int = Field(..., description="Application ID for running IOU executable")
    node_id: Optional[UUID] = None
    usage: Optional[str] = Field(None, description="How to use the node")
    console: Optional[int] = Field(None, gt=0, le=65535, description="Console TCP port")
    console_type: Optional[ConsoleType] = Field(None, description="Console type")
    md5sum: Optional[str] = Field(None, description="IOU executable checksum")
    serial_adapters: Optional[int] = Field(None, description="How many serial adapters are connected to IOU")
    ethernet_adapters: Optional[int] = Field(None, description="How many Ethernet adapters are connected to IOU")
    ram: Optional[int] = Field(None, description="Amount of RAM in MB")
    nvram: Optional[int] = Field(None, description="Amount of NVRAM in KB")
    l1_keepalives: Optional[bool] = Field(None, description="Use default IOU values")
    use_default_iou_values: Optional[bool] = Field(None, description="Always up Ethernet interfaces")
    startup_config_content: Optional[str] = Field(None, description="Content of IOU startup configuration file")
    private_config_content: Optional[str] = Field(None, description="Content of IOU private configuration file")


class IOUCreate(IOUBase):
    """
    Properties to create an IOU node.
    """

    pass


class IOUUpdate(IOUBase):
    """
    Properties to update an IOU node.
    """

    name: Optional[str] = None
    path: Optional[str] = Field(None, description="IOU executable path")
    application_id: Optional[int] = Field(None, description="Application ID for running IOU executable")


class IOU(IOUBase):

    project_id: UUID = Field(..., description="Project ID")
    node_directory: str = Field(..., description="Path to the node working directory (read only)")
    command_line: str = Field(..., description="Last command line used to start IOU (read only)")
    status: NodeStatus = Field(..., description="Container status (read only)")


class IOUStart(BaseModel):

    iourc_content: Optional[str] = Field(None, description="Content of the iourc file")
    license_check: Optional[bool] = Field(None, description="Whether the IOU license should be checked")
