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
Kernel-datapath (NIOBridge) adapter wiring for Docker containers: veth pair
creation, per-link kernel bridge enslavement, carrier semantics, relay
fallback and cleanup.
"""

import os
import uuid
from unittest.mock import MagicMock, call

import pytest
import pytest_asyncio

from unittest.mock import patch

from tests.utils import AsyncioMagicMock

from gns3server.compute.docker import Docker
from gns3server.compute.docker.docker_vm import DockerVM
from gns3server.compute.docker.docker_error import DockerError, DockerHttp404Error
from gns3server.compute.compute_error import ComputeError
from gns3server.compute.nios.nio_udp import NIOUDP
from gns3server.compute.nios.nio_bridge import NIOBridge
from gns3server.compute.ubridge.ubridge_error import UbridgeError


BRIDGE = "gns3a1b2c3d4e5f"


@pytest_asyncio.fixture
async def manager(port_manager):

    m = Docker.instance()
    m.port_manager = port_manager
    return m


@pytest_asyncio.fixture(scope="function")
async def vm(compute_project, manager):

    vm = DockerVM("test", str(uuid.uuid4()), compute_project, manager, "ubuntu:latest", aux_type="none")
    vm._cid = "e90e34656842"
    vm.mac_address = "02:42:3d:b7:93:00"
    vm._start_interface_monitor = AsyncioMagicMock()
    vm._stop_interface_monitor = AsyncioMagicMock()
    return vm


# ---------------------------------------------------------------------------
# NIO factory
# ---------------------------------------------------------------------------


def test_create_nio_bridge(vm):

    nio = vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE})
    assert isinstance(nio, NIOBridge)
    assert nio.bridge == BRIDGE
    assert nio.suspend is False


def test_create_nio_bridge_accepts_netem_filters(vm):
    """
    Impairment filters with a tc netem equivalent ride the kernel NIO (they
    become one netem qdisc on the veth host end); relay-only types are
    rejected.
    """

    nio = vm.manager.create_nio(
        {"type": "nio_bridge", "bridge": BRIDGE, "filters": {"delay": [50, 5], "packet_loss": [10]}}
    )
    assert isinstance(nio, NIOBridge)
    assert nio.filters == {"delay": [50, 5], "packet_loss": [10]}


def test_create_nio_bridge_accepts_bpf_filters(vm):
    """
    bpf expressions run on the kernel datapath as cls_bpf match-drop
    classifiers (uBridge tc bpf_drop); only frequency_drop has no kernel
    equivalent yet.
    """

    nio = vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE, "filters": {"bpf": ["icmp"]}})
    assert isinstance(nio, NIOBridge)
    assert nio.filters == {"bpf": ["icmp"]}


def test_create_nio_bridge_accepts_frequency_drop(vm):
    """
    frequency_drop runs on the kernel datapath as the eBPF classifier's
    exact every-Nth mode — every filter type is accepted on a kernel NIO.
    """

    nio = vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE, "filters": {"frequency_drop": [10]}})
    assert isinstance(nio, NIOBridge)
    assert nio.filters == {"frequency_drop": [10]}


def test_create_nio_bridge_accepts_quota(vm):

    nio = vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE, "filters": {"quota": [1000000, 100]}})
    assert isinstance(nio, NIOBridge)
    assert nio.filters == {"quota": [1000000, 100]}


def test_create_nio_bridge_accepts_markers(vm):
    """
    Markers ride the kernel NIO (attached to the veth host end via uBridge's
    AF_PACKET marker module).
    """

    nio = vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE, "markers": {"m": {"bpf": "icmp"}}})
    assert isinstance(nio, NIOBridge)
    assert nio.markers == {"m": {"bpf": "icmp"}}


# ---------------------------------------------------------------------------
# Adapter wiring (start path)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_ubridge_kernel_connection(vm):

    vm._ubridge_hypervisor = MagicMock()
    vm._namespace = 42
    nio = vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE})

    await vm._add_ubridge_connection(nio, 0)

    host_ifc, guest_ifc = vm._veth_names(0, 0)
    calls = [
        # stale-pair sweep (no-ops on a clean host)
        call.send(f'docker delete_veth "{host_ifc}"'),
        call.send(f'docker delete_veth "{guest_ifc}"'),
        call.send(f'docker create_veth "{host_ifc}" "{guest_ifc}"'),
        call.send(f'link set "{host_ifc}" down'),
        call.send(f"docker set_mac_addr {guest_ifc} 02:42:3d:b7:93:00"),
        call.send(f"docker move_to_ns {guest_ifc} 42 eth0"),
        # link attach
        call.send(f'brctl create "{BRIDGE}"'),
        call.send(f'link set "{BRIDGE}" up'),
        call.send(f'brctl addif "{BRIDGE}" "{host_ifc}"'),
        call.send(f'link set "{host_ifc}" up'),
    ]
    vm._ubridge_hypervisor.assert_has_calls(calls, any_order=True)
    assert vm._kernel_veths[(0, 0)] == host_ifc
    # no uBridge relay bridge on the kernel datapath
    assert "bridge0" not in vm._bridges


@pytest.mark.asyncio
async def test_add_ubridge_kernel_connection_applies_netem(vm):
    """
    Filters carried by the NIO become a tc netem qdisc at start (node
    restart restore), exactly like capture and markers.
    """

    vm._ubridge_hypervisor = MagicMock()
    vm._namespace = 42
    nio = vm.manager.create_nio(
        {"type": "nio_bridge", "bridge": BRIDGE, "filters": {"delay": [50, 5], "packet_loss": [10]}}
    )

    await vm._add_ubridge_connection(nio, 0)

    host_ifc, _ = vm._veth_names(0, 0)
    netem_calls = [c for c in vm._ubridge_hypervisor.method_calls if "netem set" in str(c)]
    assert call.send(f'tc netem set "{host_ifc}" delay 50 jitter 5 loss 10') in netem_calls


@pytest.mark.asyncio
async def test_add_ubridge_connection_none_nio_creates_veth(vm):
    """
    Unconnected adapters are born as veths too (the unified interface): the
    interface exists inside the container with carrier off, and any link
    type can be attached later — at runtime — without rebirthing it.
    """

    vm._ubridge_hypervisor = MagicMock()
    vm._namespace = 42

    await vm._add_ubridge_connection(None, 0)

    host_ifc, guest_ifc = vm._veth_names(0, 0)
    vm._ubridge_hypervisor.assert_has_calls(
        [
            call.send(f'docker create_veth "{host_ifc}" "{guest_ifc}"'),
            call.send(f'link set "{host_ifc}" down'),
            call.send(f"docker move_to_ns {guest_ifc} 42 eth0"),
        ],
        any_order=True,
    )
    assert vm._kernel_veths[(0, 0)] == host_ifc
    # no relay bridge and no TAP for an unconnected adapter
    assert "bridge0" not in vm._bridges
    for c in vm._ubridge_hypervisor.method_calls:
        assert "add_nio_tap" not in str(c)


@pytest.mark.asyncio
async def test_add_ubridge_connection_udp_relays_over_veth(vm):
    """
    A relay NIO at start: the adapter is born as a veth and the uBridge
    relay attaches to its host end via AF_PACKET (add_nio_ethernet) —
    no TAP anywhere.
    """

    vm._ubridge_hypervisor = MagicMock()
    vm._namespace = 42

    nio = vm.manager.create_nio({"type": "nio_udp", "lport": 4242, "rport": 4343, "rhost": "127.0.0.1"})
    await vm._add_ubridge_connection(nio, 0)

    host_ifc, _ = vm._veth_names(0, 0)
    vm._ubridge_hypervisor.assert_has_calls(
        [
            call.send(f'docker create_veth "{host_ifc}" "{vm._veth_names(0, 0)[1]}"'),
            call.send("bridge create bridge0"),
            # the host end is born down; libpcap cannot attach to an
            # admin-down interface, so the relay brings it up first
            call.send(f'link set "{host_ifc}" up'),
            call.send(f'bridge add_nio_ethernet bridge0 "{host_ifc}"'),
            call.send("bridge add_nio_udp bridge0 4242 127.0.0.1 4343"),
            call.send("bridge start bridge0"),
        ],
        any_order=True,
    )
    assert "bridge0" in vm._bridges


@pytest.mark.asyncio
async def test_add_ubridge_kernel_connection_cleans_up_on_failure(vm):

    vm._ubridge_hypervisor = MagicMock()
    vm._namespace = 42

    async def failing_send(command):
        if "create_veth" in command and "delete" not in command:
            raise UbridgeError("could not complete netlink transaction")

    vm._ubridge_send = AsyncioMagicMock(side_effect=failing_send)

    with pytest.raises(UbridgeError):
        await vm._add_ubridge_connection(vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE}), 0)

    host_ifc, _ = vm._veth_names(0, 0)
    vm._ubridge_send.assert_any_call(f'docker delete_veth "{host_ifc}"')
    assert (0, 0) not in vm._kernel_veths


# ---------------------------------------------------------------------------
# Link attach / detach
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_connect_nio_kernel_tolerates_bridge_create_race(vm):

    # Both endpoints create the per-link bridge concurrently; the loser must
    # verify (brctl show) instead of failing.
    async def send(command):
        if "brctl create" in command:
            raise UbridgeError("Could not create bridge: File exists")

    vm._ubridge_send = AsyncioMagicMock(side_effect=send)
    host_ifc, _ = vm._veth_names(0, 0)
    vm._kernel_veths[(0, 0)] = host_ifc

    nio = vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE})
    await vm._connect_nio(0, nio)

    vm._ubridge_send.assert_any_call(f'brctl show "{BRIDGE}"')
    vm._ubridge_send.assert_any_call(f'brctl addif "{BRIDGE}" "{host_ifc}"')


@pytest.mark.asyncio
async def test_connect_nio_kernel_create_failure_propagates(vm):

    async def send(command):
        if "brctl create" in command or "brctl show" in command:
            raise UbridgeError("Could not create bridge: No such device")

    vm._ubridge_send = AsyncioMagicMock(side_effect=send)
    vm._kernel_veths[(0, 0)] = vm._veth_names(0, 0)[0]

    nio = vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE})
    with pytest.raises(UbridgeError):
        await vm._connect_nio(0, nio)


@pytest.mark.asyncio
async def test_connect_nio_kernel_without_veth_raises(vm):

    vm._ubridge_send = AsyncioMagicMock()
    nio = vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE})
    with pytest.raises(DockerError, match="restart the node"):
        await vm._connect_nio(0, nio)


@pytest.mark.asyncio
async def test_remove_kernel_nio(vm):

    vm._ubridge_hypervisor = MagicMock()
    vm._ubridge_send = AsyncioMagicMock()
    vm.status = "started"
    host_ifc, _ = vm._veth_names(0, 0)
    vm._kernel_veths[(0, 0)] = host_ifc
    vm._ethernet_adapters[0].add_nio(0, vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE}))

    await vm.adapter_remove_nio_binding(0)

    vm._ubridge_send.assert_has_calls(
        [
            call(f'tc reset "{host_ifc}"'),
            call(f'link set "{host_ifc}" down'),
            call(f'brctl delif "{BRIDGE}" "{host_ifc}"'),
            call(f'brctl delete "{BRIDGE}"'),
        ],
        any_order=True,
    )
    assert vm._ethernet_adapters[0].get_nio(0) is None
    # the veth itself stays: it is the adapter interface, not the link
    assert vm._kernel_veths[(0, 0)] == host_ifc


@pytest.mark.asyncio
async def test_remove_kernel_nio_tolerates_peer_winning_bridge_delete(vm):

    # Deleting a bridge that still holds the peer's port fails with EBUSY;
    # a bridge already deleted by the peer fails with ENOENT — both expected.
    vm._ubridge_hypervisor = MagicMock()

    async def send(command):
        if "brctl delif" in command or "brctl delete" in command:
            raise UbridgeError("busy")

    vm._ubridge_send = AsyncioMagicMock(side_effect=send)
    vm._kernel_veths[(0, 0)] = vm._veth_names(0, 0)[0]
    vm._ethernet_adapters[0].add_nio(0, vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE}))

    await vm.adapter_remove_nio_binding(0)  # must not raise


# ---------------------------------------------------------------------------
# Carrier / suspend
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_adapter_carrier_kernel(vm):

    vm._ubridge_send = AsyncioMagicMock()
    host_ifc, _ = vm._veth_names(0, 0)
    vm._kernel_veths[(0, 0)] = host_ifc

    await vm._set_adapter_carrier(0, True)
    await vm._set_adapter_carrier(0, False)

    vm._ubridge_send.assert_has_calls(
        [
            call(f'link set "{host_ifc}" up'),
            call(f'link set "{host_ifc}" down'),
        ]
    )


# ---------------------------------------------------------------------------
# UDP fallback on a veth adapter (kernel link deleted, relay link created
# on a running node)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_connect_nio_udp_relays_over_veth(vm):

    vm._ubridge_send = AsyncioMagicMock()
    host_ifc, _ = vm._veth_names(0, 0)
    vm._kernel_veths[(0, 0)] = host_ifc

    nio = vm.manager.create_nio({"type": "nio_udp", "lport": 4242, "rport": 4343, "rhost": "127.0.0.1"})
    await vm._connect_nio(0, nio)

    vm._ubridge_send.assert_has_calls(
        [
            call("bridge create bridge0"),
            call(f'bridge add_nio_ethernet bridge0 "{host_ifc}"'),
            call("bridge add_nio_udp bridge0 4242 127.0.0.1 4343"),
            call("bridge start bridge0"),
        ],
        any_order=True,
    )
    assert "bridge0" in vm._bridges


@pytest.mark.asyncio
async def test_connect_nio_udp_on_veth_is_idempotent(vm):

    vm._ubridge_send = AsyncioMagicMock()
    host_ifc, _ = vm._veth_names(0, 0)
    vm._kernel_veths[(0, 0)] = host_ifc
    vm._bridges.add("bridge0")  # relay already exists from a previous link

    nio = vm.manager.create_nio({"type": "nio_udp", "lport": 4242, "rport": 4343, "rhost": "127.0.0.1"})
    await vm._connect_nio(0, nio)

    for c in vm._ubridge_send.call_args_list:
        command = c.args[0]
        assert "bridge create" not in command
        assert "add_nio_ethernet" not in command


# ---------------------------------------------------------------------------
# Guards and cleanup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_nio_kernel_applies_ebpf_drops(vm):
    """
    frequency_drop becomes the eBPF every-Nth mode and quota the byte-cap
    mode, applied after the netem/bpf pass on the same NIO update.
    """

    vm._ubridge_hypervisor = _caps_hypervisor(ebpf="1")
    vm._ubridge_send = AsyncioMagicMock()
    vm.status = "started"
    host_ifc, _ = vm._veth_names(0, 0)
    vm._kernel_veths[(0, 0)] = host_ifc
    nio = vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE})
    vm._ethernet_adapters[0].add_nio(0, nio)
    nio.filters = {"frequency_drop": [3], "quota": [1000000, 50]}

    await vm.adapter_update_nio_binding(0, nio)
    vm._ubridge_send.assert_any_call(f'tc nth_drop "{host_ifc}" 3')
    vm._ubridge_send.assert_any_call(f'tc quota_drop "{host_ifc}" 1000000 50')


@pytest.mark.asyncio
async def test_update_nio_kernel_ebpf_drop_everything(vm):
    """
    frequency_drop -1 (drop everything) maps to every 1st packet.
    """

    vm._ubridge_hypervisor = _caps_hypervisor(ebpf="1")
    vm._ubridge_send = AsyncioMagicMock()
    vm.status = "started"
    host_ifc, _ = vm._veth_names(0, 0)
    vm._kernel_veths[(0, 0)] = host_ifc
    nio = vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE})
    vm._ethernet_adapters[0].add_nio(0, nio)
    nio.filters = {"frequency_drop": [-1]}

    await vm.adapter_update_nio_binding(0, nio)
    vm._ubridge_send.assert_any_call(f'tc nth_drop "{host_ifc}" 1')
    # the quota mode is explicitly off (not left to chance)
    vm._ubridge_send.assert_any_call(f'tc quota_drop "{host_ifc}" off')


@pytest.mark.asyncio
async def test_update_nio_kernel_turns_ebpf_modes_off(vm):
    """
    A re-apply with the stateful filters removed must turn both modes off
    (the netem reset already detached the program; the offs are idempotent).
    """

    vm._ubridge_hypervisor = _caps_hypervisor(ebpf="1")
    vm._ubridge_send = AsyncioMagicMock()
    vm.status = "started"
    host_ifc, _ = vm._veth_names(0, 0)
    vm._kernel_veths[(0, 0)] = host_ifc
    nio = vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE})
    vm._ethernet_adapters[0].add_nio(0, nio)
    nio.filters = {"frequency_drop": [3]}

    await vm.adapter_update_nio_binding(0, nio)
    vm._ubridge_send.reset_mock()
    nio.filters = {"delay": [50]}
    await vm.adapter_update_nio_binding(0, nio)

    vm._ubridge_send.assert_any_call(f'tc nth_drop "{host_ifc}" off')
    vm._ubridge_send.assert_any_call(f'tc quota_drop "{host_ifc}" off')
    vm._ubridge_send.assert_any_call(f'tc window_drop "{host_ifc}" off')
    for c in vm._ubridge_send.call_args_list:
        assert "nth_drop" not in c.args[0] or "off" in c.args[0]


@pytest.mark.asyncio
async def test_apply_ebpf_drops_requires_ebpf_capability(vm):
    """
    An old or non-capped uBridge (ebpf=0) gets a clear upgrade error naming
    the setcap fix.
    """

    hyp = MagicMock()
    hyp.is_running.return_value = True
    hyp.send = AsyncioMagicMock(return_value=["netem=delay;ebpf=0;cbpf=1"])
    vm._ubridge_hypervisor = hyp
    vm._ubridge_send = AsyncioMagicMock()
    host_ifc, _ = vm._veth_names(0, 0)

    with pytest.raises(DockerError, match="setcap cap_bpf"):
        await vm._ubridge_apply_ebpf_drops(host_ifc, {"frequency_drop": [3]})
    vm._ubridge_send.assert_not_called()


@pytest.mark.asyncio
async def test_update_nio_kernel_applies_window_drop(vm):
    """
    window_drop becomes the eBPF time-window mode: the positional
    [start, outage, chance, period, jitter] maps 1:1 onto the tc command
    (trailing optionals omitted), and an absent window is turned off.
    """

    vm._ubridge_hypervisor = _caps_hypervisor(ebpf="1")
    vm._ubridge_send = AsyncioMagicMock()
    vm.status = "started"
    host_ifc, _ = vm._veth_names(0, 0)
    vm._kernel_veths[(0, 0)] = host_ifc
    nio = vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE})
    vm._ethernet_adapters[0].add_nio(0, nio)

    nio.filters = {"window_drop": [0, 2000, 100]}
    await vm.adapter_update_nio_binding(0, nio)
    vm._ubridge_send.assert_any_call(f'tc window_drop "{host_ifc}" 0 2000 100')

    vm._ubridge_send.reset_mock()
    nio.filters = {"window_drop": [500, 800, 100, 2400, 300]}
    await vm.adapter_update_nio_binding(0, nio)
    vm._ubridge_send.assert_any_call(f'tc window_drop "{host_ifc}" 500 800 100 2400 300')

    # only the window mode present: nth/quota are explicitly off
    vm._ubridge_send.assert_any_call(f'tc nth_drop "{host_ifc}" off')
    vm._ubridge_send.assert_any_call(f'tc quota_drop "{host_ifc}" off')


@pytest.mark.asyncio
async def test_apply_window_drop_requires_ebpf_capability(vm):
    """
    The window mode shares the eBPF capability gate (error names setcap).
    """

    hyp = MagicMock()
    hyp.is_running.return_value = True
    hyp.send = AsyncioMagicMock(return_value=["netem=delay;ebpf=0;cbpf=1"])
    vm._ubridge_hypervisor = hyp
    vm._ubridge_send = AsyncioMagicMock()
    host_ifc, _ = vm._veth_names(0, 0)

    with pytest.raises(DockerError, match="setcap cap_bpf"):
        await vm._ubridge_apply_ebpf_drops(host_ifc, {"window_drop": [0, 2000, 100]})
    vm._ubridge_send.assert_not_called()


@pytest.mark.asyncio
async def test_apply_ebpf_drops_skips_old_ubridge_without_filters(vm):
    """
    No stateful filters and no capability probe yet: nothing was ever
    installed on an old uBridge, so it must not be touched at all.
    """

    vm._ubridge_hypervisor = MagicMock()
    vm._ubridge_send = AsyncioMagicMock()
    host_ifc, _ = vm._veth_names(0, 0)

    await vm._ubridge_apply_ebpf_drops(host_ifc, {})
    vm._ubridge_send.assert_not_called()
    vm._ubridge_hypervisor.send.assert_not_called()


@pytest.mark.asyncio
async def test_apply_ebpf_drops_cleanup_only_probes_with_ebpf(vm):
    """
    The filter-removal path (modes off) only talks to the eBPF commands
    when the capability probe reported them — a netem-ext uBridge without
    the eBPF module must not see an unknown command.
    """

    hyp = MagicMock()
    hyp.is_running.return_value = True
    hyp.send = AsyncioMagicMock(return_value=["netem=delay,rate;ebpf=0;cbpf=1"])
    vm._ubridge_hypervisor = hyp
    vm._ubridge_send = AsyncioMagicMock()
    host_ifc, _ = vm._veth_names(0, 0)
    vm._ubridge_tc_caps = None  # force the probe (something was set before)

    await vm._ubridge_apply_ebpf_drops(host_ifc, {})
    vm._ubridge_send.assert_not_called()


def _caps_hypervisor(cbpf="1", ebpf="0"):
    """A hypervisor mock whose direct send() answers `tc capabilities`."""
    hyp = MagicMock()
    hyp.is_running.return_value = True
    hyp.send = AsyncioMagicMock(return_value=[f"netem=delay;ebpf={ebpf};cbpf={cbpf}"])
    return hyp


@pytest.mark.asyncio
async def test_update_nio_kernel_applies_bpf_drops(vm):
    """
    bpf lines reconcile as flush + one bpf_drop add per line at successive
    priorities (any line matching drops — OR semantics like the relay).
    """

    vm._ubridge_hypervisor = _caps_hypervisor()
    vm._ubridge_send = AsyncioMagicMock()
    vm.status = "started"
    host_ifc, _ = vm._veth_names(0, 0)
    vm._kernel_veths[(0, 0)] = host_ifc
    nio = vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE})
    vm._ethernet_adapters[0].add_nio(0, nio)
    nio.filters = {"bpf": ["icmp\nudp port 53"]}

    await vm.adapter_update_nio_binding(0, nio)
    vm._ubridge_send.assert_any_call(f'tc bpf_drop flush "{host_ifc}"')
    vm._ubridge_send.assert_any_call(f'tc bpf_drop add "{host_ifc}" 10 "icmp"')
    vm._ubridge_send.assert_any_call(f'tc bpf_drop add "{host_ifc}" 11 "udp port 53"')


@pytest.mark.asyncio
async def test_update_nio_kernel_flushes_bpf_drops_when_removed(vm):

    vm._ubridge_hypervisor = _caps_hypervisor()
    vm._ubridge_send = AsyncioMagicMock()
    vm.status = "started"
    host_ifc, _ = vm._veth_names(0, 0)
    vm._kernel_veths[(0, 0)] = host_ifc
    nio = vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE})
    vm._ethernet_adapters[0].add_nio(0, nio)
    nio.filters = {"bpf": ["icmp"]}

    await vm.adapter_update_nio_binding(0, nio)
    vm._ubridge_send.reset_mock()
    nio.filters = {}
    await vm.adapter_update_nio_binding(0, nio)
    vm._ubridge_send.assert_any_call(f'tc bpf_drop flush "{host_ifc}"')
    for c in vm._ubridge_send.call_args_list:
        assert "bpf_drop add" not in c.args[0]


@pytest.mark.asyncio
async def test_apply_bpf_drops_requires_cbpf_capability(vm):

    vm._ubridge_hypervisor = _caps_hypervisor(cbpf="0")
    vm._ubridge_send = AsyncioMagicMock()
    host_ifc, _ = vm._veth_names(0, 0)

    with pytest.raises(DockerError, match="upgrade uBridge"):
        await vm._ubridge_apply_bpf_drops(host_ifc, {"bpf": ["icmp"]})


@pytest.mark.asyncio
async def test_apply_bpf_drops_compile_failure_warns(vm):
    """
    A line that compiles for the controller's tcpdump but not for this
    uBridge's libpcap is skipped with a warning — mirrors the relay path.
    """

    vm._ubridge_hypervisor = _caps_hypervisor()
    host_ifc, _ = vm._veth_names(0, 0)

    async def send(command):
        if "bpf_drop add" in command:
            raise UbridgeError("209-Cannot compile filter 'icmp': can't parse filter expression: syntax error")

    vm._ubridge_send = AsyncioMagicMock(side_effect=send)
    with patch("gns3server.compute.docker.docker_vm.log.warning") as mock_log:
        await vm._ubridge_apply_bpf_drops(host_ifc, {"bpf": ["icmp"]})  # must not raise
    assert mock_log.called


@pytest.mark.asyncio
async def test_apply_bpf_drops_skips_old_ubridge_without_lines(vm):
    """
    No bpf lines and no capability probe yet: nothing was ever installed on
    an old uBridge, so it must not be touched at all (no unknown-module error).
    """

    vm._ubridge_hypervisor = MagicMock()
    vm._ubridge_send = AsyncioMagicMock()
    host_ifc, _ = vm._veth_names(0, 0)

    await vm._ubridge_apply_bpf_drops(host_ifc, {})
    vm._ubridge_send.assert_not_called()
    vm._ubridge_hypervisor.send.assert_not_called()


@pytest.mark.asyncio
async def test_ubridge_tc_capabilities_probed_once(vm):

    vm._ubridge_hypervisor = _caps_hypervisor()
    caps = await vm._ubridge_tc_capabilities()
    assert caps == {"netem": "delay", "ebpf": "0", "cbpf": "1"}
    await vm._ubridge_tc_capabilities()
    assert vm._ubridge_hypervisor.send.call_count == 1


@pytest.mark.asyncio
async def test_update_nio_kernel_applies_netem(vm):

    vm._ubridge_hypervisor = MagicMock()
    vm._ubridge_send = AsyncioMagicMock()
    vm.status = "started"
    host_ifc, _ = vm._veth_names(0, 0)
    vm._kernel_veths[(0, 0)] = host_ifc
    nio = vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE})
    vm._ethernet_adapters[0].add_nio(0, nio)
    nio.filters = {"delay": [50, 5], "packet_loss": [10], "corrupt": [2]}

    await vm.adapter_update_nio_binding(0, nio)
    vm._ubridge_send.assert_any_call(f'tc netem set "{host_ifc}" delay 50 jitter 5 loss 10 corrupt 2')


@pytest.mark.asyncio
async def test_update_nio_kernel_clears_netem(vm):
    """
    Filters dropped to empty must detach the qdisc (the veth survives link
    changes); ENOENT (no qdisc was attached) is tolerated.
    """

    vm._ubridge_hypervisor = MagicMock()
    vm._ubridge_send = AsyncioMagicMock()
    vm.status = "started"
    host_ifc, _ = vm._veth_names(0, 0)
    vm._kernel_veths[(0, 0)] = host_ifc
    nio = vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE})
    vm._ethernet_adapters[0].add_nio(0, nio)
    nio.filters = {}

    await vm.adapter_update_nio_binding(0, nio)
    vm._ubridge_send.assert_any_call(f'tc reset "{host_ifc}"')


@pytest.mark.asyncio
async def test_apply_netem_reset_tolerates_missing_qdisc(vm):

    vm._ubridge_hypervisor = MagicMock()
    from gns3server.compute.ubridge.ubridge_error import UbridgeError

    async def refuse(command):
        raise UbridgeError("207-Could not reset qdisc on gv0: No such file or directory")

    vm._ubridge_send = refuse
    host_ifc, _ = vm._veth_names(0, 0)
    # ENOENT means "already clean" — must not raise
    await vm._ubridge_apply_netem(host_ifc, {})


@pytest.mark.asyncio
async def test_apply_netem_reset_reraises_real_errors(vm):

    vm._ubridge_hypervisor = MagicMock()
    from gns3server.compute.ubridge.ubridge_error import UbridgeError

    async def refuse(command):
        raise UbridgeError("206-Could not reset qdisc on gv0: Operation not permitted")

    vm._ubridge_send = refuse
    host_ifc, _ = vm._veth_names(0, 0)
    with pytest.raises(UbridgeError):
        await vm._ubridge_apply_netem(host_ifc, {})


@pytest.mark.asyncio
async def test_update_nio_kernel_suspend_toggles_carrier(vm):

    vm._ubridge_hypervisor = MagicMock()
    vm._ubridge_send = AsyncioMagicMock()
    vm.status = "started"
    host_ifc, _ = vm._veth_names(0, 0)
    vm._kernel_veths[(0, 0)] = host_ifc
    nio = vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE})
    vm._ethernet_adapters[0].add_nio(0, nio)

    nio.suspend = True
    await vm.adapter_update_nio_binding(0, nio)
    vm._ubridge_send.assert_any_call(f'link set "{host_ifc}" down')


@pytest.mark.asyncio
async def test_start_capture_kernel_uses_af_packet(vm):

    vm._ubridge_hypervisor = MagicMock()
    vm._ubridge_send = AsyncioMagicMock()
    vm.status = "started"
    host_ifc, _ = vm._veth_names(0, 0)
    vm._kernel_veths[(0, 0)] = host_ifc
    nio = vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE})
    vm._ethernet_adapters[0].add_nio(0, nio)

    await vm.start_capture(0, "/tmp/capture.pcap")

    assert nio.capturing is True
    vm._ubridge_send.assert_any_call(f'capture start_kernel {host_ifc} "/tmp/capture.pcap"')


@pytest.mark.asyncio
async def test_stop_capture_kernel(vm):

    vm._ubridge_hypervisor = MagicMock()
    vm._ubridge_send = AsyncioMagicMock()
    vm.status = "started"
    host_ifc, _ = vm._veth_names(0, 0)
    vm._kernel_veths[(0, 0)] = host_ifc
    nio = vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE})
    vm._ethernet_adapters[0].add_nio(0, nio)
    await vm.start_capture(0, "/tmp/capture.pcap")

    await vm.stop_capture(0)

    assert nio.capturing is False
    vm._ubridge_send.assert_any_call("capture stop_kernel")


@pytest.mark.asyncio
async def test_start_capture_second_concurrent_fails(vm):
    """
    uBridge's kernel capture is a singleton per process: a second concurrent
    capture returns EALREADY and must surface to the caller.
    """

    async def send(command):
        if "capture start_kernel" in command:
            raise UbridgeError("Could not start kernel capture: Operation already in progress")

    vm._ubridge_hypervisor = MagicMock()
    vm._ubridge_send = AsyncioMagicMock(side_effect=send)
    vm.status = "started"
    vm._kernel_veths[(0, 0)] = vm._veth_names(0, 0)[0]
    nio = vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE})
    vm._ethernet_adapters[0].add_nio(0, nio)

    with pytest.raises(UbridgeError, match="already in progress"):
        await vm.start_capture(0, "/tmp/capture.pcap")


@pytest.mark.asyncio
async def test_connect_nio_kernel_restarts_capture(vm):

    vm._ubridge_send = AsyncioMagicMock()
    host_ifc, _ = vm._veth_names(0, 0)
    vm._kernel_veths[(0, 0)] = host_ifc

    nio = vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE})
    nio.start_packet_capture("/tmp/capture.pcap")
    await vm._connect_nio(0, nio)

    vm._ubridge_send.assert_any_call(f'capture start_kernel {host_ifc} "/tmp/capture.pcap"')


# ---------------------------------------------------------------------------
# Markers (AF_PACKET taps on the veth host end)
# ---------------------------------------------------------------------------


def _marker_spec(bpf="icmp", tag=1, enabled=True, direction=None, link_id="l1"):
    return {
        "bpf": bpf,
        "tag": tag,
        "enabled": enabled,
        "direction": direction,
        "data_link_type": "DLT_EN10MB",
        "link_id": link_id,
    }


@pytest.mark.asyncio
async def test_connect_nio_kernel_applies_markers(vm):

    vm._ubridge_send = AsyncioMagicMock()
    host_ifc, _ = vm._veth_names(0, 0)
    vm._kernel_veths[(0, 0)] = host_ifc

    nio = vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE, "markers": {"icmp-m": _marker_spec()}})
    await vm._connect_nio(0, nio)

    pcap = os.path.join(vm.project.markers_working_directory(), f"{vm.id}_l1_icmp-m.pcap")
    vm._ubridge_send.assert_any_call(f'marker add_kernel icmp-m {host_ifc} "icmp" tag 1 link l1 pcap "{pcap}"')
    assert vm._marker_filter_bridges[("icmp-m", "l1")] == host_ifc


@pytest.mark.asyncio
async def test_connect_nio_kernel_marker_disabled_at_apply(vm):
    """
    A disabled marker is installed but silenced (marker enable_kernel off) so
    the UI can flip it back on instantly — same contract as the relay path.
    """

    vm._ubridge_send = AsyncioMagicMock()
    host_ifc, _ = vm._veth_names(0, 0)
    vm._kernel_veths[(0, 0)] = host_ifc

    nio = vm.manager.create_nio(
        {"type": "nio_bridge", "bridge": BRIDGE, "markers": {"icmp-m": _marker_spec(enabled=False)}}
    )
    await vm._connect_nio(0, nio)

    vm._ubridge_send.assert_any_call(f"marker enable_kernel {host_ifc} icmp-m off")


@pytest.mark.asyncio
async def test_update_nio_kernel_applies_markers(vm):

    vm._ubridge_hypervisor = MagicMock()
    vm._ubridge_send = AsyncioMagicMock()
    vm.status = "started"
    host_ifc, _ = vm._veth_names(0, 0)
    vm._kernel_veths[(0, 0)] = host_ifc
    nio = vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE})
    vm._ethernet_adapters[0].add_nio(0, nio)

    nio.markers = {"tcp-m": _marker_spec(bpf="tcp", tag=2, link_id="l2")}
    await vm.adapter_update_nio_binding(0, nio)

    pcap = os.path.join(vm.project.markers_working_directory(), f"{vm.id}_l2_tcp-m.pcap")
    vm._ubridge_send.assert_any_call(f'marker add_kernel tcp-m {host_ifc} "tcp" tag 2 link l2 pcap "{pcap}"')


@pytest.mark.asyncio
async def test_marker_toggle_kernel_uses_enable_kernel(vm):

    vm._ubridge_send = AsyncioMagicMock()
    host_ifc, _ = vm._veth_names(0, 0)
    vm._kernel_veths[(0, 0)] = host_ifc
    vm._marker_filter_bridges[("icmp-m", "l1")] = host_ifc

    await vm._ubridge_set_marker_filter_state("icmp-m", False)
    vm._ubridge_send.assert_any_call(f"marker enable_kernel {host_ifc} icmp-m off")
    await vm._ubridge_set_marker_filter_state("icmp-m", True)
    vm._ubridge_send.assert_any_call(f"marker enable_kernel {host_ifc} icmp-m on")


@pytest.mark.asyncio
async def test_remove_kernel_nio_deletes_markers(vm):
    """
    The veth survives link deletion (it is the adapter interface), so kernel
    markers must be torn down explicitly — otherwise a deleted link's markers
    would keep sniffing and signaling.
    """

    vm._ubridge_hypervisor = MagicMock()
    vm._ubridge_send = AsyncioMagicMock()
    vm.status = "started"
    host_ifc, _ = vm._veth_names(0, 0)
    vm._kernel_veths[(0, 0)] = host_ifc
    vm._marker_filter_bridges[("icmp-m", "l1")] = host_ifc
    vm._marker_specs[("icmp-m", "l1")] = _marker_spec()
    vm._ethernet_adapters[0].add_nio(0, vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE}))

    await vm.adapter_remove_nio_binding(0)

    vm._ubridge_send.assert_any_call(f"marker delete_kernel {host_ifc} icmp-m")
    assert ("icmp-m", "l1") not in vm._marker_filter_bridges
    assert ("icmp-m", "l1") not in vm._marker_specs


@pytest.mark.asyncio
async def test_rebuild_marker_filter_kernel(vm):
    """
    The fine-grained rebuild path (bpf/tag/direction change) goes through the
    overridden primitives: delete_kernel + add_kernel with the new expression.
    """

    vm._ubridge_hypervisor = MagicMock()
    vm._ubridge_send = AsyncioMagicMock()
    host_ifc, _ = vm._veth_names(0, 0)
    vm._kernel_veths[(0, 0)] = host_ifc
    vm._marker_filter_bridges[("icmp-m", "l1")] = host_ifc

    await vm.rebuild_marker_filter("icmp-m", "l1", "tcp", tag=9)

    pcap = os.path.join(vm.project.markers_working_directory(), f"{vm.id}_l1_icmp-m.pcap")
    vm._ubridge_send.assert_any_call(f"marker delete_kernel {host_ifc} icmp-m")
    vm._ubridge_send.assert_any_call(f'marker add_kernel icmp-m {host_ifc} "tcp" tag 9 link l1 pcap "{pcap}"')


@pytest.mark.asyncio
async def test_remove_kernel_veths(vm):

    vm._ubridge_hypervisor = MagicMock()
    vm._ubridge_send = AsyncioMagicMock()
    host_ifc, _ = vm._veth_names(0, 0)
    vm._kernel_veths[(0, 0)] = host_ifc

    await vm._remove_kernel_veths()

    vm._ubridge_send.assert_called_once_with(f'docker delete_veth "{host_ifc}"')
    assert vm._kernel_veths == {}


def test_veth_names_deterministic_and_bounded(vm):

    host_ifc, guest_ifc = vm._veth_names(3, 2)
    assert host_ifc == f"gv{vm.id.replace('-', '')[:8]}e3p2"
    assert guest_ifc == f"gc{vm.id.replace('-', '')[:8]}e3p2"
    assert host_ifc != guest_ifc
    # multi-port adapters can reach two-digit adapter/port numbers
    long_host, long_guest = vm._veth_names(12, 8)
    assert len(long_host) <= 15 and len(long_guest) <= 15


# ---------------------------------------------------------------------------
# P6a: netem extensions (rate / reorder / gemodel / duplicate / seed / limit /
# distribution / correlation) — translation and capability gating
# ---------------------------------------------------------------------------


def _caps_hypervisor_netem(tokens="delay,jitter,loss,dup,corrupt,rate,reorder,gemodel,dist,seed,limit"):
    """A hypervisor mock whose direct send() answers `tc capabilities` with
    the full netem-extension surface."""
    hyp = MagicMock()
    hyp.is_running.return_value = True
    hyp.send = AsyncioMagicMock(return_value=[f"netem={tokens};ebpf=1;cbpf=1"])
    return hyp


@pytest.mark.asyncio
async def test_update_nio_kernel_applies_netem_extensions(vm):
    """
    The netem-extension filters merge into the single netem qdisc command,
    in the frozen grammar order.
    """

    vm._ubridge_hypervisor = _caps_hypervisor_netem()
    vm._ubridge_send = AsyncioMagicMock()
    vm.status = "started"
    host_ifc, _ = vm._veth_names(0, 0)
    vm._kernel_veths[(0, 0)] = host_ifc
    nio = vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE})
    vm._ethernet_adapters[0].add_nio(0, nio)
    nio.filters = {
        "delay": [100, 20, "normal"],
        "packet_loss": [5, 25],
        "duplicate": [10, 50],
        "corrupt": [2],
        "reorder": [25, 50, 5],
        "rate": ["512kbit"],
        "limit": [5000],
        "seed": [42],
    }

    await vm.adapter_update_nio_binding(0, nio)
    vm._ubridge_send.assert_any_call(
        f'tc netem set "{host_ifc}" delay 100 jitter 20 loss 5 correl 25 dup 10 correl 50 corrupt 2 '
        "reorder 25 correl 50 gap 5 rate 512kbit limit 5000 distribution normal seed 42"
    )


@pytest.mark.asyncio
async def test_update_nio_kernel_applies_gemodel(vm):
    """
    gemodel replaces the plain loss keyword and is mutually exclusive with
    packet_loss (the controller validates; the translation just prefers
    gemodel when both somehow arrive).
    """

    vm._ubridge_hypervisor = _caps_hypervisor_netem()
    vm._ubridge_send = AsyncioMagicMock()
    vm.status = "started"
    host_ifc, _ = vm._veth_names(0, 0)
    vm._kernel_veths[(0, 0)] = host_ifc
    nio = vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE})
    vm._ethernet_adapters[0].add_nio(0, nio)
    nio.filters = {"delay": [50, 5], "gemodel": [100, 0, 30]}

    await vm.adapter_update_nio_binding(0, nio)
    vm._ubridge_send.assert_any_call(f'tc netem set "{host_ifc}" delay 50 jitter 5 loss gemodel 100 0 30')


@pytest.mark.asyncio
async def test_apply_netem_extension_needs_capability(vm):
    """
    Extension keywords on an old uBridge (no tc capabilities / no netem-ext
    tokens) raise a clear upgrade error instead of a raw parse failure.
    """

    # old uBridge: no tc module at all -> empty capabilities
    vm._ubridge_hypervisor = MagicMock()
    vm._ubridge_hypervisor.is_running.return_value = True
    vm._ubridge_hypervisor.send = AsyncioMagicMock(side_effect=UbridgeError("201-Unknown command"))
    vm._ubridge_send = AsyncioMagicMock()
    host_ifc, _ = vm._veth_names(0, 0)

    with pytest.raises(DockerError, match="netem extensions"):
        await vm._ubridge_apply_netem(host_ifc, {"rate": ["512kbit"]})
    vm._ubridge_send.assert_not_called()


@pytest.mark.asyncio
async def test_apply_netem_extension_partial_capability(vm):
    """
    A uBridge that reports some but not all needed tokens fails on the
    missing ones (per-token check, not just build detection).
    """

    vm._ubridge_hypervisor = _caps_hypervisor_netem(tokens="delay,jitter,loss,dup,corrupt")
    vm._ubridge_send = AsyncioMagicMock()
    host_ifc, _ = vm._veth_names(0, 0)

    with pytest.raises(DockerError, match="rate, reorder"):
        await vm._ubridge_apply_netem(host_ifc, {"delay": [50], "reorder": [25], "rate": ["1mbit"]})


@pytest.mark.asyncio
async def test_apply_netem_plain_surface_never_probes(vm):
    """
    Original-surface filters (delay/loss/corrupt, and plain dup) must not
    touch the capability probe at all — an old uBridge serves them as-is.
    The reset-before-set is unconditional (kernel netem replace merges
    optional attrs, so a removed parameter would otherwise leak).
    """

    vm._ubridge_hypervisor = MagicMock()
    vm._ubridge_send = AsyncioMagicMock()
    host_ifc, _ = vm._veth_names(0, 0)

    await vm._ubridge_apply_netem(host_ifc, {"delay": [50, 5], "packet_loss": [10], "duplicate": [10], "corrupt": [2]})
    assert vm._ubridge_send.call_args_list == [
        call(f'tc reset "{host_ifc}"'),
        call(f'tc netem set "{host_ifc}" delay 50 jitter 5 loss 10 dup 10 corrupt 2'),
    ]
    vm._ubridge_hypervisor.send.assert_not_called()


@pytest.mark.asyncio
async def test_apply_netem_reset_leak_on_removal(vm):
    """
    A re-apply with a parameter REMOVED (rate gone, delay kept) must reset
    first: the kernel's netem change merges optional attributes, so a bare
    replace would keep the old rate shaping forever.
    """

    vm._ubridge_hypervisor = _caps_hypervisor_netem()
    vm._ubridge_send = AsyncioMagicMock()
    host_ifc, _ = vm._veth_names(0, 0)

    await vm._ubridge_apply_netem(host_ifc, {"delay": [50], "rate": ["1mbit"]})
    vm._ubridge_send.reset_mock()
    await vm._ubridge_apply_netem(host_ifc, {"delay": [50]})

    assert vm._ubridge_send.call_args_list == [
        call(f'tc reset "{host_ifc}"'),
        call(f'tc netem set "{host_ifc}" delay 50'),
    ]


@pytest.mark.asyncio
async def test_apply_netem_correl_gates_on_extension_build(vm):
    """
    Loss/dup correlation is an extension (the capabilities string has no
    correl token) — it gates on the netem-extension build marker "rate".
    """

    vm._ubridge_hypervisor = _caps_hypervisor_netem(tokens="delay,jitter,loss,dup,corrupt")
    vm._ubridge_send = AsyncioMagicMock()
    host_ifc, _ = vm._veth_names(0, 0)

    with pytest.raises(DockerError, match="netem extensions"):
        await vm._ubridge_apply_netem(host_ifc, {"packet_loss": [5, 25]})


def test_create_nio_bridge_accepts_netem_extension_filters(vm):

    nio = vm.manager.create_nio(
        {"type": "nio_bridge", "bridge": BRIDGE, "filters": {"rate": ["512kbit"], "reorder": [25, 0, 5]}}
    )
    assert isinstance(nio, NIOBridge)
    assert nio.filters == {"rate": ["512kbit"], "reorder": [25, 0, 5]}


def test_create_nio_udp_rejects_kernel_only_filters(vm):
    """
    The relay NIO rejects netem-extension filter types (second guard behind
    the controller).
    """

    with pytest.raises(ComputeError, match="kernel-datapath"):
        vm.manager.create_nio(
            {"type": "nio_udp", "lport": 4242, "rport": 4343, "rhost": "127.0.0.1", "filters": {"gemodel": [100, 0, 30]}}
        )


@pytest.mark.asyncio
async def test_stop_clears_relay_bridge_registry(vm):
    """
    The uBridge process dies with every bridge it hosted — stop() must drop
    the relay bridge names, or the next start skips "bridge create" (the
    gate checks the name's presence) and fails on add_nio_udp.
    """

    vm._ubridge_hypervisor = MagicMock()
    vm._ubridge_send = AsyncioMagicMock()
    vm._bridges.add("bridge1")
    vm._ubridge_tc_caps = {"netem": "delay"}

    async def query(method, path, *args, **kwargs):
        raise DockerHttp404Error("no such container")

    vm.manager.query = AsyncioMagicMock(side_effect=query)
    await vm.stop()
    assert vm._bridges == set()
    assert vm._ubridge_tc_caps is None
