#
# Copyright (C) 2021 GNS3 Technologies Inc.
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

import socket

from enum import Enum
from pydantic import (
    ConfigDict,
    BaseModel,
    Field,
    SecretStr,
    FilePath,
    DirectoryPath,
    field_validator,
    model_validator
)
from typing import List


class ControllerSettings(BaseModel):

    jwt_secret_key: str = None
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 1440  # 24 hours
    default_admin_username: str = "admin"
    default_admin_password: SecretStr = SecretStr("admin")
    model_config = ConfigDict(validate_assignment=True, str_strip_whitespace=True)


class VPCSSettings(BaseModel):

    vpcs_path: str = "vpcs"
    model_config = ConfigDict(validate_assignment=True, str_strip_whitespace=True)


class DynamipsSettings(BaseModel):

    allocate_aux_console_ports: bool = False
    mmap_support: bool = True
    dynamips_path: str = "dynamips"
    sparse_memory_support: bool = True
    ghost_ios_support: bool = True
    model_config = ConfigDict(validate_assignment=True, str_strip_whitespace=True)


class IOUSettings(BaseModel):

    iourc_path: str = None
    license_check: bool = True
    model_config = ConfigDict(validate_assignment=True, str_strip_whitespace=True)


class QemuSettings(BaseModel):

    enable_monitor: bool = True
    monitor_host: str = "127.0.0.1"
    enable_hardware_acceleration: bool = True
    require_hardware_acceleration: bool = False
    model_config = ConfigDict(validate_assignment=True, str_strip_whitespace=True)


class VirtualBoxSettings(BaseModel):

    vboxmanage_path: str = None
    model_config = ConfigDict(validate_assignment=True, str_strip_whitespace=True)


class VMwareSettings(BaseModel):

    vmrun_path: str = None
    vmnet_start_range: int = Field(2, ge=1, le=255)
    vmnet_end_range: int = Field(255, ge=1, le=255)  # should be limited to 19 on Windows
    block_host_traffic: bool = False
    model_config = ConfigDict(validate_assignment=True, str_strip_whitespace=True)

    @model_validator(mode="after")
    def check_vmnet_port_range(self) -> "VMwareSettings":
        if self.vmnet_end_range <= self.vmnet_start_range:
            raise ValueError("vmnet_end_range must be > vmnet_start_range")
        return self


class ServerProtocol(str, Enum):

    http = "http"
    https = "https"


class BuiltinSymbolTheme(str, Enum):

    classic = "Classic"
    affinity_square_blue = "Affinity-square-blue"
    affinity_square_red = "Affinity-square-red"
    affinity_square_gray = "Affinity-square-gray"
    affinity_circle_blue = "Affinity-circle-blue"
    affinity_circle_red = "Affinity-circle-red"
    affinity_circle_gray = "Affinity-circle-gray"


class ServerSettings(BaseModel):

    local: bool = False
    name: str = f"{socket.gethostname()} (controller)"
    protocol: ServerProtocol = ServerProtocol.http
    host: str = "0.0.0.0"
    port: int = Field(3080, gt=0, le=65535)
    secrets_dir: DirectoryPath = None
    certfile: FilePath = None
    certkey: FilePath = None
    enable_ssl: bool = False
    images_path: str = "~/GNS3/images"
    projects_path: str = "~/GNS3/projects"
    appliances_path: str = "~/GNS3/appliances"
    symbols_path: str = "~/GNS3/symbols"
    configs_path: str = "~/GNS3/configs"
    default_symbol_theme: BuiltinSymbolTheme = BuiltinSymbolTheme.affinity_square_blue
    allow_raw_images: bool = True
    auto_discover_images: bool = True
    report_errors: bool = True
    additional_images_paths: List[str] = Field(default_factory=list)
    console_start_port_range: int = Field(5000, gt=0, le=65535)
    console_end_port_range: int = Field(10000, gt=0, le=65535)
    vnc_console_start_port_range: int = Field(5900, ge=5900, le=65535)
    vnc_console_end_port_range: int = Field(10000, ge=5900, le=65535)
    udp_start_port_range: int = Field(10000, gt=0, le=65535)
    udp_end_port_range: int = Field(30000, gt=0, le=65535)
    ubridge_path: str = "ubridge"
    compute_username: str = "gns3"
    compute_password: SecretStr = SecretStr("")
    allowed_interfaces: List[str] = Field(default_factory=list)
    default_nat_interface: str = None
    allow_remote_console: bool = False
    enable_builtin_templates: bool = True
    model_config = ConfigDict(validate_assignment=True, str_strip_whitespace=True, use_enum_values=True)

    @field_validator("additional_images_paths", mode="before")
    @classmethod
    def split_additional_images_paths(cls, v):
        if v:
            return v.split(";")
        return list()

    @field_validator("allowed_interfaces", mode="before")
    @classmethod
    def split_allowed_interfaces(cls, v):
        if v:
            return v.split(",")
        return list()

    @model_validator(mode="after")
    def check_console_port_range(self) -> "ServerSettings":
        if self.console_end_port_range <= self.console_start_port_range:
            raise ValueError("console_end_port_range must be > console_start_port_range")
        return self

    @model_validator(mode="after")
    def check_vnc_port_range(self) -> "ServerSettings":
        if self.vnc_console_end_port_range <= self.vnc_console_start_port_range:
            raise ValueError("vnc_console_end_port_range must be > vnc_console_start_port_range")
        return self

    @model_validator(mode="after")
    def check_enable_ssl(self) -> "ServerSettings":
        if self.enable_ssl is True:
            if not self.certfile:
                raise ValueError("SSL is enabled but certfile is not configured")
            if not self.certkey:
                raise ValueError("SSL is enabled but certkey is not configured")
        return self


class ServerConfig(BaseModel):

    Server: ServerSettings = ServerSettings()
    Controller: ControllerSettings = ControllerSettings()
    VPCS: VPCSSettings = VPCSSettings()
    Dynamips: DynamipsSettings = DynamipsSettings()
    IOU: IOUSettings = IOUSettings()
    Qemu: QemuSettings = QemuSettings()
    VirtualBox: VirtualBoxSettings = VirtualBoxSettings()
    VMware: VMwareSettings = VMwareSettings()
