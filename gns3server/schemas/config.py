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
from typing import List, Optional


class ControllerSettings(BaseModel):

    jwt_secret_key: Optional[str] = Field(
        None,
        description="Secret key used to sign the JWT authentication tokens "
                    "(normally managed via the secrets directory, not the configuration file)")
    jwt_algorithm: str = Field("HS256", description="Algorithm used to sign the JWT tokens")
    jwt_access_token_expire_minutes: int = Field(
        1440, description="Lifetime of the JWT access tokens in minutes (24 hours by default)")
    jwt_refresh_token_expire_minutes: int = Field(
        43200, description="Lifetime of the JWT refresh tokens in minutes (30 days by default)")
    default_admin_username: str = Field(
        "admin",
        description="Username of the super admin account seeded when the controller database is created; "
                    "changing it has no effect until the database is re-created (which resets the account)")
    default_admin_password: SecretStr = Field(
        SecretStr("admin"),
        description="Password of the super admin account seeded when the controller database is created; "
                    "changing it has no effect until the database is re-created (which resets the account)")
    model_config = ConfigDict(validate_assignment=True, str_strip_whitespace=True)


class VPCSSettings(BaseModel):

    vpcs_path: str = Field("vpcs", description="VPCS executable location, default: search in PATH")
    model_config = ConfigDict(validate_assignment=True, str_strip_whitespace=True)


class DynamipsSettings(BaseModel):

    allocate_aux_console_ports: bool = Field(
        False, description="Allocate auxiliary console ports on IOS routers")
    mmap_support: bool = Field(
        True, description="Use memory-mapped flash files (mmap) to lower the memory usage of routers")
    dynamips_path: str = Field("dynamips", description="Dynamips executable location, default: search in PATH")
    sparse_memory_support: bool = Field(
        True, description="Use sparse memory allocation to lower the memory usage of routers")
    ghost_ios_support: bool = Field(
        True, description="Enable Ghost IOS support to share memory between identical IOS images")
    model_config = ConfigDict(validate_assignment=True, str_strip_whitespace=True)


class IOUSettings(BaseModel):

    iourc_path: Optional[str] = Field(
        None, description="Path of your .iourc file, the file is searched in $HOME/.iourc if not provided")
    license_check: bool = Field(
        True,
        description="Validate the iourc license file (if disabled, IOU will not start and no errors "
                    "will be shown when the license is invalid)")
    model_config = ConfigDict(validate_assignment=True, str_strip_whitespace=True)


class QemuSettings(BaseModel):

    enable_monitor: bool = Field(
        True, description="Use the Qemu monitor feature to communicate with Qemu VMs")
    monitor_host: str = Field("127.0.0.1", description="IP used to listen for the monitor")
    enable_hardware_acceleration: bool = Field(
        True, description="Enable hardware acceleration (KVM)")
    require_hardware_acceleration: bool = Field(
        False, description="Require hardware acceleration in order to start VMs")
    allow_unsafe_options: bool = Field(
        False, description="Allow unsafe additional command line options")
    ovmf_firmware_dir: str = Field(
        "/usr/share/OVMF", description="Path to the OVMF firmware directory")
    model_config = ConfigDict(validate_assignment=True, str_strip_whitespace=True)


class VirtualBoxSettings(BaseModel):

    vboxmanage_path: Optional[str] = None
    model_config = ConfigDict(validate_assignment=True, str_strip_whitespace=True)


class VMwareSettings(BaseModel):

    vmrun_path: Optional[str] = None
    vmnet_start_range: int = Field(2, ge=1, le=255)
    vmnet_end_range: int = Field(255, ge=1, le=255)  # should be limited to 19 on Windows
    block_host_traffic: bool = False
    model_config = ConfigDict(validate_assignment=True, str_strip_whitespace=True)

    @model_validator(mode="after")
    def check_vmnet_port_range(self) -> "VMwareSettings":
        if self.vmnet_end_range <= self.vmnet_start_range:
            raise ValueError("vmnet_end_range must be > vmnet_start_range")
        return self


class WebWiresharkSettings(BaseModel):

    enabled: bool = Field(
        True, description="Enable the Web Wireshark feature (container-based Wireshark in the browser)")
    image: str = Field(
        "gns3/web-wireshark:latest", description="Docker image for the Web Wireshark containers")
    network_subnet: str = Field(
        "172.31.0.0/22",
        description="Docker network subnet for the Web Wireshark containers (change it if it conflicts "
                    "with your existing network)")
    memory: str = Field("2g", description='Memory limit per container (e.g. "512m", "2g")')
    cpus: float = Field(1.0, description="CPU cores per container (e.g. 1.0, 2.0)")
    pids_limit: int = Field(1000, description="Process limit per container")
    model_config = ConfigDict(validate_assignment=True, str_strip_whitespace=True)


class ServerProtocol(str, Enum):

    http = "http"
    https = "https"


class UbridgeControlTransport(str, Enum):

    # TCP control channel: -H host:port. ubridge now binds loopback by default,
    # so this is reachable only locally. Retained for backward compatibility.
    tcp = "tcp"
    # AF_UNIX control channel: -U socket_path, authenticated in-kernel via
    # SO_PEERCRED (ubridge accepts only its own UID). Recommended on Linux.
    unix = "unix"


class BuiltinSymbolTheme(str, Enum):

    classic = "Classic"
    affinity_square_blue = "Affinity-square-blue"
    affinity_square_red = "Affinity-square-red"
    affinity_square_gray = "Affinity-square-gray"
    affinity_circle_blue = "Affinity-circle-blue"
    affinity_circle_red = "Affinity-circle-red"
    affinity_circle_gray = "Affinity-circle-gray"


class ServerSettings(BaseModel):

    local: bool = Field(
        False,
        description="Local server mode, set by the --local command line argument (not meant to be set by hand)")
    enable_http_auth: bool = Field(True, description="Enable compute HTTP authentication")
    name: str = Field(
        f"{socket.gethostname()} (controller)",
        description="Server name, default is what is returned by socket.gethostname()")
    protocol: ServerProtocol = Field(
        ServerProtocol.http, description="Protocol used by the server: http or https")
    host: str = Field("0.0.0.0", description="IP address where the server listens for connections")
    port: int = Field(3080, gt=0, le=65535, description="HTTP port used to control the server")
    secrets_dir: Optional[DirectoryPath] = Field(
        None, description="Directory where secrets are stored (e.g. the JWT secret key)")
    certfile: Optional[FilePath] = Field(None, description="SSL certificate file, requires enable_ssl")
    certkey: Optional[FilePath] = Field(None, description="SSL key file, requires enable_ssl")
    enable_ssl: bool = Field(False, description="Enable SSL encryption")
    images_path: str = Field("~/GNS3/images", description="Path where binary images are stored")
    projects_path: str = Field("~/GNS3/projects", description="Path where user projects are stored")
    appliances_path: str = Field("~/GNS3/appliances", description="Path where custom user appliances are stored")
    symbols_path: str = Field("~/GNS3/symbols", description="Path where custom user symbols are stored")
    configs_path: str = Field("~/GNS3/configs", description="Path where custom user configs are stored")
    resources_path: Optional[str] = Field(
        None,
        description="Path where files like built-in appliances and Docker resources are stored "
                    "(defaults to the local user data directory)")
    default_symbol_theme: BuiltinSymbolTheme = Field(
        BuiltinSymbolTheme.affinity_square_blue,
        description='Default symbol theme, e.g. "Classic" or "Affinity-square-blue"')
    allow_raw_images: bool = Field(
        True, description="Allow raw images to be uploaded to the server")
    auto_discover_images: bool = Field(
        True, description="Automatically discover images in the images directory")
    report_errors: bool = Field(
        True, description="Automatically send crash reports to the GNS3 team")
    additional_images_paths: List[str] = Field(
        default_factory=list,
        description="Additional paths to look for images (semicolon-separated in the configuration file)")
    console_start_port_range: int = Field(
        5000, gt=0, le=65535, description="First console port of the range allocated to devices")
    console_end_port_range: int = Field(
        10000, gt=0, le=65535, description="Last console port of the range allocated to devices")
    vnc_console_start_port_range: int = Field(
        5900, ge=5900, le=65535, description="First VNC console port of the range allocated to devices")
    vnc_console_end_port_range: int = Field(
        10000, ge=5900, le=65535, description="Last VNC console port of the range allocated to devices")
    udp_start_port_range: int = Field(
        10000, gt=0, le=65535,
        description="First UDP port of the range allocated for inter-device communication (two ports per link)")
    udp_end_port_range: int = Field(
        30000, gt=0, le=65535,
        description="Last UDP port of the range allocated for inter-device communication (two ports per link)")
    ubridge_path: str = Field("ubridge", description="uBridge executable location, default: search in PATH")
    ubridge_control_transport: UbridgeControlTransport = Field(
        UbridgeControlTransport.unix,
        description='uBridge control channel transport: "unix" (AF_UNIX + SO_PEERCRED, recommended '
                    'on Linux) or "tcp" (loopback, kept for backward compatibility)')
    marker_listen_host: str = Field(
        "127.0.0.1",
        description="Marker (traffic-insight) UDP sink listen host: one listener per compute process "
                    "receives uBridge MARK signals from every uBridge on this host")
    marker_listen_port: int = Field(
        3070, ge=0, le=65535,
        description="Marker UDP sink listen port (0 lets the operating system choose a free port)")
    compute_username: str = Field(
        "gns3", description='Username for compute HTTP authentication, "gns3" is the default')
    compute_password: SecretStr = Field(
        SecretStr(""),
        description="Password for compute HTTP authentication, a randomly generated password is used if not set")
    allowed_interfaces: List[str] = Field(
        default_factory=list,
        description="Only allow these interfaces to be used by GNS3, for the Cloud node for example "
                    "(comma-separated; do not forget virbr0 for the NAT node to work)")
    default_nat_interface: Optional[str] = Field(
        None, description="Interface used by the NAT node, default is virbr0 on Linux (requires libvirt)")
    allow_remote_console: bool = Field(
        False,
        description="Allow console connections from remote machines "
                    "(console ports only accept local connections by default)")
    enable_builtin_templates: bool = Field(True, description="Enable the built-in templates")
    install_builtin_appliances: bool = Field(True, description="Install the built-in appliances")
    skills_repo_url: str = Field(
        "https://github.com/gns3/gns3-skills.git",
        description="Git repository URL for the external GNS3 Copilot skills "
                    "(injection skills, prompts and device skills)")
    skills_repo_branch: str = Field("main", description="Git branch of the skills repository")
    skills_auto_update: bool = Field(
        True, description="Automatically pull updates from the skills repository when reloading")
    mcp_enable_dns_rebinding_protection: bool = Field(
        False,
        description="Enable MCP transport DNS rebinding protection "
                    "(allowed hosts and origins must be configured)")
    mcp_allowed_hosts: list[str] = Field(
        default_factory=list,
        description='Allowed hosts for MCP connections, only "host:*" port wildcards are supported '
                    '(e.g. "127.0.0.1:*")')
    mcp_allowed_origins: list[str] = Field(
        default_factory=list,
        description='Allowed origins for MCP connections (e.g. "http://localhost:*")')

    model_config = ConfigDict(validate_assignment=True, str_strip_whitespace=True)

    @field_validator("mcp_allowed_hosts", mode="before")
    @classmethod
    def split_mcp_allowed_hosts(cls, v):
        if v and isinstance(v, str):
            return v.split(",")
        if not v:
            return list()
        return v

    @field_validator("mcp_allowed_origins", mode="before")
    @classmethod
    def split_mcp_allowed_origins(cls, v):
        if v and isinstance(v, str):
            return v.split(",")
        if not v:
            return list()
        return v

    @field_validator("additional_images_paths", mode="before")
    @classmethod
    def split_additional_images_paths(cls, v):
        if v and isinstance(v, str):
            return v.split(";")
        if not v:
            return list()
        return v

    @field_validator("allowed_interfaces", mode="before")
    @classmethod
    def split_allowed_interfaces(cls, v):
        if v and isinstance(v, str):
            return v.split(",")
        if not v:
            return list()
        return v

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
    WebWireshark: WebWiresharkSettings = WebWiresharkSettings()
