#
# Copyright (C) 2020 GNS3 Technologies Inc.
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

import asyncio
import os
from unittest.mock import ANY, MagicMock, patch

import pytest
import pytest_asyncio

from gns3server.compute.notification_manager import NotificationManager
from gns3server.compute.vpcs import VPCS
from gns3server.compute.vpcs.vpcs_error import VPCSError
from gns3server.compute.vpcs.vpcs_vm import VPCSVM
from gns3server.utils import parse_version
from tests.utils import AsyncioMagicMock, asyncio_patch


@pytest_asyncio.fixture
async def manager(port_manager):

    m = VPCS.instance()
    m.port_manager = port_manager
    return m


@pytest_asyncio.fixture(scope="function")
async def vm(compute_project, manager, tmpdir, ubridge_path):

    vm = VPCSVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", compute_project, manager)
    vm._vpcs_version = parse_version("0.9")
    vm._start_ubridge = AsyncioMagicMock()
    vm._ubridge_hypervisor = MagicMock()
    vm._ubridge_hypervisor.is_running.return_value = True
    # The legacy-datapath tests run with an unknown probe answer (None):
    # the tap datapath stays off without a project warning, exactly like a
    # host whose probe failed. The tap-datapath tests patch the probe to
    # True (or False, when they assert the fallback) on top.
    with patch("gns3server.compute.vpcs.vpcs_vm.probe_vpcs_tap", new=AsyncioMagicMock(return_value=None)):
        yield vm


@pytest.mark.asyncio
async def test_vm(compute_project, manager):

    vm = VPCSVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", compute_project, manager)
    assert vm.name == "test"
    assert vm.id == "00010203-0405-0607-0809-0a0b0c0d0e0f"


@pytest.mark.asyncio
async def test_vm_check_vpcs_version(vm):

    with asyncio_patch(
        "gns3server.compute.vpcs.vpcs_vm.subprocess_check_output",
        return_value="Welcome to Virtual PC Simulator, version 0.9",
    ):
        await vm._check_vpcs_version()
        assert vm._vpcs_version == parse_version("0.9")


@pytest.mark.asyncio
async def test_vm_check_vpcs_version_0_6_1(vm):

    with asyncio_patch(
        "gns3server.compute.vpcs.vpcs_vm.subprocess_check_output",
        return_value="Welcome to Virtual PC Simulator, version 0.6.1",
    ):
        await vm._check_vpcs_version()
        assert vm._vpcs_version == parse_version("0.6.1")


@pytest.mark.asyncio
async def test_vm_invalid_vpcs_version(vm, manager):

    with asyncio_patch(
        "gns3server.compute.vpcs.vpcs_vm.subprocess_check_output",
        return_value="Welcome to Virtual PC Simulator, version 0.1",
    ):
        with pytest.raises(VPCSError):
            nio = manager.create_nio(
                {"type": "nio_udp", "lport": 4242, "rport": 4243, "rhost": "127.0.0.1", "filters": {}}
            )
            await vm.port_add_nio_binding(0, nio)
            await vm._check_vpcs_version()
            assert vm.name == "test"
            assert vm.id == "00010203-0405-0607-0809-0a0b0c0d0e0f"


@pytest.mark.asyncio
async def test_vm_invalid_vpcs_path(vm, manager):

    with patch("gns3server.compute.vpcs.vpcs_vm.VPCSVM._vpcs_path", return_value="/tmp/fake/path/vpcs"):
        with pytest.raises(VPCSError):
            nio = manager.create_nio({"type": "nio_udp", "lport": 4242, "rport": 4243, "rhost": "127.0.0.1"})
            await vm.port_add_nio_binding(0, nio)
            await vm.start()
            assert vm.name == "test"
            assert vm.id == "00010203-0405-0607-0809-0a0b0c0d0e0e"


@pytest.mark.asyncio
async def test_start(vm):

    process = MagicMock()
    process.returncode = None

    with NotificationManager.instance().queue() as queue:
        await queue.get(1)  # Ping

        with asyncio_patch("gns3server.compute.vpcs.vpcs_vm.VPCSVM._check_requirements", return_value=True):
            with asyncio_patch("asyncio.create_subprocess_exec", return_value=process) as mock_exec:
                with asyncio_patch("gns3server.compute.vpcs.vpcs_vm.VPCSVM.start_wrap_console"):
                    await vm.start()
                    assert mock_exec.call_args[0] == (
                        vm._vpcs_path(),
                        "-p",
                        str(vm._internal_console_port),
                        "-m",
                        "1",
                        "-i",
                        "1",
                        "-F",
                        "-R",
                        "-s",
                        ANY,
                        "-c",
                        ANY,
                        "-t",
                        "127.0.0.1",
                    )
                assert vm.is_running()
                assert vm.command_line == " ".join(mock_exec.call_args[0])
        (action, event, kwargs) = await queue.get(1)
        assert action == "node.updated"
        assert event == vm


@pytest.mark.asyncio
async def test_start_0_6_1(vm):
    """
    Version 0.6.1 doesn't have the -R options. It's not require
    because GNS3 provide a patch for this.
    """

    process = MagicMock()
    process.returncode = None
    vm._vpcs_version = parse_version("0.6.1")

    with asyncio_patch("gns3server.compute.vpcs.vpcs_vm.VPCSVM._check_requirements", return_value=True):
        with asyncio_patch("gns3server.compute.vpcs.vpcs_vm.VPCSVM.start_wrap_console"):
            with asyncio_patch("asyncio.create_subprocess_exec", return_value=process) as mock_exec:
                nio = VPCS.instance().create_nio(
                    {"type": "nio_udp", "lport": 4242, "rport": 4243, "rhost": "127.0.0.1", "filters": {}}
                )
                await vm.port_add_nio_binding(0, nio)
                await vm.start()
                assert mock_exec.call_args[0] == (
                    vm._vpcs_path(),
                    "-p",
                    str(vm._internal_console_port),
                    "-m",
                    "1",
                    "-i",
                    "1",
                    "-F",
                    "-s",
                    ANY,
                    "-c",
                    ANY,
                    "-t",
                    "127.0.0.1",
                )
                assert vm.is_running()


@pytest.mark.asyncio
async def test_stop(vm):

    process = MagicMock()
    # Wait process kill success
    future = asyncio.Future()
    future.set_result(True)
    process.wait.return_value = future
    process.returncode = None

    with NotificationManager.instance().queue() as queue:
        with asyncio_patch("gns3server.compute.vpcs.vpcs_vm.VPCSVM._check_requirements", return_value=True):
            with asyncio_patch("gns3server.compute.vpcs.vpcs_vm.VPCSVM.start_wrap_console"):
                with asyncio_patch("asyncio.create_subprocess_exec", return_value=process):
                    nio = VPCS.instance().create_nio(
                        {"type": "nio_udp", "lport": 4242, "rport": 4243, "rhost": "127.0.0.1", "filters": {}}
                    )
                    await vm.port_add_nio_binding(0, nio)

                    await vm.start()
                    assert vm.is_running()

                    with asyncio_patch("gns3server.utils.asyncio.wait_for_process_termination"):
                        await vm.stop()
                    assert vm.is_running() is False

                    process.terminate.assert_called_with()

                    await queue.get(1)  #  Ping
                    await queue.get(1)  #  Started

                    (action, event, kwargs) = await queue.get(1)
                    assert action == "node.updated"
                    assert event == vm


@pytest.mark.asyncio
async def test_reload(vm):

    process = MagicMock()
    # Wait process kill success
    future = asyncio.Future()
    future.set_result(True)
    process.wait.return_value = future
    process.returncode = None

    with asyncio_patch("gns3server.compute.vpcs.vpcs_vm.VPCSVM._check_requirements", return_value=True):
        with asyncio_patch("gns3server.compute.vpcs.vpcs_vm.VPCSVM.start_wrap_console"):
            with asyncio_patch("asyncio.create_subprocess_exec", return_value=process):
                nio = VPCS.instance().create_nio(
                    {"type": "nio_udp", "lport": 4242, "rport": 4243, "rhost": "127.0.0.1", "filters": {}}
                )
                await vm.port_add_nio_binding(0, nio)
                await vm.start()
                assert vm.is_running()

                vm._ubridge_send = AsyncioMagicMock()
                with asyncio_patch("gns3server.utils.asyncio.wait_for_process_termination"):
                    await vm.reload()
                assert vm.is_running() is True

                process.terminate.assert_called_with()


@pytest.mark.asyncio
async def test_add_nio_binding_udp(vm):

    nio = VPCS.instance().create_nio(
        {"type": "nio_udp", "lport": 4242, "rport": 4243, "rhost": "127.0.0.1", "filters": {}}
    )
    await vm.port_add_nio_binding(0, nio)
    assert nio.lport == 4242


@pytest.mark.asyncio
async def test_add_nio_binding_tap(vm, ethernet_device):

    with patch("gns3server.compute.base_manager.BaseManager.has_privileged_access", return_value=True):
        nio = VPCS.instance().create_nio({"type": "nio_tap", "tap_device": ethernet_device})
        await vm.port_add_nio_binding(0, nio)
        assert nio.tap_device == ethernet_device


@pytest.mark.asyncio
async def test_port_remove_nio_binding(vm):

    nio = VPCS.instance().create_nio({"type": "nio_udp", "lport": 4242, "rport": 4243, "rhost": "127.0.0.1"})
    await vm.port_add_nio_binding(0, nio)
    await vm.port_remove_nio_binding(0)
    assert vm._ethernet_adapter.ports[0] is None


def test_update_startup_script(vm):

    content = "echo GNS3 VPCS\nip 192.168.1.2\n"
    vm.startup_script = content
    filepath = os.path.join(vm.working_dir, "startup.vpc")
    assert os.path.exists(filepath)
    with open(filepath) as f:
        assert f.read() == content


def test_update_startup_script_h(vm):

    content = "set pcname %h\n"
    vm.name = "pc1"
    vm.startup_script = content
    assert os.path.exists(vm.script_file)
    with open(vm.script_file) as f:
        assert f.read() == "set pcname pc1\n"


def test_update_startup_script_with_escaping_characters_in_name(vm):

    vm.startup_script = "set pcname initial-name\n"
    vm.name = "test\\"
    assert vm.startup_script == f"set pcname test{os.linesep}"


def test_get_startup_script(vm):

    content = "echo GNS3 VPCS\nip 192.168.1.2"
    vm.startup_script = content
    assert vm.startup_script == os.linesep.join(["echo GNS3 VPCS", "ip 192.168.1.2"])


def test_get_startup_script_using_default_script(vm):
    content = "echo GNS3 VPCS\nip 192.168.1.2\n"

    # Reset script file location
    vm._script_file = None

    filepath = os.path.join(vm.working_dir, "startup.vpc")
    with open(filepath, "wb+") as f:
        assert f.write(content.encode("utf-8"))

    assert vm.startup_script == content
    assert vm.script_file == filepath


def test_change_name(vm):

    path = os.path.join(vm.working_dir, "startup.vpc")
    vm.name = "world"
    with open(path, "w+") as f:
        f.write("set pcname world")
    vm.name = "hello"
    assert vm.name == "hello"
    with open(path) as f:
        assert f.read() == "set pcname hello"
    # Support when the name is not sync with config
    with open(path, "w+") as f:
        f.write("set pcname alpha")
    vm.name = "beta"
    assert vm.name == "beta"
    with open(path) as f:
        assert f.read() == "set pcname beta"


@pytest.mark.asyncio
async def test_close(vm):

    with asyncio_patch("gns3server.compute.vpcs.vpcs_vm.VPCSVM._check_requirements", return_value=True):
        with asyncio_patch("asyncio.create_subprocess_exec", return_value=MagicMock()):
            with asyncio_patch("gns3server.compute.vpcs.vpcs_vm.VPCSVM.start_wrap_console"):
                await vm.start()
                await vm.close()
                assert vm.is_running() is False


# ----------------------------------------------------------------------
# Kernel datapath (the adapter anchor is a persistent TAP the vpcs process
# attaches to with -e -d, kept away from host auto-configuration with -n)
# ----------------------------------------------------------------------


async def _start_on_tap_datapath(vm):
    """
    Start the node with both probes answering (a -n-capable vpcs build, a
    uBridge with the tap module), returning the recorded uBridge commands.
    """

    # a startup.vpc left in the shared working directory by an earlier test
    # would append its name to the command line (the script tests run in any
    # order) — start from a clean one.
    try:
        os.remove(os.path.join(vm.working_dir, "startup.vpc"))
    except FileNotFoundError:
        pass

    commands = []

    async def record_send(command):
        commands.append(command)

    vm._ubridge_send = AsyncioMagicMock(side_effect=record_send)
    process = MagicMock()
    process.returncode = None
    with patch("gns3server.compute.vpcs.vpcs_vm.probe_vpcs_tap", new=AsyncioMagicMock(return_value=True)):
        with asyncio_patch("gns3server.compute.vpcs.vpcs_vm.VPCSVM._check_requirements", return_value=True):
            with asyncio_patch("asyncio.create_subprocess_exec", return_value=process) as mock_exec:
                with asyncio_patch("gns3server.compute.vpcs.vpcs_vm.VPCSVM.start_wrap_console"):
                    await vm.start()
    return mock_exec, commands


@pytest.mark.asyncio
async def test_start_tap_datapath(vm):
    """
    A -n-capable vpcs build on a tap-capable uBridge anchors the adapter on
    a persistent TAP and speaks tap mode: -e -d <anchor> -n, no UDP tunnel.
    """

    mock_exec, commands = await _start_on_tap_datapath(vm)
    assert vm._tap_datapath is True
    assert vm._kernel_taps == {(0, 0): "gp00010203e0p0"}
    assert mock_exec.call_args[0] == (
        vm._vpcs_path(),
        "-p",
        str(vm._internal_console_port),
        "-m",
        "1",
        "-i",
        "1",
        "-F",
        "-R",
        "-e",
        "-d",
        "gp00010203e0p0",
        "-n",
    )
    # the anchor was created through uBridge's tap module, owned by this user
    assert 'tap create "gp00010203e0p0"' in commands
    assert f"tap set_owner gp00010203e0p0 {os.getuid()}" in commands
    # no local UDP tunnel on this datapath
    assert vm._local_udp_tunnel is None


@pytest.mark.asyncio
async def test_start_legacy_datapath_when_binary_lacks_dash_n(vm):
    """
    A vpcs build without -n cannot be kept away from the host side of the
    anchor, so the node keeps the legacy UDP relay datapath.
    """

    process = MagicMock()
    process.returncode = None
    with patch("gns3server.compute.vpcs.vpcs_vm.probe_vpcs_tap", new=AsyncioMagicMock(return_value=False)):
        with asyncio_patch("gns3server.compute.vpcs.vpcs_vm.VPCSVM._check_requirements", return_value=True):
            with asyncio_patch("asyncio.create_subprocess_exec", return_value=process) as mock_exec:
                with asyncio_patch("gns3server.compute.vpcs.vpcs_vm.VPCSVM.start_wrap_console"):
                    await vm.start()

    assert vm._tap_datapath is False
    assert vm._kernel_taps == {}
    command = mock_exec.call_args[0]
    assert "-e" not in command
    assert "-n" not in command
    assert "-s" in command and "-c" in command and "-t" in command


@pytest.mark.asyncio
async def test_stop_terminates_process_before_deleting_taps(vm):
    """
    The vpcs process holds the anchor TAP open: a held device refuses
    deletion, so the TAP delete must follow the process termination (the
    suppressed delete of the old order leaked the anchor).
    """

    calls = []
    process = MagicMock()
    process.returncode = None
    process.terminate.side_effect = lambda: calls.append("terminate")

    async def record_send(command):
        commands.append(command)

    commands = []
    vm._ubridge_send = AsyncioMagicMock(side_effect=record_send)
    with patch("gns3server.compute.vpcs.vpcs_vm.probe_vpcs_tap", new=AsyncioMagicMock(return_value=True)):
        with asyncio_patch("gns3server.compute.vpcs.vpcs_vm.VPCSVM._check_requirements", return_value=True):
            with asyncio_patch("asyncio.create_subprocess_exec", return_value=process):
                with asyncio_patch("gns3server.compute.vpcs.vpcs_vm.VPCSVM.start_wrap_console"):
                    await vm.start()

    with asyncio_patch("gns3server.utils.asyncio.wait_for_process_termination"):
        await vm.stop()

    assert calls == ["terminate"]
    # every tap delete (the start-time sweep and the stop-time teardown)
    # happened after the process termination
    assert all(calls.index("terminate") < commands.index(c) for c in commands if c.startswith("tap delete"))


@pytest.mark.asyncio
async def test_add_nio_binding_duplicate_port_rejected(vm):
    """
    A port carries at most one NIO: overwriting the one a link still owns
    orphans that link's teardown.
    """

    nio = VPCS.instance().create_nio(
        {"type": "nio_udp", "lport": 4242, "rport": 4243, "rhost": "127.0.0.1", "filters": {}}
    )
    await vm.port_add_nio_binding(0, nio)
    with pytest.raises(VPCSError, match="already has a link"):
        await vm.port_add_nio_binding(0, nio)


@pytest.mark.asyncio
async def test_kernel_nio_on_legacy_datapath_rejected(vm):
    """
    A kernel link to a node running on the legacy relay datapath (no anchor)
    is refused with a clear error instead of a late uBridge failure.
    """

    vm._process = MagicMock()
    vm._process.returncode = None
    vm._tap_datapath = False
    nio = VPCS.instance().create_nio({"type": "nio_bridge", "bridge": "gns3testbridge", "filters": {}})
    with pytest.raises(VPCSError, match="legacy relay datapath"):
        await vm.port_add_nio_binding(0, nio)


@pytest.mark.asyncio
async def test_kernel_nio_attach_enslaves_the_anchor(vm):
    """
    A kernel link enslaves the anchor into the per-link bridge and installs
    the impairment filters the NIO carries — the same _kernel_attach flow
    every anchor-backed node type uses.
    """

    await _start_on_tap_datapath(vm)
    nio = VPCS.instance().create_nio(
        {"type": "nio_bridge", "bridge": "gns3testbridge", "filters": {"delay": [100]}}
    )
    await vm.port_add_nio_binding(0, nio)

    sent = [call[0][0] for call in vm._ubridge_send.call_args_list]
    assert 'brctl create "gns3testbridge"' in sent
    assert 'brctl addif "gns3testbridge" "gp00010203e0p0"' in sent
    assert any(c.startswith('tc netem set "gp00010203e0p0" delay 100') for c in sent)
