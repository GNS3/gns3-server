# -*- coding: utf-8 -*-
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

import pytest
import pytest_asyncio
import asyncio
import os

from tests.utils import asyncio_patch, AsyncioMagicMock
from gns3server.utils import parse_version
from unittest.mock import patch, MagicMock, ANY

from gns3server.compute.vpcs.vpcs_vm import VPCSVM
from gns3server.compute.vpcs.vpcs_error import VPCSError
from gns3server.compute.vpcs import VPCS
from gns3server.compute.notification_manager import NotificationManager


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
    return vm


@pytest.mark.asyncio
async def test_vm(compute_project, manager):

    vm = VPCSVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", compute_project, manager)
    assert vm.name == "test"
    assert vm.id == "00010203-0405-0607-0809-0a0b0c0d0e0f"


@pytest.mark.asyncio
async def test_vm_check_vpcs_version(vm):

    with asyncio_patch("gns3server.compute.vpcs.vpcs_vm.subprocess_check_output", return_value="Welcome to Virtual PC Simulator, version 0.9"):
        await vm._check_vpcs_version()
        assert vm._vpcs_version == parse_version("0.9")


@pytest.mark.asyncio
async def test_vm_check_vpcs_version_0_6_1(vm):

    with asyncio_patch("gns3server.compute.vpcs.vpcs_vm.subprocess_check_output", return_value="Welcome to Virtual PC Simulator, version 0.6.1"):
        await vm._check_vpcs_version()
        assert vm._vpcs_version == parse_version("0.6.1")


@pytest.mark.asyncio
async def test_vm_invalid_vpcs_version(vm, manager):

    with asyncio_patch("gns3server.compute.vpcs.vpcs_vm.subprocess_check_output", return_value="Welcome to Virtual PC Simulator, version 0.1"):
        with pytest.raises(VPCSError):
            nio = manager.create_nio({"type": "nio_udp", "lport": 4242, "rport": 4243, "rhost": "127.0.0.1", "filters": {}})
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
                    assert mock_exec.call_args[0] == (vm._vpcs_path(),
                                                      '-p',
                                                      str(vm._internal_console_port),
                                                      '-m', '1',
                                                      '-i',
                                                      '1',
                                                      '-F',
                                                      '-R',
                                                      '-s',
                                                      ANY,
                                                      '-c',
                                                      ANY,
                                                      '-t',
                                                      '127.0.0.1')
                assert vm.is_running()
                assert vm.command_line == ' '.join(mock_exec.call_args[0])
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
                nio = VPCS.instance().create_nio({"type": "nio_udp", "lport": 4242, "rport": 4243, "rhost": "127.0.0.1", "filters": {}})
                await vm.port_add_nio_binding(0, nio)
                await vm.start()
                assert mock_exec.call_args[0] == (vm._vpcs_path(),
                                                  '-p',
                                                  str(vm._internal_console_port),
                                                  '-m', '1',
                                                  '-i',
                                                  '1',
                                                  '-F',
                                                  '-s',
                                                  ANY,
                                                  '-c',
                                                  ANY,
                                                  '-t',
                                                  '127.0.0.1')
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
                    nio = VPCS.instance().create_nio({"type": "nio_udp", "lport": 4242, "rport": 4243, "rhost": "127.0.0.1", "filters": {}})
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
                nio = VPCS.instance().create_nio({"type": "nio_udp", "lport": 4242, "rport": 4243, "rhost": "127.0.0.1", "filters": {}})
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

    nio = VPCS.instance().create_nio({"type": "nio_udp", "lport": 4242, "rport": 4243, "rhost": "127.0.0.1", "filters": {}})
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
    filepath = os.path.join(vm.working_dir, 'startup.vpc')
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
    assert vm.startup_script == "set pcname test{}".format(os.linesep)


def test_get_startup_script(vm):

    content = "echo GNS3 VPCS\nip 192.168.1.2"
    vm.startup_script = content
    assert vm.startup_script == os.linesep.join(["echo GNS3 VPCS", "ip 192.168.1.2"])


def test_get_startup_script_using_default_script(vm):
    content = "echo GNS3 VPCS\nip 192.168.1.2\n"

    # Reset script file location
    vm._script_file = None

    filepath = os.path.join(vm.working_dir, 'startup.vpc')
    with open(filepath, 'wb+') as f:
        assert f.write(content.encode("utf-8"))

    assert vm.startup_script == content
    assert vm.script_file == filepath


def test_change_name(vm):

    path = os.path.join(vm.working_dir, 'startup.vpc')
    vm.name = "world"
    with open(path, 'w+') as f:
        f.write("set pcname world")
    vm.name = "hello"
    assert vm.name == "hello"
    with open(path) as f:
        assert f.read() == "set pcname hello"
    # Support when the name is not sync with config
    with open(path, 'w+') as f:
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
