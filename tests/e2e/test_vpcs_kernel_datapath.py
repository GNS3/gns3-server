#
# Copyright (C) 2026 GNS3 Technologies Inc.
# This program is free software and is redistributed under the same terms as gns3-server.
# See the LICENSE file for licensing information.
#

"""
Live end-to-end test for the VPCS node's kernel datapath (pytest marker
``e2e``): two real VPCS nodes (the local vpcs binary, its own TCP console
driven like a user would), linked through the controller REST API. VPCS is
the node type whose guest leg attaches to a *pre-created* anchor: uBridge
creates the persistent TAP and hands it to this user, and the vpcs process
opens it by name (``-e -d``) while ``-n`` keeps its hands off the host side
of the anchor — the same server-creates/guest-attaches shape as QEMU.

* two VPCS nodes on one compute report ``kernel_datapath`` when the
  compute's uBridge can create persistent TAPs (``ubridge_tap``) and the
  vpcs build has ``-n`` (``vpcs_tap``); the anchor (``gp`` TAP) exists from
  node start, before any link, and the per-link bridge enslaves exactly the
  two of them;
* real ICMP crosses the [vpcs tun fd ↔ anchor TAP] leg;
* the L2-anchor spec §E.1: with ``-n`` the anchor carries no address — vpcs
  never ran its ``ifconfig`` on it; §E.2 comes free: a VPCS sends nothing
  spontaneously (no CDP, no keepalive), so the silence window needs no
  guest shutdown;
* a ``delay 100`` filter lands as netem on both anchors, RTT grows ~200 ms;
* suspend admin-downs the anchor and kills the traffic; resume restores;
* a capture on the kernel link writes a real pcap;
* link delete releases the anchor from the bridge and it survives (the
  running vpcs holds it open) — re-creating the link re-enslaves it;
* node stop terminates vpcs first, then deletes the anchor (a held TAP
  refuses deletion — the order is the point); a restart recreates the TAP
  and rewires the link from the NIO;
* deleting the project leaves no anchors and no bridges behind.

``test_vpcs_relay_control`` is the negative control on an isolated
relay-configured instance: nothing is enslaved, no per-link bridge exists,
and the relay still carries the pings — with the legacy UDP tunnel on a
stock vpcs, or as an AF_PACKET endpoint on the anchor with a ``-n`` build
(the datapath a link rides is a server configuration, not a node property).
"""

import time

import pytest

from tests.e2e import harness

pytestmark = pytest.mark.e2e

# VPCS has one adapter with one port; the kernel scenario addresses it.
ETH = (0, 0)

PC1_IP = "10.1.1.1"
PC2_IP = "10.1.1.2"


def _configure(console, ip):
    console.run("set pcname E2E-PC")
    out = console.run(f"ip {ip}/24")
    assert ip in out, out


def test_vpcs_kernel_datapath():
    server = harness.live_server(kernel=True)
    compute = server.compute
    caps = compute.capabilities()
    if caps.get("ubridge_tap") is not True:
        pytest.skip(f"this compute's uBridge cannot create persistent TAPs (ubridge_tap={caps.get('ubridge_tap')})")
    if caps.get("vpcs_tap") is not True:
        pytest.skip(
            f"this compute's vpcs binary cannot anchor a kernel link (vpcs_tap={caps.get('vpcs_tap')}); "
            "point GNS3_E2E_VPCS (or the server's VPCS.vpcs_path) at a vpcs build with -n"
        )

    project = compute.create_project("vpcs-e2e")
    pid = project["project_id"]
    a1 = a2 = None
    try:
        n1 = compute.create_vpcs_node(pid, "E2E-PC1")
        n2 = compute.create_vpcs_node(pid, "E2E-PC2")
        n1_id, n2_id = n1["node_id"], n2["node_id"]
        a1 = harness.vpcs_anchor_name(n1_id, *ETH)
        a2 = harness.vpcs_anchor_name(n2_id, *ETH)

        # The link is created while both nodes are stopped: the kernel NIO
        # is bound with no anchors in existence yet and wired by node start
        # (the deferred-wiring path, same as every anchor-backed node).
        link = compute.create_link(pid, (n1_id, *ETH), (n2_id, *ETH))
        lid = link["link_id"]
        bridge = harness.link_bridge_name(lid)
        assert link["kernel_datapath"] is True, link
        assert not harness.tap_exists(a1), "anchors must not exist before start"

        compute.call("POST", f"/projects/{pid}/nodes/{n1_id}/start")
        compute.call("POST", f"/projects/{pid}/nodes/{n2_id}/start")
        assert harness.wait_until(lambda: harness.tap_exists(a1) and harness.tap_exists(a2), timeout=15), (a1, a2)
        c1 = harness.vpcs_console(server, pid, n1_id)
        c2 = harness.vpcs_console(server, pid, n2_id)

        # NetworkManager can release an NM-managed TAP from its bridge after
        # (re-)enslavement (docs/bugs/networkmanager-tap-release.md); take
        # the anchors out of its reach for the rest of the run (the restart
        # below re-attaches them under a fresh device).
        harness.unmanage_from_networkmanager(a1, a2)

        # Kernel objects: one persistent TAP per node, and the per-link
        # bridge has exactly the two anchors as members.
        assert harness.bridge_members(bridge) == sorted([a1, a2]), harness.bridge_members(bridge)

        # L2-anchor spec §E.1: with -n the anchor stays address-free — this
        # is the assertion the -n flag exists for (an upstream vpcs would
        # have ifconfig'd the anchor on the guest's `ip` command below).
        if harness.l2only_supported():
            harness.assert_pure_l2(a1)
            harness.assert_pure_l2(a2)
            harness.assert_pure_l2(bridge)
        else:
            print(".. uBridge without link l2only: skipping the §E.1 assertions")
        harness.assert_forwarding(a1)
        harness.assert_forwarding(a2)

        _configure(c1, PC1_IP)
        _configure(c2, PC2_IP)
        baseline = harness.wait_vpcs_ping(c1, PC2_IP)
        assert baseline["success"] == 100, baseline["raw"]
        reverse = harness.wait_vpcs_ping(c2, PC1_IP)
        assert reverse["success"] == 100, reverse["raw"]

        # L2-anchor spec §E.2: a VPCS speaks only when spoken to (no
        # platform chatter), so the silence window needs no guest shutdown —
        # the two anchors and the bridge must be quiet 2.5 s after the pings.
        if harness.l2only_supported():
            harness.assert_idle_silence(a1, a2, bridge)
        else:
            print(".. uBridge without link l2only: skipping the §E.2 assertion")

        # delay 100: netem on both anchors (each impairs one direction),
        # one-way ~100 ms => RTT grows by ~200 ms
        compute.call("PUT", f"/projects/{pid}/links/{lid}", {"filters": {"delay": [100]}})
        assert "netem" in harness.qdiscs(a1) and "netem" in harness.qdiscs(a2), (
            harness.qdiscs(a1),
            harness.qdiscs(a2),
        )
        delayed = harness.wait_vpcs_ping(c1, PC2_IP)
        assert delayed["success"] == 100, delayed["raw"]
        assert delayed["avg"] >= 150, (baseline, delayed)
        compute.call("PUT", f"/projects/{pid}/links/{lid}", {"filters": {}})
        assert "netem" not in harness.qdiscs(a1), harness.qdiscs(a1)
        fast = harness.wait_vpcs_ping(c1, PC2_IP)
        assert fast["success"] == 100 and fast["avg"] < harness.FAST_RTT_MS, fast

        # suspend: anchor admin-down — the tun fd writes go nowhere and
        # nothing crosses; resume restores
        compute.call("PUT", f"/projects/{pid}/links/{lid}", {"suspend": True})
        assert not harness.tap_up(a1)
        dead = harness.vpcs_ping(c1, PC2_IP, count=2, timeout=0.5)
        assert dead["success"] == 0, dead["raw"]
        compute.call("PUT", f"/projects/{pid}/links/{lid}", {"suspend": False})
        assert harness.tap_up(a1)
        assert harness.wait_vpcs_ping(c1, PC2_IP, attempts=5)["success"] == 100

        # capture: on the anchor, a real pcap
        capture = compute.call("POST", f"/projects/{pid}/links/{lid}/capture/start", {"data_link_type": "DLT_EN10MB"})
        harness.vpcs_ping(c1, PC2_IP, count=3)
        time.sleep(1)
        compute.call("POST", f"/projects/{pid}/links/{lid}/capture/stop")
        count, ethertypes = harness.pcap_records(capture["capture_file_path"])
        assert count >= 4, f"{capture['capture_file_path']}: {count} records"
        assert "0800" in ethertypes, ethertypes

        # delete / re-create the kernel link: the anchor leaves the bridge
        # but survives (the running vpcs holds it open), and re-creating
        # re-enslaves it without touching the process.
        compute.call("DELETE", f"/projects/{pid}/links/{lid}")
        assert harness.bridge_members(bridge) is None
        assert harness.tap_exists(a1) and harness.tap_exists(a2)
        link = compute.create_link(pid, (n1_id, *ETH), (n2_id, *ETH))
        lid = link["link_id"]
        bridge = harness.link_bridge_name(lid)
        assert link["kernel_datapath"] is True, link
        assert harness.wait_vpcs_ping(c1, PC2_IP, attempts=5)["success"] == 100

        # node stop: vpcs is terminated first and only then the anchor is
        # deleted (the process holds the TAP open — a held device refuses
        # deletion and would leak); a restart recreates the TAP, rewires the
        # link from the NIO that outlived it, and the reconfigured VPCS
        # pings again.
        print(".. stopping and restarting PC1")
        compute.call("POST", f"/projects/{pid}/nodes/{n1_id}/stop")
        assert harness.wait_until(lambda: not harness.tap_exists(a1), timeout=15), a1
        compute.call("POST", f"/projects/{pid}/nodes/{n1_id}/start")
        assert harness.wait_until(lambda: harness.tap_exists(a1), timeout=15), a1
        assert harness.bridge_members(bridge) == sorted([a1, a2]), harness.bridge_members(bridge)
        c1.close()
        c1 = harness.vpcs_console(server, pid, n1_id)
        _configure(c1, PC1_IP)
        assert harness.wait_vpcs_ping(c1, PC2_IP, attempts=5)["success"] == 100

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


def test_vpcs_relay_control():
    """
    Negative control: the same topology with ``enable_kernel_datapath =
    false`` (an isolated instance) wires nothing into the kernel — no
    per-link bridge, no enslavement — and still pings, with the relay
    filters served by the uBridge bridge engine.
    """

    server = harness.live_server(kernel=False)
    compute = server.compute

    project = compute.create_project("vpcs-relay-e2e")
    pid = project["project_id"]
    try:
        n1 = compute.create_vpcs_node(pid, "E2E-PC1")
        n2 = compute.create_vpcs_node(pid, "E2E-PC2")
        n1_id, n2_id = n1["node_id"], n2["node_id"]

        link = compute.create_link(pid, (n1_id, *ETH), (n2_id, *ETH))
        lid = link["link_id"]
        assert link["kernel_datapath"] is False, link

        compute.call("POST", f"/projects/{pid}/nodes/{n1_id}/start")
        compute.call("POST", f"/projects/{pid}/nodes/{n2_id}/start")
        c1 = harness.vpcs_console(server, pid, n1_id)
        c2 = harness.vpcs_console(server, pid, n2_id)
        _configure(c1, PC1_IP)
        _configure(c2, PC2_IP)

        # no kernel wiring: the per-link bridge does not exist
        assert harness.bridge_members(harness.link_bridge_name(lid)) is None
        relay_ping = harness.wait_vpcs_ping(c1, PC2_IP)
        assert relay_ping["success"] == 100, relay_ping["raw"]

        # the relay filters keep working: one uBridge bridge filters both
        # directions, delay 100 => RTT >= 150 ms
        compute.call("PUT", f"/projects/{pid}/links/{lid}", {"filters": {"delay": [100]}})
        delayed = harness.wait_vpcs_ping(c1, PC2_IP)
        assert delayed["success"] == 100, delayed["raw"]
        assert delayed["avg"] >= 150, delayed

        c1.close()
        c2.close()
    except BaseException:
        harness.release(server, pid, failed=True)
        raise
    harness.release(server, pid, failed=False)
