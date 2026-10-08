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

from enum import Enum
from typing import Annotated, List, Literal, Optional, Tuple
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..update import PartialUpdateModel
from .labels import Label


class LinkNode(BaseModel):
    """
    Link node data.
    """

    node_id: UUID
    adapter_number: int
    port_number: int
    label: Optional[Label] = None


class LinkNodeCreate(BaseModel):
    """
    Link node data for link creation.

    The port is given either by adapter_number and port_number, by port_name
    or by port set to "auto" (first free compatible port).
    """

    node_id: UUID
    adapter_number: Optional[int] = None
    port_number: Optional[int] = None
    port_name: Optional[str] = Field(None, description="Name of the port on the node")
    port: Optional[Literal["auto"]] = Field(None, description='Use "auto" to select the first free compatible port')
    label: Optional[Label] = None

    @model_validator(mode="after")
    def check_port_selector(self):
        numbered = self.adapter_number is not None or self.port_number is not None
        if numbered and (self.adapter_number is None or self.port_number is None):
            raise ValueError("adapter_number and port_number must be given together")
        forms = sum([numbered, self.port_name is not None, self.port is not None])
        if forms != 1:
            raise ValueError("exactly one of adapter_number and port_number, port_name or port must be given")
        return self


class LinkType(str, Enum):
    """
    Link type.
    """

    ethernet = "ethernet"
    serial = "serial"


class LinkStyle(BaseModel):
    color: Optional[str] = None
    width: Optional[int] = None
    type: Optional[int] = None
    link_type: Optional[str] = None
    bezier_curviness: Optional[int] = None
    flowchart_roundness: Optional[int] = None
    control_offset: Optional[Tuple[float, float]] = None


class LinkFilterType(str, Enum):
    """
    Packet filter type.
    """

    frequency_drop = "frequency_drop"
    packet_loss = "packet_loss"
    delay = "delay"
    corrupt = "corrupt"
    bpf = "bpf"


class LinkFilters(BaseModel):
    """
    Packet filters applied on a link. Each filter is an array of positional values.
    A filter set to an empty array or to its disabled value (0, 0 for delay, empty text for bpf) is not applied.
    """

    model_config = ConfigDict(extra="forbid")

    frequency_drop: Optional[List[Annotated[int, Field(ge=-1, le=32767)]]] = Field(
        None,
        max_length=1,
        description="[frequency]: -1 drops every packet, N > 0 drops every Nth packet, 0 disables the filter",
    )
    packet_loss: Optional[List[Annotated[int, Field(ge=0, le=100)]]] = Field(
        None,
        max_length=1,
        description="[chance]: percentage chance for a packet to be lost, 0 disables the filter",
    )
    delay: Optional[List[Annotated[int, Field(ge=0, le=32767)]]] = Field(
        None,
        max_length=2,
        description="[latency, jitter] in milliseconds: latency must be 1 to 32767 unless both values are 0, "
        "which disables the filter; jitter is 0 to 32767",
    )
    corrupt: Optional[List[Annotated[int, Field(ge=0, le=100)]]] = Field(
        None,
        max_length=1,
        description="[chance]: percentage chance for a packet to be corrupted, 0 disables the filter",
    )
    bpf: Optional[List[str]] = Field(
        None,
        max_length=1,
        description="[expressions]: BPF expressions, one per line, matching packets are dropped",
    )


class LinkFilterParameter(BaseModel):
    """
    Parameter of a packet filter.
    """

    name: str
    type: Literal["int", "text"]
    minimum: Optional[int] = None
    maximum: Optional[int] = None
    unit: Optional[str] = None


class LinkFilterDefinition(BaseModel):
    """
    Packet filter available on a link.
    """

    type: LinkFilterType
    name: str
    description: str
    parameters: List[LinkFilterParameter]


class LinkBase(BaseModel):
    """
    Link data.
    """

    nodes: Optional[List[LinkNode]] = Field(None, min_length=0, max_length=2)
    suspend: Optional[bool] = None
    link_style: Optional[LinkStyle] = None
    filters: Optional[LinkFilters] = None
    markers: Optional[dict] = Field(
        None, description="Traffic-insight markers on this link: name → {bpf, tag, enabled}"
    )
    show_filters_icon: Optional[bool] = Field(True, description="Show filters icon in Web UI")


class LinkCreate(LinkBase):
    link_id: UUID = Field(default_factory=uuid4)
    # LinkNodeCreate narrows the port selector, so it cannot be a LinkNode subclass
    nodes: List[LinkNodeCreate] = Field(..., min_length=2, max_length=2)  # type: ignore[assignment]


class LinkUpdate(PartialUpdateModel, LinkBase):
    pass


class Link(LinkBase):
    link_id: UUID
    project_id: Optional[UUID] = None
    link_type: Optional[LinkType] = None
    capturing: Optional[bool] = Field(None, description="Read only property. True if a capture running on the link")
    capture_file_name: Optional[str] = Field(
        None, description="Read only property. The name of the capture file if a capture is running"
    )
    capture_file_path: Optional[str] = Field(
        None, description="Read only property. The full path of the capture file if a capture is running"
    )
    capture_compute_id: Optional[str] = Field(
        None, description="Read only property. The compute identifier where a capture is running"
    )
    wireshark: Optional[bool] = Field(
        False, description="Read only property. True if a Web Wireshark session is active on the link"
    )


class UDPPortInfo(BaseModel):
    """
    UDP port information.
    """

    node_id: UUID
    lport: int
    rhost: str
    rport: int
    type: str


class EthernetPortInfo(BaseModel):
    """
    Ethernet port information.
    """

    node_id: UUID
    interface: str
    type: str


class LinkCapture(BaseModel):
    """
    Link capture data.
    """

    data_link_type: str = "DLT_EN10MB"
    capture_file_name: Optional[str] = None
    wireshark: bool = False


class MarkerCreate(BaseModel):
    """
    Body for attaching a traffic-insight marker to a link.

    ``name`` is optional at the controller REST layer (auto-generated when
    absent) but always set when the controller forwards to the compute.
    """

    name: Optional[str] = Field(
        None,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$",
        max_length=32,
        description="Unique marker name on the link. Auto-generated when absent.",
    )
    bpf: str
    tag: Optional[int] = None
    link_id: Optional[str] = None
    color: Optional[str] = Field(
        None,
        description="User-chosen hex color for this marker in the Web UI, e.g. '#ff5722'",
    )
    highlight_duration: Optional[int] = Field(
        None,
        ge=1,
        description=(
            "How long (milliseconds) the Web UI keeps this marker highlighted "
            "after a match. Omitted = use the UI default. Pure render hint — "
            "stored on the link, never sent to uBridge."
        ),
    )
    enabled: Optional[bool] = Field(
        None,
        description="Whether the marker is active. Defaults to true on creation.",
    )
    direction: Optional[str] = Field(
        None,
        pattern=r"^(tx|rx|both)$",
        description="Direction filter: 'tx' = capture node sending only, 'rx' = capture node receiving only, 'both' or null = both directions.",
    )
    capture_node_id: Optional[UUID] = Field(
        None,
        description=(
            "Which endpoint's uBridge hosts this marker (the 'observer'). "
            "tx/rx in `direction` are interpreted from this node's perspective. "
            "Must be one of the link's two endpoints and a marker-capable type. "
            "Omitted = server auto-picks (first started marker-capable endpoint)."
        ),
    )
    data_link_type: str = Field(
        "DLT_EN10MB",
        description=(
            "pcap link-layer type the marker's BPF compiles against and its "
            "capture file is written with (a uBridge `linktype` token). Defaults "
            "to DLT_EN10MB (Ethernet), which is omitted from the uBridge command. "
            "Only meaningful for serial links: set it to the matching serial DLT "
            "from the port's data_link_types — DLT_C_HDLC / DLT_PPP_SERIAL / "
            "DLT_FRELAY / DLT_ATM_RFC1483 — so the BPF offsets and pcap decode "
            "match the encapsulation configured in IOS. Create-only (changing it "
            "would invalidate the pcap)."
        ),
    )

    @field_validator("direction", mode="before")
    @classmethod
    def _both_to_none(cls, v):
        return None if v == "both" else v


class MarkerUpdate(BaseModel):
    """
    Body for updating a marker — partial update, every field optional.

    ``bpf`` is optional here (it is required on create). ``capture_node_id`` and
    ``name`` are create-only / path-driven and intentionally absent; an explicit
    ``direction: null`` clears the direction back to both (omitting keeps it).
    """

    bpf: Optional[str] = None
    tag: Optional[int] = None
    direction: Optional[str] = Field(
        None,
        pattern=r"^(tx|rx|both)$",
        description="Direction filter; 'both' or an explicit null clears it to both. Omit to keep.",
    )
    color: Optional[str] = Field(None, description="Hex color render hint, e.g. '#ff5722'")
    highlight_duration: Optional[int] = Field(None, ge=1, description="UI highlight duration in ms; null = UI default")
    enabled: Optional[bool] = Field(None, description="Toggle the marker on/off (instant).")

    @field_validator("direction", mode="before")
    @classmethod
    def _both_to_none(cls, v):
        return None if v == "both" else v


class MarkerDefinitionCreate(BaseModel):
    """
    Body for creating / updating a project-level marker definition.

    The definition is a template — when applied to a link the marker name is
    prefixed with ``global-`` (e.g. ``arp`` → ``global-arp``) so it can never
    collide with a per-link private marker.
    """

    name: Optional[str] = Field(
        None,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$",
        max_length=32,
        description="Unique definition name. Auto-generated when absent.",
    )
    bpf: str
    tag: Optional[int] = None
    color: Optional[str] = Field(
        None,
        description="User-chosen hex color for the marker in the Web UI, e.g. '#ff5722'",
    )
    highlight_duration: Optional[int] = Field(
        None,
        ge=1,
        description=(
            "How long (milliseconds) the Web UI keeps this marker highlighted "
            "after a match. Omitted = use the UI default. Pure render hint — "
            "stored with the definition, never sent to uBridge."
        ),
    )
    direction: Optional[str] = Field(
        None,
        pattern=r"^(tx|rx|both)$",
        description="Direction filter: 'tx' = capture node sending only, 'rx' = capture node receiving only, 'both' or null = both directions.",
    )
    data_link_type: str = Field(
        "DLT_EN10MB",
        description=(
            "pcap link-layer type for inherited markers on serial links (uBridge "
            "`linktype`). Defaults to DLT_EN10MB (Ethernet): the definition then "
            "applies only to Ethernet links and serial links are skipped. Set a "
            "serial DLT — DLT_C_HDLC / DLT_PPP_SERIAL / DLT_FRELAY / "
            "DLT_ATM_RFC1483 — to also cover serial links with that encapsulation; "
            "Ethernet links stay EN10MB regardless. Changing it re-fans-out."
        ),
    )

    @field_validator("direction", mode="before")
    @classmethod
    def _both_to_none(cls, v):
        return None if v == "both" else v
