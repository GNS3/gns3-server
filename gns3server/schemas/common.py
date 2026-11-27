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

import ipaddress
from enum import StrEnum
from typing import Annotated, Any, Optional

from pydantic import AfterValidator, BaseModel, Field, field_validator


def _known_startup_media_profile(value):
    """An empty value means console restore; any other value must be a registered profile id."""
    if not value:
        return None
    # Imported lazily: the profile registry must not load with the schemas.
    from gns3server.services.configurations.boot_media import get_profile
    from gns3server.services.configurations.shared.errors import ConfigurationError

    try:
        get_profile(value)
    except ConfigurationError:
        raise ValueError("startup_media_profile_unknown") from None
    return value


StartupMediaProfile = Annotated[str, Field(max_length=64), AfterValidator(_known_startup_media_profile)]


class ErrorMessage(BaseModel):
    """
    Error message.
    """

    message: str
    code: Optional[str] = Field(
        None,
        description="Stable machine-readable error code, for example port_in_use or node_not_found",
    )
    details: Optional[dict[str, Any]] = Field(None, description="Optional structured data about the error")


class NodeStatus(StrEnum):
    """
    Supported node statuses.
    """

    stopped = "stopped"
    started = "started"
    suspended = "suspended"
    starting = "starting"
    stopping = "stopping"


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


class ConsoleType(StrEnum):
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


class AuxType(StrEnum):
    """
    Supported auxiliary console types.
    """

    telnet = "telnet"
    ssh = "ssh"
    none = "none"


def validate_extra_hosts(value: Any) -> Any:
    """
    Validate the Docker `extra_hosts` setting: one `hostname:IP` entry per line.

    Each entry must have a non-empty hostname without whitespace and an address
    that parses as an IPv4 or IPv6 address. Entries are split on the first
    colon only, so IPv6 addresses (which contain colons themselves) are
    supported.

    Docker special values such as 'host-gateway' are rejected: GNS3 containers
    are created with networking disabled and only get interfaces from the GNS3
    topology, so there is no default Docker network for such a value to
    resolve to. Use a real, routable address instead.
    """
    if value is None:
        return value
    if not isinstance(value, str):
        raise ValueError("extra_hosts must be a string")
    for raw_line in value.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        hostname, separator, address = line.partition(":")
        hostname = hostname.strip()
        address = address.strip()
        if not separator or not hostname or not address:
            raise ValueError(
                f"Invalid extra_hosts entry '{line}': expected format is 'hostname:IP' (one entry per line)"
            )
        if any(character.isspace() for character in hostname):
            raise ValueError(f"Invalid extra_hosts entry '{line}': hostname must not contain whitespace")
        try:
            ipaddress.ip_address(address)
        except ValueError as exc:
            raise ValueError(
                f"Invalid extra_hosts entry '{line}': '{address}' is not a valid IPv4 or IPv6 address. "
                "GNS3 containers have no default Docker network, so special values such as "
                "'host-gateway' are not supported: use a real, routable address instead"
            ) from exc
    return value
