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
Live end-to-end test for the Ethernet switch kernel fast path (pytest
marker ``e2e``): a real switch (a Linux kernel bridge) between two real
c7200 routers, driven through the controller REST API and the IOS consoles.
Real ICMP crossing the switch proves the datapath:

* links created while the routers are stopped report ``kernel_datapath``
  and defer the join; once the routers boot, the controller's re-push
  makes the switch join their anchors — the switch bridge's members become
  exactly the two router anchors (no relay TAPs anywhere);
* VLAN programming applies to absorbed anchors: different access VLANs
  isolate the routers (ping dies), the same VLAN bridges them again;
* a ``delay 100`` filter lands as netem on the absorbed anchor (single
  interface, switch-owned) and the measured RTT grows by ~100 ms;
* suspend admin-downs the anchor and kills the traffic; resume restores;
* capture (hosted by the switch side) writes a pcap of ICMP records;
* deleting a link detaches the anchor (which survives — the router owns
  it) and re-creating re-joins it;
* a router stop/start keeps the wiring and the traffic;
* deleting the project removes the switch bridge and the anchors.

``test_ethernet_switch_relay_control`` is the negative control on an
isolated relay-configured instance: the same topology rides the per-port
uBridge relays (the switch bridge's members are its own relay TAPs, never
the routers' anchors) and still pings.
"""

import time

import pytest

from tests.e2e import harness

pytestmark = pytest.mark.e2e

# c7200 slot 0 is the fixed IO slot; the Ethernet PA goes in slot 1.
SLOTS = {"slot1": "PA-2FE-TX"}
ETH = (1, 0)


def _pick_image(server):
    images = server.compute.dynamips_images()
    image = next((name for name in images if name.startswith("c7200")), None)
    if not image:
        pytest.skip(f"no c7200 image available on this server (images: {images[:5]})")
    return image


def _switch_bridge_name(switch_id):
    # see EthernetSwitch._ensure_bridge
    return "gns3" + switch_id.replace("-", "")[:6]


def _create_topology(compute, pid, image, name, idlepc=None):
    switch = compute.call(
        "POST",
        f"/projects/{pid}/nodes",
        {
            "compute_id": "local",
            "name": f"{name}-SW",
            "node_type": "ethernet_switch",
            "properties": {
                "ports_mapping": [
                    {"name": "Ethernet0", "port_number": 0, "type": "access", "vlan": 1},
                    {"name": "Ethernet1", "port_number": 1, "type": "access", "vlan": 1},
                ]
            },
        },
    )
    r1 = compute.create_dynamips_router(pid, f"{name}-R1", image, SLOTS, idlepc=idlepc)
    r2 = compute.create_dynamips_router(pid, f"{name}-R2", image, SLOTS, idlepc=idlepc)
    return switch, r1, r2


def _boot(server, project_id, node_id, timeout=360):
    console = harness.ios_console(server, project_id, node_id)
    console.boot_wait(timeout=timeout)
    return console


def test_ethernet_switch_kernel_fast_path():
    server = harness.live_server(kernel=True)
    compute = server.compute
    if compute.capabilities().get("ubridge_tap") is not True:
        pytest.skip("this compute's uBridge cannot create persistent TAPs (ubridge_tap != True)")
    image = _pick_image(server)
    idlepc = harness.dynamips_idlepc(server, image)

    project = compute.create_project("esw-e2e")
    pid = project["project_id"]
    sw_bridge = None
    try:
        switch, r1, r2 = _create_topology(compute, pid, image, "E2E", idlepc)
        switch_id = switch["node_id"]
        r1_id, r2_id = r1["node_id"], r2["node_id"]
        sw_bridge = _switch_bridge_name(switch_id)
        a1 = harness.anchor_name(r1_id, *ETH)
        a2 = harness.anchor_name(r2_id, *ETH)

        # The switch bridge exists from the moment the switch node does; a
        # link against a stopped router must not fail — the join defers.
        assert harness.bridge_members(sw_bridge) == []
        link1 = compute.create_link(pid, (r1_id, *ETH), (switch_id, 0, 0))
        link2 = compute.create_link(pid, (r2_id, *ETH), (switch_id, 0, 1))
        assert link1["kernel_datapath"] is True, link1
        assert link2["kernel_datapath"] is True, link2
        assert harness.bridge_members(sw_bridge) == []

        print(".. starting routers and waiting for IOS boots")
        compute.call("POST", f"/projects/{pid}/nodes/{r1_id}/start")
        compute.call("POST", f"/projects/{pid}/nodes/{r2_id}/start")
        c1 = _boot(server, pid, r1_id)
        c2 = _boot(server, pid, r2_id)

        # Deferred joins completed by the node-start re-push: the anchors
        # ARE the switch ports now.
        assert harness.wait_until(lambda: harness.bridge_members(sw_bridge) == sorted([a1, a2]), timeout=15), (
            harness.bridge_members(sw_bridge)
        )

        harness.configure_ios(c1, "R1", eth_ip="10.1.1.1")
        harness.configure_ios(c2, "R2", eth_ip="10.1.1.2")
        print(".. both routers configured, pinging through the switch")
        baseline = harness.wait_ping(c1, "10.1.1.2")
        assert baseline["success"] == 100, baseline["raw"]

        # L2-anchor spec §E.1: the absorbed anchors and the switch bridge
        # carry no L3 identity (skipped on a uBridge without `link l2only`),
        # and the joined ports are FORWARDING — the silent-failure guard.
        if harness.l2only_supported():
            harness.assert_pure_l2(a1)
            harness.assert_pure_l2(a2)
            harness.assert_pure_l2(sw_bridge)
        else:
            print(".. uBridge without link l2only: skipping the §E.1 assertions")
        harness.assert_forwarding(a1)
        harness.assert_forwarding(a2)

        # VLAN programming on absorbed anchors: different access VLANs
        # isolate, the same VLAN bridges again.
        compute.call(
            "PUT",
            f"/projects/{pid}/nodes/{switch_id}",
            {
                "properties": {
                    "ports_mapping": [
                        {"name": "Ethernet0", "port_number": 0, "type": "access", "vlan": 10},
                        {"name": "Ethernet1", "port_number": 1, "type": "access", "vlan": 20},
                    ]
                }
            },
        )
        assert harness.bridge_members(sw_bridge) == sorted([a1, a2]), harness.bridge_members(sw_bridge)
        isolated = harness.ping(c1, "10.1.1.2", repeat=3)
        assert isolated["success"] == 0, isolated["raw"]
        assert harness.bridge_members(sw_bridge) == sorted([a1, a2]), harness.bridge_members(sw_bridge)
        compute.call(
            "PUT",
            f"/projects/{pid}/nodes/{switch_id}",
            {
                "properties": {
                    "ports_mapping": [
                        {"name": "Ethernet0", "port_number": 0, "type": "access", "vlan": 10},
                        {"name": "Ethernet1", "port_number": 1, "type": "access", "vlan": 10},
                    ]
                }
            },
        )
        rejoined = harness.wait_ping(c1, "10.1.1.2")
        assert rejoined["success"] == 100, rejoined["raw"]

        # Single-owned impairment: the filter lands on the absorbed anchor
        # (one interface — the switch's), RTT grows by ~100 ms one-way.
        compute.call("PUT", f"/projects/{pid}/links/{link1['link_id']}", {"filters": {"delay": [100]}})
        assert "netem" in harness.qdiscs(a1), harness.qdiscs(a1)
        assert "netem" not in harness.qdiscs(a2), harness.qdiscs(a2)
        delayed = harness.wait_ping(c1, "10.1.1.2")
        assert delayed["success"] == 100, delayed["raw"]
        assert 60 <= delayed["avg"] <= 250, (baseline, delayed)
        compute.call("PUT", f"/projects/{pid}/links/{link1['link_id']}", {"filters": {}})
        assert "netem" not in harness.qdiscs(a1)
        fast = harness.wait_ping(c1, "10.1.1.2")
        assert fast["success"] == 100 and fast["avg"] < 50, fast

        # suspend: the anchor admin-downs, the link is dead; resume restores
        compute.call("PUT", f"/projects/{pid}/links/{link1['link_id']}", {"suspend": True})
        assert not harness.tap_up(a1)
        dead = harness.ping(c1, "10.1.1.2", repeat=3)
        assert dead["success"] == 0, dead["raw"]
        compute.call("PUT", f"/projects/{pid}/links/{link1['link_id']}", {"suspend": False})
        assert harness.tap_up(a1)
        assert harness.wait_ping(c1, "10.1.1.2")["success"] == 100

        # capture (the controller hosts it on the switch — always-on local
        # builtin): a pcap of ICMP records written off the absorbed anchor
        capture = compute.call(
            "POST", f"/projects/{pid}/links/{link1['link_id']}/capture/start", {"data_link_type": "DLT_EN10MB"}
        )
        harness.ping(c1, "10.1.1.2")
        time.sleep(1)
        compute.call("POST", f"/projects/{pid}/links/{link1['link_id']}/capture/stop")
        count, ethertypes = harness.pcap_records(capture["capture_file_path"])
        assert count >= 4, capture["capture_file_path"]
        assert "0800" in ethertypes, ethertypes

        # link delete detaches the anchor (it survives — the router owns
        # it); re-creating re-joins it
        compute.call("DELETE", f"/projects/{pid}/links/{link2['link_id']}")
        assert harness.bridge_members(sw_bridge) == [a1]
        assert harness.tap_exists(a2)
        link2 = compute.create_link(pid, (r2_id, *ETH), (switch_id, 0, 1))
        assert link2["kernel_datapath"] is True, link2
        assert harness.wait_until(lambda: harness.bridge_members(sw_bridge) == sorted([a1, a2]), timeout=10)
        assert harness.wait_ping(c1, "10.1.1.2", attempts=5)["success"] == 100

        # router stop/start keeps the wiring: a Dynamips stop only halts the
        # emulated router — the hypervisor, the anchor and its bridge
        # membership all survive (the same stop-is-not-close semantics as
        # the per-link bridge datapath)
        print(".. stopping and restarting R1")
        compute.call("POST", f"/projects/{pid}/nodes/{r1_id}/stop")
        assert harness.tap_exists(a1)
        assert harness.bridge_members(sw_bridge) == sorted([a1, a2])
        compute.call("POST", f"/projects/{pid}/nodes/{r1_id}/start")
        c1.close()
        c1 = _boot(server, pid, r1_id)
        assert harness.wait_until(lambda: harness.bridge_members(sw_bridge) == sorted([a1, a2]), timeout=15)
        harness.configure_ios(c1, "R1", eth_ip="10.1.1.1")
        assert harness.wait_ping(c1, "10.1.1.2", attempts=5)["success"] == 100

        c1.close()
        c2.close()
    except BaseException:
        harness.release(server, pid, failed=True)
        raise
    harness.release(server, pid, failed=False)

    # project delete closed everything: switch bridge and anchors gone
    assert harness.wait_until(lambda: harness.bridge_members(sw_bridge) is None, timeout=15), sw_bridge


def test_ethernet_switch_relay_control():
    """Negative control: the same topology on an isolated relay-configured
    instance rides the per-port uBridge relays — the switch bridge's
    members are its own relay TAPs, never the routers' anchors — and still
    pings."""
    server = harness.live_server(kernel=False)
    compute = server.compute
    image = _pick_image(server)
    idlepc = harness.dynamips_idlepc(server, image)

    project = compute.create_project("esw-e2e-relay")
    pid = project["project_id"]
    sw_bridge = None
    try:
        switch, r1, r2 = _create_topology(compute, pid, image, "E2E", idlepc)
        sw_bridge = _switch_bridge_name(switch["node_id"])
        r1_id, r2_id = r1["node_id"], r2["node_id"]
        a1 = harness.anchor_name(r1_id, *ETH)

        link1 = compute.create_link(pid, (r1_id, *ETH), (switch["node_id"], 0, 0))
        link2 = compute.create_link(pid, (r2_id, *ETH), (switch["node_id"], 0, 1))
        assert link1["kernel_datapath"] is False, link1
        assert link2["kernel_datapath"] is False, link2

        print(".. starting routers and waiting for IOS boots (relay)")
        compute.call("POST", f"/projects/{pid}/nodes/{r1_id}/start")
        compute.call("POST", f"/projects/{pid}/nodes/{r2_id}/start")
        c1 = _boot(server, pid, r1_id)
        c2 = _boot(server, pid, r2_id)

        members = harness.bridge_members(sw_bridge)
        assert members == sorted([f"{sw_bridge}-0", f"{sw_bridge}-1"]), members
        assert a1 not in members
        if harness.l2only_supported():
            # creation-time hardening applies on the relay too: the switch's
            # own port TAPs and its bridge are pure L2
            for member in members:
                harness.assert_pure_l2(member)
            harness.assert_pure_l2(sw_bridge)

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

    assert harness.wait_until(lambda: harness.bridge_members(sw_bridge) is None, timeout=15), sw_bridge
