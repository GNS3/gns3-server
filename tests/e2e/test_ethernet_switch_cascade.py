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
Live end-to-end test for the switch-to-switch cascade kernel datapath
(pytest marker ``e2e``): two Ethernet switches (two Linux kernel bridges)
interconnected by a link-owned veth pair, with two c7200 routers hanging
off each switch. Real ICMP crossing both switches proves the datapath:

* the cascade link reports ``kernel_datapath`` and the veth pair
  (``gs<link_id[:10]>0/1``, a pure function of the link id) exists at once
  — switches are always-on, nothing defers — with each switch's bridge
  carrying exactly its own end as a member, both ends UP;
* a dot1q trunk cascade carries two VLANs at once: hosts in VLAN 10 and
  VLAN 20 ping across both switches simultaneously (tagged frames cross
  the pair, which is what a trunk means here);
* flipping both cascade ports symmetrically to access VLAN 10 (an
  in-place ``_reconfigure_port_vlan`` on each veth end) keeps VLAN 10
  flowing untagged and kills VLAN 20; restoring the trunk revives VLAN 20.
  Asymmetric flips are deliberately not tested: an access end egresses
  untagged, and the far trunk end would park those frames in its native
  VLAN — symmetric modes are the only sane inter-switch configuration;
* the L2-anchor spec §E.2 silence window with all four router interfaces
  shut: the absorbed anchors, both cascade ends and both switch bridges
  stay silent for 5 s;
* a ``delay 100`` filter lands as netem on BOTH veth ends (each direction
  impaired exactly once, like any two-sided kernel link) and the measured
  RTT grows by ~2 x 100 ms;
* suspend admin-downs both ends and kills both VLANs; resume restores;
* deleting the cascade link destroys the whole veth pair from either side
  (the host links and their anchors survive); re-creating the link mints a
  new pair under the new link id and the traffic returns without touching
  the routers;
* deleting the project removes both switch bridges, both veth pairs and
  the router anchors — zero host residue.

No relay control twin here: on the relay datapath a cascade is just two
per-port uBridge UDP relays, the machinery
``test_ethernet_switch_kernel_datapath.py::test_ethernet_switch_relay_control``
already drives.
"""

import pytest

from tests.e2e import harness

pytestmark = pytest.mark.e2e

# c7200 slot 0 is the fixed IO slot; the 2-port Ethernet PA goes in slot 1,
# so f1/0 = (1, 0) and f1/1 = (1, 1).
SLOTS = {"slot1": "PA-2FE-TX"}
ETH10 = (1, 0)
ETH20 = (1, 1)

IP10 = "10.1.10.%s"
IP20 = "10.1.20.%s"


def _pick_image(server):
    images = server.compute.dynamips_images()
    image = next((name for name in images if name.startswith("c7200")), None)
    if not image:
        pytest.skip(f"no c7200 image available on this server (images: {images[:5]})")
    return image


def _switch_bridge_name(switch_id):
    # see EthernetSwitch._ensure_bridge
    return "gns3" + switch_id.replace("-", "")[:6]


def _ports(cascade_type):
    """The switches' ports: two access ports (VLAN 10 / 20) and the cascade
    port — dot1q trunk (native 1) or access 10 for the symmetric flip."""
    return [
        {"name": "Ethernet0", "port_number": 0, "type": "access", "vlan": 10},
        {"name": "Ethernet1", "port_number": 1, "type": "access", "vlan": 20},
        {"name": "Ethernet2", "port_number": 2, "type": cascade_type, "vlan": 1 if cascade_type == "dot1q" else 10},
    ]


def _create_switch(compute, pid, name):
    return compute.call(
        "POST",
        f"/projects/{pid}/nodes",
        {
            "compute_id": "local",
            "name": name,
            "node_type": "ethernet_switch",
            "properties": {"ports_mapping": _ports("dot1q")},
        },
    )


def _set_ports(compute, pid, switch_id, cascade_type):
    compute.call("PUT", f"/projects/{pid}/nodes/{switch_id}", {"properties": {"ports_mapping": _ports(cascade_type)}})


def _add_eth(console, ip, ifname):
    console.run("conf t")
    console.run(f"interface {ifname}")
    console.run(f"ip address {ip} 255.255.255.0")
    console.run("no shutdown")
    console.run("end")


def _boot(server, project_id, node_id, timeout=360):
    console = harness.ios_console(server, project_id, node_id)
    console.boot_wait(timeout=timeout)
    return console


def _eth_shutdown(console, shut):
    """Shut/unshut both router interfaces on their switch links — the only
    legitimate speakers on these segments (IOS's own CDP/keepalives) — for
    §E.2's silence window; the addresses stay configured and answer once the
    interfaces are back."""
    console.run("conf t")
    console.run("interface f1/0")
    console.run("shutdown" if shut else "no shutdown")
    console.run("interface f1/1")
    console.run("shutdown" if shut else "no shutdown")
    console.run("end")


def test_ethernet_switch_cascade_kernel_datapath():
    server = harness.live_server(kernel=True)
    compute = server.compute
    if compute.capabilities().get("ubridge_tap") is not True:
        pytest.skip("this compute's uBridge cannot create persistent TAPs (ubridge_tap != True)")
    image = _pick_image(server)
    idlepc = harness.dynamips_idlepc(server, image)

    project = compute.create_project("esw-cascade-e2e")
    pid = project["project_id"]
    bridges = []
    try:
        sw1 = _create_switch(compute, pid, "E2E-SW1")
        sw2 = _create_switch(compute, pid, "E2E-SW2")
        sw1_id, sw2_id = sw1["node_id"], sw2["node_id"]
        br1, br2 = _switch_bridge_name(sw1_id), _switch_bridge_name(sw2_id)
        bridges = [br1, br2]
        r1 = compute.create_dynamips_router(pid, "E2E-R1", image, SLOTS, idlepc=idlepc)
        r2 = compute.create_dynamips_router(pid, "E2E-R2", image, SLOTS, idlepc=idlepc)
        r1_id, r2_id = r1["node_id"], r2["node_id"]
        a1_10, a1_20 = harness.anchor_name(r1_id, *ETH10), harness.anchor_name(r1_id, *ETH20)
        a2_10, a2_20 = harness.anchor_name(r2_id, *ETH10), harness.anchor_name(r2_id, *ETH20)

        # Both switch bridges exist from node creation; the cascade wires at
        # once (switches are always-on), the host links defer on the stopped
        # routers exactly like the single-switch scenario.
        assert harness.bridge_members(br1) == []
        assert harness.bridge_members(br2) == []
        host_links = [
            compute.create_link(pid, (r1_id, *ETH10), (sw1_id, 0, 0)),
            compute.create_link(pid, (r1_id, *ETH20), (sw1_id, 0, 1)),
            compute.create_link(pid, (r2_id, *ETH10), (sw2_id, 0, 0)),
            compute.create_link(pid, (r2_id, *ETH20), (sw2_id, 0, 1)),
        ]
        cascade = compute.create_link(pid, (sw1_id, 0, 2), (sw2_id, 0, 2))
        assert all(link["kernel_datapath"] is True for link in [*host_links, cascade]), (
            [link.get("kernel_datapath") for link in host_links],
            cascade.get("kernel_datapath"),
        )
        e0, e1 = harness.cascade_end_names(cascade["link_id"])
        assert harness.tap_exists(e0) and harness.tap_exists(e1)
        assert harness.tap_up(e0) and harness.tap_up(e1)
        assert harness.bridge_members(br1) == [e0], harness.bridge_members(br1)
        assert harness.bridge_members(br2) == [e1], harness.bridge_members(br2)

        print(".. starting routers and waiting for IOS boots")
        compute.call("POST", f"/projects/{pid}/nodes/{r1_id}/start")
        compute.call("POST", f"/projects/{pid}/nodes/{r2_id}/start")
        c1 = _boot(server, pid, r1_id)
        c2 = _boot(server, pid, r2_id)

        # NetworkManager can release an NM-managed TAP from its bridge after
        # (re-)enslavement (docs/bugs/networkmanager-tap-release.md); take the
        # anchors out of its reach for the rest of the run.
        harness.unmanage_from_networkmanager(a1_10, a1_20, a2_10, a2_20)

        # The deferred host joins completed via the node-start re-push: each
        # switch bridges its two router anchors plus its cascade end.
        assert harness.wait_until(lambda: harness.bridge_members(br1) == sorted([a1_10, a1_20, e0]), timeout=15), (
            harness.bridge_members(br1)
        )
        assert harness.wait_until(lambda: harness.bridge_members(br2) == sorted([a2_10, a2_20, e1]), timeout=15), (
            harness.bridge_members(br2)
        )

        harness.configure_ios(c1, "R1", eth_ip=IP10 % 1, eth_if="f1/0")
        _add_eth(c1, IP20 % 1, "f1/1")
        harness.configure_ios(c2, "R2", eth_ip=IP10 % 2, eth_if="f1/0")
        _add_eth(c2, IP20 % 2, "f1/1")
        print(".. both routers configured, pinging across the cascade")

        # A trunk cascade carries both VLANs at once — two simultaneous
        # adjacencies over the same veth pair is the tagged-frames proof.
        baseline10 = harness.wait_ping(c1, IP10 % 2)
        assert baseline10["success"] == 100, baseline10["raw"]
        baseline20 = harness.wait_ping(c1, IP20 % 2)
        assert baseline20["success"] == 100, baseline20["raw"]

        # L2-anchor spec §E.2: with all four router interfaces shut, every
        # host-side device of this fabric stays silent for 5 s — the four
        # absorbed router anchors, both cascade ends and both switch bridges
        # (the bridges are created with multicast snooping off precisely so
        # the bridge role can reach silence, see uBridge's brctl create).
        if harness.l2only_supported():
            for console in (c1, c2):
                _eth_shutdown(console, shut=True)
            harness.assert_idle_silence(a1_10, a1_20, a2_10, a2_20, e0, e1, br1, br2)
            for console in (c1, c2):
                _eth_shutdown(console, shut=False)
            assert harness.wait_ping(c1, IP10 % 2, attempts=5)["success"] == 100
            assert harness.wait_ping(c1, IP20 % 2, attempts=5)["success"] == 100
        else:
            print(".. uBridge without link l2only: skipping the §E.2 assertion")

        # L2-anchor spec §E.1: the cascade ends and both bridges carry no L3
        # identity, and the bridged ends are FORWARDING.
        if harness.l2only_supported():
            harness.assert_pure_l2(e0)
            harness.assert_pure_l2(e1)
            harness.assert_pure_l2(br1)
            harness.assert_pure_l2(br2)
        else:
            print(".. uBridge without link l2only: skipping the §E.1 assertions")
        harness.assert_forwarding(e0)
        harness.assert_forwarding(e1)

        # Symmetric mode flip on the cascade ports (in place, no member ever
        # leaves its bridge): access 10 passes VLAN 10 untagged and drops
        # VLAN 20; the trunk restores the dual-VLAN crossing.
        _set_ports(compute, pid, sw1_id, "access")
        _set_ports(compute, pid, sw2_id, "access")
        assert harness.bridge_members(br1) == sorted([a1_10, a1_20, e0]), harness.bridge_members(br1)
        assert harness.bridge_members(br2) == sorted([a2_10, a2_20, e1]), harness.bridge_members(br2)
        assert harness.wait_ping(c1, IP10 % 2)["success"] == 100
        isolated = harness.ping(c1, IP20 % 2, repeat=3)
        assert isolated["success"] == 0, isolated["raw"]
        _set_ports(compute, pid, sw1_id, "dot1q")
        _set_ports(compute, pid, sw2_id, "dot1q")
        rejoined = harness.wait_ping(c1, IP20 % 2, attempts=5)
        assert rejoined["success"] == 100, rejoined["raw"]

        # Two-sided impairment: each veth end is its own interface, so the
        # filter lands on both — one netem per direction, RTT ~= 2 x delay.
        compute.call("PUT", f"/projects/{pid}/links/{cascade['link_id']}", {"filters": {"delay": [100]}})
        assert "netem" in harness.qdiscs(e0), harness.qdiscs(e0)
        assert "netem" in harness.qdiscs(e1), harness.qdiscs(e1)
        delayed = harness.wait_ping(c1, IP10 % 2)
        assert delayed["success"] == 100, delayed["raw"]
        assert 150 <= delayed["avg"] <= 350, (baseline10, delayed)
        compute.call("PUT", f"/projects/{pid}/links/{cascade['link_id']}", {"filters": {}})
        assert "netem" not in harness.qdiscs(e0) and "netem" not in harness.qdiscs(e1)
        fast = harness.wait_ping(c1, IP10 % 2)
        assert fast["success"] == 100 and fast["avg"] < harness.FAST_RTT_MS, fast

        # suspend: both ends admin-down, both VLANs die; resume restores.
        compute.call("PUT", f"/projects/{pid}/links/{cascade['link_id']}", {"suspend": True})
        assert not harness.tap_up(e0) and not harness.tap_up(e1)
        assert harness.ping(c1, IP10 % 2, repeat=3)["success"] == 0
        assert harness.ping(c1, IP20 % 2, repeat=3)["success"] == 0
        compute.call("PUT", f"/projects/{pid}/links/{cascade['link_id']}", {"suspend": False})
        assert harness.tap_up(e0) and harness.tap_up(e1)
        assert harness.wait_ping(c1, IP10 % 2, attempts=5)["success"] == 100
        assert harness.wait_ping(c1, IP20 % 2, attempts=5)["success"] == 100

        # Cascade link fault: the whole veth pair dies with the link (either
        # side's teardown), the host links and their anchors survive; a
        # re-create mints a new pair under the new link id and the traffic
        # returns without touching the routers.
        compute.call("DELETE", f"/projects/{pid}/links/{cascade['link_id']}")
        assert not harness.tap_exists(e0) and not harness.tap_exists(e1)
        assert harness.bridge_members(br1) == sorted([a1_10, a1_20]), harness.bridge_members(br1)
        assert harness.bridge_members(br2) == sorted([a2_10, a2_20]), harness.bridge_members(br2)
        assert harness.ping(c1, IP10 % 2, repeat=3)["success"] == 0
        cascade = compute.create_link(pid, (sw1_id, 0, 2), (sw2_id, 0, 2))
        assert cascade["kernel_datapath"] is True, cascade
        n0, n1 = harness.cascade_end_names(cascade["link_id"])
        assert harness.wait_until(lambda: harness.bridge_members(br1) == sorted([a1_10, a1_20, n0]), timeout=10)
        assert harness.wait_until(lambda: harness.bridge_members(br2) == sorted([a2_10, a2_20, n1]), timeout=10)
        assert harness.wait_ping(c1, IP10 % 2, attempts=5)["success"] == 100
        assert harness.wait_ping(c1, IP20 % 2, attempts=5)["success"] == 100

        c1.close()
        c2.close()
    except BaseException:
        harness.release(server, pid, failed=True)
        raise
    harness.release(server, pid, failed=False)

    # Project delete closed everything: both switch bridges, both veth pairs
    # (the faulted one and its replacement) and all four router anchors gone.
    for bridge in bridges:
        assert harness.wait_until(lambda b=bridge: harness.bridge_members(b) is None, timeout=15), bridge
    for end in (e0, e1, n0, n1):
        assert not harness.tap_exists(end), end
    for anchor in (a1_10, a1_20, a2_10, a2_20):
        assert not harness.tap_exists(anchor), anchor
