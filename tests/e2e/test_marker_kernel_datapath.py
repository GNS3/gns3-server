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
TAG = 4242

# a busybox `ping` default frame: 14 Ethernet + 20 IP + 8 ICMP + 56 data.
PING_FRAME_LEN = 98


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
    """Start the containers and wait for init.sh to have applied their
    addresses (busybox ifup runs a moment after container start)."""
    for node in nodes:
        compute.call("POST", f"/projects/{pid}/nodes/{node['node_id']}/start")
    for node, address in zip(nodes, (R1_IP, R2_IP), strict=False):
        harness.docker_wait_address(daemon, node["container_id"], address)


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

        print(".. sending 5 ICMP echoes and collecting marker.match signals")
        result = harness.docker_ping(daemon, c1, R2_IP, count=5)
        assert result["loss"] == 0, result["raw"]

        harness.wait_until(lambda: len(_matches(marker_ws, "m-icmp")) >= 10, timeout=10)
        icmp = _matches(marker_ws, "m-icmp")
        assert len(icmp) == 10, len(icmp)  # 5 requests (tx) + 5 replies (rx)
        assert not _matches(marker_ws, "m-tcp"), "a non-matching BPF must stay silent"
        assert len(_matches(marker_ws, "m-tx")) == 5, "the tx direction sees requests only"

        for event in icmp:
            assert event["node_id"] == n1_id, event
            assert event["link_id"] == lid, event
            assert event["tag"] == TAG, event
            assert event["ts"] > 0, event
            assert event["len"] == PING_FRAME_LEN, event
        assert {e["dir"] for e in icmp} == {"tx", "rx"}, [e["dir"] for e in icmp]
        assert {e["dir"] for e in _matches(marker_ws, "m-tx")} == {"tx"}

        # The dedicated channel carries matches; the main project stream must
        # not (and must still be alive — its link.updated proves the socket).
        assert main_ws.messages("marker.match") == [], main_ws.messages("marker.match")[:3]
        assert main_ws.messages("link.updated"), "the main channel is not receiving at all"

        # Host pcap: exactly the matched frames, off the anchor
        pcap = os.path.join(markers_dir, f"{n1_id}_{lid}_m-icmp.pcap")
        assert os.path.exists(pcap), os.listdir(markers_dir)
        count, ethertypes = harness.pcap_records(pcap)
        assert count == 10, count
        assert set(ethertypes) == {"0800"}, ethertypes

        # pause: this marker's signals stop, its pcap survives, and the
        # sibling marker's matches keep flowing (the channel is alive —
        # silence is the pause, not a dead stream)
        print(".. pausing m-icmp: its signals stop while the siblings keep firing")
        compute.call("PUT", f"/projects/{pid}/links/{lid}/markers/m-icmp", {"enabled": False})
        harness.docker_ping(daemon, c1, R2_IP, count=3)
        harness.wait_until(lambda: len(_matches(marker_ws, "m-tx")) >= 8, timeout=10)
        assert len(_matches(marker_ws, "m-icmp")) == 10, "a paused marker must not signal"
        assert os.path.exists(pcap)

        # resume: signals come back, pcap keeps appending
        print(".. resuming m-icmp")
        compute.call("PUT", f"/projects/{pid}/links/{lid}/markers/m-icmp", {"enabled": True})
        harness.docker_ping(daemon, c1, R2_IP, count=2)
        harness.wait_until(lambda: len(_matches(marker_ws, "m-icmp")) >= 14, timeout=10)
        assert len(_matches(marker_ws, "m-icmp")) == 14
        assert harness.pcap_records(pcap)[0] == 14

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

        # delete: the pcap goes with the marker and the signals stop
        print(".. deleting m-icmp: pcap and signals go with it")
        compute.call("DELETE", f"/projects/{pid}/links/{lid}/markers/m-icmp")
        assert harness.wait_until(lambda: not os.path.exists(pcap), timeout=10), pcap
        harness.docker_ping(daemon, c1, R2_IP, count=2)
        harness.wait_until(lambda: len(_matches(marker_ws, "m-tx")) >= 12, timeout=10)
        assert len(_matches(marker_ws, "m-icmp")) == 14, "a deleted marker must not signal"

        compute.call("DELETE", f"/projects/{pid}/links/{lid}/markers/m-tcp")
        compute.call("DELETE", f"/projects/{pid}/links/{lid}/markers/m-tx")
        assert not os.listdir(markers_dir), os.listdir(markers_dir)
    except BaseException:
        harness.release(server, pid, failed=True)
        _close(marker_ws, main_ws)
        raise
    _close(marker_ws, main_ws)
    harness.release(server, pid, failed=False)
