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
Live end-to-end test for traffic-insight markers on the kernel datapath
(pytest marker ``e2e``): two real Alpine containers on a kernel-only link,
markers attached to a veth anchor (``marker add_kernel``) and observed on
the dedicated marker notification WebSocket. Real ICMP proves:

* a marker match arrives as a ``marker.match`` on
  ``/projects/{id}/notifications/markers/ws`` with the full identity —
  filter name, tag, link_id, capture node, timestamp, packet length,
  travel direction — and **nothing** on the main project channel (the
  whole point of the dedicated stream: matches must not head-of-line-block
  topology events);
* the BPF is enforced on the anchor: a sibling marker whose expression
  cannot match the traffic stays silent, a directioned marker only sees
  its direction (``tx`` = the capture node sending), and the pcap on the
  host holds exactly the matched frames;
* pausing a marker silences its signals while keeping its pcap; resuming
  restores them — and other markers' matches keep flowing throughout, so
  silence is never just "the channel died";
* tag replay serves the paused tag's aggregate timeline off that pcap
  (merged frames with src/dst/proto, per-source inventory, display-filter
  and link narrowing, the window endpoint) and refuses with 409 while any
  marker under the tag is still capturing (skipped when sharkd is absent);
* deleting a marker removes its pcap and silences its signals; deleting
  the project leaves no marker state behind.

Everything runs dual-stack: alongside the v4 markers the link carries v6
twin markers (one of them directioned) whose expression matches ICMPv6
echoes only — a bare ``icmp6`` would also match the guests' own DAD/MLD
control frames and break the exact-count asserts. The exact counts across
both families double as the cross-family check: neither family's traffic
reaches the other family's markers.
"""

import json
import os
import shutil
import urllib.error
import urllib.parse
import urllib.request

import pytest

from tests.e2e import harness

pytestmark = pytest.mark.e2e

# every standard Docker adapter has a single port
ETH = (0, 0)
R1_IP = "10.1.1.1"
R2_IP = "10.1.1.2"
# the dual-stack half: a ULA mirroring the v4 addressing (10.1.1.x -> fd00:1:1::x)
R1_IP6 = "fd00:1:1::1"
R2_IP6 = "fd00:1:1::2"
TAG = 4242
TAG6 = 4243

# busybox `ping` default frames: 14 Ethernet + 20/40 IP + 8 ICMP + 56 data.
PING_FRAME_LEN = 98
PING_FRAME_LEN6 = 118

# exact ICMPv6 echo match: a bare "icmp6" would also match the guests' own
# DAD/MLD/NS/NA control frames and break the exact-count asserts
ICMP6_ECHO_BPF = "icmp6 and (ip6[40] == 128 or ip6[40] == 129)"


def _resolve_container(daemon, node):
    """Fill in the node's container id from the daemon (the controller's
    node payload does not carry the compute-side id), by the deterministic
    name the server gives the container."""
    container_id = daemon.container_id(f"GNS3.{node['name']}.{node['project_id']}")
    assert container_id, f"container for {node['name']} not found on the Docker daemon"
    node["container_id"] = container_id
    return node


def _create_topology(server, pid, image):
    compute = server.compute
    daemon = harness.DockerDaemon()
    nodes = []
    for suffix, address in (("1", R1_IP), ("2", R2_IP)):
        node = compute.create_docker_node(pid, f"MARKER-E2E-{suffix}", image)
        harness.configure_docker_interfaces(node, address)
        nodes.append(_resolve_container(daemon, node))
    return nodes[0], nodes[1], daemon


def _start_topology(compute, pid, daemon, nodes):
    """Start the containers and wait for init.sh to have applied their v4
    addresses (busybox ifup runs a moment after container start); the v6
    addresses are brought up by the harness after each start."""
    for node in nodes:
        compute.call("POST", f"/projects/{pid}/nodes/{node['node_id']}/start")
    for node, (address, address6) in zip(nodes, ((R1_IP, R1_IP6), (R2_IP, R2_IP6)), strict=False):
        harness.docker_wait_address(daemon, node["container_id"], address)
        harness.docker_bring_up_ipv6(daemon, node["container_id"], address6)
        harness.docker_wait_address(daemon, node["container_id"], address6)


def _raw(compute, path):
    """GET without raising on an error status: returns ``(status, body)``
    (body parsed as JSON when possible, else the raw text). The replay
    endpoints are asserted on their status codes (409 gate / 200 data)."""
    # S310: the base URL comes from the operator (GNS3_E2E_URL or the
    # isolated instance this test just started), not untrusted input
    req = urllib.request.Request(compute.url + path, method="GET")  # noqa: S310
    req.add_header("Authorization", f"Bearer {compute.token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
            payload = resp.read()
            return resp.status, json.loads(payload) if payload else None
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")


def _matches(marker_ws, marker_name):
    return [e for e in marker_ws.events("marker.match") if e["filter"] == marker_name]


def _close(*collectors):
    for collector in collectors:
        if collector is not None:
            collector.close()


def test_marker_kernel_datapath():
    server = harness.live_server(kernel=True)
    compute = server.compute
    image = harness.ensure_docker_image(server)

    project = compute.create_project("marker-e2e")
    pid = project["project_id"]
    marker_ws = main_ws = None
    try:
        n1, n2, daemon = _create_topology(server, pid, image)
        n1_id, n2_id = n1["node_id"], n2["node_id"]
        c1 = n1["container_id"]

        link = compute.create_link(pid, (n1_id, *ETH), (n2_id, *ETH))
        lid = link["link_id"]
        assert link["kernel_datapath"] is True, link
        _start_topology(compute, pid, daemon, (n1, n2))
        baseline = harness.docker_wait_ping(daemon, c1, R2_IP)
        assert baseline["loss"] == 0, baseline["raw"]
        baseline6 = harness.docker_wait_ping(daemon, c1, R2_IP6)
        assert baseline6["loss"] == 0, baseline6["raw"]

        a1 = harness.docker_anchor_name(n1_id, *ETH)
        markers_dir = os.path.join(compute.call("GET", f"/projects/{pid}")["path"], "project-files", "markers")

        # Both channels open before the markers exist so no match is missed.
        marker_ws = harness.WebSocketCollector(server, f"/projects/{pid}/notifications/markers/ws")
        main_ws = harness.WebSocketCollector(server, f"/projects/{pid}/notifications/ws")

        print(".. attaching markers to the kernel link")
        m = compute.call(
            "POST",
            f"/projects/{pid}/links/{lid}/markers",
            {"name": "m-icmp", "bpf": "icmp", "tag": TAG, "capture_node_id": n1_id},
        )
        assert m["capture_node_id"] == n1_id and m["tag"] == TAG and m["enabled"] is True, m
        # a sibling whose expression cannot match ICMP traffic — it must stay
        # silent while the others fire (the BPF is the filter, not the marker)
        compute.call(
            "POST", f"/projects/{pid}/links/{lid}/markers", {"name": "m-tcp", "bpf": "tcp port 9999", "tag": 4343}
        )
        # direction is relative to the capture node: node1 sending only
        m_tx = compute.call(
            "POST",
            f"/projects/{pid}/links/{lid}/markers",
            {"name": "m-tx", "bpf": "icmp", "direction": "tx", "tag": 4344, "capture_node_id": n1_id},
        )
        assert m_tx["direction"] == "tx", m_tx
        # the dual-stack twin: a v6 marker with an echo-specific expression
        # (a bare "icmp6" would also match the guests' own NS/MLD/RA frames)
        m6 = compute.call(
            "POST",
            f"/projects/{pid}/links/{lid}/markers",
            {"name": "m-icmp6", "bpf": ICMP6_ECHO_BPF, "tag": TAG6, "capture_node_id": n1_id},
        )
        assert m6["capture_node_id"] == n1_id and m6["tag"] == TAG6 and m6["enabled"] is True, m6
        m_tx6 = compute.call(
            "POST",
            f"/projects/{pid}/links/{lid}/markers",
            {"name": "m-tx6", "bpf": ICMP6_ECHO_BPF, "direction": "tx", "tag": 4345, "capture_node_id": n1_id},
        )
        assert m_tx6["direction"] == "tx", m_tx6

        print(".. sending 5 v4 + 5 v6 ICMP echoes and collecting marker.match signals")
        result = harness.docker_ping(daemon, c1, R2_IP, count=5)
        assert result["loss"] == 0, result["raw"]
        result6 = harness.docker_ping(daemon, c1, R2_IP6, count=5)
        assert result6["loss"] == 0, result6["raw"]

        harness.wait_until(
            lambda: len(_matches(marker_ws, "m-icmp")) >= 10 and len(_matches(marker_ws, "m-icmp6")) >= 10, timeout=10
        )
        # exact counts across both families: each marker sees its own
        # family's 5 requests + 5 replies and nothing of the other's
        icmp = _matches(marker_ws, "m-icmp")
        assert len(icmp) == 10, len(icmp)  # 5 requests (tx) + 5 replies (rx)
        icmp6 = _matches(marker_ws, "m-icmp6")
        assert len(icmp6) == 10, len(icmp6)
        assert not _matches(marker_ws, "m-tcp"), "a non-matching BPF must stay silent"
        assert len(_matches(marker_ws, "m-tx")) == 5, "the tx direction sees requests only"
        assert len(_matches(marker_ws, "m-tx6")) == 5, "the v6 tx direction sees requests only"

        for event in icmp:
            assert event["node_id"] == n1_id, event
            assert event["link_id"] == lid, event
            assert event["tag"] == TAG, event
            assert event["ts"] > 0, event
            assert event["len"] == PING_FRAME_LEN, event
        for event in icmp6:
            assert event["node_id"] == n1_id, event
            assert event["link_id"] == lid, event
            assert event["tag"] == TAG6, event
            assert event["ts"] > 0, event
            assert event["len"] == PING_FRAME_LEN6, event
        assert {e["dir"] for e in icmp} == {"tx", "rx"}, [e["dir"] for e in icmp]
        assert {e["dir"] for e in icmp6} == {"tx", "rx"}, [e["dir"] for e in icmp6]
        assert {e["dir"] for e in _matches(marker_ws, "m-tx")} == {"tx"}
        assert {e["dir"] for e in _matches(marker_ws, "m-tx6")} == {"tx"}

        # The dedicated channel carries matches; the main project stream must
        # not (and must still be alive — its link.updated proves the socket).
        assert main_ws.messages("marker.match") == [], main_ws.messages("marker.match")[:3]
        assert main_ws.messages("link.updated"), "the main channel is not receiving at all"

        # Host pcaps: exactly the matched frames, off the anchor
        pcap = os.path.join(markers_dir, f"{n1_id}_{lid}_m-icmp.pcap")
        pcap6 = os.path.join(markers_dir, f"{n1_id}_{lid}_m-icmp6.pcap")
        assert os.path.exists(pcap), os.listdir(markers_dir)
        assert os.path.exists(pcap6), os.listdir(markers_dir)
        count, ethertypes = harness.pcap_records(pcap)
        assert count == 10, count
        assert set(ethertypes) == {"0800"}, ethertypes
        count6, ethertypes6 = harness.pcap_records(pcap6)
        assert count6 == 10, count6
        assert set(ethertypes6) == {"86dd"}, ethertypes6

        # pause: this marker's signals stop, its pcap survives, and the
        # sibling marker's matches keep flowing (the channel is alive —
        # silence is the pause, not a dead stream). Both families' streams
        # run through the paused window: the count stays frozen for either.
        print(".. pausing m-icmp: its signals stop while the siblings keep firing")
        compute.call("PUT", f"/projects/{pid}/links/{lid}/markers/m-icmp", {"enabled": False})
        harness.docker_ping(daemon, c1, R2_IP, count=3)
        harness.docker_ping(daemon, c1, R2_IP6, count=3)
        harness.wait_until(
            lambda: len(_matches(marker_ws, "m-tx")) >= 8 and len(_matches(marker_ws, "m-icmp6")) >= 16, timeout=10
        )
        assert len(_matches(marker_ws, "m-icmp")) == 10, "a paused marker must not signal"
        assert len(_matches(marker_ws, "m-icmp6")) == 16, "the 3 v6 pings must reach the v6 marker"
        assert os.path.exists(pcap)

        # resume: signals come back, pcap keeps appending
        print(".. resuming m-icmp")
        compute.call("PUT", f"/projects/{pid}/links/{lid}/markers/m-icmp", {"enabled": True})
        harness.docker_ping(daemon, c1, R2_IP, count=2)
        harness.docker_ping(daemon, c1, R2_IP6, count=2)
        harness.wait_until(
            lambda: len(_matches(marker_ws, "m-icmp")) >= 14 and len(_matches(marker_ws, "m-icmp6")) >= 20, timeout=10
        )
        assert len(_matches(marker_ws, "m-icmp")) == 14
        assert len(_matches(marker_ws, "m-icmp6")) == 20
        assert harness.pcap_records(pcap)[0] == 14
        assert harness.pcap_records(pcap6)[0] == 20

        if shutil.which("sharkd") is None:
            print(".. sharkd is not installed: skipping the tag replay section")
        else:
            # Tag replay reads the pcaps at rest: pause every marker of the
            # tag. m-icmp is the only one carrying TAG.
            print(f".. pausing m-icmp and replaying tag {TAG}")
            compute.call("PUT", f"/projects/{pid}/links/{lid}/markers/m-icmp", {"enabled": False})
            status, timeline = _raw(compute, f"/projects/{pid}/markers/tags/{TAG}/replay/range")
            assert status == 200, timeline
            assert timeline["tag"] == TAG
            assert timeline["frame_count"] == 14, timeline["frame_count"]
            assert timeline["start"] and timeline["end"], timeline
            assert timeline["sources"] == [
                {
                    "node_id": n1_id,
                    "link_id": lid,
                    "marker": "m-icmp",
                    "data_link_type": "DLT_EN10MB",
                    "count": 14,
                }
            ], timeline["sources"]
            first = timeline["frames"][0]
            assert first["src"] == R1_IP and first["dst"] == R2_IP, first
            assert "ICMP" in (first["proto"] or ""), first

            # display filter: echo requests only (5 + 2 of the 14)
            query = urllib.parse.urlencode({"filter": "icmp.type == 8"})
            status, filtered = _raw(compute, f"/projects/{pid}/markers/tags/{TAG}/replay/range?{query}")
            assert status == 200, filtered
            assert filtered["frame_count"] == 7, filtered["frame_count"]
            # unknown link: an empty stream, same shape as a zero-match filter
            query = urllib.parse.urlencode({"link": "00000000-0000-0000-0000-000000000000"})
            status, empty = _raw(compute, f"/projects/{pid}/markers/tags/{TAG}/replay/range?{query}")
            assert status == 200 and empty["frame_count"] == 0 and empty["frames"] == [], empty
            # window endpoint: the whole capture inside one window
            query = urllib.parse.urlencode({"ts": timeline["start"], "window_ms": 120000, "limit": 1000})
            status, window = _raw(compute, f"/projects/{pid}/markers/tags/{TAG}/replay/frames?{query}")
            assert status == 200 and len(window["frames"]) == 14, window

            # the gate: replay refuses while the tag is still capturing
            compute.call("PUT", f"/projects/{pid}/links/{lid}/markers/m-icmp", {"enabled": True})
            status, gate = _raw(compute, f"/projects/{pid}/markers/tags/{TAG}/replay/range")
            assert status == 409, (status, gate)

            # the same replay over the v6 tag: identical mechanics, v6 decode
            print(f".. pausing m-icmp6 and replaying tag {TAG6}")
            compute.call("PUT", f"/projects/{pid}/links/{lid}/markers/m-icmp6", {"enabled": False})
            status, timeline6 = _raw(compute, f"/projects/{pid}/markers/tags/{TAG6}/replay/range")
            assert status == 200, timeline6
            assert timeline6["tag"] == TAG6
            assert timeline6["frame_count"] == 20, timeline6["frame_count"]
            assert timeline6["start"] and timeline6["end"], timeline6
            assert timeline6["sources"] == [
                {
                    "node_id": n1_id,
                    "link_id": lid,
                    "marker": "m-icmp6",
                    "data_link_type": "DLT_EN10MB",
                    "count": 20,
                }
            ], timeline6["sources"]
            first6 = timeline6["frames"][0]
            assert first6["src"] == R1_IP6 and first6["dst"] == R2_IP6, first6
            assert "ICMPv6" in (first6["proto"] or ""), first6

            # display filter: echo requests only (5 + 3 + 2 of the 20)
            query = urllib.parse.urlencode({"filter": "icmpv6.type == 128"})
            status, filtered6 = _raw(compute, f"/projects/{pid}/markers/tags/{TAG6}/replay/range?{query}")
            assert status == 200, filtered6
            assert filtered6["frame_count"] == 10, filtered6["frame_count"]
            # unknown link: an empty stream, same shape as a zero-match filter
            query = urllib.parse.urlencode({"link": "00000000-0000-0000-0000-000000000000"})
            status, empty6 = _raw(compute, f"/projects/{pid}/markers/tags/{TAG6}/replay/range?{query}")
            assert status == 200 and empty6["frame_count"] == 0 and empty6["frames"] == [], empty6
            # window endpoint: the whole capture inside one window
            query = urllib.parse.urlencode({"ts": timeline6["start"], "window_ms": 120000, "limit": 1000})
            status, window6 = _raw(compute, f"/projects/{pid}/markers/tags/{TAG6}/replay/frames?{query}")
            assert status == 200 and len(window6["frames"]) == 20, window6

            # the gate: replay refuses while the tag is still capturing
            compute.call("PUT", f"/projects/{pid}/links/{lid}/markers/m-icmp6", {"enabled": True})
            status, gate6 = _raw(compute, f"/projects/{pid}/markers/tags/{TAG6}/replay/range")
            assert status == 409, (status, gate6)

        # delete: the pcaps go with their markers and the signals stop
        print(".. deleting m-icmp and m-icmp6: pcaps and signals go with them")
        compute.call("DELETE", f"/projects/{pid}/links/{lid}/markers/m-icmp")
        assert harness.wait_until(lambda: not os.path.exists(pcap), timeout=10), pcap
        compute.call("DELETE", f"/projects/{pid}/links/{lid}/markers/m-icmp6")
        assert harness.wait_until(lambda: not os.path.exists(pcap6), timeout=10), pcap6
        harness.docker_ping(daemon, c1, R2_IP, count=2)
        harness.docker_ping(daemon, c1, R2_IP6, count=2)
        # both still-attached directioned siblings prove the streams crossed
        # and their events were delivered before the deleted markers are
        # asserted frozen
        harness.wait_until(
            lambda: len(_matches(marker_ws, "m-tx")) >= 12 and len(_matches(marker_ws, "m-tx6")) >= 12, timeout=10
        )
        assert len(_matches(marker_ws, "m-icmp")) == 14, "a deleted marker must not signal"
        assert len(_matches(marker_ws, "m-icmp6")) == 20, "a deleted marker must not signal"

        compute.call("DELETE", f"/projects/{pid}/links/{lid}/markers/m-tcp")
        compute.call("DELETE", f"/projects/{pid}/links/{lid}/markers/m-tx")
        compute.call("DELETE", f"/projects/{pid}/links/{lid}/markers/m-tx6")
        assert not os.listdir(markers_dir), os.listdir(markers_dir)
    except BaseException:
        harness.release(server, pid, failed=True)
        _close(marker_ws, main_ws)
        raise
    _close(marker_ws, main_ws)
    harness.release(server, pid, failed=False)
