#
# Copyright (C) 2026 GNS3 Technologies Inc.
#
# This program is free software and is redistributed under the same terms as gns3-server.
# See the LICENSE file for licensing information.
#

"""
Live end-to-end test for the IOU node's kernel datapath (pytest marker
``e2e``): two real IOU routers (a real IOU image executed by the local
compute, the real IOS CLI behind the server's telnet console), driven
through the controller REST API. IOU has no host interface of its own: the
guest leg is the IOL fabric unix socket, and the kernel datapath buys the
*link segment* — one persistent anchor TAP per Ethernet bay/unit, a per-link
Linux bridge, kernel filters, suspend and capture.

* two IOU nodes on one compute report ``kernel_datapath`` when the compute's
  uBridge can terminate an IOL port on a persistent TAP
  (``ubridge_iol_tap``); the anchors (``gi`` TAPs, one per Ethernet
  bay/unit) exist from node start, before any link — and the per-link
  bridge enslaves exactly the two of them;
* real ICMP crosses the [IOL fabric ↔ TAP] port bridge;
* the L2-anchor spec §E.2 silence window with the guests shut;
* a ``delay 100`` filter lands as netem on both anchors, RTT grows ~200 ms;
* the classifier spot check on a TAP anchor: ``bpf`` match-drop and the
  eBPF ``frequency_drop`` every-nth mode (the Docker suite runs the full
  matrix on veth host ends);
* suspend admin-downs the anchor and kills the traffic; resume restores;
* a serial link between the same nodes never anchors (per-port exclusion):
  it stays on the relay, ``kernel_datapath`` is False, and real traffic
  still crosses it;
* link delete releases the port bridge's TAP leg and the anchor survives —
  re-creating the link swaps the leg back in and the traffic returns;
* node stop tears the anchors down (uBridge holds their fds — the IOL
  bridge goes first, then ``tap delete``); a restart recreates the whole
  wiring from the NIO, a delay filter applied before the stop included;
* deleting the project leaves no anchors and no bridges behind.

``test_iou_relay_control`` is the negative control on an isolated
relay-configured instance: the same topology rides the fabric socket ↔ UDP
relay (no per-link bridge, nothing enslaved) and still pings — with its
filters applied by the IOU-specific engine
(``iol_bridge add_packet_filter`` on the IOL port) really shaping the wire.
Its capture and markers ride the same engine
(``iol_bridge start_capture`` / ``iol_bridge add_packet_filter … mark``).
"""

import os
import re
import time

import pytest

from tests.e2e import harness

pytestmark = pytest.mark.e2e

# Ethernet0/0 is (bay 0, unit 0) — one adapter = four units. The adapter
# index runs over Ethernet and serial bays together, so with two Ethernet
# adapters the serial bays are 2 and 3: Serial2/0 is (2, 0).
ETH = (0, 0)
SERIAL = (2, 0)
BOOT_TIMEOUT = 360

# the dual-stack half of the Ethernet leg: a ULA mirroring 10.1.1.x. The
# serial leg stays v4-only (HDLC, not an Ethernet wire).
R1_IP6 = "fd00:1:1::1"
R2_IP6 = "fd00:1:1::2"

# exact ICMPv6 echo match for the relay marker: a bare "icmp6" would also
# match IOS's own control frames (DAD/MLD/NS/NA) and break the exact-count
# asserts
ICMP6_ECHO_BPF = "icmp6 and (ip6[40] == 128 or ip6[40] == 129)"

# L3 images only: an L2 switching image does not take an address on its
# switchports. The first is the image the kernel datapath was validated
# with, the second the matching 17.15 build.
IMAGE_PREFERENCE = ("x86_64_crb_linux-adventerprisek9-ms.iol", "l3-adventerprisek9-ms-17.15.01.bin")


def _pick_image(server):
    images = server.compute.iou_images()
    for name in IMAGE_PREFERENCE:
        if name in images:
            return name
    l3 = next((name for name in images if "adventerprisek9" in name and "l2" not in name.lower()), None)
    if not l3:
        pytest.skip(f"no L3 IOU image available on this server (images: {images[:5]})")
    return l3


def _boot(server, project_id, node_id, timeout=BOOT_TIMEOUT):
    console = harness.ios_console(server, project_id, node_id)
    console.boot_wait(timeout=timeout)
    return console


def _matches(marker_ws, marker_name):
    return [e for e in marker_ws.events("marker.match") if e["filter"] == marker_name]


def _eth_shutdown(console, shut):
    """Shut/unshut the guest's Ethernet0/0 — the only legitimate speaker on
    the link segment (the IOL fabric's own chatter) — for §E.2's silence
    window; the address stays configured and answers once it is back."""
    console.run("conf t")
    console.run("interface Ethernet0/0")
    console.run("shutdown" if shut else "no shutdown")
    console.run("end")


def test_iou_kernel_datapath():
    server = harness.live_server(kernel=True)
    compute = server.compute
    caps = compute.capabilities()
    if caps.get("ubridge_iol_tap") is not True or caps.get("ubridge_tap") is not True:
        pytest.skip(
            f"this compute's uBridge cannot serve the IOU anchor lifecycle "
            f"(ubridge_iol_tap={caps.get('ubridge_iol_tap')}, ubridge_tap={caps.get('ubridge_tap')})"
        )
    image = _pick_image(server)

    project = compute.create_project("iou-e2e")
    pid = project["project_id"]
    a1 = a2 = None
    try:
        n1 = compute.create_iou_node(pid, "E2E-R1", image)
        n2 = compute.create_iou_node(pid, "E2E-R2", image)
        n1_id, n2_id = n1["node_id"], n2["node_id"]
        a1 = harness.iou_anchor_name(n1_id, *ETH)
        a2 = harness.iou_anchor_name(n2_id, *ETH)

        # The link is created while both nodes are stopped: the kernel NIO
        # is bound with no anchors in existence yet and wired by node start
        # (the deferred-wiring path).
        link = compute.create_link(pid, (n1_id, *ETH), (n2_id, *ETH))
        lid = link["link_id"]
        bridge = harness.link_bridge_name(lid)
        assert link["kernel_datapath"] is True, link
        assert not harness.tap_exists(a1), "anchors must not exist before start"

        print(f".. starting routers on {image} and waiting for IOS boots")
        compute.call("POST", f"/projects/{pid}/nodes/{n1_id}/start")
        compute.call("POST", f"/projects/{pid}/nodes/{n2_id}/start")
        c1 = _boot(server, pid, n1_id)
        c2 = _boot(server, pid, n2_id)

        # NetworkManager can release an NM-managed TAP from its bridge after
        # (re-)enslavement (docs/bugs/networkmanager-tap-release.md); take the
        # anchors out of its reach for the rest of the run.
        harness.unmanage_from_networkmanager(a1, a2)

        # Kernel objects: the anchors are one persistent TAP per Ethernet
        # bay/unit, born with the node (all eight — the IOU port model),
        # and the per-link bridge has exactly the two addressed ports.
        for adapter in range(2):
            for port in range(4):
                name = harness.iou_anchor_name(n1_id, adapter, port)
                assert harness.tap_exists(name), name
        assert harness.tap_exists(a2), a2
        assert harness.bridge_members(bridge) == sorted([a1, a2]), harness.bridge_members(bridge)

        # L2-anchor spec §E.1: anchors and the per-link bridge carry no L3
        # identity (skipped on a uBridge without `link l2only`), and both
        # ports are FORWARDING — the silent-failure guard.
        if harness.l2only_supported():
            harness.assert_pure_l2(a1)
            harness.assert_pure_l2(a2)
            harness.assert_pure_l2(bridge)
        else:
            print(".. uBridge without link l2only: skipping the §E.1 assertions")
        harness.assert_forwarding(a1)
        harness.assert_forwarding(a2)

        harness.configure_ios(c1, "R1", eth_ip="10.1.1.1", eth_if="Ethernet0/0", eth_ipv6=R1_IP6)
        harness.configure_ios(c2, "R2", eth_ip="10.1.1.2", eth_if="Ethernet0/0", eth_ipv6=R2_IP6)
        out = c1.run("show ip int brief")
        assert re.search(r"Ethernet0/0\s+10\.1\.1\.1\s+\S+\s+\S+\s+up\s+up", out), out
        out = c1.run("show ipv6 interface brief")
        assert R1_IP6.upper() in out.upper(), out  # IOS prints v6 upper-case
        print(".. both routers configured, pinging through the [IOL fabric <-> TAP] port bridge")
        baseline = harness.wait_ping(c1, "10.1.1.2")
        assert baseline["success"] == 100, baseline["raw"]
        baseline6 = harness.wait_ping(c1, R2_IP6)
        assert baseline6["success"] == 100, baseline6["raw"]

        # L2-anchor spec §E.2: with the guests shut the anchors and the
        # per-link bridge stay silent for 5 s (these anchors are the `tap
        # create` persistent TAPs, one per Ethernet bay/unit).
        if harness.l2only_supported():
            for console in (c1, c2):
                _eth_shutdown(console, shut=True)
            harness.assert_idle_silence(a1, a2, bridge)
            for console in (c1, c2):
                _eth_shutdown(console, shut=False)
            assert harness.wait_ping(c1, "10.1.1.2", attempts=5)["success"] == 100
            assert harness.wait_ping(c1, R2_IP6, attempts=5)["success"] == 100
        else:
            print(".. uBridge without link l2only: skipping the §E.2 assertion")

        # delay 100: netem on both anchors (each impairs one direction),
        # one-way ~100 ms => RTT grows by ~200 ms
        compute.call("PUT", f"/projects/{pid}/links/{lid}", {"filters": {"delay": [100]}})
        assert "netem" in harness.qdiscs(a1) and "netem" in harness.qdiscs(a2), (
            harness.qdiscs(a1),
            harness.qdiscs(a2),
        )
        delayed = harness.wait_ping(c1, "10.1.1.2")
        assert delayed["success"] == 100, delayed["raw"]
        assert delayed["avg"] >= 150, (baseline, delayed)
        delayed6 = harness.wait_ping(c1, R2_IP6)
        assert delayed6["success"] == 100, delayed6["raw"]
        assert delayed6["avg"] >= 150, (baseline6, delayed6)
        compute.call("PUT", f"/projects/{pid}/links/{lid}", {"filters": {}})
        assert "netem" not in harness.qdiscs(a1), harness.qdiscs(a1)
        fast = harness.wait_ping(c1, "10.1.1.2")
        assert fast["success"] == 100 and fast["avg"] < harness.FAST_RTT_MS, fast
        fast6 = harness.wait_ping(c1, R2_IP6)
        assert fast6["success"] == 100 and fast6["avg"] < harness.FAST_RTT_MS, fast6

        # Classifier spot check on a TAP anchor (the Docker suite runs the
        # full matrix on veth host ends): cls_bpf match-drop and the eBPF
        # stateful classifier attach to a tun/tap anchor the same way.
        tc_caps = (caps or {}).get("ubridge_tc") or {}
        if tc_caps.get("cbpf"):
            print(".. bpf 'icmp' drops v4 ICMP only on the TAP anchor")
            compute.call("PUT", f"/projects/{pid}/links/{lid}", {"filters": {"bpf": ["icmp"]}})
            assert "clsact" in harness.qdiscs(a1) and "clsact" in harness.qdiscs(a2), (
                harness.qdiscs(a1),
                harness.qdiscs(a2),
            )
            blocked = harness.ping(c1, "10.1.1.2", repeat=4)
            assert blocked["success"] == 0, blocked["raw"]
            v6_alive = harness.wait_ping(c1, R2_IP6)
            assert v6_alive["success"] == 100, v6_alive["raw"]
            print(".. bpf 'icmp6' drops v6 ICMP only on the TAP anchor")
            compute.call("PUT", f"/projects/{pid}/links/{lid}", {"filters": {"bpf": ["icmp6"]}})
            v4_alive = harness.wait_ping(c1, "10.1.1.2")
            assert v4_alive["success"] == 100, v4_alive["raw"]
            blocked6 = harness.ping(c1, R2_IP6, repeat=4)
            assert blocked6["success"] == 0, blocked6["raw"]
            compute.call("PUT", f"/projects/{pid}/links/{lid}", {"filters": {}})
            assert "clsact" not in harness.qdiscs(a1), harness.qdiscs(a1)
            assert harness.wait_ping(c1, "10.1.1.2")["success"] == 100
            assert harness.wait_ping(c1, R2_IP6)["success"] == 100
        else:
            print(".. uBridge reports no cbpf: skipping the bpf check")

        modes = tc_caps.get("ebpf_modes") or []
        if "nth" in modes:
            print(".. frequency_drop 3 (eBPF nth) on the TAP anchor")
            compute.call("PUT", f"/projects/{pid}/links/{lid}", {"filters": {"frequency_drop": [3]}})
            nth = harness.ping(c1, "10.1.1.2", repeat=9)
            loss = 100 - nth["success"]
            print(f"..   {loss} % round-trip loss")
            # the kernel counts per direction: 1 - (2/3)^2 = 55.6 % round trip
            assert 20 <= loss <= 90, nth["raw"]
            nth6 = harness.ping(c1, R2_IP6, repeat=9)
            loss6 = 100 - nth6["success"]
            print(f"..   {loss6} % round-trip loss (v6)")
            assert 20 <= loss6 <= 90, nth6["raw"]
            compute.call("PUT", f"/projects/{pid}/links/{lid}", {"filters": {}})
            assert harness.wait_ping(c1, "10.1.1.2")["success"] == 100
            assert harness.wait_ping(c1, R2_IP6)["success"] == 100
        else:
            print(".. uBridge reports no eBPF nth: skipping the frequency_drop check")

        # suspend: anchor admin-down (the port bridge's TAP writes fail EIO,
        # nothing comes back); resume restores
        compute.call("PUT", f"/projects/{pid}/links/{lid}", {"suspend": True})
        assert not harness.tap_up(a1)
        dead = harness.ping(c1, "10.1.1.2", repeat=3)
        assert dead["success"] == 0, dead["raw"]
        dead6 = harness.ping(c1, R2_IP6, repeat=3)
        assert dead6["success"] == 0, dead6["raw"]
        compute.call("PUT", f"/projects/{pid}/links/{lid}", {"suspend": False})
        assert harness.tap_up(a1)
        assert harness.wait_ping(c1, "10.1.1.2")["success"] == 100
        assert harness.wait_ping(c1, R2_IP6)["success"] == 100

        # capture: AF_PACKET on the anchor writes a real pcap — both
        # families inside the window
        capture = compute.call("POST", f"/projects/{pid}/links/{lid}/capture/start", {"data_link_type": "DLT_EN10MB"})
        harness.ping(c1, "10.1.1.2")
        harness.ping(c1, R2_IP6)
        time.sleep(1)
        compute.call("POST", f"/projects/{pid}/links/{lid}/capture/stop")
        path = capture["capture_file_path"]
        count, ethertypes = harness.pcap_records(path)
        assert count >= 8, f"{path}: {count} records"
        assert "0800" in ethertypes, (path, ethertypes)
        assert "86dd" in ethertypes, (path, ethertypes)

        # serial link between the same nodes: per-port exclusion keeps it on
        # the relay, where the real traffic still crosses (IOU-specific —
        # serial bays never anchor)
        serial = compute.create_link(pid, (n1_id, *SERIAL), (n2_id, *SERIAL))
        assert serial["kernel_datapath"] is False, serial
        harness.configure_ios(c1, "R1", serial_ip="10.2.2.1", serial_if="Serial2/0", clock=True)
        harness.configure_ios(c2, "R2", serial_ip="10.2.2.2", serial_if="Serial2/0")
        relay_ping = harness.wait_ping(c1, "10.2.2.2")
        assert relay_ping["success"] == 100, relay_ping["raw"]
        compute.call("DELETE", f"/projects/{pid}/links/{serial['link_id']}")

        # delete / re-create the kernel link: the port bridge's TAP leg is
        # released (stop -> delete_nio_tap), the anchor survives (the node
        # owns it), and re-creating swaps the leg back in — the fabric
        # socket binding never re-binds across the churn.
        compute.call("DELETE", f"/projects/{pid}/links/{lid}")
        assert harness.bridge_members(bridge) is None
        assert harness.tap_exists(a1) and harness.tap_exists(a2)
        link = compute.create_link(pid, (n1_id, *ETH), (n2_id, *ETH))
        lid = link["link_id"]
        bridge = harness.link_bridge_name(lid)
        assert link["kernel_datapath"] is True, link
        assert harness.wait_ping(c1, "10.1.1.2", attempts=5)["success"] == 100
        assert harness.wait_ping(c1, R2_IP6, attempts=5)["success"] == 100

        # node stop: uBridge holds the anchor fds, so the IOL bridge goes
        # first and the taps with it (a stopped node must not litter the
        # host with gi devices); a restart recreates the whole wiring from
        # the NIO that outlived it — *including the NIO's filters*, which
        # land on the freshly created anchor. The delay filter goes on
        # before the stop so the restart has something to restore.
        print(".. stopping and restarting router 1 with a delay filter applied")
        compute.call("PUT", f"/projects/{pid}/links/{lid}", {"filters": {"delay": [100]}})
        compute.call("POST", f"/projects/{pid}/nodes/{n1_id}/stop")
        assert harness.wait_until(lambda: not harness.tap_exists(a1), timeout=15), a1
        # the per-link bridge lost this end's port; it may be gone entirely
        # (both endpoints delete it, last one wins)
        assert harness.bridge_members(bridge) in (None, [a2]), harness.bridge_members(bridge)
        compute.call("POST", f"/projects/{pid}/nodes/{n1_id}/start")
        c1.close()
        c1 = _boot(server, pid, n1_id)
        assert harness.tap_exists(a1)
        assert harness.bridge_members(bridge) == sorted([a1, a2]), harness.bridge_members(bridge)
        assert harness.wait_until(lambda: "netem" in harness.qdiscs(a1), timeout=15), harness.qdiscs(a1)
        harness.configure_ios(c1, "R1", eth_ip="10.1.1.1", eth_if="Ethernet0/0", eth_ipv6=R1_IP6)
        survivor = harness.wait_ping(c1, "10.1.1.2", attempts=5)
        assert survivor["success"] == 100, survivor["raw"]
        assert survivor["avg"] >= 150, (baseline, survivor)
        survivor6 = harness.wait_ping(c1, R2_IP6, attempts=5)
        assert survivor6["success"] == 100, survivor6["raw"]
        assert survivor6["avg"] >= 150, (baseline6, survivor6)
        compute.call("PUT", f"/projects/{pid}/links/{lid}", {"filters": {}})
        cleared = harness.ping(c1, "10.1.1.2", repeat=3)
        assert cleared["success"] == 100 and cleared["avg"] < harness.FAST_RTT_MS, (baseline, cleared)
        cleared6 = harness.ping(c1, R2_IP6, repeat=3)
        assert cleared6["success"] == 100 and cleared6["avg"] < harness.FAST_RTT_MS, (baseline6, cleared6)

        c1.close()
        c2.close()
    except BaseException:
        harness.release(server, pid, failed=True)
        raise
    harness.release(server, pid, failed=False)

    # deleting the project closed the nodes: anchors and bridges go with them
    assert harness.wait_until(lambda: not harness.tap_exists(a1) and not harness.tap_exists(a2), timeout=15), (
        a1,
        a2,
    )


def test_iou_relay_control():
    """
    Negative control: the same topology with ``enable_kernel_datapath =
    false`` (an isolated instance) wires nothing into the kernel — no
    per-link bridge, no enslavement — and still pings over the fabric
    socket ↔ UDP relay. The relay's filters ride the IOU-specific engine:
    the IOL port's userspace filter list (``iol_bridge add_packet_filter``),
    walked by both the fabric → wire and wire → fabric paths.

    Anchors DO exist here (an IOU node creates its port TAPs at start
    whenever the uBridge can terminate an IOL port on one); the server
    configuration only decides whether links are attached to them (the same
    semantics as QEMU's and Dynamips' anchors).
    """

    server = harness.live_server(kernel=False)
    compute = server.compute
    image = _pick_image(server)

    project = compute.create_project("iou-relay-e2e")
    pid = project["project_id"]
    a1 = None
    try:
        n1 = compute.create_iou_node(pid, "E2E-R1", image)
        n2 = compute.create_iou_node(pid, "E2E-R2", image)
        n1_id, n2_id = n1["node_id"], n2["node_id"]
        a1 = harness.iou_anchor_name(n1_id, *ETH)

        link = compute.create_link(pid, (n1_id, *ETH), (n2_id, *ETH))
        assert link["kernel_datapath"] is False, link

        print(".. starting routers and waiting for IOS boots (relay)")
        compute.call("POST", f"/projects/{pid}/nodes/{n1_id}/start")
        compute.call("POST", f"/projects/{pid}/nodes/{n2_id}/start")
        c1 = _boot(server, pid, n1_id)
        c2 = _boot(server, pid, n2_id)

        # no kernel wiring: the anchor (if born) is nobody's bridge port
        assert harness.bridge_members(harness.link_bridge_name(link["link_id"])) is None
        if harness.tap_exists(a1):
            assert not harness.tap_up(a1), a1
            if harness.l2only_supported():
                # the L2 hardening is a creation-time property, not a
                # datapath one: relay anchors are pure L2 too
                harness.assert_pure_l2(a1)
        harness.configure_ios(c1, "R1", eth_ip="10.1.1.1", eth_if="Ethernet0/0", eth_ipv6=R1_IP6)
        harness.configure_ios(c2, "R2", eth_ip="10.1.1.2", eth_if="Ethernet0/0", eth_ipv6=R2_IP6)
        relay_ping = harness.wait_ping(c1, "10.1.1.2")
        assert relay_ping["success"] == 100, relay_ping["raw"]
        relay_ping6 = harness.wait_ping(c1, R2_IP6)
        assert relay_ping6["success"] == 100, relay_ping6["raw"]

        # The relay link's filters really shape the wire on the IOU engine
        # too. delay 100: one delay line per direction (the port's IOL and
        # NIO sides are separate lines), so the RTT grows by ~200 ms.
        lid = link["link_id"]
        offered = {entry["type"] for entry in compute.call("GET", f"/projects/{pid}/links/{lid}/available_filters")}
        assert "delay" in offered and "frequency_drop" in offered, offered

        print(".. iol_bridge relay filter: delay 100 ms (per-direction delay lines, RTT +~200 ms)")
        compute.call("PUT", f"/projects/{pid}/links/{lid}", {"filters": {"delay": [100]}})
        delayed = harness.ping(c1, "10.1.1.2", repeat=5)
        assert delayed["success"] == 100, delayed["raw"]
        assert delayed["avg"] >= 150, (relay_ping, delayed)
        delayed6 = harness.ping(c1, R2_IP6, repeat=5)
        assert delayed6["success"] == 100, delayed6["raw"]
        assert delayed6["avg"] >= 150, (relay_ping6, delayed6)
        compute.call("PUT", f"/projects/{pid}/links/{lid}", {"filters": {}})
        fast = harness.ping(c1, "10.1.1.2", repeat=3)
        assert fast["success"] == 100 and fast["avg"] < harness.FAST_RTT_MS, (relay_ping, fast)
        fast6 = harness.ping(c1, R2_IP6, repeat=3)
        assert fast6["success"] == 100 and fast6["avg"] < harness.FAST_RTT_MS, (relay_ping6, fast6)

        # frequency_drop shares one counter between the port's two
        # directions: on an alternating ping stream one whole direction dies
        # (same semantics as the plain relay's bridge filters).
        print(".. iol_bridge relay filter: frequency_drop 2 (shared counter, one direction dies)")
        compute.call("PUT", f"/projects/{pid}/links/{lid}", {"filters": {"frequency_drop": [2]}})
        dropped = harness.ping(c1, "10.1.1.2", repeat=6)
        print(f"..   success {dropped['success']} %")
        assert dropped["success"] <= 50, dropped["raw"]
        dropped6 = harness.ping(c1, R2_IP6, repeat=6)
        print(f"..   success {dropped6['success']} % (v6)")
        assert dropped6["success"] <= 50, dropped6["raw"]
        compute.call("PUT", f"/projects/{pid}/links/{lid}", {"filters": {}})
        recovered = harness.wait_ping(c1, "10.1.1.2")
        assert recovered["success"] == 100, recovered["raw"]
        recovered6 = harness.wait_ping(c1, R2_IP6)
        assert recovered6["success"] == 100, recovered6["raw"]

        # capture on the relay: iol_bridge start_capture on the port's IOL
        # location (the IOU engine's own capture path, distinct from the
        # kernel datapath's capture start_kernel on the anchor)
        print(".. iol_bridge relay capture: start_capture writes the ICMP exchange")
        capture = compute.call("POST", f"/projects/{pid}/links/{lid}/capture/start", {"data_link_type": "DLT_EN10MB"})
        harness.ping(c1, "10.1.1.2", repeat=5)
        harness.ping(c1, R2_IP6, repeat=5)
        time.sleep(1)
        compute.call("POST", f"/projects/{pid}/links/{lid}/capture/stop")
        path = capture["capture_file_path"]
        count, ethertypes = harness.pcap_records(path)
        assert count >= 8, f"{path}: {count} records"
        assert "0800" in ethertypes, (path, ethertypes)
        assert "86dd" in ethertypes, (path, ethertypes)

        # markers on the relay: iol_bridge add_packet_filter ... mark on the
        # port's IOL location, signalled over the dedicated marker WS
        print(".. iol_bridge relay markers: 5 v4 + 5 v6 ICMP echoes through mark filters")
        marker_ws = harness.WebSocketCollector(server, f"/projects/{pid}/notifications/markers/ws")
        try:
            m = compute.call(
                "POST",
                f"/projects/{pid}/links/{lid}/markers",
                {"name": "m-icmp", "bpf": "icmp", "tag": 4242, "capture_node_id": n1_id},
            )
            assert m["capture_node_id"] == n1_id and m["enabled"] is True, m
            m6 = compute.call(
                "POST",
                f"/projects/{pid}/links/{lid}/markers",
                {"name": "m-icmp6", "bpf": ICMP6_ECHO_BPF, "tag": 4243, "capture_node_id": n1_id},
            )
            assert m6["capture_node_id"] == n1_id and m6["enabled"] is True, m6
            result = harness.ping(c1, "10.1.1.2", repeat=5)
            assert result["success"] == 100, result["raw"]
            result6 = harness.ping(c1, R2_IP6, repeat=5)
            assert result6["success"] == 100, result6["raw"]
            harness.wait_until(
                lambda: len(_matches(marker_ws, "m-icmp")) >= 10 and len(_matches(marker_ws, "m-icmp6")) >= 10,
                timeout=10,
            )
            # exact counts across both families: neither marker sees the
            # other family's frames
            icmp = _matches(marker_ws, "m-icmp")
            assert len(icmp) == 10, len(icmp)  # 5 requests + 5 replies
            icmp6 = _matches(marker_ws, "m-icmp6")
            assert len(icmp6) == 10, len(icmp6)
            assert {e["dir"] for e in icmp} == {"tx", "rx"}, [e["dir"] for e in icmp]
            assert {e["dir"] for e in icmp6} == {"tx", "rx"}, [e["dir"] for e in icmp6]
            for event in icmp:
                assert event["node_id"] == n1_id, event
                assert event["link_id"] == lid, event
                assert event["tag"] == 4242, event
            for event in icmp6:
                assert event["node_id"] == n1_id, event
                assert event["link_id"] == lid, event
                assert event["tag"] == 4243, event
            markers_dir = os.path.join(compute.call("GET", f"/projects/{pid}")["path"], "project-files", "markers")
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
            # deleting a marker removes its pcap with it
            compute.call("DELETE", f"/projects/{pid}/links/{lid}/markers/m-icmp6")
            assert harness.wait_until(lambda: not os.path.exists(pcap6), timeout=10), pcap6
            compute.call("DELETE", f"/projects/{pid}/links/{lid}/markers/m-icmp")
            assert harness.wait_until(lambda: not os.path.exists(pcap), timeout=10), pcap
        finally:
            marker_ws.close()

        c1.close()
        c2.close()
    except BaseException:
        harness.release(server, pid, failed=True)
        raise
    harness.release(server, pid, failed=False)

    # deleting the project closed the nodes: the port TAPs go with them
    assert harness.wait_until(lambda: not harness.tap_exists(a1), timeout=15), a1
