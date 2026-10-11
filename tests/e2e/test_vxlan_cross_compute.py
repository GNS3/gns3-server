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

"""
Live end-to-end test for cross-compute VXLAN links (pytest marker ``e2e``):
two computes on one machine — the harness's isolated instance on the host and
a second isolated instance inside a network namespace joined to the host by a
veth pair (``harness.cross_compute_fabric``) — with one real Alpine container
per compute, linked across the tunnel.

Two computes on one machine cannot tunnel from the host namespace: the kernel
keeps one VXLAN socket per (namespace, dstport), and both ends of a link must
register the same VNI on it, so the pair collides by design (the controller
falls back to the relay for same-host pairs). Separate network namespaces
give the pair its two sockets, and the veth pair is the L2 fabric the tunnels
ride — the closest a single machine gets to two hosts. The same-host
fallback itself is asserted by the controller unit tests; this scenario is
the real-kernel proof of the tunnel.

Needs root: a network namespace is privileged to create and to enter, and the
second compute's node files (its project directories) are written by the
test. Run it as::

    sudo env GNS3_E2E_IMAGES=$HOME/GNS3/images pytest -m e2e \\
        tests/e2e/test_vxlan_cross_compute.py -s

What it asserts:

* both ends report the same VNI on the shared dstport, each pointing at the
  other machine's address, and each per-link bridge enslaves exactly
  ``[anchor, tunnel]``;
* the tunnel device's MTU is the underlay MTU minus 50 (the kernel derives
  it from the lower device the peer route resolves to), the bridges inherit
  it, and a frame past it is dropped at the bridge egress while one at it
  crosses — the reason the datapath is opt-in on non-jumbo fabrics;
* real dual-stack ICMP crosses, a ``delay 100`` filter shapes it (one end
  per direction), link delete leaves no device or bridge on either machine;
* a stale tunnel device squatting on the link's deterministic name is
  replaced by the attach path, and the tunnel recovers;
* a device squatting the link's VNI at node start self-heals: the start
  re-wires the link on a fresh VNI — the peer re-wired too — and succeeds.
"""

import os
import re
import subprocess
import time

import pytest

from gns3server.utils.vxlan import VXLAN_VNI_MAX, VXLAN_VNI_MIN, vxlan_device_name
from tests.e2e import harness

pytestmark = pytest.mark.e2e

# every standard Docker adapter has a single port
ETH = (0, 0)
G1_IP = "10.66.1.1"
G2_IP = "10.66.1.2"
# the dual-stack half: a ULA mirroring the v4 addressing
G1_IP6 = "fd00:66:1::1"
G2_IP6 = "fd00:66:1::2"

# ICMP payloads against the derived tunnel MTU (underlay 1500 -> tunnel
# 1450): 1400 + 42 bytes of headers is a 1442-byte frame, under the bridge
# egress gate; 1500 + 42 is a 1542-byte frame, over it — and over the
# guest's own 1500 MTU too, so the IP stack may fragment it; either way the
# pieces cannot cross the 1450-wide egress and the ping must fail silently.
FIT_PAYLOAD = 1400
TOO_BIG_PAYLOAD = 1500


def _ip(*argv):
    """Run an iproute2 command on the host (the scenario runs as root)."""
    ip = harness.IP
    assert ip, "ip binary not found"
    # S603: resolved binary, fixed argv from the test itself
    return subprocess.run([ip, *argv], capture_output=True, text=True, check=True)  # noqa: S603


def _host_vxlan_attrs(name):
    """(vni, dstport, remote) of a host-side tunnel device, from
    ``ip -d link show``."""
    details = _ip("-d", "link", "show", name).stdout
    vni = re.search(r"\bvxlan id (\d+)", details)
    dstport = re.search(r"\bdstport (\d+)", details)
    remote = re.search(r"\bremote (\S+)", details)
    assert vni and dstport and remote, details
    return int(vni.group(1)), int(dstport.group(1)), remote.group(1)


def _peer_vxlan_attrs(fabric, name):
    details = fabric.vxlan_show(name)
    assert details, f"tunnel device {name} missing inside {fabric.netns}"
    vni = re.search(r"\bvxlan id (\d+)", details)
    dstport = re.search(r"\bdstport (\d+)", details)
    remote = re.search(r"\bremote (\S+)", details)
    assert vni and dstport and remote, details
    return int(vni.group(1)), int(dstport.group(1)), remote.group(1)


def _container_id(daemon, node):
    container_id = daemon.container_id(f"GNS3.{node['name']}.{node['project_id']}")
    assert container_id, f"container for {node['name']} not found on the Docker daemon"
    node["container_id"] = container_id
    return container_id


def _start_pair(compute, pid, daemon, n1, n2):
    """Start both containers and wait for their userspace to be reachable:
    the v4 address from the interfaces file (init.sh), the v6 twin from the
    harness (the daemon's disable_ipv6 on bridge networks makes the
    interfaces-file route fail). The container ids are re-resolved after the
    starts: a project reopen can replace a stale container with a fresh one
    under the same deterministic name (a new id)."""
    for node in (n1, n2):
        compute.call("POST", f"/projects/{pid}/nodes/{node['node_id']}/start")
        _container_id(daemon, node)
    for node, address in ((n1, G1_IP), (n2, G2_IP)):
        harness.docker_wait_address(daemon, node["container_id"], address)
    for node, address6 in ((n1, G1_IP6), (n2, G2_IP6)):
        harness.docker_bring_up_ipv6(daemon, node["container_id"], address6)


def test_vxlan_cross_compute_link():
    if os.geteuid() != 0:
        pytest.skip(
            "cross-compute VXLAN needs a second network stack (a netns) and writes the second "
            "compute's node files: run as root, e.g. `sudo env GNS3_E2E_IMAGES=$HOME/GNS3/images "
            "pytest -m e2e tests/e2e/test_vxlan_cross_compute.py -s`"
        )

    fabric = harness.cross_compute_fabric()
    server = harness.live_server(kernel=True, vxlan=True)
    peer = harness.start_isolated_peer(fabric)
    compute = server.compute
    daemon = harness.DockerDaemon()
    failed = True
    pid = None
    try:
        peer_id = harness.register_remote_compute(server, peer)
        image = harness.ensure_docker_image(server)
        project = compute.create_project("vxlan-e2e")
        pid = project["project_id"]

        print(".. creating one container per compute")
        n1 = compute.create_docker_node(pid, "VXE1", image)
        harness.configure_docker_interfaces(n1, G1_IP)
        _container_id(daemon, n1)
        n2 = compute.create_docker_node(pid, "VXE2", image, compute_id=peer_id)
        harness.configure_docker_interfaces(n2, G2_IP)
        _container_id(daemon, n2)
        assert n1["compute_id"] == "local", n1["compute_id"]
        assert n2["compute_id"] == peer_id, n2["compute_id"]

        print(".. linking them across the computes")
        link = compute.create_link(pid, (n1["node_id"], *ETH), (n2["node_id"], *ETH))
        lid = link["link_id"]
        assert link["kernel_datapath"] is True, link
        bridge = harness.link_bridge_name(lid)
        a1 = harness.docker_anchor_name(n1["node_id"], *ETH)
        a2 = harness.docker_anchor_name(n2["node_id"], *ETH)
        vx1 = vxlan_device_name(lid, n1["node_id"])
        vx2 = vxlan_device_name(lid, n2["node_id"])
        assert not harness.tap_exists(vx1), "the tunnel lands with node start"

        print(".. starting the containers (the wiring lands with node start)")
        _start_pair(compute, pid, daemon, n1, n2)

        print(".. asserting the tunnel on both machines")
        assert harness.tap_exists(vx1), f"tunnel device {vx1} missing on the host"
        assert harness.bridge_members(bridge) == sorted([a1, vx1]), harness.bridge_members(bridge)
        assert fabric.bridge_members(bridge) == sorted([a2, vx2]), fabric.bridge_members(bridge)
        vni1, port1, remote1 = _host_vxlan_attrs(vx1)
        vni2, port2, remote2 = _peer_vxlan_attrs(fabric, vx2)
        assert vni1 == vni2, (vni1, vni2)
        assert VXLAN_VNI_MIN <= vni1 <= VXLAN_VNI_MAX, vni1
        assert port1 == port2, (port1, port2)
        assert remote1 == fabric.peer_ip, (remote1, fabric.peer_ip)
        assert remote2 == fabric.host_ip, (remote2, fabric.host_ip)

        # MTU: the kernel derives the tunnel device's MTU from the lower
        # device the peer route resolves to (underlay - 50 for the outer
        # headers), and the per-link bridge — no MTU of its own — reports
        # the minimum of its ports, i.e. the honest "what this fabric can
        # carry".
        underlay_mtu = int(harness.sysfs(f"/sys/class/net/{fabric.host_ifc}/mtu"))
        assert underlay_mtu == 1500, underlay_mtu  # the veth default; the derived MTU follows from it
        assert int(harness.sysfs(f"/sys/class/net/{vx1}/mtu")) == underlay_mtu - 50
        assert int(harness.sysfs(f"/sys/class/net/{bridge}/mtu")) == underlay_mtu - 50
        assert fabric.iface_mtu(vx2) == underlay_mtu - 50
        assert fabric.iface_mtu(bridge) == underlay_mtu - 50
        assert fabric.iface_mtu(fabric.peer_ifc) == underlay_mtu

        # The tunnel device is an L2 anchor like any other: hardened
        # (lenient — the shared with plain `ip` in the doc's example) and
        # FORWARDING on both bridges.
        if harness.l2only_supported():
            harness.assert_pure_l2(vx1)
        harness.assert_forwarding(vx1)
        assert fabric.brport_state(vx2) == "3", fabric.brport_state(vx2)

        print(".. pinging across the tunnel")
        ping = harness.docker_wait_ping(daemon, n1["container_id"], G2_IP)
        assert ping["loss"] == 0, ping["raw"]
        assert ping["avg"] is not None and ping["avg"] < 50, ping
        ping6 = harness.docker_wait_ping(daemon, n1["container_id"], G2_IP6)
        assert ping6["loss"] == 0, ping6["raw"]

        # The derived MTU is the hard limit: a frame at it crosses, one past
        # it is dropped at the bridge egress — silently, which is why the
        # deployment has to size the underlay for the frames its guests send.
        fit = harness.docker_ping(daemon, n1["container_id"], G2_IP, size=FIT_PAYLOAD)
        assert fit["loss"] == 0, fit["raw"]
        too_big = harness.docker_ping(daemon, n1["container_id"], G2_IP, count=2, size=TOO_BIG_PAYLOAD)
        assert too_big["loss"] > 0 or too_big["exit"] != 0, too_big["raw"]

        print(".. delay 100 shapes the tunnel on both ends (one direction each)")
        compute.call("PUT", f"/projects/{pid}/links/{lid}", {"filters": {"delay": [100]}})
        time.sleep(1)
        delayed = harness.docker_ping(daemon, n1["container_id"], G2_IP, count=5, interval=None, timeout=2)
        assert delayed["loss"] == 0, delayed["raw"]
        assert 150 <= (delayed["avg"] or 0) <= 450, delayed
        compute.call("PUT", f"/projects/{pid}/links/{lid}", {"filters": {}})

        print(".. a stale device on the link's name is replaced on node restart")
        compute.call("POST", f"/projects/{pid}/nodes/{n1['node_id']}/stop")
        _ip("link", "del", vx1)
        # A stale tunnel: same deterministic name, some other VNI/port —
        # what a crashed run or a hand-made device would leave behind.
        _ip("link", "add", vx1, "type", "vxlan", "id", "4242", "dstport", "47999", "remote", "127.0.0.1")
        compute.call("POST", f"/projects/{pid}/nodes/{n1['node_id']}/start")
        harness.docker_wait_address(daemon, n1["container_id"], G1_IP)
        harness.docker_bring_up_ipv6(daemon, n1["container_id"], G1_IP6)
        stale_vni, stale_port, stale_remote = _host_vxlan_attrs(vx1)
        assert (stale_vni, stale_port, stale_remote) == (vni1, port1, remote1), (stale_vni, stale_port, stale_remote)
        assert harness.bridge_members(bridge) == sorted([a1, vx1]), harness.bridge_members(bridge)
        assert int(harness.sysfs(f"/sys/class/net/{bridge}/mtu")) == underlay_mtu - 50
        assert harness.docker_wait_ping(daemon, n1["container_id"], G2_IP, attempts=5)["loss"] == 0

        print(".. a VNI squatted at node start self-heals on a fresh VNI")
        compute.call("POST", f"/projects/{pid}/nodes/{n1['node_id']}/stop")
        # A device holding the link's exact VNI on the shared dstport socket
        # — what a colliding link (or an operator) would have registered.
        # The node's start replays the stored NIO, the kernel refuses the
        # VNI, and the controller must re-wire the link on a fresh one and
        # retry the start instead of failing it.
        _ip("link", "add", "gvxsquat", "type", "vxlan", "id", str(vni1), "dstport", str(port1), "remote", "127.0.0.1")
        try:
            compute.call("POST", f"/projects/{pid}/nodes/{n1['node_id']}/start")
            harness.docker_wait_address(daemon, n1["container_id"], G1_IP)
            harness.docker_bring_up_ipv6(daemon, n1["container_id"], G1_IP6)
            healed_vni, healed_port, healed_remote = _host_vxlan_attrs(vx1)
            assert healed_vni != vni1, (healed_vni, vni1)
            assert VXLAN_VNI_MIN <= healed_vni <= VXLAN_VNI_MAX, healed_vni
            assert healed_port == port1, (healed_port, port1)
            assert healed_remote == remote1, (healed_remote, remote1)
            # the peer was re-wired to the fresh VNI too — the pair must agree
            peer_vni, _, _ = _peer_vxlan_attrs(fabric, vx2)
            assert peer_vni == healed_vni, (peer_vni, healed_vni)
            assert harness.docker_wait_ping(daemon, n1["container_id"], G2_IP, attempts=5)["loss"] == 0
        finally:
            _ip("link", "del", "gvxsquat")

        print(".. deleting the link leaves no tunnel or bridge behind on either machine")
        compute.call("DELETE", f"/projects/{pid}/links/{lid}")
        assert not harness.tap_exists(vx1)
        assert not harness.tap_exists(bridge)
        assert not fabric.iface_exists(vx2), f"tunnel device {vx2} survived on the peer"
        assert fabric.bridge_members(bridge) is None

        print(".. closing and reopening the project rebuilds the tunnel through the batch path")
        compute.call("POST", f"/projects/{pid}/close")
        compute.call("POST", f"/projects/{pid}/open")
        _start_pair(compute, pid, daemon, n1, n2)
        assert harness.tap_exists(vx1), f"tunnel device {vx1} not rebuilt on reopen"
        assert fabric.iface_exists(vx2), f"tunnel device {vx2} not rebuilt on reopen"
        assert harness.docker_wait_ping(daemon, n1["container_id"], G2_IP, attempts=5)["loss"] == 0

        failed = False
    finally:
        keep = failed and harness.keep_on_failure()
        if not keep:
            peer.stop()
        if pid is not None:
            harness.release(server, pid, failed=failed)
        else:
            server.stop()
        if keep:
            print(f"\n!! kept the fabric {fabric.netns} (and its peer compute) for inspection")
        else:
            fabric.teardown()
