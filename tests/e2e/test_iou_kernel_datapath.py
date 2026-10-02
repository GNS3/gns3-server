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
"""

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

        harness.configure_ios(c1, "R1", eth_ip="10.1.1.1", eth_if="Ethernet0/0")
        harness.configure_ios(c2, "R2", eth_ip="10.1.1.2", eth_if="Ethernet0/0")
        out = c1.run("show ip int brief")
        assert re.search(r"Ethernet0/0\s+10\.1\.1\.1\s+\S+\s+\S+\s+up\s+up", out), out
        print(".. both routers configured, pinging through the [IOL fabric <-> TAP] port bridge")
        baseline = harness.wait_ping(c1, "10.1.1.2")
        assert baseline["success"] == 100, baseline["raw"]

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
        compute.call("PUT", f"/projects/{pid}/links/{lid}", {"filters": {}})
        assert "netem" not in harness.qdiscs(a1), harness.qdiscs(a1)
        fast = harness.wait_ping(c1, "10.1.1.2")
        assert fast["success"] == 100 and fast["avg"] < 50, fast

        # Classifier spot check on a TAP anchor (the Docker suite runs the
        # full matrix on veth host ends): cls_bpf match-drop and the eBPF
        # stateful classifier attach to a tun/tap anchor the same way.
        tc_caps = (caps or {}).get("ubridge_tc") or {}
        if tc_caps.get("cbpf"):
            print(".. bpf 'icmp' drops everything on the TAP anchor")
            compute.call("PUT", f"/projects/{pid}/links/{lid}", {"filters": {"bpf": ["icmp"]}})
            assert "clsact" in harness.qdiscs(a1) and "clsact" in harness.qdiscs(a2), (
                harness.qdiscs(a1),
                harness.qdiscs(a2),
            )
            blocked = harness.ping(c1, "10.1.1.2", repeat=4)
            assert blocked["success"] == 0, blocked["raw"]
            compute.call("PUT", f"/projects/{pid}/links/{lid}", {"filters": {}})
            assert "clsact" not in harness.qdiscs(a1), harness.qdiscs(a1)
            assert harness.wait_ping(c1, "10.1.1.2")["success"] == 100
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
            compute.call("PUT", f"/projects/{pid}/links/{lid}", {"filters": {}})
            assert harness.wait_ping(c1, "10.1.1.2")["success"] == 100
        else:
            print(".. uBridge reports no eBPF nth: skipping the frequency_drop check")

        # suspend: anchor admin-down (the port bridge's TAP writes fail EIO,
        # nothing comes back); resume restores
        compute.call("PUT", f"/projects/{pid}/links/{lid}", {"suspend": True})
        assert not harness.tap_up(a1)
        dead = harness.ping(c1, "10.1.1.2", repeat=3)
        assert dead["success"] == 0, dead["raw"]
        compute.call("PUT", f"/projects/{pid}/links/{lid}", {"suspend": False})
        assert harness.tap_up(a1)
        assert harness.wait_ping(c1, "10.1.1.2")["success"] == 100

        # capture: AF_PACKET on the anchor writes a real pcap
        capture = compute.call("POST", f"/projects/{pid}/links/{lid}/capture/start", {"data_link_type": "DLT_EN10MB"})
        harness.ping(c1, "10.1.1.2")
        time.sleep(1)
        compute.call("POST", f"/projects/{pid}/links/{lid}/capture/stop")
        path = capture["capture_file_path"]
        count, ethertypes = harness.pcap_records(path)
        assert count >= 4, f"{path}: {count} records"
        assert "0800" in ethertypes, (path, ethertypes)

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
        harness.configure_ios(c1, "R1", eth_ip="10.1.1.1", eth_if="Ethernet0/0")
        survivor = harness.wait_ping(c1, "10.1.1.2", attempts=5)
        assert survivor["success"] == 100, survivor["raw"]
        assert survivor["avg"] >= 150, (baseline, survivor)
        compute.call("PUT", f"/projects/{pid}/links/{lid}", {"filters": {}})
        cleared = harness.ping(c1, "10.1.1.2", repeat=3)
        assert cleared["success"] == 100 and cleared["avg"] < 50, (baseline, cleared)

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
        harness.configure_ios(c1, "R1", eth_ip="10.1.1.1", eth_if="Ethernet0/0")
        harness.configure_ios(c2, "R2", eth_ip="10.1.1.2", eth_if="Ethernet0/0")
        relay_ping = harness.wait_ping(c1, "10.1.1.2")
        assert relay_ping["success"] == 100, relay_ping["raw"]

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
        compute.call("PUT", f"/projects/{pid}/links/{lid}", {"filters": {}})
        fast = harness.ping(c1, "10.1.1.2", repeat=3)
        assert fast["success"] == 100 and fast["avg"] < 50, (relay_ping, fast)

        # frequency_drop shares one counter between the port's two
        # directions: on an alternating ping stream one whole direction dies
        # (same semantics as the plain relay's bridge filters).
        print(".. iol_bridge relay filter: frequency_drop 2 (shared counter, one direction dies)")
        compute.call("PUT", f"/projects/{pid}/links/{lid}", {"filters": {"frequency_drop": [2]}})
        dropped = harness.ping(c1, "10.1.1.2", repeat=6)
        print(f"..   success {dropped['success']} %")
        assert dropped["success"] <= 50, dropped["raw"]
        compute.call("PUT", f"/projects/{pid}/links/{lid}", {"filters": {}})
        recovered = harness.wait_ping(c1, "10.1.1.2")
        assert recovered["success"] == 100, recovered["raw"]

        c1.close()
        c2.close()
    except BaseException:
        harness.release(server, pid, failed=True)
        raise
    harness.release(server, pid, failed=False)

    # deleting the project closed the nodes: the port TAPs go with them
    assert harness.wait_until(lambda: not harness.tap_exists(a1), timeout=15), a1
