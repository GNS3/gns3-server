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
from uuid import UUID

from ..common import NodeStatus, CustomAdapter, ConsoleType, AuxType


class DockerBase(BaseModel):
    """
    Common Docker node properties.
    """

    name: str
    image: str = Field(..., description="Docker image name")
    node_id: Optional[UUID] = None
    console: Optional[int] = Field(None, gt=0, le=65535, description="Console TCP port")
    console_type: Optional[ConsoleType] = Field(None, description="Console type")
    console_resolution: Optional[str] = Field(None, pattern="^[0-9]+x[0-9]+$", description="Console resolution for VNC")
    console_http_port: Optional[int] = Field(None, description="Internal port in the container for the HTTP server")
    console_http_path: Optional[str] = Field(None, description="Path of the web interface")
    aux: Optional[int] = Field(None, gt=0, le=65535, description="Auxiliary TCP port")
    aux_type: Optional[AuxType] = Field(None, description="Auxiliary console type")
    usage: Optional[str] = Field(None, description="How to use the Docker container")
    start_command: Optional[str] = Field(None, description="Docker CMD entry")
    adapters: Optional[int] = Field(None, ge=0, le=99, description="Number of adapters")
    environment: Optional[str] = Field(None, description="Docker environment variables")
    extra_hosts: Optional[str] = Field(None, description="Docker extra hosts (added to /etc/hosts)")
    extra_volumes: Optional[List[str]] = Field(None, description="Additional directories to make persistent")
    memory: Optional[int] = Field(None, description="Maximum amount of memory the container can use in MB")
    cpus: Optional[float] = Field(None, description="Maximum amount of CPU resources the container can use")
    custom_adapters: Optional[List[CustomAdapter]] = Field(None, description="Custom adapters")


class DockerCreate(DockerBase):
    """
    Properties to create a Docker node.
    """

    pass


class DockerUpdate(DockerBase):
    """
    Properties to update a Docker node.
    """

    name: Optional[str] = None
    image: Optional[str] = Field(None, description="Docker image name")


class Docker(DockerBase):

    container_id: str = Field(
        ..., min_length=12, max_length=64, pattern="^[a-f0-9]+$", description="Docker container ID (read only)"
    )
    project_id: UUID = Field(..., description="Project ID")
    node_directory: str = Field(..., description="Path to the node working directory (read only)")
    status: NodeStatus = Field(..., description="Container status (read only)")
