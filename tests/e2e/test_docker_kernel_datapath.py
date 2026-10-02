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
Live end-to-end tests for the standard Docker node's kernel datapath (pytest
marker ``e2e``): two real Alpine containers, addressed from the host the way
a GNS3 user does (the node's persistent ``/etc/network/interfaces``, applied
by the container's init.sh) and driven through the Docker daemon socket the
server itself uses. The scenarios cover:

* ``test_docker_kernel_fast_path`` — the veth datapath itself: the link
  reports ``kernel_datapath``, the per-link kernel bridge enslaves exactly
  the two veth host ends, real ICMP crosses kernel-only, the L2-anchor spec
  §E assertions hold (no L3 identity, FORWARDING ports, idle silence), a
  ``delay 100`` filter lands as netem on both host ends, suspend kills the
  traffic at the carrier, capture writes a real pcap, link delete/re-create
  and container stop/start leave the wiring consistent, and deleting the
  project leaves no veth or bridge behind.
* ``test_docker_kernel_filter_matrix`` — one filter type at a time on a live
  kernel link, each asserted by its effect on real traffic (RTT, loss,
  per-seq outage evidence) and its tc state, from netem core and the netem
  extensions to the cls_bpf and eBPF classifiers; the kernel-only types are
  offered by ``available_filters`` and everything restores cleanly.
* ``test_docker_relay_control`` — the negative control on an isolated
  relay-configured instance: no per-link kernel bridge, the wire is the
  uBridge relay, the kernel-only filter types are hidden — and the relay's
  own filter set (delay, frequency_drop, bpf) really shapes the wire, as
  uBridge userspace filters on the filter node's bridge
  (``bridge add_packet_filter``); its capture (``bridge start_capture``)
  and its markers (``bridge add_packet_filter … mark``) ride the same
  relay engine, not the kernel datapath's AF_PACKET modules.
* ``test_docker_relay_to_kernel_reopen_upgrade`` — the server's datapath
  choice is flipped (relay → kernel) across a restart and the project is
  reopened: the link is rebuilt on the kernel datapath and forwards.

The image is pinned by digest (``harness.ensure_docker_image``): a cached
copy costs no network, a miss pulls through the server's own pull route,
and no cache + no registry skips the scenario.
"""

import os
import re
import time

import pytest

from tests.e2e import harness

pytestmark = pytest.mark.e2e

# every standard Docker adapter has a single port
ETH = (0, 0)
R1_IP = "10.1.1.1"
R2_IP = "10.1.1.2"


def _resolve_container(daemon, node):
    """Fill in the node's container id from the daemon (the controller's
    node payload does not carry the compute-side id), by the deterministic
    name the server gives the container."""
    container_id = daemon.container_id(f"GNS3.{node['name']}.{node['project_id']}")
    assert container_id, f"container for {node['name']} not found on the Docker daemon"
    node["container_id"] = container_id
    return node


def _create_topology(server, pid, image, name):
    """Two containers with addressed eth0s. The harness reaches their guests
    through the Docker daemon socket — the same socket the server uses."""
    compute = server.compute
    daemon = harness.DockerDaemon()
    nodes = []
    for suffix, address in (("1", R1_IP), ("2", R2_IP)):
        node = compute.create_docker_node(pid, f"{name}-{suffix}", image)
        harness.configure_docker_interfaces(node, address)
        nodes.append(_resolve_container(daemon, node))
    return nodes[0], nodes[1], daemon


def _start_addresses(compute, pid, daemon, nodes, addresses):
    """Start the containers and wait for init.sh to have applied their
    addresses (busybox ifup runs a moment after container start)."""
    for node in nodes:
        compute.call("POST", f"/projects/{pid}/nodes/{node['node_id']}/start")
    for node, address in zip(nodes, addresses, strict=False):
        harness.docker_wait_address(daemon, node["container_id"], address)


def _put_filters(compute, pid, lid, filters):
    compute.call("PUT", f"/projects/{pid}/links/{lid}", {"filters": filters})


def _clear_filters(compute, pid, lid, *anchors):
    """Clear the link's filters and assert the teardown reached the kernel:
    no netem qdisc and no clsact left on the anchors."""
    _put_filters(compute, pid, lid, {})
    for anchor in anchors:
        assert "netem" not in harness.qdiscs(anchor), harness.qdiscs(anchor)
        assert "clsact" not in harness.qdiscs(anchor), harness.qdiscs(anchor)


def _filter_types(compute, pid, lid):
    return {entry["type"] for entry in compute.call("GET", f"/projects/{pid}/links/{lid}/available_filters")}


def _matches(marker_ws, marker_name):
    return [e for e in marker_ws.events("marker.match") if e["filter"] == marker_name]


def _silence_guest(daemon, container_id):
    """Silence the guest for the idle-silence measurement — the docker
    analogue of shutting the IOS interfaces in the dynamips scenario. The
    link goes down first (a guest's own chatter is not just IPv6: Linux
    re-sends its boot-time IGMP membership report seconds later), then its
    IPv6 stack is switched off so the re-up does not re-fire DAD/MLD. The
    IPv4 address stays configured and answers once the link is back."""
    code, output = daemon.exec(
        container_id,
        ["sh", "-c", "ip link set eth0 down && echo 1 > /proc/sys/net/ipv6/conf/eth0/disable_ipv6"],
    )
    assert code == 0, output


def _unsilence_guest(daemon, container_id):
    code, output = daemon.exec(container_id, ["ip", "link", "set", "eth0", "up"])
    assert code == 0, output


def test_docker_kernel_fast_path():
    server = harness.live_server(kernel=True)
    compute = server.compute
    image = harness.ensure_docker_image(server)

    project = compute.create_project("docker-e2e")
    pid = project["project_id"]
    a1 = a2 = bridge = None
    try:
        n1, n2, daemon = _create_topology(server, pid, image, "E2E")
        n1_id, n2_id = n1["node_id"], n2["node_id"]
        c1, c2 = n1["container_id"], n2["container_id"]
        a1 = harness.docker_anchor_name(n1_id, *ETH)
        a2 = harness.docker_anchor_name(n2_id, *ETH)

        # The link is created while both containers are stopped: the kernel
        # NIO is bound with no anchors in existence yet and attached by
        # container start (the deferred-wiring path).
        link = compute.create_link(pid, (n1_id, *ETH), (n2_id, *ETH))
        lid = link["link_id"]
        bridge = harness.link_bridge_name(lid)
        assert link["kernel_datapath"] is True, link
        assert not harness.tap_exists(a1), "the veth pair is born at container start"

        print(".. starting containers")
        _start_addresses(compute, pid, daemon, (n1, n2), (R1_IP, R2_IP))

        # Kernel objects: the veth host ends exist and the per-link bridge
        # enslaves exactly the two of them.
        assert harness.tap_exists(a1) and harness.tap_exists(a2), (a1, a2)
        assert harness.bridge_members(bridge) == sorted([a1, a2]), harness.bridge_members(bridge)

        # L2-anchor spec §E.1 (anchors and bridge carry no L3 identity;
        # skipped on a uBridge without `link l2only`) and the forwarding
        # guard — a DOWN bridge silently forwards nothing.
        if harness.l2only_supported():
            harness.assert_pure_l2(a1)
            harness.assert_pure_l2(a2)
            harness.assert_pure_l2(bridge)
        else:
            print(".. uBridge without link l2only: skipping the §E.1 assertions")
        harness.assert_forwarding(a1)
        harness.assert_forwarding(a2)

        print(".. pinging between the containers over the kernel link")
        baseline = harness.docker_wait_ping(daemon, c1, R2_IP)
        assert baseline["loss"] == 0, baseline["raw"]
        assert baseline["avg"] is not None and baseline["avg"] < 50, baseline

        # §E.2: with the guests silenced the segment is silent for 5 s —
        # the host anchors do not generate the MLD/DAD flood an unhardened
        # device produces (baseline: 6 frames / 2 s).
        if harness.l2only_supported():
            _silence_guest(daemon, c1)
            _silence_guest(daemon, c2)
            harness.assert_idle_silence(a1, a2, bridge)
            _unsilence_guest(daemon, c1)
            _unsilence_guest(daemon, c2)
            assert harness.docker_wait_ping(daemon, c1, R2_IP, attempts=5)["loss"] == 0

        # delay 100: netem on both host ends (each impairs one direction),
        # one-way ~100 ms => RTT grows by ~200 ms
        _put_filters(compute, pid, lid, {"delay": [100]})
        assert "netem" in harness.qdiscs(a1) and "netem" in harness.qdiscs(a2), (
            harness.qdiscs(a1),
            harness.qdiscs(a2),
        )
        delayed = harness.docker_wait_ping(daemon, c1, R2_IP)
        assert delayed["loss"] == 0 and delayed["avg"] >= 150, (baseline, delayed)
        _put_filters(compute, pid, lid, {})
        assert "netem" not in harness.qdiscs(a1), harness.qdiscs(a1)
        fast = harness.docker_wait_ping(daemon, c1, R2_IP)
        assert fast["loss"] == 0 and fast["avg"] < 50, fast

        # suspend: the host end admin-downs (carrier loss into the
        # container), the link is dead; resume restores
        compute.call("PUT", f"/projects/{pid}/links/{lid}", {"suspend": True})
        assert not harness.tap_up(a1)
        dead = harness.docker_ping(daemon, c1, R2_IP, count=3, timeout=1)
        assert dead["loss"] == 100, dead["raw"]
        compute.call("PUT", f"/projects/{pid}/links/{lid}", {"suspend": False})
        assert harness.tap_up(a1)
        assert harness.docker_wait_ping(daemon, c1, R2_IP)["loss"] == 0

        # capture: AF_PACKET on the anchor writes a real pcap
        capture = compute.call("POST", f"/projects/{pid}/links/{lid}/capture/start", {"data_link_type": "DLT_EN10MB"})
        harness.docker_ping(daemon, c1, R2_IP)
        time.sleep(1)
        compute.call("POST", f"/projects/{pid}/links/{lid}/capture/stop")
        path = capture["capture_file_path"]
        count, ethertypes = harness.pcap_records(path)
        assert count >= 4, f"{path}: {count} records"
        assert "0800" in ethertypes, (path, ethertypes)

        # link delete detaches both ends (the veths survive — they are the
        # adapters); re-creating enslaves them again and the traffic returns
        compute.call("DELETE", f"/projects/{pid}/links/{lid}")
        assert harness.bridge_members(bridge) is None
        assert harness.tap_exists(a1) and harness.tap_exists(a2)
        link = compute.create_link(pid, (n1_id, *ETH), (n2_id, *ETH))
        lid = link["link_id"]
        bridge = harness.link_bridge_name(lid)
        assert link["kernel_datapath"] is True, link
        assert harness.docker_wait_ping(daemon, c1, R2_IP, attempts=5)["loss"] == 0

        # container stop: the veth host ends are deleted explicitly (a veth
        # outlives its container's netns) and the bridge goes with them; a
        # restart rebuilds the whole wiring from the NIO
        print(".. stopping and restarting container 1")
        compute.call("POST", f"/projects/{pid}/nodes/{n1_id}/stop")
        assert harness.wait_until(lambda: not harness.tap_exists(a1), timeout=15), a1
        assert harness.bridge_members(bridge) in (None, [a2]), harness.bridge_members(bridge)
        compute.call("POST", f"/projects/{pid}/nodes/{n1_id}/start")
        harness.docker_wait_address(daemon, c1, R1_IP)
        assert harness.tap_exists(a1)
        assert harness.wait_until(lambda: harness.bridge_members(bridge) == sorted([a1, a2]), timeout=15)
        assert harness.docker_wait_ping(daemon, c1, R2_IP, attempts=5)["loss"] == 0
    except BaseException:
        harness.release(server, pid, failed=True)
        raise
    harness.release(server, pid, failed=False)

    # deleting the project closed the containers: veths and bridges go
    assert harness.wait_until(lambda: not harness.tap_exists(a1) and not harness.tap_exists(a2), timeout=15), (
        a1,
        a2,
    )
    assert harness.wait_until(lambda: harness.bridge_members(bridge) is None, timeout=10), bridge


def test_docker_kernel_filter_matrix():
    """One filter type at a time on a live kernel link, each asserted by its
    effect on real traffic and its tc state. Types the uBridge on this
    compute cannot serve (bpf without cbpf, the eBPF modes without ebpf) are
    skipped rather than failed — the capability chain is ``available_filters``'
    contract, and a compute reporting nothing keeps the full list."""
    server = harness.live_server(kernel=True)
    compute = server.compute
    caps = (compute.capabilities() or {}).get("ubridge_tc") or {}
    image = harness.ensure_docker_image(server)

    project = compute.create_project("docker-filter-e2e")
    pid = project["project_id"]
    try:
        n1, n2, daemon = _create_topology(server, pid, image, "E2E")
        n1_id, n2_id = n1["node_id"], n2["node_id"]
        c1 = n1["container_id"]
        a1 = harness.docker_anchor_name(n1_id, *ETH)
        a2 = harness.docker_anchor_name(n2_id, *ETH)

        link = compute.create_link(pid, (n1_id, *ETH), (n2_id, *ETH))
        lid = link["link_id"]
        assert link["kernel_datapath"] is True, link

        _start_addresses(compute, pid, daemon, (n1, n2), (R1_IP, R2_IP))
        baseline = harness.docker_wait_ping(daemon, c1, R2_IP)
        assert baseline["loss"] == 0, baseline["raw"]

        # The kernel link offers the kernel-only types the compute's uBridge
        # reports it can run (all of them on this uBridge).
        offered = _filter_types(compute, pid, lid)
        assert {"delay", "packet_loss", "corrupt", "duplicate", "bpf"} <= offered, offered
        if not {"rate", "reorder", "gemodel", "seed", "limit"} & offered:
            pytest.skip(f"this compute's uBridge reports no netem extensions: {sorted(offered)}")

        # -- netem core ----------------------------------------------------
        print(".. delay 100")
        _put_filters(compute, pid, lid, {"delay": [100]})
        assert "netem" in harness.qdiscs(a1) and "netem" in harness.qdiscs(a2), (
            harness.qdiscs(a1),
            harness.qdiscs(a2),
        )
        delayed = harness.docker_ping(daemon, c1, R2_IP)
        print(f"..   {delayed['avg']} ms RTT")
        assert delayed["loss"] == 0 and delayed["avg"] >= 150, (baseline, delayed)

        print(".. delay 50 jitter 20 distribution normal")
        _put_filters(compute, pid, lid, {"delay": [50, 20, "normal"]})
        # the jitter parameter lands verbatim...; the sampled RTT mean is a
        # random variable (per-direction ~N(50, 20)), so only the elevation
        # is asserted, with margin — 10 packets put the sample mean's sigma
        # around 9 ms
        assert re.search(r"delay 50ms\s+20ms", harness.qdiscs(a1)), harness.qdiscs(a1)
        jittered = harness.docker_ping(daemon, c1, R2_IP, count=10)
        print(f"..   {jittered['avg']} ms RTT")
        assert jittered["loss"] == 0 and jittered["avg"] >= 65, jittered
        _clear_filters(compute, pid, lid, a1, a2)

        print(".. packet_loss 30")
        _put_filters(compute, pid, lid, {"packet_loss": [30]})
        lossy = harness.docker_ping(daemon, c1, R2_IP, count=20)
        print(f"..   {lossy['loss']} % round-trip loss")
        # round trip = 1 - 0.7^2 ~ 51 %; the stochastic draw must land
        # somewhere between "clearly lossy" and "not a black hole"
        assert 20 <= lossy["loss"] <= 80, lossy["raw"]
        _clear_filters(compute, pid, lid, a1, a2)

        print(".. corrupt 30")
        _put_filters(compute, pid, lid, {"corrupt": [30]})
        assert "corrupt 30%" in harness.qdiscs(a1), harness.qdiscs(a1)
        # a corrupted frame fails its checksum and is dropped: the same
        # round-trip arithmetic as packet_loss (1 - 0.7^2)
        corrupt = harness.docker_ping(daemon, c1, R2_IP, count=20)
        print(f"..   {corrupt['loss']} % round-trip loss")
        assert 20 <= corrupt["loss"] <= 80, corrupt["raw"]
        _clear_filters(compute, pid, lid, a1, a2)

        print(".. duplicate 50")
        _put_filters(compute, pid, lid, {"duplicate": [50]})
        assert "dup" in harness.qdiscs(a1), harness.qdiscs(a1)
        # duplicated frames are absorbed by the stack: no loss, traffic flows
        dups = harness.docker_ping(daemon, c1, R2_IP, count=5)
        assert dups["loss"] == 0, dups["raw"]
        _clear_filters(compute, pid, lid, a1, a2)

        # -- netem extensions (kernel-only) --------------------------------
        print(".. delay 50 + reorder 25 correl 50 gap 5")
        _put_filters(compute, pid, lid, {"delay": [50], "reorder": [25, 50, 5]})
        assert "reorder" in harness.qdiscs(a1), harness.qdiscs(a1)
        reordered = harness.docker_ping(daemon, c1, R2_IP, count=10)
        assert reordered["loss"] <= 60, reordered["raw"]
        _clear_filters(compute, pid, lid, a1, a2)

        print(".. delay 50 + seed 42 + limit 5000")
        _put_filters(compute, pid, lid, {"delay": [50], "seed": [42], "limit": [5000]})
        assert "limit 5000" in harness.qdiscs(a1), harness.qdiscs(a1)
        seeded = harness.docker_ping(daemon, c1, R2_IP)
        assert seeded["loss"] == 0 and seeded["avg"] >= 80, seeded
        _clear_filters(compute, pid, lid, a1, a2)

        print(".. gemodel 100/0/30 (steady-state bad, 30 % loss)")
        _put_filters(compute, pid, lid, {"gemodel": [100, 0, 30]})
        assert "gemodel" in harness.qdiscs(a1), harness.qdiscs(a1)
        gemodel = harness.docker_ping(daemon, c1, R2_IP, count=20)
        print(f"..   {gemodel['loss']} % round-trip loss")
        assert 20 <= gemodel["loss"] <= 90, gemodel["raw"]
        _clear_filters(compute, pid, lid, a1, a2)

        print(".. rate 512kbit (1400-byte pings)")
        _put_filters(compute, pid, lid, {"rate": ["512kbit"]})
        assert "rate" in harness.qdiscs(a1).lower(), harness.qdiscs(a1)
        # 1400+28 bytes at 512 kbit ≈ 22 ms serialization per direction
        rated = harness.docker_ping(daemon, c1, R2_IP, size=1400)
        print(f"..   {rated['avg']} ms RTT")
        assert rated["loss"] == 0 and rated["avg"] >= 30, (baseline, rated)
        _clear_filters(compute, pid, lid, a1, a2)

        # -- cls_bpf match-drop --------------------------------------------
        if caps.get("cbpf"):
            print(".. bpf 'icmp' drops everything")
            _put_filters(compute, pid, lid, {"bpf": ["icmp"]})
            assert "clsact" in harness.qdiscs(a1), harness.qdiscs(a1)
            dropped = harness.docker_ping(daemon, c1, R2_IP, count=4)
            assert dropped["loss"] == 100, dropped["raw"]

            print(".. bpf 'greater 150' discriminates by frame size")
            _put_filters(compute, pid, lid, {"bpf": ["greater 150"]})
            small = harness.docker_ping(daemon, c1, R2_IP, count=4)
            assert small["loss"] == 0, small["raw"]
            big = harness.docker_ping(daemon, c1, R2_IP, count=4, size=300)
            assert big["loss"] == 100, big["raw"]
            _clear_filters(compute, pid, lid, a1, a2)
        else:
            print(".. uBridge reports no cbpf: skipping the bpf filter checks")

        # -- eBPF stateful classifier --------------------------------------
        modes = caps.get("ebpf_modes") or []
        if "nth" in modes:
            print(".. frequency_drop 3 (every 3rd packet per direction)")
            _put_filters(compute, pid, lid, {"frequency_drop": [3]})
            nth = harness.docker_ping(daemon, c1, R2_IP, count=20)
            print(f"..   {nth['loss']} % round-trip loss")
            # kernel counts per direction: 1 - (2/3)^2 = 55.6 % round trip
            assert 30 <= nth["loss"] <= 80, nth["raw"]
            _put_filters(compute, pid, lid, {"frequency_drop": [-1]})
            all_dropped = harness.docker_ping(daemon, c1, R2_IP, count=4)
            assert all_dropped["loss"] == 100, all_dropped["raw"]
            _clear_filters(compute, pid, lid, a1, a2)
        if "quota" in modes:
            print(".. quota 3000 bytes hard cutoff")
            _put_filters(compute, pid, lid, {"quota": [3000, 100]})
            # 1400-byte pings: the per-direction byte caps run out after
            # ~2 packets, then nothing passes until the quota is reset
            cut = harness.docker_ping(daemon, c1, R2_IP, count=5, size=1400)
            assert cut["loss"] >= 40, cut["raw"]
            after = harness.docker_ping(daemon, c1, R2_IP, count=4)
            assert after["loss"] == 100, after["raw"]
            _clear_filters(compute, pid, lid, a1, a2)
            assert harness.docker_ping(daemon, c1, R2_IP, count=4)["loss"] == 0
        if "window" in modes:
            print(".. window_drop [1000, 2000, 100] — one outage with passes on both sides")
            _put_filters(compute, pid, lid, {"window_drop": [1000, 2000, 100]})
            # 25 pings at 5/s: seqs before t=1 s and after t=3 s answer, the
            # middle is gone — per-sequence evidence of a bounded outage
            code, output = daemon.exec(c1, ["ping", "-c", "25", "-i", "0.2", "-W", "1", R2_IP], timeout=30)
            replied = {int(m.group(1)) for m in re.finditer(r"seq=(\d+)", output)}
            missing = set(range(25)) - replied
            assert 0 in replied and 24 in replied, (sorted(replied), output)
            assert missing and max(missing) - min(missing) >= 5, (sorted(replied), output)
            _clear_filters(compute, pid, lid, a1, a2)
            assert harness.docker_ping(daemon, c1, R2_IP, count=4)["loss"] == 0
    except BaseException:
        harness.release(server, pid, failed=True)
        raise
    harness.release(server, pid, failed=False)

    assert harness.wait_until(lambda: not harness.tap_exists(a1) and not harness.tap_exists(a2), timeout=15), (
        a1,
        a2,
    )


def test_docker_relay_control():
    """Negative control: the same topology on an isolated relay-configured
    instance wires nothing into the kernel — no per-link bridge, no
    enslavement — and still pings over the uBridge UDP relay, its filters,
    capture and markers all riding the relay engine."""
    server = harness.live_server(kernel=False)
    compute = server.compute
    image = harness.ensure_docker_image(server)

    project = compute.create_project("docker-relay-e2e")
    pid = project["project_id"]
    a1 = None
    try:
        n1, n2, daemon = _create_topology(server, pid, image, "E2E")
        n1_id, n2_id = n1["node_id"], n2["node_id"]
        a1 = harness.docker_anchor_name(n1_id, *ETH)

        link = compute.create_link(pid, (n1_id, *ETH), (n2_id, *ETH))
        assert link["kernel_datapath"] is False, link

        _start_addresses(compute, pid, daemon, (n1, n2), (R1_IP, R2_IP))

        # No kernel wiring: no per-link bridge, the veth host end is just a
        # relay endpoint (up, pure L2 — the hardening is a creation-time
        # property, not a datapath one)
        assert harness.bridge_members(harness.link_bridge_name(link["link_id"])) is None
        if harness.tap_exists(a1):
            assert harness.tap_up(a1), a1
            if harness.l2only_supported():
                harness.assert_pure_l2(a1)

        relay_ping = harness.docker_wait_ping(daemon, n1["container_id"], R2_IP)
        assert relay_ping["loss"] == 0, relay_ping["raw"]

        # available_filters hides the kernel-only types on the relay
        offered = _filter_types(compute, pid, link["link_id"])
        assert "delay" in offered and "frequency_drop" in offered, offered
        assert not (offered & {"rate", "reorder", "gemodel", "duplicate", "seed", "limit", "quota", "window_drop"}), (
            offered
        )

        # The relay's filters are real uBridge userspace filters walked by
        # the bridge's two listener threads: both directions of the wire
        # cross them. delay 100 creates one delay line per direction, so the
        # RTT grows by ~200 ms.
        print(".. relay filters: delay 100 ms (one delay line per direction, RTT +~200 ms)")
        _put_filters(compute, pid, link["link_id"], {"delay": [100]})
        harness.docker_wait_ping(daemon, n1["container_id"], R2_IP)
        delayed = harness.docker_ping(daemon, n1["container_id"], R2_IP, count=5)
        assert delayed["loss"] == 0, delayed["raw"]
        assert delayed["avg"] >= 150, (relay_ping, delayed)
        _put_filters(compute, pid, link["link_id"], {})
        fast = harness.docker_wait_ping(daemon, n1["container_id"], R2_IP)
        assert fast["loss"] == 0 and fast["avg"] < 50, (relay_ping, fast)

        # frequency_drop counts every packet crossing the bridge, both
        # directions sharing one counter, so on an alternating ping stream
        # the same direction dies on every crossing (probed against uBridge
        # directly: replies drop, round trips die wholesale). -1 is the
        # drop-everything encoding the suspend emulation uses.
        print(".. relay filters: frequency_drop 2 (shared counter, one direction dies)")
        _put_filters(compute, pid, link["link_id"], {"frequency_drop": [2]})
        dropped = harness.docker_ping(daemon, n1["container_id"], R2_IP, count=10)
        print(f"..   {dropped['loss']} % round-trip loss")
        assert dropped["loss"] >= 50, dropped["raw"]
        _put_filters(compute, pid, link["link_id"], {"frequency_drop": [-1]})
        blackholed = harness.docker_ping(daemon, n1["container_id"], R2_IP, count=4)
        assert blackholed["loss"] == 100, blackholed["raw"]

        # bpf on the relay is uBridge's libpcap userspace match-drop — a
        # different engine from the kernel datapath's cls_bpf
        print(".. relay filters: bpf 'icmp' drops every ICMP frame")
        _put_filters(compute, pid, link["link_id"], {"bpf": ["icmp"]})
        icmp_dropped = harness.docker_ping(daemon, n1["container_id"], R2_IP, count=4)
        assert icmp_dropped["loss"] == 100, icmp_dropped["raw"]
        print(".. relay filters: bpf 'greater 150' discriminates by frame size")
        _put_filters(compute, pid, link["link_id"], {"bpf": ["greater 150"]})
        small = harness.docker_ping(daemon, n1["container_id"], R2_IP, count=4)
        assert small["loss"] == 0, small["raw"]
        big = harness.docker_ping(daemon, n1["container_id"], R2_IP, count=4, size=300)
        assert big["loss"] == 100, big["raw"]
        _put_filters(compute, pid, link["link_id"], {})
        assert harness.docker_ping(daemon, n1["container_id"], R2_IP, count=5)["loss"] == 0

        # capture on the relay: the same REST call as the kernel datapath's,
        # hosted by the relay node's uBridge bridge (bridge start_capture)
        # instead of AF_PACKET on an anchor
        print(".. relay capture: bridge start_capture writes the ICMP exchange")
        capture = compute.call(
            "POST", f"/projects/{pid}/links/{link['link_id']}/capture/start", {"data_link_type": "DLT_EN10MB"}
        )
        harness.docker_ping(daemon, n1["container_id"], R2_IP)
        time.sleep(1)
        compute.call("POST", f"/projects/{pid}/links/{link['link_id']}/capture/stop")
        path = capture["capture_file_path"]
        count, ethertypes = harness.pcap_records(path)
        assert count >= 4, f"{path}: {count} records"
        assert "0800" in ethertypes, (path, ethertypes)

        # markers on the relay are uBridge's `mark` packet filter on the
        # relay bridge (bridge add_packet_filter ... mark), signalled over
        # the same dedicated marker WS — the relay engine's observability
        # path (the kernel datapath's marker add_kernel is the other one)
        print(".. relay marker: 5 ICMP echoes through a mark filter on the relay bridge")
        marker_ws = harness.WebSocketCollector(server, f"/projects/{pid}/notifications/markers/ws")
        try:
            m = compute.call(
                "POST",
                f"/projects/{pid}/links/{link['link_id']}/markers",
                {"name": "m-icmp", "bpf": "icmp", "tag": 4242, "capture_node_id": n1_id},
            )
            assert m["capture_node_id"] == n1_id and m["enabled"] is True, m
            result = harness.docker_ping(daemon, n1["container_id"], R2_IP, count=5)
            assert result["loss"] == 0, result["raw"]
            harness.wait_until(lambda: len(_matches(marker_ws, "m-icmp")) >= 10, timeout=10)
            icmp = _matches(marker_ws, "m-icmp")
            assert len(icmp) == 10, len(icmp)  # 5 requests + 5 replies
            assert {e["dir"] for e in icmp} == {"tx", "rx"}, [e["dir"] for e in icmp]
            for event in icmp:
                assert event["node_id"] == n1_id, event
                assert event["link_id"] == link["link_id"], event
                assert event["tag"] == 4242, event
                assert event["len"] == 98, event  # busybox ping frame
            # the marker's pcap on the host holds exactly the matched frames
            markers_dir = os.path.join(compute.call("GET", f"/projects/{pid}")["path"], "project-files", "markers")
            pcap = os.path.join(markers_dir, f"{n1_id}_{link['link_id']}_m-icmp.pcap")
            assert os.path.exists(pcap), os.listdir(markers_dir)
            count, ethertypes = harness.pcap_records(pcap)
            assert count == 10, count
            assert set(ethertypes) == {"0800"}, ethertypes
            # deleting the marker removes its pcap with it
            compute.call("DELETE", f"/projects/{pid}/links/{link['link_id']}/markers/m-icmp")
            assert harness.wait_until(lambda: not os.path.exists(pcap), timeout=10), pcap
        finally:
            marker_ws.close()
    except BaseException:
        harness.release(server, pid, failed=True)
        raise
    harness.release(server, pid, failed=False)

    assert harness.wait_until(lambda: not harness.tap_exists(a1), timeout=15), a1


def test_docker_relay_to_kernel_reopen_upgrade():
    """The server's datapath choice is a live decision: with the project
    created on a relay instance, flipping ``enable_kernel_datapath`` across
    a server restart and reopening the project rebuilds the link on the
    kernel datapath (the upgrade path a deployment takes) and it forwards."""
    if os.environ.get("GNS3_E2E_URL"):
        pytest.skip("this scenario restarts the server — it needs an isolated instance")
    server = harness.live_server(kernel=False)
    compute = server.compute
    image = harness.ensure_docker_image(server)

    project = compute.create_project("docker-upgrade-e2e")
    pid = project["project_id"]
    a1 = a2 = bridge = None
    try:
        n1, n2, daemon = _create_topology(server, pid, image, "E2E")
        n1_id, n2_id = n1["node_id"], n2["node_id"]
        a1 = harness.docker_anchor_name(n1_id, *ETH)
        a2 = harness.docker_anchor_name(n2_id, *ETH)

        link = compute.create_link(pid, (n1_id, *ETH), (n2_id, *ETH))
        assert link["kernel_datapath"] is False, link
        bridge = harness.link_bridge_name(link["link_id"])

        _start_addresses(compute, pid, daemon, (n1, n2), (R1_IP, R2_IP))
        assert harness.bridge_members(bridge) is None
        assert harness.docker_wait_ping(daemon, n1["container_id"], R2_IP)["loss"] == 0

        # Flip the datapath choice and reopen the project: every link
        # re-runs _prepare, which re-evaluates eligibility live.
        print(".. restarting the server with enable_kernel_datapath=True")
        server.restart(kernel=True)
        compute = server.compute
        compute.call("POST", f"/projects/{pid}/open")
        n1 = _resolve_container(daemon, compute.node(pid, n1_id))
        n2 = _resolve_container(daemon, compute.node(pid, n2_id))
        link = compute.call("GET", f"/projects/{pid}/links/{link['link_id']}")
        assert link["kernel_datapath"] is True, link
        assert not harness.tap_exists(a1), "containers are stopped after the reopen"

        _start_addresses(compute, pid, daemon, (n1, n2), (R1_IP, R2_IP))
        assert harness.wait_until(lambda: harness.bridge_members(bridge) == sorted([a1, a2]), timeout=15)
        assert harness.docker_wait_ping(daemon, n1["container_id"], R2_IP, attempts=5)["loss"] == 0
    except BaseException:
        harness.release(server, pid, failed=True)
        raise
    harness.release(server, pid, failed=False)

    assert harness.wait_until(lambda: not harness.tap_exists(a1) and not harness.tap_exists(a2), timeout=15), (
        a1,
        a2,
    )
    assert harness.wait_until(lambda: harness.bridge_members(bridge) is None, timeout=10), bridge
