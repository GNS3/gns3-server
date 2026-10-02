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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

"""
Kernel-datapath wiring for Dynamips routers: the persistent TAP every
Ethernet slot/port owns (Ethernet adapters and WIC-1ENET ports only — serial,
ATM and POS adapters never anchor), the hypervisor TAP NIO (nio create_tap)
that holds the anchor open, per-link enslavement, the deferred wiring of
kernel links bound while the node was stopped, and the stop order (the
hypervisor's fds released before the TAPs are unpersisted — QEMU's order,
since here it is Dynamips that holds them).
"""

import os
import shutil
import contextlib

import pytest
import pytest_asyncio

from unittest.mock import MagicMock, patch

from tests.utils import AsyncioMagicMock

from gns3server.compute.dynamips import Dynamips
from gns3server.compute.dynamips.nodes.router import Router
from gns3server.compute.dynamips.dynamips_error import DynamipsError
from gns3server.compute.dynamips.adapters.gt96100_fe import GT96100_FE
from gns3server.compute.dynamips.adapters.pa_4t import PA_4T
from gns3server.compute.dynamips.adapters.pa_fe_tx import PA_FE_TX
from gns3server.compute.dynamips.adapters.wic_1enet import WIC_1ENET
from gns3server.compute.ubridge.ubridge_error import UbridgeError
from gns3server.compute.nios.nio_bridge import NIOBridge


NODE_ID = "00010203-0405-0607-0809-0a0b0c0d0e0f"
BRIDGE = "gns3a1b2c3d4e5f"
TAP00 = "gd00010203e0p0"  # the router fixture's node id, slot 0 port 0
TAP01 = "gd00010203e0p1"
TAP016 = "gd00010203e0p16"  # WIC-1ENET port in WIC slot 0


class FakeDynamipsHypervisor:
    """Records the hypervisor protocol; answers status queries."""

    def __init__(self, status_code=2):
        self.commands = []
        self._status_code = status_code

    def is_running(self):
        return True

    async def send(self, command):
        self.commands.append(command)
        if command.startswith("vm get_status"):
            return [str(self._status_code)]
        return ["100-OK"]


@pytest_asyncio.fixture
async def manager(port_manager):

    m = Dynamips.instance()
    m.port_manager = port_manager
    return m


@pytest_asyncio.fixture
async def router(compute_project, manager):

    router = Router("R1", NODE_ID, compute_project, manager)
    router._hypervisor = FakeDynamipsHypervisor()
    router._ubridge_hypervisor = MagicMock()
    router._ubridge_hypervisor.is_running.return_value = True
    router._ubridge_send = AsyncioMagicMock()
    # slot 0: a 2-port Ethernet motherboard with a WIC-1ENET in WIC slot 0
    # (port 16); slot 1: a serial PA that must never anchor.
    router._create_slots(2)
    router._slots[0] = GT96100_FE()
    router._slots[0]._wics[0] = WIC_1ENET()
    router._slots[1] = PA_4T()
    yield router
    # compute_project is the shared, id-fixed project every compute test
    # file reuses (ProjectManager caches by id); leave its dynamips module
    # directory as this fixture found it (absent) — a later manager test
    # creates it with os.makedirs and no exist_ok.
    shutil.rmtree(router._working_directory, ignore_errors=True)
    with contextlib.suppress(OSError):
        os.rmdir(compute_project.module_working_path(manager.module_name.lower()))


async def _nio(router, **kwargs):
    settings = {"type": "nio_bridge", "bridge": BRIDGE}
    settings.update(kwargs)
    return await router.manager.create_nio(router, settings)


def _hypervisor_commands(router):
    return list(router._hypervisor.commands)


def _ubridge_commands(router):
    return [str(c[0][0]) if c[0] else "" for c in router._ubridge_send.call_args_list]


# ---------------------------------------------------------------------------
# Anchor topology: which ports anchor at all
# ---------------------------------------------------------------------------


def test_ethernet_slot_ports_skip_serial_and_include_wics(router):
    """
    Only Ethernet-carrying ports anchor: the PA's two ports plus the
    WIC-1ENET port (numbered from 16 per WIC slot), never the serial PA.
    """

    assert router._ethernet_slot_ports() == [(0, 0), (0, 1), (0, 16)]


def test_tap_name_fits_ifnamsiz(router):
    """
    The anchor name has to fit IFNAMSIZ (15) even for WIC port numbers.
    """

    assert len(router._tap_name(6, 48)) <= 15


def test_kernel_host_ifc_is_none_before_start(router):
    assert router._kernel_host_ifc(0, 0) is None


# ---------------------------------------------------------------------------
# Anchor lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prepare_tap_datapath_creates_one_tap_per_ethernet_port(router):
    """
    On a capable uBridge every Ethernet slot/port gets its persistent TAP —
    swept of leftovers first, ownership handed to this user (so the
    unprivileged hypervisor can open it), born down.
    """

    router._ubridge_send.reset_mock()
    await router._prepare_tap_datapath()

    assert router._tap_datapath is True
    assert router._kernel_taps == {(0, 0): TAP00, (0, 1): TAP01, (0, 16): TAP016}
    router._ubridge_send.assert_any_call(f'tap delete "{TAP00}"')
    router._ubridge_send.assert_any_call(f'tap create "{TAP00}"')
    router._ubridge_send.assert_any_call(f"tap set_owner {TAP016} {os.getuid()}")
    router._ubridge_send.assert_any_call(f'link set "{TAP016}" down')


@pytest.mark.asyncio
async def test_prepare_tap_datapath_falls_back_without_the_tap_module(router):
    """
    A uBridge without the tap module keeps the router on the relay datapath —
    it still starts, it just cannot carry kernel links.
    """

    async def refuse_probe(command):
        if "prob" in command:
            raise UbridgeError("Unknown command")
        return ["100-OK"]

    router._ubridge_send.side_effect = refuse_probe
    with patch.object(router.project, "emit") as emit:
        await router._prepare_tap_datapath()

    assert router._tap_datapath is False
    assert router._kernel_taps == {}
    assert emit.called


@pytest.mark.asyncio
async def test_prepare_tap_datapath_skips_ghost_routers(compute_project, manager):
    """
    Ghost IOS images share RAM with a real router and never link: no uBridge,
    no anchors.
    """

    ghost = Router("Ghost", NODE_ID, compute_project, manager, ghost_flag=True)
    ghost._start_ubridge = AsyncioMagicMock()
    await ghost._prepare_tap_datapath()

    assert ghost._tap_datapath is False
    assert not ghost._start_ubridge.called


@pytest.mark.asyncio
async def test_prepare_tap_datapath_keeps_existing_anchors_across_a_restart(router):
    """
    Nothing is undone at node stop, so a restart must not recreate an anchor
    a surviving kernel link is still enslaved to.
    """

    await router._prepare_tap_datapath()
    router._ubridge_send.reset_mock()

    await router._prepare_tap_datapath()

    assert router._kernel_taps == {(0, 0): TAP00, (0, 1): TAP01, (0, 16): TAP016}
    assert not any("tap create" in c or "tap delete" in c for c in _ubridge_commands(router))


@pytest.mark.asyncio
async def test_prepare_tap_datapath_wires_nios_bound_while_stopped(router):
    """
    A kernel link bound to a stopped router could only be stored (no anchors
    existed); the start wires it — the hypervisor opens the anchor and binds
    the port, the anchor joins the per-link bridge.
    """

    router.status = "stopped"
    nio = await _nio(router)
    router._slots[0].add_nio(0, nio)

    router._ubridge_send.reset_mock()
    router._hypervisor.commands.clear()
    await router._prepare_tap_datapath()

    hypervisor = _hypervisor_commands(router)
    assert any(c.startswith("nio create_tap tap-") and c.endswith(f"{TAP00}") for c in hypervisor)
    assert any(c.startswith(f"vm slot_add_nio_binding \"R1\" 0 0 tap-") for c in hypervisor)
    router._ubridge_send.assert_any_call(f'brctl addif "{BRIDGE}" "{TAP00}"')
    assert (0, 0) in router._tap_nios


# ---------------------------------------------------------------------------
# Link attach / detach
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_attach_kernel_nio_opens_the_anchor_in_the_hypervisor_and_enslaves_it(router):
    """
    A kernel link opens the port's anchor TAP in the Dynamips hypervisor
    (Dynamips holds the fd — QEMU's shape), binds it to the slot/port, then
    enslaves the anchor into the per-link kernel bridge.
    """

    router.status = "started"
    router._kernel_taps[(0, 0)] = TAP00
    nio = await _nio(router)

    await router._attach_kernel_nio(0, 0, nio)

    hypervisor = _hypervisor_commands(router)
    assert any(c.startswith("nio create_tap tap-") and c.endswith(f"{TAP00}") for c in hypervisor)
    assert any(c.startswith('vm slot_add_nio_binding "R1" 0 0 tap-') for c in hypervisor)
    router._ubridge_send.assert_any_call(f'brctl create "{BRIDGE}"')
    router._ubridge_send.assert_any_call(f'link set "{BRIDGE}" up')
    router._ubridge_send.assert_any_call(f'brctl addif "{BRIDGE}" "{TAP00}"')
    router._ubridge_send.assert_any_call(f'link set "{TAP00}" up')


@pytest.mark.asyncio
async def test_slot_add_nio_binding_refuses_an_occupied_port(router):
    """
    The compute-side backstop of the duplicate-port guard: a second NIO for
    a port that already carries one is refused here instead of overwriting
    (the wiring's own idempotence check would silently skip the attach and
    rebind the bookkeeping) — the occupying link's teardown needs its own
    NIO handle, and its host state with it.
    """

    router.status = "started"
    router._kernel_taps[(0, 0)] = TAP00
    first = await _nio(router)
    await router.slot_add_nio_binding(0, 0, first)
    assert router._slots[0].get_nio(0) is first

    second = await _nio(router, bridge="gns3other")
    with pytest.raises(DynamipsError, match="already has a link"):
        await router.slot_add_nio_binding(0, 0, second)

    assert router._slots[0].get_nio(0) is first


@pytest.mark.asyncio
async def test_slot_add_nio_binding_attach_failure_leaves_the_port_unbound(router):
    """
    The bookkeeping happens last: a kernel attach that fails mid-way (the
    anchor is another link's bridge port — uBridge EBUSY) must leave the
    port without a binding, so the failed link creates no half-wired state.
    """

    router.status = "started"
    router._kernel_taps[(0, 0)] = TAP00
    router._ubridge_send.side_effect = UbridgeError("208-Device or resource busy")

    nio = await _nio(router)
    with pytest.raises(UbridgeError):
        await router.slot_add_nio_binding(0, 0, nio)

    assert router._slots[0].get_nio(0) is None


@pytest.mark.asyncio
async def test_attach_kernel_nio_without_anchor_on_a_running_node_raises(router):
    """
    A kernel link on a serial port (or a router that never anchored) is an
    error naming the relay datapath, not a silent fallback.
    """

    router.status = "started"
    nio = await _nio(router)

    with pytest.raises(DynamipsError, match="relay datapath"):
        await router._attach_kernel_nio(1, 0, nio)


@pytest.mark.asyncio
async def test_attach_kernel_nio_defers_on_a_stopped_node(router):
    """
    On a stopped router there are no anchors yet: the NIO is stored and the
    wiring happens at start (test above), so nothing is sent.
    """

    router.status = "stopped"
    nio = await _nio(router)

    await router._attach_kernel_nio(1, 0, nio)

    assert _hypervisor_commands(router) == []
    assert not router._ubridge_send.called


@pytest.mark.asyncio
async def test_attach_kernel_nio_is_idempotent_across_a_restart(router):
    """
    A stop tears nothing down, so a wired port must not re-bind on the next
    start: a second nio create_tap would orphan the first NIO's fd and the
    re-enslavement would collide on the bridge.
    """

    router.status = "started"
    router._kernel_taps[(0, 0)] = TAP00
    nio = await _nio(router)
    await router._attach_kernel_nio(0, 0, nio)
    hypervisor_first = list(_hypervisor_commands(router))
    router._ubridge_send.reset_mock()

    await router._attach_kernel_nio(0, 0, nio)

    assert _hypervisor_commands(router) == hypervisor_first
    assert not router._ubridge_send.called


@pytest.mark.asyncio
async def test_add_nio_binding_relay_keeps_the_udp_tunnel(router):
    """
    A relay link is wired exactly as before: the hypervisor NIO is a UDP NIO
    tunneled through loopback into the node's uBridge relay.
    """

    router.status = "started"
    nio = await router.manager.create_nio(
        router, {"type": "nio_udp", "lport": 20000, "rhost": "127.0.0.1", "rport": 20001}
    )

    await router.slot_add_nio_binding(0, 0, nio)

    hypervisor = _hypervisor_commands(router)
    assert any(c.startswith("nio create_udp udp-") for c in hypervisor)
    assert any(c.startswith('vm slot_add_nio_binding "R1" 0 0 udp-') for c in hypervisor)
    ubridge = _ubridge_commands(router)
    assert any(c.startswith("bridge create DYNAMIPS-") for c in ubridge)
    assert any(c.startswith("bridge add_nio_udp DYNAMIPS-") for c in ubridge)
    assert any(c.startswith("bridge start DYNAMIPS-") for c in ubridge)


@pytest.mark.asyncio
async def test_add_nio_binding_kernel_binds_and_enslaves(router):
    """
    The route-level add path dispatches a NIOBridge to the kernel wiring and
    stores it in the slot adapter like any NIO.
    """

    router.status = "started"
    router._kernel_taps[(0, 0)] = TAP00
    nio = await _nio(router)

    await router.slot_add_nio_binding(0, 0, nio)

    assert router._slots[0].get_nio(0) is nio
    router._ubridge_send.assert_any_call(f'brctl addif "{BRIDGE}" "{TAP00}"')


@pytest.mark.asyncio
async def test_update_nio_binding_kernel_reapplies_on_the_anchor(router):
    """
    A filter update on an attached kernel link reconciles on the anchor
    (tc) without re-binding the port or re-enslaving the TAP.
    """

    router._kernel_taps[(0, 0)] = TAP00
    nio = await _nio(router, filters={"delay": [10]})
    router._slots[0].add_nio(0, nio)

    await router.slot_update_nio_binding(0, 0, nio)

    router._ubridge_send.assert_any_call(f'tc reset "{TAP00}"')
    router._ubridge_send.assert_any_call(f'tc netem set "{TAP00}" delay 10')
    assert not any("slot_add_nio_binding" in c for c in _hypervisor_commands(router))
    assert not any("brctl addif" in c for c in _ubridge_commands(router))


@pytest.mark.asyncio
async def test_update_nio_binding_kernel_suspend_flaps_the_anchor(router):
    """
    Suspending a kernel link admin-downs the anchor — the native carrier,
    which is why the route must copy suspend onto the NIO.
    """

    router._kernel_taps[(0, 0)] = TAP00
    nio = await _nio(router)
    router._slots[0].add_nio(0, nio)
    nio.suspend = True

    await router.slot_update_nio_binding(0, 0, nio)

    router._ubridge_send.assert_any_call(f'link set "{TAP00}" down')


@pytest.mark.asyncio
async def test_remove_nio_binding_kernel_releases_the_fd_and_detaches(router):
    """
    Removing a kernel link detaches the anchor from the per-link bridge,
    resets its qdisc, and unbinds the port plus deletes the hypervisor TAP
    NIO — releasing Dynamips's fd while the control channels live.
    """

    router.status = "started"
    router._kernel_taps[(0, 0)] = TAP00
    nio = await _nio(router)
    router._slots[0].add_nio(0, nio)
    await router._attach_kernel_nio(0, 0, nio)
    router._ubridge_send.reset_mock()
    router._hypervisor.commands.clear()

    removed = await router.slot_remove_nio_binding(0, 0)

    assert removed is nio
    assert router._slots[0].get_nio(0) is None
    router._ubridge_send.assert_any_call(f'tc reset "{TAP00}"')
    router._ubridge_send.assert_any_call(f'brctl delif "{BRIDGE}" "{TAP00}"')
    router._ubridge_send.assert_any_call(f'brctl delete "{BRIDGE}"')
    hypervisor = _hypervisor_commands(router)
    assert any(c.startswith('vm slot_remove_nio_binding "R1" 0 0') for c in hypervisor)
    assert any(c.startswith("nio delete tap-") for c in hypervisor)
    assert (0, 0) not in router._tap_nios


# ---------------------------------------------------------------------------
# Stop order (the hypervisor holds the anchor fds — QEMU's order)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stop_ubridge_releases_hypervisor_fds_before_deleting_taps(router):
    """
    The hypervisor's TAP NIOs are unbound and deleted first (closing every
    anchor fd), then the TAPs are unpersisted, then the per-link bridges go —
    all before uBridge itself stops.
    """

    router.status = "started"
    router._kernel_taps[(0, 0)] = TAP00
    nio = await _nio(router)
    router._slots[0].add_nio(0, nio)
    await router._attach_kernel_nio(0, 0, nio)
    router._ubridge_send.reset_mock()
    router._hypervisor.commands.clear()

    with patch(
        "gns3server.compute.base_node.BaseNode._stop_ubridge", new=AsyncioMagicMock()
    ) as stop:
        await router._stop_ubridge()

    hypervisor = _hypervisor_commands(router)
    ubridge = _ubridge_commands(router)
    unbind = next(i for i, c in enumerate(hypervisor) if c.startswith('vm slot_remove_nio_binding "R1" 0 0'))
    nio_delete = next(i for i, c in enumerate(hypervisor) if c.startswith("nio delete tap-"))
    tap_delete = next(i for i, c in enumerate(ubridge) if c == f'tap delete "{TAP00}"')
    brctl_delete = next(i for i, c in enumerate(ubridge) if c == f'brctl delete "{BRIDGE}"')
    assert unbind < nio_delete
    assert tap_delete < brctl_delete
    assert stop.called
    assert router._kernel_taps == {}
    assert router._tap_nios == {}
    assert router._ubridge_tc_caps is None


@pytest.mark.asyncio
async def test_remove_kernel_bridges_covers_wic_ports(router):
    """
    The bridge sweep walks adapters derived from the anchor map, so a kernel
    link on a WIC-1ENET port (inside a non-Ethernet motherboard) is found.
    """

    router._kernel_taps[(0, 16)] = TAP016
    wic_nio = await _nio(router)
    router._slots[0].add_nio(16, wic_nio)

    await router._remove_kernel_bridges()

    router._ubridge_send.assert_any_call(f'brctl delete "{BRIDGE}"')


@pytest.mark.asyncio
async def test_slot_add_binding_hot_adds_anchors(router):
    """
    An adapter inserted while the router runs (OIR) gets its anchors created
    at once, so a kernel link can attach without a restart.
    """

    router.status = "started"
    router._tap_datapath = True
    router._kernel_taps[(0, 0)] = TAP00
    router._slots[1] = None  # free the serial slot for the hot-insert

    await router.slot_add_binding(1, PA_FE_TX())

    assert router._kernel_taps[(1, 0)] == "gd00010203e1p0"


# ---------------------------------------------------------------------------
# Capture (kernel: the anchor; relay: the Dynamips NIO's own pcap)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_capture_on_a_kernel_link_uses_the_anchor(router):
    router._kernel_taps[(0, 0)] = TAP00
    nio = await _nio(router)
    router._slots[0].add_nio(0, nio)

    await router.start_capture(0, 0, "/tmp/test.pcap")
    router._ubridge_send.assert_any_call(f'capture start_kernel {TAP00} "/tmp/test.pcap"')
    assert not any("bind_filter" in c for c in _hypervisor_commands(router))

    await router.stop_capture(0, 0)
    router._ubridge_send.assert_any_call("capture stop_kernel")


@pytest.mark.asyncio
async def test_capture_on_a_relay_link_uses_the_dynamips_nio(router):
    nio = await router.manager.create_nio(
        router, {"type": "nio_udp", "lport": 20000, "rhost": "127.0.0.1", "rport": 20001}
    )
    router._slots[0].add_nio(0, nio)

    await router.start_capture(0, 0, "/tmp/test.pcap")
    assert not any("capture start_kernel" in c for c in _ubridge_commands(router))
    hypervisor = _hypervisor_commands(router)
    assert any(c.startswith("nio bind_filter udp-") and c.endswith(" capture") for c in hypervisor)
    assert any(c.startswith("nio setup_filter udp-") for c in hypervisor)


# ---------------------------------------------------------------------------
# Markers (the polymorphic anchor: relay bridge name on relay, TAP on kernel)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_markers_on_a_kernel_link_attach_to_the_anchor(router):
    """
    The marker reconcile is datapath-agnostic: with the anchor as the
    location, the attach/toggle/delete primitives translate to
    marker *_kernel on the TAP.
    """

    router._kernel_taps[(0, 0)] = TAP00
    nio = await _nio(router)
    nio.markers = {
        "m1": {"bpf": "vlan 100", "link_id": "lk1", "enabled": True, "data_link_type": "DLT_EN10MB"},
    }
    router._slots[0].add_nio(0, nio)

    await router._ubridge_apply_markers(TAP00, nio)

    router._ubridge_send.assert_any_call(
        f'marker add_kernel m1 {TAP00} "vlan 100" link lk1 pcap "{router.project.markers_working_directory()}/'
        f'{router.id}_lk1_m1.pcap"'
    )
    assert router._marker_filter_bridges[("m1", "lk1")] == TAP00

    await router._ubridge_set_marker_filter_state("m1", False)
    router._ubridge_send.assert_any_call(f"marker enable_kernel {TAP00} m1 off")

    await router.delete_marker_capture("m1", "lk1", nio)
    router._ubridge_send.assert_any_call(f"marker delete_kernel {TAP00} m1")


@pytest.mark.asyncio
async def test_markers_on_a_relay_link_keep_the_ubridge_shape(router):
    """
    On the relay datapath the same reconcile talks to the uBridge relay
    bridge behind the Dynamips UDP tunnel — unchanged behaviour.
    """

    nio = await router.manager.create_nio(
        router, {"type": "nio_udp", "lport": 20000, "rhost": "127.0.0.1", "rport": 20001}
    )
    nio.markers = {
        "m1": {"bpf": "vlan 100", "link_id": "lk1", "enabled": True, "data_link_type": "DLT_EN10MB"},
    }
    router._slots[0].add_nio(0, nio)
    tunnel_bridge = "DYNAMIPS-20000-20001"

    await router._ubridge_apply_markers(tunnel_bridge, nio)

    router._ubridge_send.assert_any_call(
        f'bridge add_packet_filter {tunnel_bridge} m1 mark "vlan 100" link lk1 pcap '
        f'"{router.project.markers_working_directory()}/{router.id}_lk1_m1.pcap"'
    )


# ---------------------------------------------------------------------------
# Manager NIO construction
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_manager_create_nio_builds_the_bridge_nio(router):
    """
    The Dynamips manager accepts nio_bridge settings (the kernel-datapath
    NIO the controller POSTs) — without it the route 422s before the router
    ever sees the link.
    """

    nio = await router.manager.create_nio(
        router, {"type": "nio_bridge", "bridge": BRIDGE, "filters": {"delay": [5]}, "suspend": True}
    )
    assert isinstance(nio, NIOBridge)
    assert nio.bridge == BRIDGE
    assert nio.filters == {"delay": [5]}
    assert nio.suspend is True
    assert _hypervisor_commands(router) == []


# ---------------------------------------------------------------------------
# Externally bridged anchors (an Ethernet switch absorbed them)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_external_bridge_nio_skips_bridge_membership(router):
    """
    A NIOBridge with no bridge means an Ethernet switch owns the anchor's
    bridge membership: the router still opens the anchor in the hypervisor
    (the TAP needs its fd holder) but never touches any kernel bridge.
    """

    router.status = "started"
    router._kernel_taps[(0, 0)] = TAP00
    nio = await _nio(router, bridge=None)

    await router.slot_add_nio_binding(0, 0, nio)

    hypervisor = _hypervisor_commands(router)
    assert any(c.startswith("nio create_tap tap-") for c in hypervisor)
    assert any(c.startswith('vm slot_add_nio_binding "R1" 0 0 tap-') for c in hypervisor)
    assert not any("brctl" in c for c in _ubridge_commands(router))


@pytest.mark.asyncio
async def test_external_bridge_nio_remove_skips_bridge_ops(router):
    """
    Detaching an externally bridged anchor releases the hypervisor's fd and
    resets the link state, but must not delif or delete any bridge — the
    switch owns them, and deleting the switch's bridge would take the whole
    switch down.
    """

    router.status = "started"
    router._kernel_taps[(0, 0)] = TAP00
    nio = await _nio(router, bridge=None)
    await router.slot_add_nio_binding(0, 0, nio)
    router._ubridge_send.reset_mock()

    await router.slot_remove_nio_binding(0, 0)

    commands = _ubridge_commands(router)
    assert not any("brctl" in c for c in commands), commands
    assert any(c == f'tc reset "{TAP00}"' for c in commands)


@pytest.mark.asyncio
async def test_remove_kernel_bridges_skips_external_nios(router):
    """
    The bridge sweep never deletes a bridge this node does not own.
    """

    router._kernel_taps[(0, 0)] = TAP00
    external = await _nio(router, bridge=None)
    router._slots[0].add_nio(0, external)

    await router._remove_kernel_bridges()

    assert not any("brctl" in c for c in _ubridge_commands(router))
