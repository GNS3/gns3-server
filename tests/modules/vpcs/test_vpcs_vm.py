# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 GNS3 Technologies Inc.
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
import asyncio
import os
from tests.utils import asyncio_patch


from unittest.mock import patch, MagicMock
from gns3server.modules.vpcs.vpcs_vm import VPCSVM
from gns3server.modules.vpcs.vpcs_error import VPCSError
from gns3server.modules.vpcs import VPCS


@pytest.fixture(scope="module")
def manager(port_manager):
    m = VPCS.instance()
    m.port_manager = port_manager
    return m


@pytest.fixture(scope="function")
def vm(project, manager):
    return VPCSVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", project, manager)


def test_vm(project, manager):
    vm = VPCSVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", project, manager)
    assert vm.name == "test"
    assert vm.uuid == "00010203-0405-0607-0809-0a0b0c0d0e0f"


def test_vm_invalid_vpcs_version(loop, project, manager):
    with asyncio_patch("gns3server.modules.vpcs.vpcs_vm.VPCSVM._get_vpcs_welcome", return_value="Welcome to Virtual PC Simulator, version 0.1"):
        with pytest.raises(VPCSError):
            vm = VPCSVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", project, manager)
            vm.port_add_nio_binding(0, {"type": "nio_udp", "lport": 4242, "rport": 4243, "rhost": "127.0.0.1"})
            loop.run_until_complete(asyncio.async(vm.start()))
            assert vm.name == "test"
            assert vm.uuid == "00010203-0405-0607-0809-0a0b0c0d0e0f"


@patch("gns3server.config.Config.get_section_config", return_value={"path": "/bin/test_fake"})
def test_vm_invalid_vpcs_path(project, manager, loop):
    with pytest.raises(VPCSError):
        vm = VPCSVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0e", project, manager)
        vm.port_add_nio_binding(0, {"type": "nio_udp", "lport": 4242, "rport": 4243, "rhost": "127.0.0.1"})
        loop.run_until_complete(asyncio.async(vm.start()))
        assert vm.name == "test"
        assert vm.uuid == "00010203-0405-0607-0809-0a0b0c0d0e0e"


def test_start(loop, vm):
    with asyncio_patch("gns3server.modules.vpcs.vpcs_vm.VPCSVM._check_requirements", return_value=True):
        with asyncio_patch("asyncio.create_subprocess_exec", return_value=MagicMock()):
            nio = vm.port_add_nio_binding(0, {"type": "nio_udp", "lport": 4242, "rport": 4243, "rhost": "127.0.0.1"})

            loop.run_until_complete(asyncio.async(vm.start()))
            assert vm.is_running()


def test_stop(loop, vm):
    process = MagicMock()
    with asyncio_patch("gns3server.modules.vpcs.vpcs_vm.VPCSVM._check_requirements", return_value=True):
        with asyncio_patch("asyncio.create_subprocess_exec", return_value=process):
            nio = vm.port_add_nio_binding(0, {"type": "nio_udp", "lport": 4242, "rport": 4243, "rhost": "127.0.0.1"})

            loop.run_until_complete(asyncio.async(vm.start()))
            assert vm.is_running()
            loop.run_until_complete(asyncio.async(vm.stop()))
            assert vm.is_running() is False
            process.terminate.assert_called_with()


def test_reload(loop, vm):
    process = MagicMock()
    with asyncio_patch("gns3server.modules.vpcs.vpcs_vm.VPCSVM._check_requirements", return_value=True):
        with asyncio_patch("asyncio.create_subprocess_exec", return_value=process):
            nio = vm.port_add_nio_binding(0, {"type": "nio_udp", "lport": 4242, "rport": 4243, "rhost": "127.0.0.1"})

            loop.run_until_complete(asyncio.async(vm.start()))
            assert vm.is_running()
            loop.run_until_complete(asyncio.async(vm.reload()))
            assert vm.is_running() is True
            process.terminate.assert_called_with()


def test_add_nio_binding_udp(vm):
    nio = vm.port_add_nio_binding(0, {"type": "nio_udp", "lport": 4242, "rport": 4243, "rhost": "127.0.0.1"})
    assert nio.lport == 4242


def test_add_nio_binding_tap(vm):
    with patch("gns3server.modules.vpcs.vpcs_vm.has_privileged_access", return_value=True):
        nio = vm.port_add_nio_binding(0, {"type": "nio_tap", "tap_device": "test"})
        assert nio.tap_device == "test"


def test_add_nio_binding_tap_no_privileged_access(vm):
    with patch("gns3server.modules.vpcs.vpcs_vm.has_privileged_access", return_value=False):
        with pytest.raises(VPCSError):
            vm.port_add_nio_binding(0, {"type": "nio_tap", "tap_device": "test"})
    assert vm._ethernet_adapter.ports[0] is None


def test_port_remove_nio_binding(vm):
    nio = vm.port_add_nio_binding(0, {"type": "nio_udp", "lport": 4242, "rport": 4243, "rhost": "127.0.0.1"})
    vm.port_remove_nio_binding(0)
    assert vm._ethernet_adapter.ports[0] is None


def test_update_startup_script(vm):
    content = "echo GNS3 VPCS\nip 192.168.1.2\n"
    vm.startup_script = content
    filepath = os.path.join(vm.working_dir, 'startup.vpcs')
    assert os.path.exists(filepath)
    with open(filepath) as f:
        assert f.read() == content


def test_update_startup_script(vm):
    content = "echo GNS3 VPCS\nip 192.168.1.2\n"
    vm.startup_script = content
    filepath = os.path.join(vm.working_dir, 'startup.vpcs')
    assert os.path.exists(filepath)
    with open(filepath) as f:
        assert f.read() == content


def test_get_startup_script(vm):
    content = "echo GNS3 VPCS\nip 192.168.1.2\n"
    vm.startup_script = content
    assert vm.startup_script == content


def test_change_console_port(vm, port_manager):
    port1 = port_manager.get_free_console_port()
    port2 = port_manager.get_free_console_port()
    port_manager.release_console_port(port1)
    port_manager.release_console_port(port2)
    print(vm.console)
    print(port1)
    vm.console = port1
    vm.console = port2
    assert vm.console == port2
    port_manager.reserve_console_port(port1)


def test_change_name(vm, tmpdir):
    path = os.path.join(str(tmpdir), 'startup.vpcs')
    vm.name = "world"
    with open(path, 'w+') as f:
        f.write("name world")
    vm.script_file = path
    vm.name = "hello"
    assert vm.name == "hello"
    with open(path) as f:
        assert f.read() == "name hello"


def test_change_script_file(vm, tmpdir):
    path = os.path.join(str(tmpdir), 'startup2.vpcs')
    vm.script_file = path
    assert vm.script_file == path


def test_destroy(vm, port_manager):
    with asyncio_patch("gns3server.modules.vpcs.vpcs_vm.VPCSVM._check_requirements", return_value=True):
        with asyncio_patch("asyncio.create_subprocess_exec", return_value=MagicMock()):
            vm.start()
            port = vm.console
            vm.destroy()
            # Raise an exception if the port is not free
            port_manager.reserve_console_port(port)
            assert vm.is_running() is False
