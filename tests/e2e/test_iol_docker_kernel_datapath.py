#
# Copyright (C) 2026 GNS3 Technologies Inc.
#
# This program is free software and is redistributed under the same terms as gns3-server.
# See the LICENSE file for licensing information.
#

"""
Live end-to-end test for the IOL runner container's kernel datapath (pytest
marker ``e2e``): two real iol-xe containers (Cisco CML's iol-runner images,
the real IOS-XE CLI on PID 1 stdio), driven through the controller REST API
and their telnet consoles. The guest leg stays the runner's unix-socket pair
— the kernel datapath buys the *link segment*: anchor TAPs, a per-link Linux
bridge, kernel filters, suspend and capture.

* two containers on one compute report ``kernel_datapath`` when the compute's
  uBridge has both the tap module and the swappable bridge TAP leg
  (``ubridge_bridge_tap``); the anchors (``gx`` TAPs) exist from node start,
  before any link — and the per-link bridge enslaves exactly the two of them;
* real ICMP crosses the [unix ↔ TAP] port bridge relay;
* the L2-anchor spec §E.2 silence window with the guests shut — the
  behavioral half of the hardening on an anchor created by uBridge's
  bridge TAP module;
* a ``delay 100`` filter lands as netem on both anchors, RTT grows ~200 ms;
* the classifier spot check on a TAP anchor: ``bpf`` match-drop and the
  eBPF ``frequency_drop`` every-nth mode (the Docker suite runs the full
  matrix on veth host ends);
* suspend admin-downs the anchor and kills the traffic; resume restores;
* link delete releases the port bridge's TAP leg (stop → delete_nio_tap) and
  the anchor survives — re-creating the link swaps the leg back in (the
  c-socket binding never re-binds) and the traffic returns;
* node stop tears the anchors down (uBridge holds their fds — port bridges
  first, then tap delete); a restart recreates the whole wiring from the NIO;
* deleting the project leaves no anchors and no bridges behind.

``test_iol_docker_relay_control`` is the negative control on an isolated
relay-configured instance: the same topology rides unix ↔ UDP through the
uBridge relay (no anchors ever exist) and still pings.

Every checkpoint runs dual-stack: the IOS-XE guests carry a ULA v6 address
next to their v4 one and each checkpoint pings both families — including
the TAP-anchor bpf spot check (the libpcap expression is family-specific:
each drop filter is asserted to kill its own family and leave the other
alive) and the eBPF nth classifier (family-blind, asserted on both).
"""

import re
import time

import pytest

from tests.e2e import harness

pytestmark = pytest.mark.e2e

# one adapter = one 4-port unit; Ethernet0/0 is (adapter 0, port 0)
ETH = (0, 0)
BOOT_TIMEOUT = 360

# the dual-stack half: a ULA mirroring 10.1.1.x
R1_IP6 = "fd00:1:1::1"
R2_IP6 = "fd00:1:1::2"


def _pick_image(server):
    images = server.compute.docker_images()
    image = next((name for name in images if name.startswith("iol-xe/iol-xe:")), None)
    if not image:
        pytest.skip(f"no iol-xe/iol-xe image available on this server (images: {images[:5]})")
    return image


def _boot(server, project_id, node_id, timeout=BOOT_TIMEOUT):
    node = server.compute.node(project_id, node_id)
    console = harness.IOSConsole(node["console_host"], node["console"])
    # straight_prompt: IOL boots from its NVRAM startup config straight into
    # the CLI — no "Press RETURN" sentinel on this console
    console.boot_wait(timeout=timeout, straight_prompt=True)
    return console


def _eth_shutdown(console, shut):
    """Shut/unshut the guest's Ethernet0/0 — the only legitimate speaker on
    the link segment (the IOL instance's own chatter) — for §E.2's silence
    window; the address stays configured and answers once it is back."""
    console.run("conf t")
    console.run("interface Ethernet0/0")
    console.run("shutdown" if shut else "no shutdown")
    console.run("end")


def _topology(compute, pid, image, name):
    n1 = compute.create_iol_router(pid, f"{name}-1", image)
    n2 = compute.create_iol_router(pid, f"{name}-2", image)
    return n1, n2


def test_iol_docker_kernel_datapath():
    server = harness.live_server(kernel=True)
    compute = server.compute
    caps = compute.capabilities()
    if caps.get("ubridge_bridge_tap") is not True or caps.get("ubridge_tap") is not True:
        pytest.skip(
            f"this compute's uBridge cannot serve the IOL container anchor lifecycle "
            f"(ubridge_bridge_tap={caps.get('ubridge_bridge_tap')}, ubridge_tap={caps.get('ubridge_tap')})"
        )
    image = _pick_image(server)
    harness.stage_iol_base_config(server)

    project = compute.create_project("iol-e2e")
    pid = project["project_id"]
    a1 = a2 = None
    try:
        n1, n2 = _topology(compute, pid, image, "E2E")
        n1_id, n2_id = n1["node_id"], n2["node_id"]
        a1 = harness.iol_anchor_name(n1_id, *ETH)
        a2 = harness.iol_anchor_name(n2_id, *ETH)

        # The link is created while both containers are stopped: the kernel
        # NIO is bound with no anchors in existence yet and wired by node
        # start (the deferred-wiring path).
        link = compute.create_link(pid, (n1_id, *ETH), (n2_id, *ETH))
        lid = link["link_id"]
        bridge = harness.link_bridge_name(lid)
        assert link["kernel_datapath"] is True, link
        assert not harness.tap_exists(a1), "anchors must not exist before start"

        print(".. starting containers and waiting for IOS-XE boots")
        compute.call("POST", f"/projects/{pid}/nodes/{n1_id}/start")
        compute.call("POST", f"/projects/{pid}/nodes/{n2_id}/start")
        c1 = _boot(server, pid, n1_id)
        c2 = _boot(server, pid, n2_id)

        # NetworkManager can release an NM-managed TAP from its bridge after
        # (re-)enslavement (docs/bugs/networkmanager-tap-release.md); take the
        # anchors out of its reach for the rest of the run.
        harness.unmanage_from_networkmanager(a1, a2)

        # Kernel objects: anchors exist (born with the node, before the link
        # was ever wired) and the per-link bridge has exactly the two of them.
        assert harness.tap_exists(a1) and harness.tap_exists(a2), (a1, a2)
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
        print(".. both routers configured, pinging through the port-bridge swap")
        baseline = harness.wait_ping(c1, "10.1.1.2")
        assert baseline["success"] == 100, baseline["raw"]
        baseline6 = harness.wait_ping(c1, R2_IP6)
        assert baseline6["success"] == 100, baseline6["raw"]

        # L2-anchor spec §E.2: with the guests shut the anchors and the
        # per-link bridge stay silent for 5 s. These anchors come from
        # uBridge's bridge TAP module (`bridge add_nio_tap`) — the creator
        # whose missing hardening the spec caught live; this is the
        # behavioral half of that guarantee.
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

        # Classifier spot check on the container's TAP anchor (the Docker
        # suite runs the full matrix on veth host ends): cls_bpf match-drop
        # and the eBPF stateful classifier attach to a tun/tap anchor the
        # same way.
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

        # delete / re-create the kernel link: the port bridge's TAP leg is
        # released (stop -> delete_nio_tap), the anchor survives (the node
        # owns it), and re-creating swaps the leg back in — the unix binding
        # never re-binds across the churn.
        compute.call("DELETE", f"/projects/{pid}/links/{lid}")
        assert harness.bridge_members(bridge) is None
        assert harness.tap_exists(a1) and harness.tap_exists(a2)
        link = compute.create_link(pid, (n1_id, *ETH), (n2_id, *ETH))
        lid = link["link_id"]
        bridge = harness.link_bridge_name(lid)
        assert link["kernel_datapath"] is True, link
        assert harness.wait_ping(c1, "10.1.1.2", attempts=5)["success"] == 100
        assert harness.wait_ping(c1, R2_IP6, attempts=5)["success"] == 100

        # node stop: uBridge holds the anchor fds, so the port bridges go
        # first and the taps with them (a stopped container must not litter
        # the host with gx devices); a restart recreates the whole wiring
        # from the NIO that outlived it.
        print(".. stopping and restarting container 1")
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
        harness.configure_ios(c1, "R1", eth_ip="10.1.1.1", eth_if="Ethernet0/0", eth_ipv6=R1_IP6)
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


def test_iol_docker_relay_control():
    """
    Negative control: the same topology with ``enable_kernel_datapath =
    false`` (an isolated instance) wires nothing into the kernel — no
    per-link bridge, no enslavement — and still pings over the unix ↔ UDP
    relay.

    Anchors DO exist here (an IOL container creates its port TAPs at start
    whenever the uBridge tap module and the swappable leg are available);
    the server configuration only decides whether links are attached to
    them (the same semantics as QEMU's and Dynamips' anchors).
    """

    server = harness.live_server(kernel=False)
    compute = server.compute
    image = _pick_image(server)
    harness.stage_iol_base_config(server)

    project = compute.create_project("iol-relay-e2e")
    pid = project["project_id"]
    n1_id = n2_id = a1 = None
    try:
        n1, n2 = _topology(compute, pid, image, "E2E")
        n1_id, n2_id = n1["node_id"], n2["node_id"]
        a1 = harness.iol_anchor_name(n1_id, *ETH)

        link = compute.create_link(pid, (n1_id, *ETH), (n2_id, *ETH))
        assert link["kernel_datapath"] is False, link

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

        c1.close()
        c2.close()
    except BaseException:
        harness.release(server, pid, failed=True)
        raise
    harness.release(server, pid, failed=False)
