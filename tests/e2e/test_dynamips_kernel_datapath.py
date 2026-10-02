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
Live end-to-end test for the Dynamips kernel datapath (pytest marker
``e2e``): two real c7200 routers on a real IOS image, one Ethernet link on
the kernel path and one serial link on the relay, driven through the
controller REST API and the IOS consoles. Real ICMP proves the datapath:

* the link reports ``kernel_datapath`` and the per-link kernel bridge on
  this host has exactly the two anchor TAPs enslaved (kernel objects, not
  server bookkeeping);
* a ``delay 100`` filter shows up as netem on the anchors and the measured
  RTT rises by ~2x100 ms; clearing it resets the qdiscs and the RTT;
* suspend drives the anchor administratively down and the pings stop;
* capture writes a pcap full of ICMP frames;
* a serial link between the same routers stays on the relay and still
  pings (the relay regression net);
* deleting / re-creating the link, and stopping / starting a router, leave
  the wiring consistent;
* deleting the project leaves no anchors or bridges behind.

``test_dynamips_relay_control`` is the negative control: the same topology
on an isolated relay-configured instance wires nothing into the kernel — no
per-link bridge, nothing enslaved — and still pings, so the kernel objects
above can only come from the kernel datapath. (The anchors themselves exist
on both: they are the adapter's port interfaces, created by node start
whenever the tap module is available, exactly like QEMU's TAPs.)
"""

import re
import time

import pytest

from tests.e2e import harness

pytestmark = pytest.mark.e2e

# c7200 slot 0 is the fixed IO slot; the Ethernet PA goes in slot 1 (two
# FE ports) and the serial PA in slot 2 (four ports).
SLOTS = {"slot1": "PA-2FE-TX", "slot2": "PA-4T+"}
ETH = (1, 0)
SERIAL = (2, 0)


def _pick_image(server):
    images = server.compute.dynamips_images()
    image = next((name for name in images if name.startswith("c7200")), None)
    if not image:
        pytest.skip(f"no c7200 image available on this server (images: {images[:5]})")
    return image


def _boot(server, project_id, node_id, timeout=360):
    console = harness.dynamips_console(server, project_id, node_id)
    console.boot_wait(timeout=timeout)
    return console


def _eth_shutdown(console, shut):
    console.run("conf t")
    console.run("interface f1/0")
    console.run("shutdown" if shut else "no shutdown")
    console.run("end")


def test_dynamips_kernel_datapath():
    server = harness.live_server(kernel=True)
    compute = server.compute
    if compute.capabilities().get("ubridge_tap") is not True:
        pytest.skip("this compute's uBridge cannot create persistent TAPs (ubridge_tap != True)")
    image = _pick_image(server)

    project = compute.create_project("dyn-e2e")
    pid = project["project_id"]
    t1 = t2 = None
    try:
        r1 = compute.create_dynamips_router(pid, "E2E-R1", image, SLOTS)
        r2 = compute.create_dynamips_router(pid, "E2E-R2", image, SLOTS)
        r1_id, r2_id = r1["node_id"], r2["node_id"]
        t1 = harness.anchor_name(r1_id, *ETH)
        t2 = harness.anchor_name(r2_id, *ETH)

        # The link is created while both routers are stopped: the kernel NIO
        # is bound with no anchors in existence yet and attached by node
        # start (the deferred-wiring path).
        link = compute.create_link(pid, (r1_id, *ETH), (r2_id, *ETH))
        lid = link["link_id"]
        bridge = harness.link_bridge_name(lid)
        assert link["kernel_datapath"] is True, link
        assert not harness.tap_exists(t1), "anchors must not exist before start"

        print(".. starting routers and waiting for IOS boots")
        compute.call("POST", f"/projects/{pid}/nodes/{r1_id}/start")
        compute.call("POST", f"/projects/{pid}/nodes/{r2_id}/start")
        c1 = _boot(server, pid, r1_id)
        c2 = _boot(server, pid, r2_id)

        # Kernel objects: anchors exist and the per-link bridge has exactly
        # the two of them enslaved.
        assert harness.tap_exists(t1) and harness.tap_exists(t2), (t1, t2)
        assert harness.bridge_members(bridge) == sorted([t1, t2]), harness.bridge_members(bridge)

        # L2-anchor spec §E.1: anchors and the per-link bridge carry no L3
        # identity (skipped on a uBridge without `link l2only` — the spec's
        # degradation), and both ports are FORWARDING — the silent-failure
        # guard against a bridge device left DOWN.
        if harness.l2only_supported():
            harness.assert_pure_l2(t1)
            harness.assert_pure_l2(t2)
            harness.assert_pure_l2(bridge)
        else:
            print(".. uBridge without link l2only: skipping the §E.1 assertions")
        harness.assert_forwarding(t1)
        harness.assert_forwarding(t2)

        harness.configure_ios(c1, "R1", eth_ip="10.1.1.1")
        harness.configure_ios(c2, "R2", eth_ip="10.1.1.2")
        out = c1.run("show ip int brief")
        assert re.search(r"FastEthernet1/0\s+10\.1\.1\.1\s+\S+\s+\S+\s+up\s+up", out), out
        print(".. both routers configured, pinging over the kernel link")
        baseline = harness.wait_ping(c1, "10.1.1.2")
        assert baseline["success"] == 100, baseline["raw"]

        # L2-anchor spec §E.2: shut the guest interfaces (silencing IOS's own
        # CDP/keepalives — the only legitimate speakers on the segment) and
        # demand the host side stays silent for 5 s: without the hardening
        # the host's own MLD/DAD noise floods the link (6 frames / 2 s).
        if harness.l2only_supported():
            for console in (c1, c2):
                _eth_shutdown(console, shut=True)
            harness.assert_idle_silence(t1, t2, bridge)
            for console in (c1, c2):
                _eth_shutdown(console, shut=False)
            assert harness.wait_ping(c1, "10.1.1.2", attempts=5)["success"] == 100

        # delay 100: netem on both anchors (each impairs one direction),
        # one-way ~100 ms => RTT grows by ~200 ms
        compute.call("PUT", f"/projects/{pid}/links/{lid}", {"filters": {"delay": [100]}})
        assert "netem" in harness.qdiscs(t1) and "netem" in harness.qdiscs(t2), (
            harness.qdiscs(t1),
            harness.qdiscs(t2),
        )
        delayed = harness.wait_ping(c1, "10.1.1.2")
        assert delayed["success"] == 100, delayed["raw"]
        assert delayed["avg"] >= 150, (baseline, delayed)
        compute.call("PUT", f"/projects/{pid}/links/{lid}", {"filters": {}})
        assert "netem" not in harness.qdiscs(t1), harness.qdiscs(t1)
        fast = harness.wait_ping(c1, "10.1.1.2")
        assert fast["success"] == 100 and fast["avg"] < 50, fast

        # suspend: anchor admin-down, traffic dead; resume restores it
        compute.call("PUT", f"/projects/{pid}/links/{lid}", {"suspend": True})
        assert not harness.tap_up(t1)
        dead = harness.ping(c1, "10.1.1.2", repeat=3)
        assert dead["success"] == 0, dead["raw"]
        compute.call("PUT", f"/projects/{pid}/links/{lid}", {"suspend": False})
        assert harness.tap_up(t1)
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

        # serial link between the same routers: per-port exclusion keeps it
        # on the relay, where the real traffic still crosses
        serial = compute.create_link(pid, (r1_id, *SERIAL), (r2_id, *SERIAL))
        assert serial["kernel_datapath"] is False, serial
        harness.configure_ios(c1, "R1", serial_ip="10.2.2.1", clock=True)
        harness.configure_ios(c2, "R2", serial_ip="10.2.2.2")
        relay_ping = harness.wait_ping(c1, "10.2.2.2")
        assert relay_ping["success"] == 100, relay_ping["raw"]
        compute.call("DELETE", f"/projects/{pid}/links/{serial['link_id']}")

        # delete / re-create the kernel link: anchors survive, the bridge
        # goes and comes back
        compute.call("DELETE", f"/projects/{pid}/links/{lid}")
        assert harness.bridge_members(bridge) is None
        assert harness.tap_exists(t1) and harness.tap_exists(t2)
        link = compute.create_link(pid, (r1_id, *ETH), (r2_id, *ETH))
        lid = link["link_id"]
        bridge = harness.link_bridge_name(lid)
        assert link["kernel_datapath"] is True, link
        assert harness.wait_ping(c1, "10.1.1.2", attempts=5)["success"] == 100

        # stop / start keeps the whole wiring (the Dynamips hypervisor
        # outlives ``vm stop``); the restarted router just reboots and is
        # reconfigured
        print(".. stopping and restarting R1")
        compute.call("POST", f"/projects/{pid}/nodes/{r1_id}/stop")
        assert harness.tap_exists(t1)
        assert harness.bridge_members(bridge) == sorted([t1, t2])
        compute.call("POST", f"/projects/{pid}/nodes/{r1_id}/start")
        c1.close()
        c1 = _boot(server, pid, r1_id)
        assert harness.bridge_members(bridge) == sorted([t1, t2])
        harness.configure_ios(c1, "R1", eth_ip="10.1.1.1")
        assert harness.wait_ping(c1, "10.1.1.2", attempts=5)["success"] == 100

        c1.close()
        c2.close()
    except BaseException:
        harness.release(server, pid, failed=True)
        raise
    harness.release(server, pid, failed=False)

    # deleting the project closes the nodes: anchors and bridges go with them
    assert harness.wait_until(lambda: not harness.tap_exists(t1) and not harness.tap_exists(t2), timeout=15), (
        t1,
        t2,
    )
    assert harness.wait_until(lambda: harness.bridge_members(bridge) is None, timeout=10), bridge


def test_dynamips_relay_control():
    """Negative control: the same topology with ``enable_kernel_datapath =
    false`` (an isolated instance) wires nothing into the kernel — no
    per-link bridge, no enslavement — and still pings over the relay.

    Anchors DO exist here (a Dynamips router creates its port TAPs at start
    whenever the uBridge tap module is available — they are the adapter's
    interfaces, exactly like QEMU's); the server configuration only decides
    whether links are attached to them."""
    server = harness.live_server(kernel=False)
    compute = server.compute
    image = _pick_image(server)

    project = compute.create_project("dyn-e2e-relay")
    pid = project["project_id"]
    t1 = None
    try:
        r1 = compute.create_dynamips_router(pid, "E2E-R1", image, SLOTS)
        r2 = compute.create_dynamips_router(pid, "E2E-R2", image, SLOTS)
        r1_id, r2_id = r1["node_id"], r2["node_id"]
        t1 = harness.anchor_name(r1_id, *ETH)

        link = compute.create_link(pid, (r1_id, *ETH), (r2_id, *ETH))
        lid = link["link_id"]
        assert link["kernel_datapath"] is False, link

        print(".. starting routers and waiting for IOS boots (relay)")
        compute.call("POST", f"/projects/{pid}/nodes/{r1_id}/start")
        compute.call("POST", f"/projects/{pid}/nodes/{r2_id}/start")
        c1 = _boot(server, pid, r1_id)
        c2 = _boot(server, pid, r2_id)

        # no per-link kernel bridge on the relay: nothing is enslaved, the
        # anchor (if present) is just an idle port interface
        assert harness.bridge_members(harness.link_bridge_name(lid)) is None
        if harness.tap_exists(t1):
            assert not harness.tap_up(t1), "an unattached relay anchor should sit down"
            if harness.l2only_supported():
                # the L2 hardening is a creation-time property, not a
                # datapath one: relay anchors are pure L2 too
                harness.assert_pure_l2(t1)

        harness.configure_ios(c1, "R1", eth_ip="10.1.1.1")
        harness.configure_ios(c2, "R2", eth_ip="10.1.1.2")
        relay_ping = harness.wait_ping(c1, "10.1.1.2")
        assert relay_ping["success"] == 100, relay_ping["raw"]

        c1.close()
        c2.close()
    except BaseException:
        harness.release(server, pid, failed=True)
        raise
    harness.release(server, pid, failed=False)

    assert harness.wait_until(lambda: not harness.tap_exists(t1), timeout=15), t1
