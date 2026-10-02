#
# Copyright (C) 2026 GNS3 Technologies Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation as either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

"""
Kernel-datapath wiring for IOU: the persistent TAP every Ethernet bay/unit
owns, the IOL-fabric binding (iol_bridge add_nio_tap) a kernel link adds to
it, kernel-link enslavement, the relay fallback for a uBridge without the
command, and the reverse-of-QEMU stop order (uBridge holds the anchor fds).
"""

import pytest
import pytest_asyncio

from unittest.mock import MagicMock, patch

from tests.utils import AsyncioMagicMock

from gns3server.compute.iou import IOU
from gns3server.compute.iou.iou_vm import IOUVM
from gns3server.compute.iou.iou_error import IOUError
from gns3server.compute.nios.nio_bridge import NIOBridge
from gns3server.compute.ubridge.ubridge_error import UbridgeError


NODE_ID = "00010203-0405-0607-0809-0a0b0c0d0e0f"
BRIDGE = "gns3a1b2c3d4e5f"
TAP00 = "gi00010203e0p0"  # the vm fixture's node id, bay 0 unit 0
IOL_BRIDGE = "IOL-BRIDGE-513"  # application_id 1 + 512


@pytest_asyncio.fixture
async def manager(port_manager):

    m = IOU.instance()
    m.port_manager = port_manager
    return m


@pytest_asyncio.fixture(scope="function")
async def vm(compute_project, manager):

    vm = IOUVM("test", NODE_ID, compute_project, manager, application_id=1)
    vm._ubridge_hypervisor = MagicMock()
    vm._ubridge_hypervisor.is_running.return_value = True
    vm._ubridge_send = AsyncioMagicMock()
    return vm


def _capable(vm, monkeypatch):
    """Make the iol-tap capability probe answer True."""

    async def probe(timeout=15.0):
        return True

    monkeypatch.setattr("gns3server.compute.iou.iou_vm.probe_iol_tap_support", probe)
    return vm


# ---------------------------------------------------------------------------
# Anchor lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prepare_tap_datapath_creates_one_tap_per_ethernet_unit(vm, monkeypatch):
    """
    On a capable uBridge every Ethernet bay/unit gets its persistent TAP —
    four units per bay, the IOU adapter model — swept of leftovers first and
    born down. Serial bays never anchor.
    """

    _capable(vm, monkeypatch)
    await vm._prepare_tap_datapath()

    assert vm._tap_datapath is True
    assert set(vm._kernel_taps) == {(bay, unit) for bay in range(2) for unit in range(4)}
    assert vm._kernel_taps[(0, 0)] == TAP00
    vm._ubridge_send.assert_any_call(f'tap delete "{TAP00}"')
    vm._ubridge_send.assert_any_call(f'tap create "{TAP00}"')
    vm._ubridge_send.assert_any_call(f'link set "{TAP00}" down')
    assert not any("set_owner" in str(c) for c in vm._ubridge_send.call_args_list)


@pytest.mark.asyncio
async def test_prepare_tap_datapath_falls_back_without_the_command(vm, monkeypatch):
    """
    A uBridge without iol_bridge add_nio_tap keeps the node on the relay
    datapath — it still starts, it just cannot carry kernel links.
    """

    async def probe(timeout=15.0):
        return None

    monkeypatch.setattr("gns3server.compute.iou.iou_vm.probe_iol_tap_support", probe)
    with patch.object(vm.project, "emit") as emit:
        await vm._prepare_tap_datapath()

    assert vm._tap_datapath is False
    assert vm._kernel_taps == {}
    assert emit.called


def test_tap_name_fits_ifnamsiz(vm):
    """
    The anchor name has to fit IFNAMSIZ (15) even for a late bay/unit.
    """

    assert len(vm._tap_name(15, 3)) <= 15


def test_kernel_host_ifc_is_none_on_serial_bays(vm):
    """
    Serial bays (past the Ethernet adapters) never anchor, so a kernel link
    there fails with the serial-port message rather than wiring nonsense.
    """

    assert vm._kernel_host_ifc(2, 0) is None


# ---------------------------------------------------------------------------
# Link attach / detach
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_attach_kernel_nio_binds_the_anchor_and_enslaves_it(vm):
    """
    A kernel link binds the port's anchor TAP to the IOL bridge (uBridge
    holds the fd and relays the fabric onto it), then enslaves the TAP into
    the per-link kernel bridge.
    """

    vm._kernel_taps[(0, 0)] = TAP00
    nio = vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE})

    await vm._attach_kernel_nio(0, 0, nio)

    vm._ubridge_send.assert_any_call(f'iol_bridge add_nio_tap {IOL_BRIDGE} 1 0 0 "{TAP00}"')
    vm._ubridge_send.assert_any_call(f'brctl create "{BRIDGE}"')
    vm._ubridge_send.assert_any_call(f'link set "{BRIDGE}" up')
    vm._ubridge_send.assert_any_call(f'brctl addif "{BRIDGE}" "{TAP00}"')
    vm._ubridge_send.assert_any_call(f'link set "{TAP00}" up')


@pytest.mark.asyncio
async def test_attach_kernel_nio_without_anchor_raises(vm):
    """
    A kernel link on a serial bay (or a node that never anchored) is an
    error naming the relay datapath, not a silent fallback.
    """

    nio = vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE})

    with pytest.raises(IOUError, match="no TAP anchor"):
        await vm._attach_kernel_nio(2, 0, nio)


@pytest.mark.asyncio
async def test_add_nio_binding_refuses_an_occupied_port(vm):
    """
    The compute-side backstop of the duplicate-port guard: a second NIO for
    a port that already carries one is refused here instead of overwriting
    — the occupying link's teardown needs its own NIO handle, and its host
    state with it.
    """

    vm._kernel_taps[(0, 0)] = TAP00
    first = vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE})
    await vm.adapter_add_nio_binding(0, 0, first)
    assert vm._ethernet_adapters[0].get_nio(0) is first

    second = vm.manager.create_nio({"type": "nio_bridge", "bridge": "gns3other"})
    with pytest.raises(IOUError, match="already has a link"):
        await vm.adapter_add_nio_binding(0, 0, second)

    assert vm._ethernet_adapters[0].get_nio(0) is first


@pytest.mark.asyncio
async def test_add_nio_binding_attach_failure_leaves_the_port_unbound(vm):
    """
    The bookkeeping happens last: an attach that fails mid-way (uBridge
    EBUSY on a held anchor) must leave the port without a binding, so the
    failed link creates no half-wired state.
    """

    vm._kernel_taps[(0, 0)] = TAP00
    vm._ubridge_send.side_effect = UbridgeError("208-Device or resource busy")

    nio = vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE})
    with pytest.raises(UbridgeError):
        await vm.adapter_add_nio_binding(0, 0, nio)

    assert vm._ethernet_adapters[0].get_nio(0) is None


@pytest.mark.asyncio
async def test_add_nio_binding_relay_keeps_the_iol_udp_path(vm):
    """
    A relay link is wired exactly as before: a UDP NIO on the IOL bridge
    port, userspace filters at the port's IOL location.
    """

    vm._ubridge_hypervisor.is_running.return_value = True
    nio = vm.manager.create_nio({"type": "nio_udp", "lport": 20000, "rhost": "127.0.0.1", "rport": 20001})
    nio.filters = {"delay": [10]}

    await vm.adapter_add_nio_binding(0, 0, nio)

    vm._ubridge_send.assert_any_call(f"iol_bridge add_nio_udp {IOL_BRIDGE} 1 0 0 20000 127.0.0.1 20001")
    vm._ubridge_send.assert_any_call(f"iol_bridge reset_packet_filters {IOL_BRIDGE} 0 0")
    vm._ubridge_send.assert_any_call(f"iol_bridge add_packet_filter {IOL_BRIDGE} 0 0 filter0 delay 10")


@pytest.mark.asyncio
async def test_update_nio_binding_kernel_reapplies_on_the_anchor(vm):
    """
    A filter update on an attached kernel link reconciles on the anchor
    (tc) without re-binding the IOL port or re-enslaving the TAP.
    """

    vm._kernel_taps[(0, 0)] = TAP00
    nio = vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE})
    vm._ethernet_adapters[0].add_nio(0, nio)
    nio.filters = {"delay": [10]}

    await vm.adapter_update_nio_binding(0, 0, nio)

    vm._ubridge_send.assert_any_call(f'tc reset "{TAP00}"')
    vm._ubridge_send.assert_any_call(f'tc netem set "{TAP00}" delay 10')
    assert not any("iol_bridge add_nio" in str(c) for c in vm._ubridge_send.call_args_list)
    assert not any("brctl addif" in str(c) for c in vm._ubridge_send.call_args_list)


@pytest.mark.asyncio
async def test_update_nio_binding_kernel_suspend_flaps_the_anchor(vm):
    """
    Suspending a kernel link admin-downs the anchor: the IOL relay's writes
    fail EIO (dropped) and nothing comes back — a genuinely dead link.
    """

    vm._kernel_taps[(0, 0)] = TAP00
    nio = vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE})
    vm._ethernet_adapters[0].add_nio(0, nio)
    nio.suspend = True

    await vm.adapter_update_nio_binding(0, 0, nio)

    vm._ubridge_send.assert_any_call(f'link set "{TAP00}" down')


@pytest.mark.asyncio
async def test_remove_nio_binding_kernel_releases_the_fd_and_detaches(vm):
    """
    Removing a kernel link detaches the anchor from the per-link bridge,
    resets its qdisc, and unbinds the port from the TAP — releasing uBridge's
    fd while the control channel lives, so a later tap delete cannot hit
    EBADFD.
    """

    vm._kernel_taps[(0, 0)] = TAP00
    nio = vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE})
    vm._ethernet_adapters[0].add_nio(0, nio)

    await vm.adapter_remove_nio_binding(0, 0)

    vm._ubridge_send.assert_any_call(f'tc reset "{TAP00}"')
    vm._ubridge_send.assert_any_call(f'brctl delif "{BRIDGE}" "{TAP00}"')
    vm._ubridge_send.assert_any_call(f'brctl delete "{BRIDGE}"')
    vm._ubridge_send.assert_any_call(f"iol_bridge delete_nio_tap {IOL_BRIDGE} 0 0")


# ---------------------------------------------------------------------------
# Stop order (uBridge holds the anchor fds — the reverse of QEMU)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stop_ubridge_releases_fds_before_deleting_taps(vm):
    """
    The IOL bridge must be deleted (closing every port's TAP fd) before the
    taps are unpersisted, and the per-link bridges still need the control
    channel — all before the hypervisor itself stops.
    """

    vm._kernel_taps[(0, 0)] = TAP00
    nio = vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE})
    vm._ethernet_adapters[0].add_nio(0, nio)

    with patch("gns3server.compute.base_node.BaseNode._stop_ubridge", new=AsyncioMagicMock()) as stop:
        await vm._stop_ubridge()

    commands = [str(c[0][0]) if c[0] else "" for c in vm._ubridge_send.call_args_list]
    assert commands.index(f"iol_bridge delete {IOL_BRIDGE}") < commands.index(f'tap delete "{TAP00}"')
    assert commands.index(f'tap delete "{TAP00}"') < commands.index(f'brctl delete "{BRIDGE}"')
    assert commands.index(f'brctl delete "{BRIDGE}"') < len(commands)
    assert stop.called
    assert vm._kernel_taps == {}
    assert vm._ubridge_tc_caps is None


# ---------------------------------------------------------------------------
# _networking (node start with links already attached)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_networking_wires_kernel_and_relay_ports(vm):
    """
    On start, a kernel-linked port binds its anchor to the IOL bridge and
    enslaves it; a relay-linked port keeps its UDP NIO. The IOL bridge is
    recreated and started around both.
    """

    vm._kernel_taps[(0, 0)] = TAP00
    kernel_nio = vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE})
    vm._ethernet_adapters[0].add_nio(0, kernel_nio)
    relay_nio = vm.manager.create_nio({"type": "nio_udp", "lport": 20000, "rhost": "127.0.0.1", "rport": 20001})
    vm._ethernet_adapters[1].add_nio(1, relay_nio)

    await vm._networking()

    vm._ubridge_send.assert_any_call(f"iol_bridge delete {IOL_BRIDGE}")
    vm._ubridge_send.assert_any_call(f"iol_bridge create {IOL_BRIDGE} 513")
    vm._ubridge_send.assert_any_call(f'iol_bridge add_nio_tap {IOL_BRIDGE} 1 0 0 "{TAP00}"')
    vm._ubridge_send.assert_any_call(f'brctl addif "{BRIDGE}" "{TAP00}"')
    vm._ubridge_send.assert_any_call(f"iol_bridge add_nio_udp {IOL_BRIDGE} 1 1 1 20000 127.0.0.1 20001")
    vm._ubridge_send.assert_any_call(f"iol_bridge start {IOL_BRIDGE}")


@pytest.mark.asyncio
async def test_networking_restores_relay_capture_with_port_coordinates(vm):
    """
    A capture active across a restart is restored on the port's bay/unit —
    the iol_bridge command takes them positionally (the old restore sent a
    3-arg command uBridge refused with 203).
    """

    relay_nio = vm.manager.create_nio({"type": "nio_udp", "lport": 20000, "rhost": "127.0.0.1", "rport": 20001})
    relay_nio.start_packet_capture("/tmp/capture.pcap", "DLT_EN10MB")
    vm._ethernet_adapters[0].add_nio(0, relay_nio)

    await vm._networking()

    vm._ubridge_send.assert_any_call(f'iol_bridge start_capture {IOL_BRIDGE} 0 0 "/tmp/capture.pcap" EN10MB')


# ---------------------------------------------------------------------------
# Capture
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_capture_on_a_kernel_link_uses_the_anchor(vm):
    vm._kernel_taps[(0, 0)] = TAP00
    nio = vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE})
    vm._ethernet_adapters[0].add_nio(0, nio)

    await vm.start_capture(0, 0, "/tmp/test.pcap")
    vm._ubridge_send.assert_any_call(f'capture start_kernel {TAP00} "/tmp/test.pcap"')

    await vm.stop_capture(0, 0)
    vm._ubridge_send.assert_any_call("capture stop_kernel")


@pytest.mark.asyncio
async def test_capture_on_a_relay_link_uses_the_iol_port(vm):
    nio = vm.manager.create_nio({"type": "nio_udp", "lport": 20000, "rhost": "127.0.0.1", "rport": 20001})
    vm._ethernet_adapters[0].add_nio(0, nio)

    await vm.start_capture(0, 0, "/tmp/test.pcap")
    vm._ubridge_send.assert_any_call(f'iol_bridge start_capture {IOL_BRIDGE} 0 0 "/tmp/test.pcap" EN10MB')

    await vm.stop_capture(0, 0)
    vm._ubridge_send.assert_any_call(f"iol_bridge stop_capture {IOL_BRIDGE} 0 0")


# ---------------------------------------------------------------------------
# Markers (the polymorphic anchor: IOL location on relay, TAP on kernel)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_markers_on_a_kernel_link_attach_to_the_anchor(vm):
    """
    The marker reconcile is datapath-agnostic: with the anchor as the
    location, the attach/toggle/delete primitives translate to
    marker *_kernel on the TAP.
    """

    vm._kernel_taps[(0, 0)] = TAP00
    nio = vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE})
    nio.markers = {
        "m1": {"bpf": "vlan 100", "link_id": "lk1", "enabled": True, "data_link_type": "DLT_EN10MB"},
    }
    vm._ethernet_adapters[0].add_nio(0, nio)

    await vm._ubridge_apply_markers(TAP00, nio)

    vm._ubridge_send.assert_any_call(
        f'marker add_kernel m1 {TAP00} "vlan 100" link lk1 pcap "{vm.project.markers_working_directory()}/'
        f'{vm.id}_lk1_m1.pcap"'
    )
    assert vm._marker_filter_bridges[("m1", "lk1")] == TAP00

    await vm._ubridge_set_marker_filter_state("m1", False)
    vm._ubridge_send.assert_any_call(f"marker enable_kernel {TAP00} m1 off")

    await vm.delete_marker_capture("m1", "lk1", nio)
    vm._ubridge_send.assert_any_call(f"marker delete_kernel {TAP00} m1")


@pytest.mark.asyncio
async def test_markers_on_a_relay_link_keep_the_iol_shape(vm):
    """
    On the relay datapath the same reconcile talks iol_bridge, with the
    bay/unit positionals — unchanged behaviour.
    """

    nio = vm.manager.create_nio({"type": "nio_udp", "lport": 20000, "rhost": "127.0.0.1", "rport": 20001})
    nio.markers = {
        "m1": {"bpf": "vlan 100", "link_id": "lk1", "enabled": True, "data_link_type": "DLT_EN10MB"},
    }
    vm._ethernet_adapters[0].add_nio(0, nio)
    location = f"{IOL_BRIDGE} 0 0"

    await vm._ubridge_apply_markers(location, nio)

    vm._ubridge_send.assert_any_call(
        f'iol_bridge add_packet_filter {location} m1 mark "vlan 100" link lk1 pcap '
        f'"{vm.project.markers_working_directory()}/{vm.id}_lk1_m1.pcap"'
    )
    assert vm._marker_filter_bridges[("m1", "lk1")] == location

    await vm._ubridge_set_marker_filter_state("m1", False)
    vm._ubridge_send.assert_any_call(f"iol_bridge enable_packet_filter {location} m1 off")

    await vm.delete_marker_capture("m1", "lk1", nio)
    vm._ubridge_send.assert_any_call(f"iol_bridge delete_packet_filter {location} m1")
