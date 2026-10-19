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


from enum import StrEnum
from typing import List, Optional, Union

from pydantic import BaseModel, Field


class UDPNIOType(StrEnum):
    udp = "nio_udp"


class UDPNIO(BaseModel):
    """
    UDP Network Input/Output properties.
    """

    type: UDPNIOType
    lport: int = Field(..., gt=0, le=65535, description="Local port")
    rhost: str = Field(..., description="Remote host")
    rport: int = Field(..., gt=0, le=65535, description="Remote port")
    suspend: Optional[bool] = Field(None, description="Suspend the NIO")
    filters: Optional[dict] = Field(
        None,
        description="Packet filters (relay-supported types only: delay/packet_loss/corrupt/frequency_drop/bpf — "
        "the netem extensions and the quota mode need a kernel-datapath NIO)",
    )
    markers: Optional[dict] = Field(None, description="Traffic-insight markers")


class EthernetNIOType(StrEnum):
    ethernet = "nio_ethernet"


class EthernetNIO(BaseModel):
    """
    Generic Ethernet Network Input/Output properties.
    """

    type: EthernetNIOType
    ethernet_device: str = Field(..., description="Ethernet device name e.g. eth0")


class TAPNIOType(StrEnum):
    tap = "nio_tap"


class TAPNIO(BaseModel):
    """
    TAP Network Input/Output properties.
    """

    type: TAPNIOType
    tap_device: str = Field(..., description="TAP device name e.g. tap0")


class BridgeNIOType(StrEnum):
    bridge = "nio_bridge"


class BridgeVxlan(BaseModel):
    """
    VXLAN tunnel spec carried by a cross-compute BridgeNIO. Each endpoint
    creates one VXLAN device (uBridge ``vxlan create``) and enslaves it into
    the link's per-link kernel bridge next to the node's anchor; the kernel
    encapsulates/decapsulates the frames. The controller derives the name
    and VNI (utils.vxlan) and resolves the peer address, so both endpoints
    agree on the VNI without ever talking to each other.

    The device's MTU is derived by the kernel from the underlay interface
    the route to ``remote`` picks (MTU - 50 for the outer headers), which is
    what the link's bridge then reports as "what this fabric can carry".
    """

    name: str = Field(..., max_length=15, description="VXLAN device name on this endpoint's host (IFNAMSIZ-1)")
    vni: int = Field(..., ge=1, le=16777215, description="VXLAN network identifier, identical on both endpoints")
    remote: str = Field(..., description="Peer compute's address (unicast tunnel endpoint)")
    dstport: int = Field(..., ge=1, le=65535, description="UDP destination port, identical on both endpoints")


class BridgeNIO(BaseModel):
    """
    Kernel-datapath bridge Network Input/Output properties. The NIO tells the
    node to enslave its veth host end into the named kernel bridge instead of
    wiring a uBridge UDP relay. Impairment filters run on the veth host end:
    delay/packet_loss/corrupt and the netem extensions (rate, reorder,
    gemodel, duplicate, seed, limit, jitter distributions, loss correlation)
    as one tc netem qdisc, bpf as cls_bpf match-drop classifiers (needs a
    uBridge reporting cbpf), frequency_drop and quota as the eBPF stateful
    classifier (needs ebpf). Markers and packet capture are served by
    uBridge's AF_PACKET modules on the veth host end.

    ``bridge`` may be None: the anchor is then bridged by an Ethernet switch
    (its own kernel bridge absorbed it) and the node applies only carrier,
    markers and impairments — never bridge membership.
    """

    type: BridgeNIOType
    # Required-but-nullable: the NIO factories read nio_settings["bridge"],
    # and the create/update routes drop unset fields — an omitted key would
    # pass validation and then surface as a KeyError (500) during binding.
    bridge: Optional[str] = Field(
        ...,
        description="Kernel bridge name e.g. gns3a1b2c3d4e5; None when an Ethernet switch "
        "owns the anchor's bridge membership (absorbed link)",
    )
    vxlan: Optional[BridgeVxlan] = Field(
        None,
        description="Cross-compute tunnel: the VXLAN device this end creates and enslaves into the bridge "
        "next to the anchor; absent for same-host kernel links",
    )
    suspend: Optional[bool] = Field(None, description="Suspend the NIO")
    filters: Optional[dict] = Field(
        None,
        description="Packet filters served on the veth host end (netem surface + extensions via one tc netem qdisc, "
        "bpf via cls_bpf, frequency_drop/quota via the eBPF classifier)",
    )
    markers: Optional[dict] = Field(None, description="Traffic-insight markers (attached to the veth host end)")


class AnchorNIOType(StrEnum):
    anchor = "nio_anchor"


class AnchorNIO(BaseModel):
    """
    Anchor-absorbing Network Input/Output properties, for a node that owns a
    kernel bridge (the Ethernet switch): the named foreign interface — the
    peer's kernel-datapath anchor — is joined to the node's own bridge with
    the node's port settings applied to it. The mirror of BridgeNIO; filters,
    markers and capture ride the NIO and attach to the named anchor.
    """

    type: AnchorNIOType
    anchor: str = Field(..., description="Host interface to absorb e.g. gv00010203e0p0")
    peer: Optional[str] = Field(
        None,
        description="Switch-to-switch cascade: the other end of the veth pair this port is one end of. Present on "
        "exactly one side (the owner, which creates and destroys the pair); absent for an absorbed anchor",
    )
    suspend: Optional[bool] = Field(None, description="Suspend the NIO")
    filters: Optional[dict] = Field(
        None,
        description="Packet filters served on the absorbed anchor (netem surface + extensions via one tc netem "
        "qdisc, bpf via cls_bpf, frequency_drop/quota via the eBPF classifier)",
    )
    markers: Optional[dict] = Field(None, description="Traffic-insight markers (attached to the absorbed anchor)")


class MarkerToggle(BaseModel):
    """
    Body for the per-marker enable/disable toggle endpoint: flips a running
    uBridge marker filter with ``enable_packet_filter on|off`` (no NIO rebuild,
    so the pcap identity and emitted counter are preserved).
    """

    enabled: bool


class MarkerRebuild(BaseModel):
    """
    Body for the per-marker rebuild endpoint: re-install a single uBridge marker
    filter with new BPF/tag/direction via ``delete_packet_filter`` + add (NOT a
    bridge-wide reset), so sibling markers keep their pcaps open. The marker's
    own pcap is reopened by uBridge on re-add (new capture session for the new
    BPF), which is expected.
    """

    bpf: str
    tag: Optional[int] = None
    direction: Optional[str] = None
    enabled: bool = True
    link_id: str = ""


class BatchNIOEntry(BaseModel):
    """
    A single NIO binding to create as part of a project-wide batch.
    """

    node_id: str = Field(..., description="Node the NIO is attached to")
    adapter_number: int = Field(0, ge=0, description="Adapter number")
    port_number: int = Field(0, ge=0, description="Port number")
    nio: Union[UDPNIO, BridgeNIO, AnchorNIO] = Field(..., description="NIO settings")


class BatchNIOCreate(BaseModel):
    """
    Body for the project-wide batch NIO endpoint: create many NIO bindings in a
    single request (used during project open) to avoid one HTTP round-trip per
    NIO between controller and compute.
    """

    nios: List[BatchNIOEntry] = Field(..., description="NIO bindings to create")
