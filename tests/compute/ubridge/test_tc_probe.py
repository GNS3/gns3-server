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
from gns3server.compute.ubridge.tc_probe import probe_tc_capabilities
from gns3server.compute.ubridge.ubridge_error import UbridgeError

pytestmark = pytest.mark.asyncio


class FakeHypervisor:
    """Records spawns; answers `tc capabilities` with a canned reply."""

    reply = ["netem=delay,rate;ebpf=1;cbpf=1;ebpf_modes=nth,quota,window,flow"]
    error = None
    spawned = 0

    def __init__(self, project, path, working_dir, transport, host, node_id):

        self.commands = []
        FakeHypervisor.spawned += 1

    async def start(self):
        pass

    async def connect(self):
        pass

    async def send(self, command):

        self.commands.append(command)
        if self.error:
            raise UbridgeError(self.error)
        if command == "tc capabilities":
            return FakeHypervisor.reply
        return ["OK"]

    async def stop(self):
        pass


@pytest.fixture(autouse=True)
def probe_env(monkeypatch, tmp_path):

    FakeHypervisor.spawned = 0
    FakeHypervisor.error = None
    FakeHypervisor.reply = ["netem=delay,rate;ebpf=1;cbpf=1;ebpf_modes=nth,quota,window,flow"]
    tc_probe._cache.clear()
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
