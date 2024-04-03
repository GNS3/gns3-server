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


from . import Category, TemplateBase
from ...common import ConsoleType, AuxType, CustomAdapter

from pydantic import Field
from typing import Optional, List


class DockerTemplate(TemplateBase):

    category: Optional[Category] = "guest"
    default_name_format: Optional[str] = "{name}-{0}"
    symbol: Optional[str] = "docker_guest"
    image: str = Field(..., description="Docker image name")
    adapters: Optional[int] = Field(1, ge=0, le=100, description="Number of adapters")
    start_command: Optional[str] = Field("", description="Docker CMD entry")
    environment: Optional[str] = Field("", description="Docker environment variables")
    console_type: Optional[ConsoleType] = Field("telnet", description="Console type")
    aux_type: Optional[AuxType] = Field("none", description="Auxiliary console type")
    console_auto_start: Optional[bool] = Field(
        False, description="Automatically start the console when the node has started"
    )
    console_http_port: Optional[int] = Field(
        80, gt=0, le=65535, description="Internal port in the container for the HTTP server"
    )
    console_http_path: Optional[str] = Field(
        "/",
        description="Path of the web interface",
    )
    console_resolution: Optional[str] = Field(
        "1024x768", pattern="^[0-9]+x[0-9]+$", description="Console resolution for VNC"
    )
    extra_hosts: Optional[str] = Field("", description="Docker extra hosts (added to /etc/hosts)")
    extra_volumes: Optional[List] = Field([], description="Additional directories to make persistent")
    memory: Optional[int] = Field(0, description="Maximum amount of memory the container can use in MB")
    cpus: Optional[float] = Field(0, description="Maximum amount of CPU resources the container can use")
    custom_adapters: Optional[List[CustomAdapter]] = Field(default_factory=list, description="Custom adapters")


class DockerTemplateUpdate(DockerTemplate):

    image: Optional[str] = Field(None, description="Docker image name")