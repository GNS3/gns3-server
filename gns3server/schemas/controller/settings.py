#
# Copyright (C) 2026 GNS3 Technologies Inc.
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
#

"""
Schemas for the server settings endpoints (GET/PUT /v3/settings).

The VirtualBox and VMware sections are deprecated and intentionally not
exposed. Controller.jwt_secret_key is excluded everywhere: it is loaded
from the secrets directory and overrides whatever the configuration file
says, so exposing or writing it via the API would be useless at best and
a secret leak at worst.
"""

from typing import List, Optional

from pydantic import ConfigDict, BaseModel, Field

from ..config import (
    BuiltinSymbolTheme,
    ControllerSettings,
    DynamipsSettings,
    IOUSettings,
    QemuSettings,
    ServerProtocol,
    ServerSettings,
    UbridgeControlTransport,
    VPCSSettings,
    WebWiresharkSettings,
)

# matches the pydantic v2 SecretStr serialization mask
SECRET_MASK = "**********"


class ServerSettingsResponse(ServerSettings):

    # plain strings instead of FilePath/DirectoryPath: paths are validated when
    # the settings are loaded or updated, not when echoed back to the client
    secrets_dir: Optional[str] = Field(
        None, description="Directory where secrets are stored (e.g. the JWT secret key)")
    certfile: Optional[str] = Field(None, description="SSL certificate file, requires enable_ssl")
    certkey: Optional[str] = Field(None, description="SSL key file, requires enable_ssl")
    # Optional overrides: typed as plain "str = None" in the config schema,
    # which fails re-validation when the value actually is None
    resources_path: Optional[str] = Field(
        None,
        description="Path where files like built-in appliances and Docker resources are stored "
                    "(defaults to the local user data directory)")
    default_nat_interface: Optional[str] = Field(
        None, description="Interface used by the NAT node, default is virbr0 on Linux (requires libvirt)")


class ControllerSettingsResponse(ControllerSettings):

    # never serialized: managed via the secrets directory, not the configuration file
    jwt_secret_key: Optional[str] = Field(
        default=None, exclude=True,
        description="Secret key used to sign the JWT authentication tokens "
                    "(normally managed via the secrets directory, not the configuration file)")


class IOUSettingsResponse(IOUSettings):

    iourc_path: Optional[str] = Field(
        None, description="Path of your .iourc file, the file is searched in $HOME/.iourc if not provided")


class SettingsResponse(BaseModel):

    Server: ServerSettingsResponse
    Controller: ControllerSettingsResponse
    VPCS: VPCSSettings
    Dynamips: DynamipsSettings
    IOU: IOUSettingsResponse
    Qemu: QemuSettings
    WebWireshark: WebWiresharkSettings


class ServerSettingsUpdate(BaseModel):
    """
    Every field optional: JSON null removes the option from the configuration
    file (restoring its default), missing fields are left untouched.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    local: Optional[bool] = None
    enable_http_auth: Optional[bool] = None
    name: Optional[str] = None
    protocol: Optional[ServerProtocol] = None
    host: Optional[str] = None
    port: Optional[int] = Field(None, gt=0, le=65535)
    secrets_dir: Optional[str] = None
    certfile: Optional[str] = None
    certkey: Optional[str] = None
    enable_ssl: Optional[bool] = None
    images_path: Optional[str] = None
    projects_path: Optional[str] = None
    appliances_path: Optional[str] = None
    symbols_path: Optional[str] = None
    configs_path: Optional[str] = None
    resources_path: Optional[str] = None
    default_symbol_theme: Optional[BuiltinSymbolTheme] = None
    allow_raw_images: Optional[bool] = None
    auto_discover_images: Optional[bool] = None
    report_errors: Optional[bool] = None
    additional_images_paths: Optional[List[str]] = None
    console_start_port_range: Optional[int] = Field(None, gt=0, le=65535)
    console_end_port_range: Optional[int] = Field(None, gt=0, le=65535)
    vnc_console_start_port_range: Optional[int] = Field(None, ge=5900, le=65535)
    vnc_console_end_port_range: Optional[int] = Field(None, ge=5900, le=65535)
    udp_start_port_range: Optional[int] = Field(None, gt=0, le=65535)
    udp_end_port_range: Optional[int] = Field(None, gt=0, le=65535)
    ubridge_path: Optional[str] = None
    ubridge_control_transport: Optional[UbridgeControlTransport] = None
    marker_listen_host: Optional[str] = None
    marker_listen_port: Optional[int] = Field(None, ge=0, le=65535)
    compute_username: Optional[str] = None
    # plain str so the route can compare against SECRET_MASK / empty string
    compute_password: Optional[str] = None
    allowed_interfaces: Optional[List[str]] = None
    default_nat_interface: Optional[str] = None
    allow_remote_console: Optional[bool] = None
    enable_builtin_templates: Optional[bool] = None
    install_builtin_appliances: Optional[bool] = None
    skills_repo_url: Optional[str] = None
    skills_repo_branch: Optional[str] = None
    skills_auto_update: Optional[bool] = None
    mcp_enable_dns_rebinding_protection: Optional[bool] = None
    mcp_allowed_hosts: Optional[List[str]] = None
    mcp_allowed_origins: Optional[List[str]] = None


class ControllerSettingsUpdate(BaseModel):
    """
    No jwt_secret_key field on purpose (see module docstring).
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    jwt_algorithm: Optional[str] = None
    jwt_access_token_expire_minutes: Optional[int] = None
    jwt_refresh_token_expire_minutes: Optional[int] = None
    default_admin_username: Optional[str] = None
    default_admin_password: Optional[str] = None


class VPCSSettingsUpdate(BaseModel):

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    vpcs_path: Optional[str] = None


class DynamipsSettingsUpdate(BaseModel):

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    allocate_aux_console_ports: Optional[bool] = None
    mmap_support: Optional[bool] = None
    dynamips_path: Optional[str] = None
    sparse_memory_support: Optional[bool] = None
    ghost_ios_support: Optional[bool] = None


class IOUSettingsUpdate(BaseModel):

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    iourc_path: Optional[str] = None
    license_check: Optional[bool] = None


class QemuSettingsUpdate(BaseModel):

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    enable_monitor: Optional[bool] = None
    monitor_host: Optional[str] = None
    enable_hardware_acceleration: Optional[bool] = None
    require_hardware_acceleration: Optional[bool] = None
    allow_unsafe_options: Optional[bool] = None
    ovmf_firmware_dir: Optional[str] = None


class WebWiresharkSettingsUpdate(BaseModel):

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    enabled: Optional[bool] = None
    image: Optional[str] = None
    network_subnet: Optional[str] = None
    memory: Optional[str] = None
    cpus: Optional[float] = None
    pids_limit: Optional[int] = None


class SettingsUpdate(BaseModel):

    model_config = ConfigDict(extra="forbid")

    Server: Optional[ServerSettingsUpdate] = None
    Controller: Optional[ControllerSettingsUpdate] = None
    VPCS: Optional[VPCSSettingsUpdate] = None
    Dynamips: Optional[DynamipsSettingsUpdate] = None
    IOU: Optional[IOUSettingsUpdate] = None
    Qemu: Optional[QemuSettingsUpdate] = None
    WebWireshark: Optional[WebWiresharkSettingsUpdate] = None


class SettingsUpdateResponse(SettingsResponse):

    restart_required: List[str] = Field(
        default_factory=list,
        description="Changed 'Section.option' settings that require a server restart to take effect"
    )
