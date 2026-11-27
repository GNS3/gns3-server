"""Configuration API schemas: capture, sets, assignments, wipe and archives."""

import base64
import binascii
from enum import StrEnum
from typing import Literal, get_args
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

ConsoleDeviceType = Literal[
    "cisco_ios_telnet",
    "cisco_nxos",
    "cisco_asa",
    "cisco_xr",
    "cisco_viptela",
    "mikrotik_routeros",
    "paloalto_panos",
    "arista_eos",
    "juniper_junos",
]


CONSOLE_DEVICE_TYPES = frozenset(get_args(ConsoleDeviceType))


def normalize_device_type(value):
    # Existing Netmiko metadata can name either the SSH or Telnet variant. The
    # capture worker always uses our private Telnet bridge to the serial stream.
    #
    # ASAv and Catalyst 8000v/CSR run the ASA and IOS-XE CLIs. Netmiko names
    # them cisco_asa(_ssh) and cisco_xe(_ssh/_telnet), so they reuse those
    # existing recipes instead of needing recipes of their own.
    aliases = {
        "cisco_ios": "cisco_ios_telnet",
        "cisco_xe": "cisco_ios_telnet",
        "cisco_xe_ssh": "cisco_ios_telnet",
        "cisco_xe_telnet": "cisco_ios_telnet",
        "cisco_nxos_telnet": "cisco_nxos",
        "cisco_asa_telnet": "cisco_asa",
        "cisco_asa_ssh": "cisco_asa",
        "cisco_xr_telnet": "cisco_xr",
        "mikrotik_routeros_telnet": "mikrotik_routeros",
        "cisco_viptela_telnet": "cisco_viptela",
        "paloalto_panos_telnet": "paloalto_panos",
        "arista_eos_telnet": "arista_eos",
        "juniper_junos_telnet": "juniper_junos",
    }
    return aliases.get(value, value) if isinstance(value, str) else value


# Docker entries that are a file of the container rather than console commands.
DOCKER_FILE_DEVICE_TYPES = ("linux_interfaces", "frr")


def compatible_device_type(node_type, device_type):
    """Whether a saved entry of ``device_type`` can belong to a node of ``node_type``."""
    if node_type == "vpcs":
        return device_type == "vpcs"
    if node_type in ("dynamips", "iou"):
        return device_type == "cisco_ios_telnet"
    if node_type == "qemu":
        return device_type in CONSOLE_DEVICE_TYPES
    return node_type == "docker" and (device_type in CONSOLE_DEVICE_TYPES or device_type in DOCKER_FILE_DEVICE_TYPES)


def docker_network_file(netmiko_device_type):
    """True when a plain Docker node's startup is its ``/etc/network/interfaces`` (no console recipe declared)."""
    return normalize_device_type(netmiko_device_type) in (None, "", "linux", "linux_telnet")


MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_EXPORT_BYTES = 32 * 1024 * 1024
MAX_CREDENTIAL_CHARACTERS = 256


def is_single_line(value: str) -> bool:
    """A bounded value with no control characters: safe to type into a console."""
    return len(value) <= MAX_CREDENTIAL_CHARACTERS and not any(ord(char) < 32 or ord(char) == 127 for char in value)


def clean_set_name(value: str) -> str:
    """The trimmed name of a configuration set; raises ValueError when blank or holding control characters."""
    value = value.strip()
    if not value or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("Invalid set name")
    return value


class ContractModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", ser_json_bytes="base64", val_json_bytes="base64")


class Engine(StrEnum):
    dynamips = "dynamips"
    iou = "iou"
    qemu = "qemu"
    docker = "docker"
    vpcs = "vpcs"


# The node types the startup configuration feature supports.
STARTUP_ENGINES = frozenset(Engine)


class Source(StrEnum):
    saved_startup = "saved_startup"
    saved_files = "saved_files"
    running = "running"
    save_then_capture = "save_then_capture"


class ConsoleCredentials(ContractModel):
    username: str = Field(default="", max_length=MAX_CREDENTIAL_CHARACTERS, repr=False)
    password: SecretStr = Field(default_factory=lambda: SecretStr(""), repr=False)
    enable_secret: SecretStr = Field(default_factory=lambda: SecretStr(""), repr=False)

    @field_validator("username", "password", "enable_secret")
    @classmethod
    def single_line(cls, value):
        if not is_single_line(value.get_secret_value() if isinstance(value, SecretStr) else value):
            raise ValueError("Expected a bounded single-line credential")
        return value

    def request_data(self):
        return {
            "username": self.username,
            "password": self.password.get_secret_value(),
            "enable_secret": self.enable_secret.get_secret_value(),
        }


class ExportOptions(ContractModel):
    source: Source | None = None
    device_type: ConsoleDeviceType | None = None
    credentials: ConsoleCredentials | None = Field(default=None, repr=False)
    backup: bool = Field(default=False, strict=True)

    @field_validator("device_type", mode="before")
    @classmethod
    def console_driver(cls, value):
        return normalize_device_type(value)

    def request_data(self):
        data = self.model_dump(mode="json", exclude={"credentials"})
        if self.credentials is not None:
            data["credentials"] = self.credentials.request_data()
        return data


class ExportFile(ContractModel):
    filename: str = Field(min_length=1, max_length=255)
    content: bytes = Field(strict=True, min_length=1, max_length=MAX_FILE_BYTES, repr=False)

    @field_validator("filename")
    @classmethod
    def safe_filename(cls, value):
        if any(part in ("", ".", "..") for part in value.split("/")) or any(
            ord(char) < 32 or ord(char) == 127 or char in '\\:*?"<>|' for char in value
        ):
            raise ValueError("Expected a relative configuration filename")
        return value


class ExportResult(ContractModel):
    project_id: UUID
    node_id: UUID
    engine: Engine
    source: Source
    files: tuple[ExportFile, ...] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def bounded_files(self):
        names = [file.filename.casefold() for file in self.files]
        if len(set(names)) != len(names) or sum(len(file.content) for file in self.files) > MAX_EXPORT_BYTES:
            raise ValueError("Duplicate filenames or oversized export")
        return self


DEFAULT_SET = UUID(int=0)


StartupDeviceType = ConsoleDeviceType | Literal["linux_interfaces", "frr", "vpcs"]


class StartupEntry(ContractModel):
    device_type: StartupDeviceType
    content: str = Field(default="", max_length=MAX_FILE_BYTES, repr=False)
    enabled: bool = Field(default=False, strict=True)

    @field_validator("device_type", mode="before")
    @classmethod
    def driver(cls, value):
        return normalize_device_type(value)

    @field_validator("content")
    @classmethod
    def bounded_content(cls, value):
        if len(value.encode("utf-8")) > MAX_FILE_BYTES or any(ord(c) < 32 and c not in "\r\n\t" for c in value):
            raise ValueError("Invalid configuration content")
        return value


class ApplyOptions(StartupEntry):
    content: str = Field(min_length=1, max_length=MAX_FILE_BYTES, repr=False)
    credentials: ConsoleCredentials = Field(default_factory=ConsoleCredentials, repr=False)
    wait_ready: bool = Field(default=False, strict=True)
    running: bool = Field(default=False, strict=True)


class MediaRequest(ContractModel):
    """Stage (or, with no content, withdraw) native boot media for the next boot."""

    profile: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9-]*$")
    content: str | None = Field(default=None, max_length=MAX_FILE_BYTES, repr=False)
    # Saved console password for profiles that provision the admin account (never echoed back).
    admin_password: SecretStr | None = Field(default=None, max_length=256, repr=False)

    @field_validator("content")
    @classmethod
    def bounded_content(cls, value):
        if value is not None:
            StartupEntry.bounded_content(value)
        return value


class ConfigurationSet(ContractModel):
    id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1, max_length=80)
    nodes: dict[UUID, StartupEntry] = Field(default_factory=dict, max_length=1000)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        return clean_set_name(value)


class StartupDocument(ContractModel):
    version: int = Field(default=1, ge=1, le=1)
    revision: int = Field(default=0, ge=0)
    selected: UUID = DEFAULT_SET
    sets: tuple[ConfigurationSet, ...] = Field(
        default_factory=lambda: (ConfigurationSet(id=DEFAULT_SET, name="Default"),), min_length=1, max_length=32
    )

    @model_validator(mode="after")
    def valid_sets(self):
        ids = [s.id for s in self.sets]
        names = [s.name.casefold() for s in self.sets]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate_configuration_set_ids")
        if len(set(names)) != len(names):
            raise ValueError("duplicate_configuration_set_names")
        if self.selected not in ids:
            raise ValueError("selected_configuration_set_not_found")
        return self


class CaptureRequest(ContractModel):
    set_id: UUID
    node_ids: tuple[UUID, ...] = Field(default=(), max_length=1000)


class WipeRequest(ContractModel):
    """Wipe an explicit node list, or every supported node with ``all=true``.

    An empty body never means "everything": the caller must choose one form.
    """

    # "Wipe all" names every node it confirmed, so this is above any real project size.
    node_ids: tuple[UUID, ...] = Field(default=(), max_length=10000)
    all: bool = False

    @model_validator(mode="after")
    def require_explicit_selection(self):
        if self.all == bool(self.node_ids):
            raise ValueError("configuration_wipe_selection_required")
        return self


class ApplyRequest(ContractModel):
    set_id: UUID
    revision: int = Field(ge=0)


class Selection(ContractModel):
    kind: Literal["none", "set"] = "none"
    set_id: UUID | None = None

    @model_validator(mode="after")
    def valid_reference(self):
        if (self.set_id is not None) != (self.kind == "set"):
            raise ValueError("Expected exactly the reference selected by kind")
        return self


class BulkSelectionUpdate(ContractModel):
    """One startup choice for several nodes: a set, or none (the device boots with its image defaults)."""

    revision: int = Field(ge=0)
    node_ids: tuple[UUID, ...] = Field(min_length=1, max_length=1000)
    selection: Selection


class StartupConfigurationState(StartupDocument):
    """Editor transport; assignments retain their own persisted revision."""

    selection_revision: int | None = Field(default=None, ge=0)
    selections: dict[UUID, Selection] | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def guarded_selections(self):
        if (self.selections is None) != (self.selection_revision is None):
            raise ValueError("Startup selections require their revision")
        return self


class SetName(ContractModel):
    name: str = Field(min_length=1, max_length=80)
    revision: int = Field(ge=0)
    select: bool = Field(default=False, strict=True)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        return clean_set_name(value)


class RuntimeState(ContractModel):
    version: Literal[1] = 1
    generation: int = Field(ge=0, strict=True)
    state: Literal["legacy_existing", "resetting", "preparing", "clean", "prepared", "initialized"]


class ArchiveNode(ContractModel):
    node_id: UUID
    node_name: str = Field(default="", max_length=128)
    node_type: str = Field(default="", max_length=40)
    device_type: str = Field(min_length=1, max_length=64)
    enabled: bool = Field(default=False, strict=True)
    # An empty entry is a legal set member: it keeps membership metadata
    # without transferring content.
    text: str = Field(default="", max_length=MAX_FILE_BYTES, repr=False)
    # Version 2: the archive member that holds the text (absent for an empty entry). Version 1 keeps it inline.
    file: str | None = Field(default=None, max_length=200, pattern=r"^nodes/[^/\\]+$")


# A base64 JSON request stays below the 34 MiB configuration route budget.
MAX_ARCHIVE_BYTES = 24 * 1024 * 1024


class ArchiveManifest(ContractModel):
    """Archive metadata. Names and node labels are hints; node IDs are canonical."""

    # 1: the texts inline in the manifest. 2: one readable file per node.
    version: Literal[2] = 2
    kind: Literal["gns3-startup-configuration-set"] = "gns3-startup-configuration-set"
    created_at: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)$")
    source_project_id: UUID | None = None
    source_set_id: UUID | None = None
    set_name: str = Field(min_length=1, max_length=80)
    nodes: tuple[ArchiveNode, ...] = Field(default=(), max_length=1000)

    @field_validator("set_name")
    @classmethod
    def clean_archive_set_name(cls, value):
        return clean_set_name(value)

    @model_validator(mode="after")
    def unique_nodes(self):
        if len({node.node_id for node in self.nodes}) != len(self.nodes):
            raise ValueError("duplicate_configuration_archive_nodes")
        return self


class ArchiveImport(ContractModel):
    archive: str = Field(min_length=1, max_length=4 * ((MAX_ARCHIVE_BYTES + 2) // 3), repr=False)
    name: str | None = Field(default=None, max_length=80)
    nodes: dict[UUID, UUID] = Field(default_factory=dict, max_length=1000)
    select: bool = Field(default=False, strict=True)
    assign_nodes: bool = Field(default=False, strict=True)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        return value if value is None else clean_set_name(value)

    def payload(self):
        # Standard base64 transport. Imported lazily:
        # schemas load before the service package during startup.
        from gns3server.services.configurations.shared.errors import ConfigurationError

        try:
            return base64.b64decode(self.archive, altchars=b"-_", validate=True)
        except (ValueError, binascii.Error):
            raise ConfigurationError("invalid_configuration_archive") from None
