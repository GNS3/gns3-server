#
# Copyright (C) 2026 GNS3 Technologies Inc.
# This program is free software and is redistributed under the same terms as gns3-server.
# See the LICENSE file for licensing information.
#

"""
Live end-to-end test for the QEMU node's kernel datapath (pytest marker
``e2e``): two real IOSv routers (a real qcow2 image run by the local qemu
binary, the real IOS CLI behind the server's telnet console), driven through
the controller REST API. QEMU is the node type whose guest leg *is* the
anchor: uBridge creates one persistent TAP per adapter before launch and
hands it to this user, and QEMU opens it by ifname as its netdev
(``-netdev tap,ifname=...,script=no,downscript=no``) — no userspace hop, no
port bridge, the anchor is the NIC's host side.

* two QEMU nodes on one compute report ``kernel_datapath`` when the
  compute's uBridge can create persistent TAPs (``ubridge_tap``); the
  anchors (``gq`` TAPs, one per adapter) exist from node start, before any
  link — and the per-link bridge enslaves exactly the two of them;
* real ICMP crosses the [QEMU netdev ↔ TAP] anchor;
* the L2-anchor spec §E.2 silence window with the guests shut (the anchors
  here are QEMU's own netdevs);
* a ``delay 100`` filter lands as netem on both anchors, RTT grows ~200 ms;
* suspend admin-downs the anchor (the e1000 loses carrier) and kills the
  traffic; resume restores;
* a capture on the kernel link writes a real pcap;
* link delete releases the anchor from the bridge and it survives (the
  running VM holds it open) — re-creating the link re-enslaves it and the
  traffic returns;
* node stop deletes every anchor of the node together with the orphan
  bridges; a restart recreates the TAPs and rewires the link from the NIO;
* deleting the project leaves no anchors and no bridges behind.

``test_qemu_relay_control`` is the negative control on an isolated
relay-configured instance: the anchors still exist (a QEMU node creates its
adapter TAPs at start whenever uBridge can), but nothing is enslaved — the
relay attaches the anchor itself as an AF_PACKET endpoint, so it stays up
and carrying while the link rides the uBridge relay. This differs from
IOU's relay, where the fabric socket carries the traffic and the anchors
sit idle: QEMU has no other leg, the TAP is the netdev either way.

Every checkpoint runs dual-stack: the IOSv guests carry a ULA v6 address
next to their v4 one and each checkpoint pings both families.
"""

import re
import time

import pytest

from tests.e2e import harness

pytestmark = pytest.mark.e2e

# One NIC per adapter, port number always 0: adapter 0 is GigabitEthernet0/0.
ETH = (0, 0)
# IOSv boots a real IOS from an emulated disk — slower than IOU (the boot
# wait is event-driven; this is only the failure cap).
BOOT_TIMEOUT = 480

# L3 images only (an IOSv-L2 image switchports its interfaces). The first
# is the image on this host the kernel datapath was validated with.
IMAGE_PREFERENCE = ("vios-adventerprisek9-m.spa.159-3.m12.qcow2",)
GUEST_ETH_IF = "GigabitEthernet0/0"

# the dual-stack half: a ULA mirroring 10.1.1.x
R1_IP6 = "fd00:1:1::1"
R2_IP6 = "fd00:1:1::2"


def _pick_image(server):
    images = server.compute.qemu_images()
    for name in IMAGE_PREFERENCE:
        if name in images:
            return name
    l3 = next(
        (name for name in images if "vios" in name.lower() and "l2" not in name.lower() and name.endswith(".qcow2")),
        None,
    )
    if not l3:
        pytest.skip(f"no L3 IOSv qcow2 available on this server (images: {images[:5]})")
    return l3


def _boot(server, project_id, node_id, timeout=BOOT_TIMEOUT):
    console = harness.ios_console(server, project_id, node_id)
    console.boot_wait(timeout=timeout)
    return console


def _eth_shutdown(console, shut):
    """Shut/unshut the guest's GigabitEthernet0/0 — the only legitimate
    speaker on the link segment (IOSv's own chatter) — for §E.2's silence
    window; the address stays configured and answers once it is back."""
    console.run("conf t")
    console.run(f"interface {GUEST_ETH_IF}")
    console.run("shutdown" if shut else "no shutdown")
    console.run("end")


def test_qemu_kernel_datapath():
    server = harness.live_server(kernel=True)
    compute = server.compute
    caps = compute.capabilities()
    if caps.get("ubridge_tap") is not True:
        pytest.skip(
            f"this compute's uBridge cannot create the QEMU adapter TAPs (ubridge_tap={caps.get('ubridge_tap')})"
        )
    image = _pick_image(server)

    project = compute.create_project("qemu-e2e")
    pid = project["project_id"]
    a1 = a2 = None
    try:
        n1 = compute.create_qemu_node(pid, "E2E-R1", image)
        n2 = compute.create_qemu_node(pid, "E2E-R2", image)
        n1_id, n2_id = n1["node_id"], n2["node_id"]
        a1 = harness.qemu_anchor_name(n1_id, *ETH)
        a2 = harness.qemu_anchor_name(n2_id, *ETH)

        # The link is created while both nodes are stopped: the kernel NIO
        # is bound with no anchors in existence yet and wired by node start
        # (the deferred-wiring path).
        link = compute.create_link(pid, (n1_id, *ETH), (n2_id, *ETH))
        lid = link["link_id"]
        bridge = harness.link_bridge_name(lid)
        assert link["kernel_datapath"] is True, link
        assert not harness.tap_exists(a1), "anchors must not exist before start"

        print(f".. starting IOSv routers on {image} (a real IOS boot — the slow leg of this scenario)")
        compute.call("POST", f"/projects/{pid}/nodes/{n1_id}/start")
        compute.call("POST", f"/projects/{pid}/nodes/{n2_id}/start")
        c1 = _boot(server, pid, n1_id)
        c2 = _boot(server, pid, n2_id)

        # NetworkManager can release an NM-managed TAP from its bridge after
        # (re-)enslavement (docs/bugs/networkmanager-tap-release.md); take the
        # anchors out of its reach for the rest of the run (the restart below
        # re-attaches them under fresh devices).
        harness.unmanage_from_networkmanager(a1, a2, harness.qemu_anchor_name(n1_id, 1))

        # Kernel objects: one persistent TAP per adapter (both adapters of
        # router 1, the addressed one of router 2), and the per-link bridge
        # has exactly the two addressed ports.
        for adapter in range(2):
            name = harness.qemu_anchor_name(n1_id, adapter)
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

        harness.configure_ios(c1, "R1", eth_ip="10.1.1.1", eth_if=GUEST_ETH_IF, eth_ipv6=R1_IP6)
        harness.configure_ios(c2, "R2", eth_ip="10.1.1.2", eth_if=GUEST_ETH_IF, eth_ipv6=R2_IP6)
        out = c1.run("show ip int brief")
        assert re.search(r"GigabitEthernet0/0\s+10\.1\.1\.1\s+\S+\s+\S+\s+up\s+up", out), out
        out = c1.run("show ipv6 interface brief")
        assert R1_IP6.upper() in out.upper(), out  # IOS prints v6 upper-case
        print(".. both routers configured, pinging through the anchor TAPs")
        baseline = harness.wait_ping(c1, "10.1.1.2")
        assert baseline["success"] == 100, baseline["raw"]
        baseline6 = harness.wait_ping(c1, R2_IP6)
        assert baseline6["success"] == 100, baseline6["raw"]

        # L2-anchor spec §E.2: with the guests shut the anchors (QEMU's own
        # netdevs) and the per-link bridge stay silent for 5 s.
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

        # suspend: anchor admin-down — the e1000 loses carrier, the bridge
        # port is disabled and nothing crosses; resume restores
        compute.call("PUT", f"/projects/{pid}/links/{lid}", {"suspend": True})
        assert not harness.tap_up(a1)
        dead = harness.ping(c1, "10.1.1.2", repeat=3)
        assert dead["success"] == 0, dead["raw"]
        dead6 = harness.ping(c1, R2_IP6, repeat=3)
        assert dead6["success"] == 0, dead6["raw"]
        compute.call("PUT", f"/projects/{pid}/links/{lid}", {"suspend": False})
        assert harness.tap_up(a1)
        assert harness.wait_ping(c1, "10.1.1.2", attempts=5)["success"] == 100
        assert harness.wait_ping(c1, R2_IP6, attempts=5)["success"] == 100

        # capture: on the anchor, a real pcap — both families inside the window
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

        # delete / re-create the kernel link: the anchor leaves the bridge
        # but survives (the running VM holds it open — this is QEMU's own
        # netdev), and re-creating re-enslaves it without touching the VM.
        compute.call("DELETE", f"/projects/{pid}/links/{lid}")
        assert harness.bridge_members(bridge) is None
        assert harness.tap_exists(a1) and harness.tap_exists(a2)
        link = compute.create_link(pid, (n1_id, *ETH), (n2_id, *ETH))
        lid = link["link_id"]
        bridge = harness.link_bridge_name(lid)
        assert link["kernel_datapath"] is True, link
        assert harness.wait_ping(c1, "10.1.1.2", attempts=5)["success"] == 100
        assert harness.wait_ping(c1, R2_IP6, attempts=5)["success"] == 100

        # node stop: QEMU exits and uBridge deletes every anchor of the
        # node together with the orphan bridges (a stopped node must not
        # litter the host with gq devices); a restart recreates the TAPs
        # and rewires the link from the NIO that outlived it.
        print(".. stopping and restarting router 1")
        compute.call("POST", f"/projects/{pid}/nodes/{n1_id}/stop")
        second = harness.qemu_anchor_name(n1_id, 1)
        assert harness.wait_until(lambda: not harness.tap_exists(a1) and not harness.tap_exists(second), timeout=15), (
            a1,
            second,
        )
        # the per-link bridge lost this end's port; it may be gone entirely
        # (both endpoints delete it, last one wins)
        assert harness.bridge_members(bridge) in (None, [a2]), harness.bridge_members(bridge)
        compute.call("POST", f"/projects/{pid}/nodes/{n1_id}/start")
        c1.close()
        c1 = _boot(server, pid, n1_id)
        assert harness.tap_exists(a1)
        assert harness.bridge_members(bridge) == sorted([a1, a2]), harness.bridge_members(bridge)
        harness.configure_ios(c1, "R1", eth_ip="10.1.1.1", eth_if=GUEST_ETH_IF, eth_ipv6=R1_IP6)
        assert harness.wait_ping(c1, "10.1.1.2", attempts=5)["success"] == 100
        assert harness.wait_ping(c1, R2_IP6, attempts=5)["success"] == 100

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


def test_qemu_relay_control():
    """
    Negative control: the same topology with ``enable_kernel_datapath =
    false`` (an isolated instance) wires nothing into the kernel — no
    per-link bridge, no enslavement — and still pings.

    The anchors DO exist and carry: a QEMU node creates its adapter TAPs at
    start whenever uBridge can (the netdev needs them), and on the relay
    the anchor itself becomes the uBridge relay's AF_PACKET endpoint — up
    and forwarding into the relay bridge. The server configuration only
    decides whether a *link* enslaves them.
    """

    server = harness.live_server(kernel=False)
    compute = server.compute
    caps = compute.capabilities()
    if caps.get("ubridge_tap") is not True:
        pytest.skip(
            f"this compute's uBridge cannot create the QEMU adapter TAPs (ubridge_tap={caps.get('ubridge_tap')})"
        )
    image = _pick_image(server)

    project = compute.create_project("qemu-relay-e2e")
    pid = project["project_id"]
    a1 = None
    try:
        n1 = compute.create_qemu_node(pid, "E2E-R1", image)
        n2 = compute.create_qemu_node(pid, "E2E-R2", image)
        n1_id, n2_id = n1["node_id"], n2["node_id"]
        a1 = harness.qemu_anchor_name(n1_id, *ETH)

        link = compute.create_link(pid, (n1_id, *ETH), (n2_id, *ETH))
        assert link["kernel_datapath"] is False, link

        print(".. starting IOSv routers and waiting for IOS boots (relay)")
        compute.call("POST", f"/projects/{pid}/nodes/{n1_id}/start")
        compute.call("POST", f"/projects/{pid}/nodes/{n2_id}/start")
        c1 = _boot(server, pid, n1_id)
        c2 = _boot(server, pid, n2_id)

        # no kernel wiring: nobody enslaved the anchors, the per-link
        # bridge does not exist — but the anchor is up and carrying as the
        # relay's AF_PACKET endpoint
        assert harness.bridge_members(harness.link_bridge_name(link["link_id"])) is None
        assert harness.tap_exists(a1), a1
        assert harness.tap_up(a1), a1
        if harness.l2only_supported():
            # the L2 hardening is a creation-time property, not a datapath
            # one: relay anchors are pure L2 too
            harness.assert_pure_l2(a1)
        harness.configure_ios(c1, "R1", eth_ip="10.1.1.1", eth_if=GUEST_ETH_IF, eth_ipv6=R1_IP6)
        harness.configure_ios(c2, "R2", eth_ip="10.1.1.2", eth_if=GUEST_ETH_IF, eth_ipv6=R2_IP6)
        relay_ping = harness.wait_ping(c1, "10.1.1.2")
        assert relay_ping["success"] == 100, relay_ping["raw"]
        relay_ping6 = harness.wait_ping(c1, R2_IP6)
        assert relay_ping6["success"] == 100, relay_ping6["raw"]

        c1.close()
        c2.close()
    except BaseException:
        harness.release(server, pid, failed=True)
        raise
    harness.release(server, pid, failed=False)

    # deleting the project closed the nodes: the adapter TAPs go with them
    assert harness.wait_until(lambda: not harness.tap_exists(a1), timeout=15), a1
