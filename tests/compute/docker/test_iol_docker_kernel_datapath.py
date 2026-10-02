#
# Copyright (C) 2026 GNS3 Technologies Inc.
#
# This program is free software and is distributed under the same terms as gns3-server.
# See the LICENSE file for licensing information.
#

"""
Kernel-datapath tests for IOLDockerVM: the persistent TAP anchors (one per
Ethernet bay/unit), the per-port bridge's swappable topology leg (unix ↔ UDP
relay vs unix ↔ TAP anchor) and the teardown order the fd holders dictate.

Image-free: everything is asserted against the uBridge command stream and
the anchor naming contract.
"""

import uuid

import pytest
import pytest_asyncio

from unittest.mock import MagicMock, patch

from tests.utils import AsyncioMagicMock

from gns3server.compute.docker import Docker
from gns3server.compute.docker.docker_error import DockerError
from gns3server.compute.docker.iol_docker_vm import IOLDockerVM


NODE_ID = "00010203-0405-0607-0809-0a0b0c0d0e0f"
TAP00 = "gx00010203e0p0"  # the vm fixture's node id, bay 0 unit 0
TAP01 = "gx00010203e0p1"
TAP10 = "gx00010203e1p0"
PORT_BRIDGE = "bridge0"  # adapter 0 port 0 (single-port naming)
BRIDGE = "gns3abc123def45"  # the per-link kernel bridge carried by the NIO


@pytest_asyncio.fixture
async def manager(port_manager):

    m = Docker.instance()
    m.port_manager = port_manager
    return m


@pytest_asyncio.fixture(scope="function")
async def vm(compute_project, manager):

    vm = IOLDockerVM(
        "iol-xe-1",
        NODE_ID,
        compute_project,
        manager,
        "iol-xe/iol-xe:17-18-02",
        environment="GNS3_IOL_RUNNER=1",
        adapters=2,
    )
    vm._cid = "e90e34656842"
    vm.application_id = 700
    vm._ubridge_hypervisor = MagicMock()
    vm._ubridge_hypervisor.is_running.return_value = True
    vm._ubridge_send = AsyncioMagicMock()
    return vm


def _capable(vm, monkeypatch):
    """Make both anchor-lifecycle probes answer True."""

    async def probe(timeout=15.0):
        return True

    monkeypatch.setattr("gns3server.compute.docker.iol_docker_vm.probe_bridge_tap_support", probe)
    monkeypatch.setattr("gns3server.compute.docker.iol_docker_vm.probe_tap_support", probe)
    return vm


def _commands(vm):
    return [str(c.args[0]) for c in vm._ubridge_send.call_args_list]


# ---------------------------------------------------------------------------
# Anchor lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prepare_tap_datapath_creates_one_tap_per_bay_unit(vm, monkeypatch):
    """
    On a capable uBridge every Ethernet bay/unit gets its persistent TAP —
    four units per adapter (the IOU model), swept of leftovers first and
    born down. No set_owner: uBridge itself holds these fds.
    """

    _capable(vm, monkeypatch)
    await vm._prepare_tap_datapath()

    assert vm._tap_datapath is True
    assert set(vm._kernel_taps) == {(bay, unit) for bay in range(2) for unit in range(4)}
    assert vm._kernel_taps[(0, 0)] == TAP00
    commands = _commands(vm)
    assert f'tap delete "{TAP00}"' in commands  # the sweep precedes every create
    assert commands.index(f'tap delete "{TAP00}"') < commands.index(f'tap create "{TAP00}"')
    assert f'link set "{TAP00}" down' in commands
    assert not any("set_owner" in c for c in commands)


@pytest.mark.asyncio
async def test_prepare_tap_datapath_falls_back_without_either_probe(vm, monkeypatch):
    """
    A uBridge without the swappable TAP leg (or without the tap module at
    all) keeps the node on the relay datapath — it still starts, it just
    cannot carry kernel links.
    """

    async def probe(timeout=15.0):
        return None

    monkeypatch.setattr("gns3server.compute.docker.iol_docker_vm.probe_bridge_tap_support", probe)
    monkeypatch.setattr("gns3server.compute.docker.iol_docker_vm.probe_tap_support", probe)
    await vm._prepare_tap_datapath()

    assert vm._tap_datapath is False
    assert vm._kernel_taps == {}
    assert not any("tap create" in c for c in _commands(vm))


def test_tap_name_fits_ifnamsiz(vm):
    """
    The anchor name has to fit IFNAMSIZ (15) even for a late bay/unit.
    """

    assert len(vm._tap_name(7, 3)) <= 15


# ---------------------------------------------------------------------------
# Link attach / detach (the port bridge's swappable topology leg)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_attach_kernel_link_swaps_the_port_leg_to_the_anchor(vm):
    """
    A kernel link ensures the anchor (the frozen ensure-then-add contract —
    add_nio_tap on an absent name would open a transient TAP), swaps the
    port bridge's topology leg to it, runs the shared mixin flow (per-link
    kernel bridge, capture/markers/filters) and starts the relay — the unix
    binding untouched throughout.
    """

    vm._kernel_taps[(0, 0)] = TAP00
    vm._bridges.add(PORT_BRIDGE)  # the start flow registered the port bridge
    nio = vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE})

    await vm._attach_kernel_link(0, 0, nio)

    commands = _commands(vm)
    assert f'tap create "{TAP00}"' in commands  # ensure-then-add
    assert commands.index(f'tap create "{TAP00}"') < commands.index(f'bridge add_nio_tap {PORT_BRIDGE} "{TAP00}"')
    assert f'brctl create "{BRIDGE}"' in commands
    assert f'brctl addif "{BRIDGE}" "{TAP00}"' in commands
    assert commands.index(f'brctl addif "{BRIDGE}" "{TAP00}"') < commands.index(f"bridge start {PORT_BRIDGE}")
    assert f'link set "{TAP00}" up' in commands  # the carrier pass brings the anchor up
    assert not any("add_nio_udp" in c for c in commands)


@pytest.mark.asyncio
async def test_ensure_anchor_creates_only_when_missing(vm, monkeypatch):
    """
    tap create is strictly create-only (IFF_TUN_EXCL — an existing device
    answers EBUSY), so the ensure checks existence first: a present anchor
    costs no command, a swept one is recreated (the repair half of the
    ensure-then-add contract).
    """

    vm._kernel_taps[(0, 0)] = TAP00

    with monkeypatch.context() as missing:
        missing.setattr("os.path.exists", lambda p: False)
        await vm._ensure_anchor(0, 0)
    assert f'tap create "{TAP00}"' in _commands(vm)

    vm._ubridge_send.reset_mock()
    with monkeypatch.context() as present:
        present.setattr("os.path.exists", lambda p: True)
        await vm._ensure_anchor(0, 0)
    vm._ubridge_send.assert_not_called()


@pytest.mark.asyncio
async def test_attach_kernel_link_without_anchor_raises(vm):
    """
    A kernel link on a node that never anchored (relay-only uBridge, or a
    start that predates the kernel datapath) is an error naming the relay
    datapath, not a silent fallback.
    """

    nio = vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE})

    with pytest.raises(DockerError, match="no TAP anchor"):
        await vm._attach_kernel_link(0, 0, nio)


@pytest.mark.asyncio
async def test_add_ubridge_connection_routes_a_kernel_nio_to_the_anchor(vm):
    """
    The start-flow entry (also the restart-with-attached-link path) accepts
    a kernel NIO where the vendor class rejects it: the port bridge is
    ensured, then the same attach flow runs.
    """

    vm._kernel_taps[(0, 0)] = TAP00
    vm._bridges.add(PORT_BRIDGE)
    nio = vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE})

    await vm._add_ubridge_connection(nio, 0, 0)

    assert f'bridge add_nio_tap {PORT_BRIDGE} "{TAP00}"' in _commands(vm)


@pytest.mark.asyncio
async def test_add_nio_binding_relay_keeps_the_unix_udp_shape(vm):
    """
    A relay link on a running node wires only the UDP half — the port bridge
    and its unix NIO already exist from the start flow.
    """

    vm.status = "started"
    vm._bridges.add(PORT_BRIDGE)
    nio = vm.manager.create_nio({"type": "nio_udp", "lport": 20000, "rhost": "127.0.0.1", "rport": 20001})

    await vm.adapter_add_nio_binding(0, nio, 0)

    commands = _commands(vm)
    assert "bridge add_nio_udp bridge0 20000 127.0.0.1 20001" in commands
    assert "bridge start bridge0" in commands
    assert not any("add_nio_tap" in c for c in commands)


@pytest.mark.asyncio
async def test_update_nio_binding_kernel_reapplies_on_the_anchor(vm):
    """
    A filter update on an attached kernel link reconciles on the anchor (tc)
    without re-swapping the port leg or re-enslaving the TAP.
    """

    vm.status = "started"
    vm._kernel_taps[(0, 0)] = TAP00
    nio = vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE})
    vm._ethernet_adapters[0].add_nio(0, nio)
    nio.filters = {"delay": [10]}

    await vm.adapter_update_nio_binding(0, nio, 0)

    commands = _commands(vm)
    assert f'tc reset "{TAP00}"' in commands
    assert f'tc netem set "{TAP00}" delay 10' in commands
    assert not any("add_nio_tap" in c for c in commands)
    assert not any("brctl addif" in c for c in commands)


@pytest.mark.asyncio
async def test_update_nio_binding_kernel_suspend_flaps_the_anchor(vm):
    """
    Suspending a kernel link admin-downs the anchor: the port bridge's TAP
    writes fail EIO (dropped) and nothing comes back — a genuinely dead
    link, where the relay datapath used the synthetic filter instead.
    """

    vm.status = "started"
    vm._kernel_taps[(0, 0)] = TAP00
    nio = vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE})
    vm._ethernet_adapters[0].add_nio(0, nio)
    nio.suspend = True

    await vm.adapter_update_nio_binding(0, nio, 0)

    assert f'link set "{TAP00}" down' in _commands(vm)


@pytest.mark.asyncio
async def test_remove_nio_binding_kernel_releases_the_port_leg_first(vm):
    """
    Removing a kernel link stops the port bridge (its relay threads hold the
    NIO pointers for their whole life — delete_nio_tap refuses while
    running), releases the TAP NIO by name, then the shared anchor-side
    teardown runs: qdisc reset, brctl delif, per-link bridge deletion.
    """

    vm._kernel_taps[(0, 0)] = TAP00
    nio = vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE})
    vm._ethernet_adapters[0].add_nio(0, nio)

    await vm.adapter_remove_nio_binding(0, 0)

    commands = _commands(vm)
    assert f"bridge stop {PORT_BRIDGE}" in commands
    assert f'bridge delete_nio_tap {PORT_BRIDGE} "{TAP00}"' in commands
    assert commands.index(f"bridge stop {PORT_BRIDGE}") < commands.index(f'bridge delete_nio_tap {PORT_BRIDGE} "{TAP00}"')
    assert f'tc reset "{TAP00}"' in commands
    assert f'brctl delif "{BRIDGE}" "{TAP00}"' in commands
    assert f'brctl delete "{BRIDGE}"' in commands
    assert commands.index(f'bridge delete_nio_tap {PORT_BRIDGE} "{TAP00}"') < commands.index(f'tc reset "{TAP00}"')


@pytest.mark.asyncio
async def test_remove_nio_binding_relay_keeps_the_udp_teardown(vm):
    """
    Removing a relay link keeps the historical teardown: stop + UDP NIO
    removal, the unix NIO and its binding untouched.
    """

    vm.status = "started"
    vm._bridges.add(PORT_BRIDGE)
    nio = vm.manager.create_nio({"type": "nio_udp", "lport": 20000, "rhost": "127.0.0.1", "rport": 20001})
    vm._ethernet_adapters[0].add_nio(0, nio)

    await vm.adapter_remove_nio_binding(0, 0)

    commands = _commands(vm)
    assert f"bridge stop {PORT_BRIDGE}" in commands
    assert "bridge remove_nio_udp bridge0 20000 127.0.0.1 20001" in commands
    assert not any("delete_nio_tap" in c for c in commands)


# ---------------------------------------------------------------------------
# Stop order (the port bridges hold the anchor fds)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stop_ubridge_releases_fds_before_deleting_taps(vm):
    """
    The port bridges hold the anchor TAP fds (bridge add_nio_tap), so they
    are deleted first — closing the fds — before the taps are unpersisted
    (tap delete answers EBADFD on a held device), and the per-link kernel
    bridges still need the live control channel. All before the hypervisor
    itself stops.
    """

    vm._kernel_taps[(0, 0)] = TAP00
    vm._kernel_taps[(1, 0)] = TAP10
    nio = vm.manager.create_nio({"type": "nio_bridge", "bridge": BRIDGE})
    vm._ethernet_adapters[0].add_nio(0, nio)

    with patch("gns3server.compute.docker.docker_vm.DockerVM._stop_ubridge", new=AsyncioMagicMock()) as stop:
        await vm._stop_ubridge()

    stop.assert_called_once()
    commands = _commands(vm)
    assert f"bridge delete {PORT_BRIDGE}" in commands
    assert "bridge delete bridge1" in commands  # bay 1 unit 0 (port 0 keeps the historical name)
    assert commands.index(f"bridge delete {PORT_BRIDGE}") < commands.index(f'tap delete "{TAP00}"')
    assert commands.index("bridge delete bridge1") < commands.index(f'tap delete "{TAP10}"')
    assert commands.index(f'tap delete "{TAP00}"') < commands.index(f'brctl delete "{BRIDGE}"')
    assert vm._kernel_taps == {}
    assert vm._tap_datapath is False


@pytest.mark.asyncio
async def test_start_ubridge_prepares_the_datapath_before_any_link(vm):
    """
    The anchors are born with the node (uBridge control channel up, before
    the start loop attaches links): an anchor that appears only with its
    link would leave the switch fast path's deferred join waiting forever.
    """

    with (
        patch("gns3server.compute.base_node.BaseNode._start_ubridge", new=AsyncioMagicMock()) as start,
        patch.object(IOLDockerVM, "_prepare_tap_datapath", new=AsyncioMagicMock()) as prepare,
    ):
        await vm._start_ubridge(require_privileged_access=True)

    start.assert_called_once()
    prepare.assert_called_once()


# ---------------------------------------------------------------------------
# Anchor naming (the shared contract)
# ---------------------------------------------------------------------------


def test_anchor_names_follow_the_iol_docker_key():
    """
    The controller names an IOL runner's anchor for switch absorption with
    the same function the compute creates it under — the iol_docker key,
    never the docker veth namespace.
    """

    from gns3server.utils.kernel_anchor import kernel_anchor_name, kernel_anchor_type

    environment = "GNS3_IOL_RUNNER=1\nGNS3_IOL_STARTUP_CONFIG=cfg.txt"
    assert kernel_anchor_type("docker", environment) == "iol_docker"
    assert kernel_anchor_type("docker", "GNS3_UNIX_SOCKET_NIO=1") == "docker"
    assert kernel_anchor_name(kernel_anchor_type("docker", environment), NODE_ID, 0, 1) == TAP01
