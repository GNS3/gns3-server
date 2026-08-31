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
from typing import List, Optional, Tuple
from enum import Enum
from uuid import UUID, uuid4

from .labels import Label


class LinkNode(BaseModel):
    """
    Link node data.
    """

    node_id: UUID
    adapter_number: int
    port_number: int
    label: Optional[Label] = None


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


class LinkBase(BaseModel):
    """
    Link data.
    """

    nodes: Optional[List[LinkNode]] = Field(None, min_length=0, max_length=2)
    suspend: Optional[bool] = None
    link_style: Optional[LinkStyle] = None
    filters: Optional[dict] = None
    markers: Optional[dict] = Field(
        None,
        description="Traffic-insight markers on this link: name → {bpf, tag, enabled}"
    )
    show_filters_icon: Optional[bool] = Field(
        True,
        description="Show filters icon in Web UI"
    )


class LinkCreate(LinkBase):

    link_id: UUID = Field(default_factory=uuid4)
    nodes: List[LinkNode] = Field(..., min_length=2, max_length=2)


class LinkUpdate(LinkBase):

    pass


class Link(LinkBase):

    link_id: UUID
    project_id: Optional[UUID] = None
    link_type: Optional[LinkType] = None
    capturing: Optional[bool] = Field(
        None,
        description="Read only property. True if a capture running on the link"
    )
    capture_file_name: Optional[str] = Field(
        None,
        description="Read only property. The name of the capture file if a capture is running"
    )
    capture_file_path: Optional[str] = Field(
        None,
        description="Read only property. The full path of the capture file if a capture is running"
    )
    capture_compute_id: Optional[str] = Field(
        None,
        description="Read only property. The compute identifier where a capture is running"
    )
    wireshark: Optional[bool] = Field(
        False,
        description="Read only property. True if a Web Wireshark session is active on the link"
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
        description='Unique marker name on the link. Auto-generated when absent.',
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
    highlight_duration: Optional[int] = Field(
        None, ge=1, description="UI highlight duration in ms; null = UI default"
    )
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


