#!/usr/bin/env python
#
# Copyright (C) 2025 GNS3 Technologies Inc.
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

"""
Controller-layer tests for the traffic-insight marker feature:

* UDPLink.start_marker / stop_marker / update_marker — storage, guards,
  inheritance bypass, and partial-update preservation of render hints.
* Project.create/update/delete_marker_definition — fan-out, sync, cleanup.
* Project.apply_defs_to_new_link and the markers aggregation property.
"""

import uuid

import pytest
from unittest.mock import MagicMock, patch
from contextlib import ExitStack

from tests.utils import AsyncioMagicMock

from gns3server.controller.udp_link import UDPLink
from gns3server.controller.ports.ethernet_port import EthernetPort
from gns3server.controller.ports.serial_port import SerialPort
from gns3server.controller.node import Node
from gns3server.controller.controller_error import ControllerError, ControllerNotFoundError


def _valid_bpf():
    """Bypass tcpdump-based BPF validation so tests don't depend on tcpdump.

    Patches both namespaces that import ``validate_bpf_syntax`` by name: the
    per-link ``udp_link`` (private marker create/update) and the project layer
    (definition create/update/load), which is now the single validation point
    for inherited copies.
    """
    stack = ExitStack()
    for target in (
        "gns3server.controller.udp_link.validate_bpf_syntax",
        "gns3server.controller.project.validate_bpf_syntax",
    ):
        stack.enter_context(patch(target, return_value={"valid": True, "error": None}))
    return stack


async def _make_link(project, port_cls=EthernetPort, node_types=("vpcs", "vpcs")):
    """Build a created UDPLink between two nodes on a mocked compute.

    ``port_cls`` defaults to EthernetPort; pass SerialPort for a serial link
    (the link's link_type follows the port). ``node_types`` overrides the
    endpoint node types (e.g. a switch-to-switch link).
    """

    compute = MagicMock()
    compute.id = "local"
    compute.host = "example.com"

    node1 = Node(project, compute, "n1", node_type=node_types[0])
    node1._ports = [port_cls("E0", 0, 0, 0)]
    node2 = Node(project, compute, "n2", node_type=node_types[1])
    node2._ports = [port_cls("E0", 0, 0, 1)]

    async def subnet(_other):
        return ("192.168.1.1", "192.168.1.2")

    async def udp_cb(path, data={}, **kwargs):
        response = MagicMock()
        response.json = {"udp_port": 1234}
        return response

    compute.get_ip_on_same_subnet.side_effect = subnet
    compute.post.side_effect = udp_cb
    # start_marker / update_marker push via node.put -> compute.put; make it awaitable.
    compute.put = AsyncioMagicMock()
    compute.delete = AsyncioMagicMock()

    link = UDPLink(project)
    await link.add_node(node1, 0, 0)
    await link.add_node(node2, 0, 1)
    # Register with the project so definition fan-out (which iterates _links) reaches it.
    project._links[link.id] = link
    return link


# ---------------------------------------------------------------------------
# UDPLink.start_marker
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_start_marker_stores_entry(project):

    with _valid_bpf():
        link = await _make_link(project)
        await link.start_marker("icmp", "icmp", tag=7, color="#ff5722", highlight_duration=800)

    entry = link.markers["icmp"]
    assert entry["bpf"] == "icmp"
    assert entry["tag"] == 7
    assert entry["color"] == "#ff5722"
    assert entry["highlight_duration"] == 800
    assert entry["enabled"] is True
    assert entry["capture_node_id"] in {n["node"].id for n in link._nodes}


@pytest.mark.asyncio
async def test_start_marker_on_ethernet_switch_link(project):
    """A switch-to-switch link can host a marker: the brctl Ethernet switch
    runs a per-port uBridge relay the `mark` filter attaches to."""

    with _valid_bpf():
        link = await _make_link(project, node_types=("ethernet_switch", "ethernet_switch"))
        await link.start_marker("icmp", "icmp")

    entry = link.markers["icmp"]
    switch_ids = {n["node"].id for n in link._nodes}
    assert entry["capture_node_id"] in switch_ids
    # the marker rides exactly one side's NIO and is pushed via update()
    carrying = [d for d in link._link_data if "icmp" in d["markers"]]
    assert len(carrying) == 1
    assert "inherited_from" not in entry


@pytest.mark.asyncio
async def test_start_marker_stores_data_link_type(project):
    # data_link_type is stored on the marker and flows into the per-node spec
    # (the compute-side source for the uBridge `linktype` keyword). Serial-only;
    # defaults to DLT_EN10MB when omitted (Ethernet → linktype omitted).
    with _valid_bpf():
        link = await _make_link(project)
        await link.start_marker("ospf", "ospf", data_link_type="DLT_C_HDLC")

    assert link.markers["ospf"]["data_link_type"] == "DLT_C_HDLC"
    capture_id = link.markers["ospf"]["capture_node_id"]
    capture_side = next(n for n in link._nodes if n["node"].id == capture_id)
    assert link._markers_for_node(capture_side["node"])["ospf"]["data_link_type"] == "DLT_C_HDLC"

    # Default when omitted = Ethernet.
    with _valid_bpf():
        link2 = await _make_link(project)
        await link2.start_marker("icmp", "icmp")
    cid = link2.markers["icmp"]["capture_node_id"]
    cside = next(n for n in link2._nodes if n["node"].id == cid)
    assert link2._markers_for_node(cside["node"])["icmp"]["data_link_type"] == "DLT_EN10MB"


@pytest.mark.asyncio
async def test_start_marker_pins_capture_node(project):
    # Auto-pick would choose node1 (first endpoint); pin to node2 explicitly.
    with _valid_bpf():
        link = await _make_link(project)
        chosen = link._nodes[1]["node"].id
        auto = link._nodes[0]["node"].id
        assert chosen != auto  # sanity: the pin must actually mean something
        await link.start_marker("icmp", "icmp", capture_node_id=chosen)

    assert link.markers["icmp"]["capture_node_id"] == chosen


@pytest.mark.asyncio
async def test_start_marker_rejects_non_endpoint_capture_node(project):

    with _valid_bpf():
        link = await _make_link(project)
        with pytest.raises(ControllerNotFoundError):
            await link.start_marker("icmp", "icmp", capture_node_id="11111111-2222-3333-4444-555555555555")


@pytest.mark.asyncio
async def test_start_marker_capture_node_ignored_for_inherited(project):
    # Definitions are link-agnostic: an inherited marker must auto-pick even
    # if a capture_node_id leaks through, never trusting the caller's pin.
    with _valid_bpf():
        link = await _make_link(project)
        leaked = link._nodes[1]["node"].id
        await link.start_marker("m", "icmp", capture_node_id=leaked, inherited_from="arp")

    assert link.markers["m"]["capture_node_id"] == link._nodes[0]["node"].id


@pytest.mark.asyncio
async def test_start_marker_rejects_duplicate(project):

    with _valid_bpf():
        link = await _make_link(project)
        await link.start_marker("icmp", "icmp")
        with pytest.raises(ControllerError):
            await link.start_marker("icmp", "tcp")


@pytest.mark.asyncio
async def test_start_marker_rejects_invalid_bpf(project):

    link = await _make_link(project)
    with patch("gns3server.controller.udp_link.validate_bpf_syntax",
               return_value={"valid": False, "error": "bad expression"}):
        with pytest.raises(ControllerError):
            await link.start_marker("bad", "not a real bpf")


# ---------------------------------------------------------------------------
# UDPLink.stop_marker
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stop_marker_removes(project):

    with _valid_bpf():
        link = await _make_link(project)
        await link.start_marker("icmp", "icmp")
        assert "icmp" in link.markers
        await link.stop_marker("icmp")
    assert "icmp" not in link.markers


@pytest.mark.asyncio
async def test_stop_marker_rejects_inherited(project):

    with _valid_bpf():
        link = await _make_link(project)
        await link.inherit_marker("arp", {"bpf": "arp"})
        # Per-link delete of an inherited marker must be refused (use the def API).
        with pytest.raises(ControllerError):
            await link.stop_marker("global-arp")
    assert "global-arp" in link.markers  # still present


@pytest.mark.asyncio
async def test_stop_marker_inherited_bypass(project):
    """The def-delete path passes inherited=True to remove inherited copies."""

    with _valid_bpf():
        link = await _make_link(project)
        await link.inherit_marker("arp", {"bpf": "arp"})
        await link.stop_marker("global-arp", inherited=True)
    assert "global-arp" not in link.markers


@pytest.mark.asyncio
async def test_stop_marker_unknown_raises(project):

    link = await _make_link(project)
    with pytest.raises(ControllerNotFoundError):
        await link.stop_marker("nope")


# ---------------------------------------------------------------------------
# UDPLink.update_marker
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_marker_preserves_render_hints(project):
    """A partial update (bpf only) must not reset color/highlight_duration/tag."""

    with _valid_bpf():
        link = await _make_link(project)
        await link.start_marker("m", "icmp", tag=1, color="#ff5722", highlight_duration=800)
        await link.update_marker("m", bpf="tcp port 80")

    entry = link.markers["m"]
    assert entry["bpf"] == "tcp port 80"
    assert entry["color"] == "#ff5722"          # preserved
    assert entry["highlight_duration"] == 800   # preserved
    assert entry["tag"] == 1                    # preserved


@pytest.mark.asyncio
async def test_update_marker_changes_fields(project):

    with _valid_bpf():
        link = await _make_link(project)
        await link.start_marker("m", "icmp", highlight_duration=800)
        await link.update_marker("m", highlight_duration=1500, enabled=False, tag=9)

    entry = link.markers["m"]
    assert entry["highlight_duration"] == 1500
    assert entry["enabled"] is False
    assert entry["tag"] == 9


@pytest.mark.asyncio
async def test_update_marker_rejects_inherited(project):

    with _valid_bpf():
        link = await _make_link(project)
        await link.inherit_marker("arp", {"bpf": "arp"})
        with pytest.raises(ControllerError):
            await link.update_marker("global-arp", bpf="tcp")


@pytest.mark.asyncio
async def test_update_marker_inherited_bypass(project):
    """The def-sync path passes inherited=True to update inherited copies."""

    with _valid_bpf():
        link = await _make_link(project)
        await link.inherit_marker("arp", {"bpf": "arp", "highlight_duration": 500})
        await link.update_marker("global-arp", highlight_duration=1200, inherited=True)
    assert link.markers["global-arp"]["highlight_duration"] == 1200


# ---------------------------------------------------------------------------
# Link.inherit_marker + persistence
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_inherit_marker_creates_global_copy(project):

    with _valid_bpf():
        link = await _make_link(project)
        await link.inherit_marker("arp", {"bpf": "arp", "tag": 3, "color": "#111", "highlight_duration": 400})

    entry = link.markers["global-arp"]
    assert entry["bpf"] == "arp"
    assert entry["tag"] == 3
    assert entry["color"] == "#111"
    assert entry["highlight_duration"] == 400
    assert entry["inherited_from"] == "arp"


@pytest.mark.asyncio
async def test_persist_markers_excludes_inherited(project):
    """Inherited markers are re-created from definitions on load, never persisted."""

    with _valid_bpf():
        link = await _make_link(project)
        await link.start_marker("private", "icmp", highlight_duration=800)
        await link.inherit_marker("arp", {"bpf": "arp"})

    persisted = link._persist_markers()
    assert set(persisted.keys()) == {"private"}
    assert "global-arp" not in persisted


@pytest.mark.asyncio
async def test_load_marker_preserves_direction_and_highlight_duration(project):
    """Regression: a private marker's direction + highlight_duration must survive
    a close/reopen round-trip through the topology file.

    _create_link_from_topology_data previously restored only bpf/tag/enabled/
    color/capture_node_id, silently dropping direction (→ reverted to "both")
    and highlight_duration.
    """
    compute = MagicMock()
    compute.id = "local"
    compute.host = "example.com"

    async def subnet(_other):
        return ("192.168.1.1", "192.168.1.2")

    async def udp_cb(path, data={}, **kwargs):
        response = MagicMock()
        response.json = {"udp_port": 1234}
        return response

    compute.get_ip_on_same_subnet.side_effect = subnet
    compute.post.side_effect = udp_cb
    # Attaching the 2nd node auto-creates the link (NIO round-trips).
    compute.put = AsyncioMagicMock()
    compute.delete = AsyncioMagicMock()

    node1 = Node(project, compute, "n1", node_type="vpcs")
    node1._ports = [EthernetPort("E0", 0, 0, 0)]
    node2 = Node(project, compute, "n2", node_type="vpcs")
    node2._ports = [EthernetPort("E0", 0, 0, 1)]
    # _create_link_from_topology_data resolves nodes via project.get_node().
    project._nodes[node1.id] = node1
    project._nodes[node2.id] = node2

    capture_node_id = str(uuid.uuid4())
    link_id = str(uuid.uuid4())
    link_data = {
        "link_id": link_id,
        "nodes": [
            {"node_id": node1.id, "adapter_number": 0, "port_number": 0, "label": "a"},
            {"node_id": node2.id, "adapter_number": 0, "port_number": 1, "label": "b"},
        ],
        "markers": {
            "icmp": {
                "bpf": "icmp",
                "direction": "rx",
                "highlight_duration": 800,
                "tag": 7,
                "color": "#ff5722",
                "enabled": True,
                "capture_node_id": capture_node_id,
            }
        },
    }
    with patch(
        "gns3server.controller.project.validate_bpf_syntax",
        return_value={"valid": True, "error": None},
    ):
        await project._create_link_from_topology_data(link_data)

    # The link survives (2 attached nodes); pull it back from the project.
    link = project._links[link_id]
    entry = link._markers["icmp"]
    assert entry["direction"] == "rx"           # dropped before the fix
    assert entry["highlight_duration"] == 800   # dropped before the fix
    assert entry["tag"] == 7
    assert entry["color"] == "#ff5722"
    assert entry["capture_node_id"] == capture_node_id
    assert entry["enabled"] is True


@pytest.mark.asyncio
async def test_asdict_markers_runtime_vs_dump(project):
    """Runtime asdict exposes all markers; topology dump drops inherited ones."""

    with _valid_bpf():
        link = await _make_link(project)
        await link.start_marker("private", "icmp")
        await link.inherit_marker("arp", {"bpf": "arp"})

    runtime = link.asdict()
    assert set(runtime["markers"].keys()) == {"private", "global-arp"}
    dumped = link.asdict(topology_dump=True)
    assert set(dumped["markers"].keys()) == {"private"}


# ---------------------------------------------------------------------------
# Project-level marker definitions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_marker_definition_fans_out(project):

    with _valid_bpf():
        link1 = await _make_link(project)
        link2 = await _make_link(project)
        await project.create_marker_definition("arp", "arp", tag=5, highlight_duration=1200)

    for link in (link1, link2):
        entry = link.markers["global-arp"]
        assert entry["inherited_from"] == "arp"
        assert entry["bpf"] == "arp"
        assert entry["highlight_duration"] == 1200
    assert project.marker_definitions["arp"]["highlight_duration"] == 1200


@pytest.mark.asyncio
async def test_definition_fans_out_over_many_links(project):
    # The fan-out is concurrent (bounded) — a large topology must not serialize
    # N compute round-trips — but behaviorally every link still receives the
    # marker and per-link failures stay isolated.
    with _valid_bpf():
        links = [await _make_link(project) for _ in range(20)]
        await project.create_marker_definition("arp", "arp", highlight_duration=700)

    for link in links:
        assert link.markers["global-arp"]["highlight_duration"] == 700
        assert link.markers["global-arp"]["inherited_from"] == "arp"
    assert project.marker_definitions["arp"]["highlight_duration"] == 700


@pytest.mark.asyncio
async def test_update_marker_definition_syncs(project):

    with _valid_bpf():
        link1 = await _make_link(project)
        link2 = await _make_link(project)
        await project.create_marker_definition("arp", "arp", highlight_duration=500)
        await project.update_marker_definition("arp", highlight_duration=1500, bpf="arp or rarp")

    for link in (link1, link2):
        assert link.markers["global-arp"]["highlight_duration"] == 1500
        assert link.markers["global-arp"]["bpf"] == "arp or rarp"
    assert project.marker_definitions["arp"]["highlight_duration"] == 1500


@pytest.mark.asyncio
async def test_definition_serial_dlt_fans_out_to_serial_link(project):
    # A definition with a serial data_link_type covers serial links with that
    # encapsulation AND ethernet links with EN10MB (one definition, mixed topo).
    with _valid_bpf():
        serial_link = await _make_link(project, SerialPort)
        eth_link = await _make_link(project)
        await project.create_marker_definition("ospf", "ospf", data_link_type="DLT_C_HDLC")

    assert serial_link._link_type == "serial"
    assert serial_link.markers["global-ospf"]["data_link_type"] == "DLT_C_HDLC"
    assert eth_link.markers["global-ospf"]["data_link_type"] == "DLT_EN10MB"


@pytest.mark.asyncio
async def test_definition_default_skips_serial_link(project):
    # Default (EN10MB) definition is Ethernet-only: serial links are skipped
    # (an EN10MB pcap on a serial link would be undecodable).
    with _valid_bpf():
        serial_link = await _make_link(project, SerialPort)
        eth_link = await _make_link(project)
        await project.create_marker_definition("arp", "arp")

    assert "global-arp" not in serial_link.markers
    assert "global-arp" in eth_link.markers


@pytest.mark.asyncio
async def test_update_definition_data_link_type_refans_out(project):
    # Changing data_link_type re-evaluates which links host the marker: a serial
    # link skipped under the default gains the marker once a WAN DLT is chosen.
    with _valid_bpf():
        serial_link = await _make_link(project, SerialPort)
        await project.create_marker_definition("ospf", "ospf")
        assert "global-ospf" not in serial_link.markers  # default → serial skipped
        await project.update_marker_definition("ospf", data_link_type="DLT_PPP_SERIAL")

    assert serial_link.markers["global-ospf"]["data_link_type"] == "DLT_PPP_SERIAL"


@pytest.mark.asyncio
async def test_delete_marker_definition_clears(project):
    """Regression: deleting a def must remove inherited copies from every link."""

    with _valid_bpf():
        link1 = await _make_link(project)
        link2 = await _make_link(project)
        await project.create_marker_definition("arp", "arp")
        assert "global-arp" in link1.markers
        await project.delete_marker_definition("arp")

    assert "global-arp" not in link1.markers
    assert "global-arp" not in link2.markers
    assert "arp" not in project.marker_definitions


@pytest.mark.asyncio
async def test_apply_defs_to_new_link(project):
    """A link created after a definition exists inherits it automatically."""

    with _valid_bpf():
        await project.create_marker_definition("arp", "arp")
        new_link = await _make_link(project)

    assert "global-arp" in new_link.markers
    assert new_link.markers["global-arp"]["inherited_from"] == "arp"


@pytest.mark.asyncio
async def test_create_marker_definition_validates_bpf_once(project):
    # A definition validates its BPF once (project layer); the inherited fan-out
    # to every link must NOT re-validate — no tcpdump subprocess per link.
    with patch("gns3server.controller.project.validate_bpf_syntax",
               return_value={"valid": True, "error": None}) as proj_val, \
         patch("gns3server.controller.udp_link.validate_bpf_syntax",
               return_value={"valid": True, "error": None}) as link_val:
        await _make_link(project)
        await _make_link(project)
        await project.create_marker_definition("arp", "arp")

    assert proj_val.call_count == 1          # validated once at the def layer
    assert link_val.call_count == 0          # fan-out skipped per-link validation


@pytest.mark.asyncio
async def test_create_marker_definition_rejects_invalid_bpf(project):

    with patch("gns3server.controller.project.validate_bpf_syntax",
               return_value={"valid": False, "error": "syntax error"}):
        with pytest.raises(ControllerError):
            await project.create_marker_definition("arp", "not a real bpf")
    assert "arp" not in project.marker_definitions


@pytest.mark.asyncio
async def test_update_marker_definition_skips_per_link_validation(project):
    # Updating a def's BPF validates once more (project); the per-link sync
    # (update_marker with inherited=True) must NOT re-validate.
    with patch("gns3server.controller.project.validate_bpf_syntax",
               return_value={"valid": True, "error": None}) as proj_val, \
         patch("gns3server.controller.udp_link.validate_bpf_syntax",
               return_value={"valid": True, "error": None}) as link_val:
        await _make_link(project)
        await _make_link(project)
        await project.create_marker_definition("arp", "arp")
        await project.update_marker_definition("arp", bpf="arp or rarp")

    assert proj_val.call_count == 2          # once on create, once on update
    assert link_val.call_count == 0          # sync skipped per-link validation


@pytest.mark.asyncio
async def test_start_marker_skips_validation_for_inherited(project):
    # An inherited marker rides an already-validated definition BPF, so
    # start_marker must not call validate_bpf_syntax.
    with patch("gns3server.controller.udp_link.validate_bpf_syntax",
               return_value={"valid": True, "error": None}) as link_val:
        link = await _make_link(project)
        await link.inherit_marker("arp", {"bpf": "arp"})

    assert link_val.call_count == 0
    assert link.markers["global-arp"]["bpf"] == "arp"


@pytest.mark.asyncio
async def test_start_marker_validates_for_private(project):
    # A private (non-inherited) marker still validates inline.
    with patch("gns3server.controller.udp_link.validate_bpf_syntax",
               return_value={"valid": True, "error": None}) as link_val:
        link = await _make_link(project)
        await link.start_marker("icmp", "icmp")

    assert link_val.call_count == 1


@pytest.mark.asyncio
async def test_markers_aggregation(project):

    with _valid_bpf():
        link = await _make_link(project)
        await link.start_marker("icmp", "icmp", highlight_duration=800)

    agg = project.markers
    key = f"{link.id}/icmp"
    assert key in agg
    assert agg[key]["bpf"] == "icmp"
    assert agg[key]["highlight_duration"] == 800
    assert agg[key]["link_id"] == link.id
    assert agg[key]["node_id"] == agg[key]["capture_node_id"]


# ---------------------------------------------------------------------------
# Direction clear/preserve semantics (sentinel _UNSET vs explicit None)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_marker_clears_direction(project):
    # Explicit direction=None clears the filter back to "both directions" —
    # distinct from omitting the kwarg (which preserves the stored value).
    with _valid_bpf():
        link = await _make_link(project)
        await link.start_marker("m", "icmp", direction="tx")
        assert link.markers["m"]["direction"] == "tx"
        await link.update_marker("m", direction=None)
    assert link.markers["m"]["direction"] is None


@pytest.mark.asyncio
async def test_update_marker_preserves_direction_when_omitted(project):
    # Omitting direction entirely is a partial update: the stored value stays.
    with _valid_bpf():
        link = await _make_link(project)
        await link.start_marker("m", "icmp", direction="tx")
        await link.update_marker("m", tag=9)
    assert link.markers["m"]["direction"] == "tx"
    assert link.markers["m"]["tag"] == 9


@pytest.mark.asyncio
async def test_update_marker_definition_clears_direction(project):
    # Clearing a definition's direction must propagate to every inherited copy.
    # New defs can't carry tx/rx, but a legacy def loaded from an old topology
    # could — so inject one and confirm a clear syncs every copy.
    with _valid_bpf():
        link1 = await _make_link(project)
        link2 = await _make_link(project)
        await project.create_marker_definition("arp", "arp")
        # Simulate a legacy directional value persisted before the restriction.
        project._marker_definitions["arp"]["direction"] = "tx"
        await link1.update_marker("global-arp", direction="tx", inherited=True)
        await link2.update_marker("global-arp", direction="tx", inherited=True)
        for link in (link1, link2):
            assert link.markers["global-arp"]["direction"] == "tx"
        await project.update_marker_definition("arp", direction=None)

    assert project.marker_definitions["arp"]["direction"] is None
    for link in (link1, link2):
        assert link.markers["global-arp"]["direction"] is None


# ---------------------------------------------------------------------------
# Capture-node routing + capability validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pinned_marker_routes_only_to_chosen_node(project):
    # The marker rides only the pinned capture node's NIO; the far endpoint sees nothing.
    with _valid_bpf():
        link = await _make_link(project)
        chosen = link._nodes[1]["node"]
        other = link._nodes[0]["node"]
        await link.start_marker("icmp", "icmp", capture_node_id=chosen.id)

    assert "icmp" in link._markers_for_node(chosen)
    assert "icmp" not in link._markers_for_node(other)


@pytest.mark.asyncio
async def test_markers_for_node_carries_direction(project):
    # The NIO-bound marker spec forwards direction so uBridge gets the dir token.
    with _valid_bpf():
        link = await _make_link(project)
        node = link._nodes[0]["node"]  # auto-pick selects the first capable endpoint
        await link.start_marker("m", "icmp", direction="rx")

    assert link._markers_for_node(node)["m"]["direction"] == "rx"


@pytest.mark.asyncio
async def test_start_marker_rejects_non_capable_capture_node(project):
    # A NAT endpoint has no uBridge bridge. Pinning to it must fail even though
    # it IS a link endpoint (distinct from the not-an-endpoint -> 404 case).
    with _valid_bpf():
        link = await _make_link(project)
        nat = Node(project, link._nodes[0]["node"].compute, "nat", node_type="nat")
        link._nodes.append({"node": nat, "adapter_number": 0, "port_number": 0})
        with pytest.raises(ControllerError):
            await link.start_marker("m", "icmp", capture_node_id=nat.id)


# ---------------------------------------------------------------------------
# Part A/B: enabled reaches uBridge + instant per-filter toggle
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_markers_for_node_keeps_disabled_and_carries_enabled(project):
    # Part A: a disabled marker is NOT dropped from the NIO payload (so uBridge
    # can install it then turn it off) and the spec carries `enabled`.
    with _valid_bpf():
        link = await _make_link(project)
        node = link._nodes[0]["node"]
        await link.start_marker("m", "icmp")
        await link.update_marker("m", enabled=False)
    spec = link._markers_for_node(node).get("m")
    assert spec is not None
    assert spec["enabled"] is False


@pytest.mark.asyncio
async def test_update_marker_enabled_only_hits_toggle_route(project):
    # Part B: an enabled-only change routes to the per-marker toggle endpoint,
    # not a full NIO reset+reapply.
    with _valid_bpf():
        link = await _make_link(project)
        node = link._nodes[0]["node"]
        await link.start_marker("m", "icmp")
        compute = node.compute
        compute.put.reset_mock()
        await link.update_marker("m", enabled=False)
    paths = [c.args[0] for c in compute.put.call_args_list]
    assert any("/markers/m" in p for p in paths)
    assert not any(p.endswith("/nio") for p in paths)


@pytest.mark.asyncio
async def test_update_marker_with_bpf_rebuilds_single_filter(project):
    # A bpf change rebuilds just this marker's filter (delete + add), NOT a full
    # NIO reapply, so sibling markers' pcaps stay open.
    with _valid_bpf():
        link = await _make_link(project)
        node = link._nodes[0]["node"]
        await link.start_marker("m", "icmp")
        compute = node.compute
        compute.put.reset_mock()
        await link.update_marker("m", bpf="tcp")
    paths = [c.args[0] for c in compute.put.call_args_list]
    assert any(p.endswith("/markers/m/rebuild") for p in paths)
    assert not any(p.endswith("/nio") for p in paths)  # no full NIO reapply


@pytest.mark.asyncio
async def test_update_marker_ui_only_does_not_push(project):
    # color/highlight_duration are UI-only — stored, never pushed to uBridge.
    with _valid_bpf():
        link = await _make_link(project)
        node = link._nodes[0]["node"]
        await link.start_marker("m", "icmp")
        compute = node.compute
        compute.put.reset_mock()
        await link.update_marker("m", color="#ffffff", highlight_duration=1500)
    assert compute.put.call_args_list == []  # nothing pushed to uBridge
    assert link.markers["m"]["color"] == "#ffffff"
    assert link.markers["m"]["highlight_duration"] == 1500


# ---------------------------------------------------------------------------
# Per-definition pause/resume (toggle every inherited global-{name} copy)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pause_marker_definition_toggles_copies_off(project):
    with _valid_bpf():
        link1 = await _make_link(project)
        link2 = await _make_link(project)
        await project.create_marker_definition("arp", "arp")
        assert link1.markers["global-arp"]["enabled"] is True
        assert link2.markers["global-arp"]["enabled"] is True
        await project.pause_marker_definition("arp")
    assert project.marker_definitions["arp"]["paused"] is True
    assert link1.markers["global-arp"]["enabled"] is False
    assert link2.markers["global-arp"]["enabled"] is False


@pytest.mark.asyncio
async def test_resume_marker_definition_toggles_copies_on(project):
    with _valid_bpf():
        link = await _make_link(project)
        await project.create_marker_definition("arp", "arp")
        await project.pause_marker_definition("arp")
        assert link.markers["global-arp"]["enabled"] is False
        await project.resume_marker_definition("arp")
    assert project.marker_definitions["arp"]["paused"] is False
    assert link.markers["global-arp"]["enabled"] is True


@pytest.mark.asyncio
async def test_paused_definition_inherited_as_disabled(project):
    # A link created after the definition was paused inherits it already off.
    with _valid_bpf():
        await project.create_marker_definition("arp", "arp")
        await project.pause_marker_definition("arp")
        new_link = await _make_link(project)
    assert new_link.markers["global-arp"]["enabled"] is False


# ---------------------------------------------------------------------------
# Marker definition direction (tx/rx rejected — it is capture-node-relative)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_marker_definition_rejects_directional(project):
    # tx/rx is relative to the auto-selected capture node → rejected at the def level.
    with pytest.raises(ControllerError):
        await project.create_marker_definition("arp", "arp", direction="tx")
    with pytest.raises(ControllerError):
        await project.create_marker_definition("arp", "arp", direction="rx")
    assert "arp" not in project.marker_definitions  # nothing created


@pytest.mark.asyncio
async def test_create_marker_definition_allows_both(project):
    await project.create_marker_definition("arp", "arp")           # default both
    await project.create_marker_definition("icmp", "icmp", direction=None)
    assert project.marker_definitions["arp"]["direction"] is None
    assert project.marker_definitions["icmp"]["direction"] is None


@pytest.mark.asyncio
async def test_update_marker_definition_rejects_directional(project):
    await project.create_marker_definition("arp", "arp")           # both
    with pytest.raises(ControllerError):
        await project.update_marker_definition("arp", direction="tx")
    # omitted direction and explicit clear-to-both are both fine
    await project.update_marker_definition("arp", color="#ffffff")
    await project.update_marker_definition("arp", direction=None)
    assert project.marker_definitions["arp"]["direction"] is None


@pytest.mark.asyncio
async def test_stop_marker_deletes_capture_pcap(project):
    # Removing a marker asks the capture node's compute to delete its pcap, so
    # the file is cleaned up even with the node stopped (the NIO reapply path
    # only runs while uBridge is up).
    with _valid_bpf():
        link = await _make_link(project)
        capture = link._nodes[0]["node"]
        await link.start_marker("icmp", "icmp", capture_node_id=capture.id)
        capture.delete = AsyncioMagicMock()
        await link.stop_marker("icmp")

    capture.delete.assert_called_once_with(
        "/adapters/0/ports/0/markers/icmp", params={"link_id": link.id}
    )
