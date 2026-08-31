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

from pydantic import BaseModel, Field, field_validator
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


class ExtraConfig(BaseModel):
    """
    A configuration file injected into a Docker container.

    GNS3 writes ``content`` to a host file and bind-mounts it read-only at
    ``target`` inside the container. Used to seed NOS startup configs (e.g.
    XRd first-boot config, FRR frr.conf) without rebuilding the image.
    """

    target: str = Field(..., description="Absolute path inside the container where the file is mounted")
    content: str = Field("", description="File content written by GNS3 and bind-mounted read-only into the container")

    @field_validator("target")
    @classmethod
    def target_is_an_absolute_file_path(cls, v):
        """
        Reject at save time (template/appliance/node PUT) what would only
        blow up at node-create time — after a potentially multi-GB image
        pull: relative paths, '..' components and directory forms ('/',
        '/etc/').
        """
        if not v.startswith("/") or v.endswith("/") or ".." in v.split("/"):
            raise ValueError(
                "target must be an absolute file path inside the container "
                "(start with '/', name a file, no '..' components)"
            )
        return v


class ConsoleType(str, Enum):
    """
    Supported console types.
    """

    vnc = "vnc"
    telnet = "telnet"
    ssh = "ssh"
    http = "http"
    https = "https"
    spice = "spice"
    spice_agent = "spice+agent"
    none = "none"
    docker_exec = "docker_exec"


class AuxType(str, Enum):
    """
    Supported auxiliary console types.
    """

    telnet = "telnet"
    ssh = "ssh"
    none = "none"
