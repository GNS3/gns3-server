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
Kernel-datapath wiring for QEMU: the persistent TAP every adapter owns, its
netdev, kernel-link enslavement, relay attach on the anchor, capture, and the
legacy socket-netdev fallback for a uBridge without the tap module.
"""

import asyncio
import os
import stat
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio

from gns3server.compute.qemu import Qemu
from gns3server.compute.qemu.qemu_error import QemuError
from gns3server.compute.qemu.qemu_vm import QemuVM
from gns3server.compute.ubridge.ubridge_error import UbridgeError
from tests.utils import AsyncioMagicMock, asyncio_patch

BRIDGE = "gns3a1b2c3d4e5f"
TAP0 = "gq00010203e0p0"  # the vm fixture's node id, adapter 0
TAP1 = "gq00010203e1p0"  # ... adapter 1


@pytest_asyncio.fixture
async def manager(port_manager):

    m = Qemu.instance()
    m.port_manager = port_manager
    return m


@pytest.fixture
def fake_qemu_binary(monkeypatch, tmpdir):

    monkeypatch.setenv("PATH", str(tmpdir))
    bin_path = os.path.join(os.environ["PATH"], "qemu-system-x86_64")
    with open(bin_path, "w+") as f:
        f.write("1")
    os.chmod(bin_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    return bin_path


@pytest_asyncio.fixture(scope="function")
async def vm(compute_project, manager, fake_qemu_binary):

    vm = QemuVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", compute_project, manager, qemu_path=fake_qemu_binary)
    vm._process_priority = "normal"
    vm._ubridge_hypervisor = MagicMock()
    vm._ubridge_hypervisor.is_running.return_value = True
    vm._ubridge_send = AsyncioMagicMock()
    return vm


def _running(vm):
    """Make is_running() true without a real process."""

    vm._process = MagicMock(returncode=None)


# ---------------------------------------------------------------------------
# TAP lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prepare_tap_datapath_creates_adapter_taps(vm):
    """
    The tap module is probed once per start; on success every adapter gets its
    persistent TAP, owned by this user (so unprivileged QEMU can open it) and
    born down (carrier off until a link attaches). A leftover from a previous
    run is swept first.
    """

    await vm._prepare_tap_datapath()

    assert vm._tap_datapath is True
    assert vm._kernel_taps == {(0, 0): TAP0}
    vm._ubridge_send.assert_any_call('tap create "gq00010203prob"')
    vm._ubridge_send.assert_any_call('tap delete "gq00010203prob"')
    vm._ubridge_send.assert_any_call(f'tap delete "{TAP0}"')
    vm._ubridge_send.assert_any_call(f'tap create "{TAP0}"')
    vm._ubridge_send.assert_any_call(f"tap set_owner {TAP0} {os.getuid()}")
    vm._ubridge_send.assert_any_call(f'link set "{TAP0}" down')


@pytest.mark.asyncio
async def test_prepare_tap_datapath_falls_back_without_the_tap_module(vm):
    """
    A uBridge build without the tap module keeps the legacy socket-netdev
    datapath — the node still starts, it just cannot carry kernel links.
    """

    async def send(command):
        if command.startswith("tap create"):
            raise UbridgeError("202-Unknown command 'create'")

    vm._ubridge_send = AsyncioMagicMock(side_effect=send)
    with patch.object(vm.project, "emit") as emit:
        await vm._prepare_tap_datapath()

    assert vm._tap_datapath is False
    assert vm._kernel_taps == {}
    assert emit.called


@pytest.mark.asyncio
async def test_tap_name_fits_ifnamsiz(vm):
    """
    The anchor name has to fit IFNAMSIZ (15) even for a late adapter.
    """

    vm.adapters = 32
    assert len(vm._tap_name(31)) <= 15


@pytest.mark.asyncio
async def test_network_options_use_the_tap_anchor(vm):
    """
    On the TAP datapath the netdev is the adapter's anchor, not a UDP socket.
    """

    vm._tap_datapath = True
    vm._kernel_taps[(0, 0)] = TAP0

    options = await vm._network_options()

    assert f"tap,id=gns3-0,ifname={TAP0},script=no,downscript=no" in options
    assert not any(option.startswith("socket,") for option in options)
    assert not vm._local_udp_tunnels


@pytest.mark.asyncio
async def test_network_options_keep_the_legacy_socket_netdev(vm):
    """
    Without the tap module nothing changes: the local UDP tunnel into uBridge
    is still the adapter's netdev.
    """

    vm._tap_datapath = False

    options = await vm._network_options()

    assert any(option.startswith("socket,id=gns3-0,udp=") for option in options)
    assert vm._local_udp_tunnels


# ---------------------------------------------------------------------------
# Link attach / detach
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_connect_nio_kernel_link_enslaves_the_tap(vm):
    """
    A kernel link enslaves the adapter's TAP into the per-link kernel bridge,
    with the bridge brought up first (a bridge that is down keeps its ports
    DISABLED and forwards nothing, silently).
    """

    vm._tap_datapath = True
    vm._kernel_taps[(0, 0)] = TAP0
    nio = vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE})

    await vm._connect_nio(0, nio)

    vm._ubridge_send.assert_any_call(f'brctl create "{BRIDGE}"')
    vm._ubridge_send.assert_any_call(f'link set "{BRIDGE}" up')
    vm._ubridge_send.assert_any_call(f'brctl addif "{BRIDGE}" "{TAP0}"')


@pytest.mark.asyncio
async def test_connect_nio_relay_uses_the_tap_as_af_packet_endpoint(vm):
    """
    A relay link attaches the TAP to the uBridge relay bridge via AF_PACKET
    (not the TAP NIO: that one takes the fd QEMU holds).
    """

    vm._tap_datapath = True
    vm._kernel_taps[(0, 0)] = TAP0
    nio = vm.manager.create_nio({"type": "nio_udp", "lport": 20000, "rhost": "127.0.0.1", "rport": 20001})

    await vm._connect_nio(0, nio)

    bridge = f"QEMU-{vm.id}-0"
    vm._ubridge_send.assert_any_call(f"bridge create {bridge}")
    vm._ubridge_send.assert_any_call(f'link set "{TAP0}" up')
    vm._ubridge_send.assert_any_call(f'bridge add_nio_ethernet {bridge} "{TAP0}"')
    vm._ubridge_send.assert_any_call(f"bridge add_nio_udp {bridge} 20000 127.0.0.1 20001")
    vm._ubridge_send.assert_any_call(f"bridge start {bridge}")


@pytest.mark.asyncio
async def test_connect_nio_without_anchor_raises(vm):
    """
    A kernel link on an adapter whose TAP does not exist (a VM started before
    the TAP datapath) fails with an actionable message.
    """

    vm._tap_datapath = True
    nio = vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE})

    with pytest.raises(QemuError, match="no TAP interface"):
        await vm._connect_nio(0, nio)


@pytest.mark.asyncio
async def test_legacy_datapath_rejects_kernel_link(vm):
    """
    The legacy datapath has no anchor to enslave: a kernel link there is an
    error, not a silent fallback to the relay.
    """

    vm._tap_datapath = False
    nio = vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE})

    with pytest.raises(QemuError, match="legacy relay datapath"):
        await vm._connect_nio(0, nio)


@pytest.mark.asyncio
async def test_add_nio_binding_on_a_running_vm_attaches_and_brings_the_carrier_up(vm):
    _running(vm)
    vm._tap_datapath = True
    vm._kernel_taps[(0, 0)] = TAP0
    nio = vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE})

    await vm.adapter_add_nio_binding(0, nio)

    vm._ubridge_send.assert_any_call(f'brctl addif "{BRIDGE}" "{TAP0}"')
    vm._ubridge_send.assert_any_call(f'link set "{TAP0}" up')


@pytest.mark.asyncio
async def test_update_nio_binding_reapplies_filters_on_the_anchor(vm):
    """
    A filter update on an attached kernel link reconciles on the anchor
    without re-enslaving it (no second addif).
    """

    _running(vm)
    vm._tap_datapath = True
    vm._kernel_taps[(0, 0)] = TAP0
    nio = vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE})
    vm._ethernet_adapters[0].add_nio(0, nio)
    nio.filters = {"delay": [10]}

    await vm.adapter_update_nio_binding(0, nio)

    vm._ubridge_send.assert_any_call(f'tc reset "{TAP0}"')
    vm._ubridge_send.assert_any_call(f'tc netem set "{TAP0}" delay 10')
    assert not any("brctl addif" in str(c) for c in vm._ubridge_send.call_args_list)


@pytest.mark.asyncio
async def test_remove_nio_binding_detaches_the_anchor(vm):
    """
    Removing a kernel link resets the anchor (no impairment survives on the
    adapter) and detaches it from the bridge.
    """

    _running(vm)
    vm._tap_datapath = True
    vm._kernel_taps[(0, 0)] = TAP0
    nio = vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE})
    vm._ethernet_adapters[0].add_nio(0, nio)

    with asyncio_patch("gns3server.compute.qemu.qemu_vm.QemuVM.stop_capture"):
        await vm.adapter_remove_nio_binding(0)

    vm._ubridge_send.assert_any_call(f'tc reset "{TAP0}"')
    vm._ubridge_send.assert_any_call(f'brctl delif "{BRIDGE}" "{TAP0}"')
    vm._ubridge_send.assert_any_call(f'brctl delete "{BRIDGE}"')


@pytest.mark.asyncio
async def test_stop_ubridge_removes_taps_and_orphan_bridges(vm):
    """
    A stopped VM has no links attached, so the TAPs and any per-link bridge
    it still holds are removed while the uBridge control channel is up.
    """

    vm._kernel_taps[(0, 0)] = TAP0
    nio = vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE})
    vm._ethernet_adapters[0].add_nio(0, nio)

    with asyncio_patch("gns3server.compute.base_node.BaseNode._stop_ubridge") as stop:
        await vm._stop_ubridge()

    vm._ubridge_send.assert_any_call(f'tap delete "{TAP0}"')
    vm._ubridge_send.assert_any_call(f'brctl delete "{BRIDGE}"')
    assert stop.called
    assert vm._kernel_taps == {}
    assert vm._ubridge_tc_caps is None


# ---------------------------------------------------------------------------
# Capture
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_capture_on_a_kernel_link_uses_the_anchor(vm):
    vm._tap_datapath = True
    vm._kernel_taps[(0, 0)] = TAP0
    nio = vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE})
    vm._ethernet_adapters[0].add_nio(0, nio)

    await vm.start_capture(0, "/tmp/test.pcap")
    vm._ubridge_send.assert_any_call(f'capture start_kernel {TAP0} "/tmp/test.pcap"')

    await vm.stop_capture(0)
    vm._ubridge_send.assert_any_call("capture stop_kernel")


@pytest.mark.asyncio
async def test_capture_on_a_relay_link_uses_the_relay_bridge(vm):
    vm._tap_datapath = True
    vm._kernel_taps[(0, 0)] = TAP0
    nio = vm.manager.create_nio({"type": "nio_udp", "lport": 20000, "rhost": "127.0.0.1", "rport": 20001})
    vm._ethernet_adapters[0].add_nio(0, nio)

    await vm.start_capture(0, "/tmp/test.pcap")
    vm._ubridge_send.assert_any_call(f'bridge start_capture QEMU-{vm.id}-0 "/tmp/test.pcap"')

    await vm.stop_capture(0)
    vm._ubridge_send.assert_any_call(f"bridge stop_capture QEMU-{vm.id}-0")


@pytest.mark.asyncio
async def test_stop_stops_the_process_before_deleting_the_taps(vm):
    """
    The QEMU process is the guest side of every adapter TAP, and uBridge's
    tap delete refuses a held device ("Device or resource busy") — that
    best-effort delete is suppressed, so removing the taps while QEMU still
    ran leaked the persistent TAPs. The process must be gone first (the same
    lesson as IOU's reverse stop order: process side, then the devices).
    """

    _running(vm)
    order = []

    async def fake_termination(process, timeout=None):
        order.append("process")

    async def fake_stop_ubridge():
        order.append("taps")

    with (
        patch("gns3server.utils.asyncio.wait_for_process_termination", new=fake_termination),
        patch.object(vm, "_stop_ubridge", new=fake_stop_ubridge),
        asyncio_patch("gns3server.compute.qemu.qemu_vm.QemuVM._export_config"),
        asyncio_patch("gns3server.compute.qemu.qemu_vm.QemuVM._clear_save_vm_stated"),
        asyncio_patch("gns3server.compute.base_node.BaseNode.stop"),
    ):
        await vm.stop()

    assert order == ["process", "taps"]


@pytest.mark.asyncio
async def test_stop_releases_the_datapath_even_when_the_stop_body_raises(vm):
    """
    The finally keeps a mid-stop raise (an export error here) from skipping
    the uBridge/TAP release — the datapath would otherwise outlive a failed
    stop with nothing left to reclaim it.
    """

    _running(vm)
    stopped = AsyncioMagicMock()

    async def failing_export():
        raise QemuError("qemu-img is missing")

    with (
        patch("gns3server.utils.asyncio.wait_for_process_termination", new=AsyncioMagicMock()),
        patch.object(vm, "_export_config", new=failing_export),
        patch.object(vm, "_stop_ubridge", new=stopped),
        asyncio_patch("gns3server.compute.qemu.qemu_vm.QemuVM._clear_save_vm_stated"),
    ):
        with pytest.raises(QemuError, match="qemu-img is missing"):
            await vm.stop()

    assert stopped.call_count == 1


@pytest.mark.asyncio
async def test_start_failure_before_the_launch_tears_down_the_datapath(vm):
    """
    A raise before the QEMU launch (a broken qemu_path in _build_command)
    must take the uBridge/TAP datapath down again: a node reporting a failed
    start must not keep a uBridge process and the anchor TAPs alive.
    """

    stopped = AsyncioMagicMock()
    with (
        patch.object(vm, "check_available_ram"),
        patch.object(vm, "_prepare_tap_datapath", new=AsyncioMagicMock()),
        patch.object(vm, "_build_command", new=AsyncioMagicMock(side_effect=QemuError("qemu-img is missing"))),
        patch.object(vm, "_stop_ubridge", new=stopped),
    ):
        with pytest.raises(QemuError, match="qemu-img is missing"):
            await vm.start()

    assert stopped.call_count == 1


@pytest.mark.asyncio
async def test_add_nio_binding_refuses_an_occupied_adapter(vm):
    """
    The compute-side backstop of the controller's duplicate-port guard: a
    second NIO for an adapter that already carries one is refused instead of
    silently overwriting the binding the first link's teardown still needs.
    """

    vm._tap_datapath = True
    vm._kernel_taps[(0, 0)] = TAP0
    first = vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE})
    await vm.adapter_add_nio_binding(0, first)

    second = vm.manager.create_nio({"type": "nio_bridge", "bridge": "gns3otherbridge"})
    with pytest.raises(QemuError, match="already has a link"):
        await vm.adapter_add_nio_binding(0, second)

    assert vm._ethernet_adapters[0].get_nio(0) is first


@pytest.mark.asyncio
async def test_concurrent_stops_sweep_every_tap_exactly_once(vm):
    """
    The process monitor calls stop() by itself when QEMU dies, so an API stop
    and a process-death stop run concurrently in the normal case. Both used to
    reach the TAP sweep, which walks the adapter map across awaits: whichever
    swept first cleared the map under the other's iterator, and the survivor
    died with "dictionary changed size during iteration" — logged against the
    monitor's task as "Task exception was never retrieved", with the rest of
    its sweep skipped.

    The first stop is parked inside the sweep while the second one runs to
    completion (in the fixed code it waits on the execution lock instead), then
    released: every TAP must be swept exactly once and the sweep must survive.
    """

    _running(vm)
    vm._tap_datapath = True
    vm._kernel_taps[(0, 0)] = TAP0
    vm._kernel_taps[(1, 0)] = TAP1

    release = asyncio.Event()
    deletes = []

    async def send(command):
        if command.startswith("tap delete"):
            deletes.append(command)
            if len(deletes) == 1:
                # park the first stop in the middle of its sweep
                await release.wait()

    vm._ubridge_send = AsyncioMagicMock(side_effect=send)

    async def fake_termination(process, timeout=None):
        pass

    with (
        patch("gns3server.utils.asyncio.wait_for_process_termination", new=fake_termination),
        asyncio_patch("gns3server.compute.qemu.qemu_vm.QemuVM._export_config"),
        asyncio_patch("gns3server.compute.qemu.qemu_vm.QemuVM._clear_save_vm_stated"),
        asyncio_patch("gns3server.compute.base_node.BaseNode.stop"),
    ):
        api_stop = asyncio.ensure_future(vm.stop())
        for _ in range(50):
            if deletes:
                break
            await asyncio.sleep(0)
        assert deletes, "the first stop never reached the TAP sweep"

        monitor_stop = asyncio.ensure_future(vm.stop())
        for _ in range(50):
            if monitor_stop.done():
                break
            await asyncio.sleep(0)

        release.set()
        await asyncio.gather(api_stop, monitor_stop)

    assert sorted(deletes) == [f'tap delete "{TAP0}"', f'tap delete "{TAP1}"']
