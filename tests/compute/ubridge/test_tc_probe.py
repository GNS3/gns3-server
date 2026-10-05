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

import pytest

from gns3server.compute.ubridge import tc_probe
from gns3server.compute.ubridge.tc_probe import (
    probe_bridge_tap_support,
    probe_iol_tap_support,
    probe_tap_support,
    probe_tc_capabilities,
)
from gns3server.compute.ubridge.ubridge_error import UbridgeError

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
    FakeHypervisor.reply = ["netem=delay,rate;ebpf=1;cbpf=1;ebpf_modes=nth,quota,window,flow"]
    tc_probe._cache.clear()
    tc_probe._tap_cache.clear()
    tc_probe._iol_tap_cache.clear()
    tc_probe._bridge_tap_cache.clear()
    FakeHypervisor.last = None
    # a real file on disk: the cache is keyed on its (path, mtime, size)
    binary = tmp_path / "ubridge"
    binary.write_bytes(b"")
    monkeypatch.setattr(tc_probe.shutil, "which", lambda name: str(binary))
    monkeypatch.setattr(tc_probe, "Hypervisor", FakeHypervisor)


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
