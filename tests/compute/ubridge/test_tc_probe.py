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
The standalone `tc capabilities` probe behind the compute /capabilities
payload: spawn a throwaway uBridge, ask once, cache by binary identity.
"""

import asyncio
import os

import pytest

from gns3server.compute.ubridge import tc_probe
from gns3server.compute.ubridge.tc_probe import (
    probe_bridge_tap_support,
    probe_iol_tap_support,
    probe_tap_support,
    probe_tc_capabilities,
    probe_vxlan_support,
)
from gns3server.compute.ubridge.ubridge_error import UbridgeError
from gns3server.config import Config

pytestmark = pytest.mark.asyncio


class FakeHypervisor:
    """Records spawns; answers `tc capabilities` with a canned reply."""

    last = None

    reply = ["netem=delay,rate;ebpf=1;cbpf=1;ebpf_modes=nth,quota,window,flow"]
    error = None
    error_prefix = None  # fail only commands starting with this (a build missing one command)
    # what `bridge delete_nio_tap` answers: a new build's 214 (the bridge
    # doesn't exist), None = answer 100 (an impossible reply on the probe's
    # uuid name — the probe must treat it as unknown)
    bridge_tap_error = "214-bridge 'nosuch' doesn't exist"
    # False = a build older than the kernel dataplane (uBridge < 1.3.1)
    supports_kernel_datapath = True
    version = "1.3.1"
    spawned = 0

    def __init__(self, project, path, working_dir, transport, host, node_id):

        self.commands = []
        FakeHypervisor.last = self
        FakeHypervisor.spawned += 1

    async def start(self):
        pass

    async def connect(self):
        pass

    async def send(self, command):

        self.commands.append(command)
        if self.error:
            raise UbridgeError(self.error)
        if self.error_prefix and command.startswith(self.error_prefix):
            raise UbridgeError("202-Unknown command")
        if command.startswith("bridge delete_nio_tap "):
            if FakeHypervisor.bridge_tap_error:
                raise UbridgeError(FakeHypervisor.bridge_tap_error)
            return ["OK"]
        if command == "tc capabilities":
            return FakeHypervisor.reply
        return ["OK"]

    async def stop(self):
        pass


@pytest.fixture(autouse=True)
def probe_env(monkeypatch, tmp_path):

    FakeHypervisor.spawned = 0
    FakeHypervisor.error = None
    FakeHypervisor.error_prefix = None
    FakeHypervisor.bridge_tap_error = "214-bridge 'nosuch' doesn't exist"
    FakeHypervisor.supports_kernel_datapath = True
    FakeHypervisor.version = "1.3.1"
    FakeHypervisor.reply = ["netem=delay,rate;ebpf=1;cbpf=1;ebpf_modes=nth,quota,window,flow"]
    tc_probe._cache.clear()
    tc_probe._tap_cache.clear()
    tc_probe._iol_tap_cache.clear()
    tc_probe._bridge_tap_cache.clear()
    tc_probe._vxlan_cache.clear()
    FakeHypervisor.last = None
    # a real file on disk: the cache is keyed on its (path, mtime, size,
    # ctime)
    binary = tmp_path / "ubridge"
    binary.write_bytes(b"")
    monkeypatch.setattr(tc_probe.shutil, "which", lambda name: str(binary))
    monkeypatch.setattr(tc_probe, "Hypervisor", FakeHypervisor)
    return str(binary)


async def test_probe_returns_parsed_report():

    caps = await probe_tc_capabilities()
    assert caps == {
        "netem": "delay,rate",
        "ebpf": "1",
        "cbpf": "1",
        "ebpf_modes": "nth,quota,window,flow",
    }
    assert FakeHypervisor.spawned == 1


async def test_probe_cached_by_binary_identity():

    first = await probe_tc_capabilities()
    second = await probe_tc_capabilities()
    assert first is second
    assert FakeHypervisor.spawned == 1


async def test_probe_failure_means_unknown():

    FakeHypervisor.error = "Unknown command"  # old uBridge build
    assert await probe_tc_capabilities() is None
    # the failure is cached too: no respawn loop on every /capabilities hit
    assert await probe_tc_capabilities() is None
    assert FakeHypervisor.spawned == 1


async def test_probe_missing_binary_means_unknown(monkeypatch):

    monkeypatch.setattr(tc_probe.shutil, "which", lambda name: None)
    assert await probe_tc_capabilities() is None
    assert FakeHypervisor.spawned == 0


async def test_probe_reprobes_when_the_binary_attributes_change(probe_env):

    # Ensure following chmod changes mode even under restrictive test-process umasks.
    os.chmod(probe_env, 0o700)
    assert await probe_tc_capabilities() is not None
    # chmod touches ctime but neither mtime nor size: a setcap/chmod remedy
    # after a permission-related probe failure must be able to flip the
    # cached verdict without a server restart. Wait for this filesystem's
    # timestamp clock to advance before changing mode.
    await asyncio.sleep(0.02)
    os.chmod(probe_env, 0o600)
    assert await probe_tc_capabilities() is not None
    assert FakeHypervisor.spawned == 2


async def test_probe_bridge_tap_unknown_when_ubridge_will_not_start(monkeypatch):
    """start() can raise UbridgeError (unusable binary): unknown, never a
    failed /capabilities response."""

    async def failing_start(self):
        raise UbridgeError("uBridge executable version must be >= 2.4.0")

    monkeypatch.setattr(FakeHypervisor, "start", failing_start)
    assert await probe_bridge_tap_support() is None


async def test_probe_empty_reply_means_unknown():

    FakeHypervisor.reply = []
    assert await probe_tc_capabilities() is None


async def test_probe_tap_support_creates_and_deletes_a_probe_tap():

    assert await probe_tap_support() is True
    assert FakeHypervisor.spawned == 1
    commands = FakeHypervisor.last.commands
    assert commands[0].startswith("tap create ")
    assert commands[1].startswith("tap delete ")


async def test_probe_tap_support_unknown_on_an_old_build():

    FakeHypervisor.error = "202-Unknown command 'create'"
    assert await probe_tap_support() is None
    # cached like the tc report: no respawn on every /capabilities hit
    assert await probe_tap_support() is None
    assert FakeHypervisor.spawned == 1


async def test_probe_tap_support_missing_binary(monkeypatch):

    monkeypatch.setattr(tc_probe.shutil, "which", lambda name: None)
    assert await probe_tap_support() is None
    assert FakeHypervisor.spawned == 0


async def test_probe_iol_tap_support_runs_one_cycle_on_a_scratch_bridge():
    """
    The probe walks the exact add_nio_tap/delete_nio_tap cycle a kernel link
    uses, on a scratch bridge whose id sits above the per-node id space, and
    cleans up both scratch resources even when the cycle itself fails.
    """

    assert await probe_iol_tap_support() is True
    assert FakeHypervisor.spawned == 1
    commands = FakeHypervisor.last.commands
    assert commands[0].startswith("iol_bridge create gns3iolprobe")
    assert commands[0].endswith(" 1050")
    assert commands[1].startswith("tap create gns3ita")
    assert commands[2].startswith("iol_bridge add_nio_tap ")
    assert commands[2].split()[-1].startswith("gns3ita")
    assert commands[3].startswith("iol_bridge delete_nio_tap ")
    # cleanup: bridge first (it releases the TAP fd), then the device
    assert commands[4].startswith("iol_bridge delete ")
    assert commands[5].startswith("tap delete ")


async def test_probe_iol_tap_support_unknown_on_an_old_build():
    """
    A uBridge without iol_bridge add_nio_tap answers "Unknown command": the
    probe reports unknown (IOU stays on the relay datapath), cleans up its
    scratch bridge and tap, and caches the failure.
    """

    FakeHypervisor.error_prefix = "iol_bridge add_nio_tap"
    assert await probe_iol_tap_support() is None
    commands = FakeHypervisor.last.commands
    assert any(c.startswith("iol_bridge delete ") for c in commands)
    assert any(c.startswith("tap delete ") for c in commands)
    # cached like the other probes: no respawn on every /capabilities hit
    assert await probe_iol_tap_support() is None
    assert FakeHypervisor.spawned == 1


async def test_probe_iol_tap_support_missing_binary(monkeypatch):

    monkeypatch.setattr(tc_probe.shutil, "which", lambda name: None)
    assert await probe_iol_tap_support() is None
    assert FakeHypervisor.spawned == 0


async def test_probe_bridge_tap_support_asks_one_unused_bridge():
    """
    The probe needs no scratch objects and no capabilities: one command
    against a bridge that cannot exist, whose 214 answer means the command
    ran (new build). Nothing is created, nothing needs cleaning up.
    """

    assert await probe_bridge_tap_support() is True
    assert FakeHypervisor.spawned == 1
    commands = FakeHypervisor.last.commands
    assert len(commands) == 1
    assert commands[0].startswith("bridge delete_nio_tap gns3brtapprobe")
    # cached like the other probes: no respawn on every /capabilities hit
    assert await probe_bridge_tap_support() is True
    assert FakeHypervisor.spawned == 1


async def test_probe_bridge_tap_support_unknown_on_an_old_build():
    """
    A uBridge without the command answers 202 "Unknown command": unknown, so
    IOL runner containers stay on the relay datapath. A 100 answer is
    unknown too — the bridge "existed" on the probe's uuid name, which
    cannot happen on a sane build.
    """

    FakeHypervisor.error_prefix = "bridge delete_nio_tap"
    assert await probe_bridge_tap_support() is None

    FakeHypervisor.error_prefix = None
    FakeHypervisor.bridge_tap_error = None
    tc_probe._bridge_tap_cache.clear()
    assert await probe_bridge_tap_support() is None


async def test_probe_bridge_tap_support_missing_binary(monkeypatch):

    monkeypatch.setattr(tc_probe.shutil, "which", lambda name: None)
    assert await probe_bridge_tap_support() is None
    assert FakeHypervisor.spawned == 0


@pytest.mark.parametrize(
    "probe", [probe_tap_support, probe_iol_tap_support, probe_bridge_tap_support, probe_vxlan_support]
)
async def test_anchor_probes_unknown_below_the_kernel_dataplane_version(probe):
    """
    uBridge 1.2.3 already has the tap module, so its `tap create` succeeds —
    but the kernel links built on that answer need commands that only 1.3.x
    has (per-interface `capture stop_kernel`, kernel markers, ...). A build
    below the kernel-dataplane version is unknown without being asked
    anything, so every node stays on the relay datapath.
    """

    FakeHypervisor.supports_kernel_datapath = False
    FakeHypervisor.version = "1.2.3"
    assert await probe() is None
    assert FakeHypervisor.spawned == 1
    assert FakeHypervisor.last.commands == []


class _FixedUuid:
    """A uuid4 stand-in whose .int/.hex pin the probe's random draws."""

    def __init__(self, value):
        self.int = value
        self.hex = f"{value:032x}"


def _probe_create_port():
    """The dstport of the one `vxlan create` the probe issued."""

    create = next(c for c in FakeHypervisor.last.commands if c.startswith("vxlan create "))
    return int(create.rsplit("dstport=", 1)[1])


async def test_probe_vxlan_avoids_the_configured_dstport(monkeypatch, probe_env):
    """
    A scratch draw landing exactly on the configured dstport must move: on
    that port the scratch VNI shares a demux table with the live links'
    devices, and an unlucky VNI draw would make the probe report the
    capability unknown for the process's lifetime (the result is cached).
    """

    # int % 10000 == 9999 -> the scratch window draws its very last value
    monkeypatch.setattr(tc_probe.uuid, "uuid4", lambda: _FixedUuid(29999))
    settings = Config.instance().settings.Server
    monkeypatch.setattr(settings, "vxlan_dstport", 29999)

    assert await probe_vxlan_support() is True
    assert _probe_create_port() == 20000


async def test_probe_vxlan_scratch_port_stays_off_the_configured_one(monkeypatch, probe_env):
    """
    Whatever the configured dstport, the probe's socket never lands on it
    and stays inside its scratch window.
    """

    settings = Config.instance().settings.Server
    for configured in (4789, 20000, 25000, 29999):
        monkeypatch.setattr(settings, "vxlan_dstport", configured)
        tc_probe._vxlan_cache.clear()
        assert await probe_vxlan_support() is True
        port = _probe_create_port()
        assert 20000 <= port <= 29999, port
        assert port != configured, (port, configured)
