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
import aiohttp
import asyncio
import os
import sys
import stat
import re
from tests.utils import asyncio_patch


from unittest.mock import patch, MagicMock
from gns3server.modules.qemu.qemu_vm import QemuVM
from gns3server.modules.qemu.qemu_error import QemuError
from gns3server.modules.qemu import Qemu


@pytest.fixture(scope="module")
def manager(port_manager):
    m = Qemu.instance()
    m.port_manager = port_manager
    return m


@pytest.fixture
def fake_qemu_img_binary():

    # Should not crash with unicode characters
    bin_path = os.path.join(os.environ["PATH"], "qemu-img\u62FF")
    with open(bin_path, "w+") as f:
        f.write("1")
    os.chmod(bin_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    return bin_path


@pytest.fixture
def fake_qemu_binary():

    if sys.platform.startswith("win"):
        bin_path = os.path.join(os.environ["PATH"], "qemu_x42.EXE")
    else:
        bin_path = os.path.join(os.environ["PATH"], "qemu_x42")
    with open(bin_path, "w+") as f:
        f.write("1")
    os.chmod(bin_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    return bin_path


@pytest.fixture(scope="function")
def vm(project, manager, fake_qemu_binary, fake_qemu_img_binary):
    manager.port_manager.console_host = "127.0.0.1"
    return QemuVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", project, manager, qemu_path=fake_qemu_binary)


@pytest.fixture(scope="function")
def running_subprocess_mock():
    mm = MagicMock()
    mm.returncode = None
    return mm


def test_vm(project, manager, fake_qemu_binary):
    vm = QemuVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", project, manager, qemu_path=fake_qemu_binary)
    assert vm.name == "test"
    assert vm.id == "00010203-0405-0607-0809-0a0b0c0d0e0f"


def test_is_running(vm, running_subprocess_mock):

    vm._process = None
    assert vm.is_running() is False
    vm._process = running_subprocess_mock
    assert vm.is_running()
    vm._process.returncode = -1
    assert vm.is_running() is False


def test_start(loop, vm, running_subprocess_mock):
    with asyncio_patch("asyncio.create_subprocess_exec", return_value=running_subprocess_mock):
        loop.run_until_complete(asyncio.async(vm.start()))
        assert vm.is_running()


def test_stop(loop, vm, running_subprocess_mock):
    process = running_subprocess_mock

    # Wait process kill success
    future = asyncio.Future()
    future.set_result(True)
    process.wait.return_value = future

    with asyncio_patch("asyncio.create_subprocess_exec", return_value=process):
        nio = Qemu.instance().create_nio(vm.qemu_path, {"type": "nio_udp", "lport": 4242, "rport": 4243, "rhost": "127.0.0.1"})
        vm.adapter_add_nio_binding(0, nio)
        loop.run_until_complete(asyncio.async(vm.start()))
        assert vm.is_running()
        loop.run_until_complete(asyncio.async(vm.stop()))
        assert vm.is_running() is False
        process.terminate.assert_called_with()


def test_reload(loop, vm):

    with asyncio_patch("gns3server.modules.qemu.QemuVM._control_vm") as mock:
        loop.run_until_complete(asyncio.async(vm.reload()))
        assert mock.called_with("system_reset")


def test_suspend(loop, vm):

    control_vm_result = MagicMock()
    control_vm_result.match.group.decode.return_value = "running"
    with asyncio_patch("gns3server.modules.qemu.QemuVM._control_vm", return_value=control_vm_result) as mock:
        loop.run_until_complete(asyncio.async(vm.suspend()))
        assert mock.called_with("system_reset")


def test_add_nio_binding_udp(vm, loop):
    nio = Qemu.instance().create_nio(vm.qemu_path, {"type": "nio_udp", "lport": 4242, "rport": 4243, "rhost": "127.0.0.1"})
    loop.run_until_complete(asyncio.async(vm.adapter_add_nio_binding(0, nio)))
    assert nio.lport == 4242


def test_add_nio_binding_ethernet(vm, loop):
    with patch("gns3server.modules.base_manager.BaseManager._has_privileged_access", return_value=True):
        nio = Qemu.instance().create_nio(vm.qemu_path, {"type": "nio_generic_ethernet", "ethernet_device": "eth0"})
        loop.run_until_complete(asyncio.async(vm.adapter_add_nio_binding(0, nio)))
        assert nio.ethernet_device == "eth0"


def test_port_remove_nio_binding(vm, loop):
    nio = Qemu.instance().create_nio(vm.qemu_path, {"type": "nio_udp", "lport": 4242, "rport": 4243, "rhost": "127.0.0.1"})
    loop.run_until_complete(asyncio.async(vm.adapter_add_nio_binding(0, nio)))
    loop.run_until_complete(asyncio.async(vm.adapter_remove_nio_binding(0)))
    assert vm._ethernet_adapters[0].ports[0] is None


def test_close(vm, port_manager, loop):
    with asyncio_patch("asyncio.create_subprocess_exec", return_value=MagicMock()):
        loop.run_until_complete(asyncio.async(vm.start()))

        console_port = vm.console

        loop.run_until_complete(asyncio.async(vm.close()))

        # Raise an exception if the port is not free
        port_manager.reserve_tcp_port(console_port, vm.project)

        assert vm.is_running() is False


def test_set_qemu_path(vm, tmpdir, fake_qemu_binary):

    # Raise because none
    with pytest.raises(QemuError):
        vm.qemu_path = None

    # Should not crash with unicode characters
    path = str(tmpdir / "bla\u62FF")

    # Raise because file doesn't exists
    with pytest.raises(QemuError):
        vm.qemu_path = path

    with open(path, "w+") as f:
        f.write("1")

    # Raise because file is not executable
    if not sys.platform.startswith("win"):
        with pytest.raises(QemuError):
            vm.qemu_path = path

    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)

    vm.qemu_path = path
    assert vm.qemu_path == path


def test_set_qemu_path_environ(vm, tmpdir, fake_qemu_binary):

    # It should find the binary in the path
    vm.qemu_path = "qemu_x42"

    assert vm.qemu_path == fake_qemu_binary


def test_disk_options(vm, loop, fake_qemu_img_binary):

    with asyncio_patch("asyncio.create_subprocess_exec", return_value=MagicMock()) as process:
        loop.run_until_complete(asyncio.async(vm._disk_options()))
        assert process.called
        args, kwargs = process.call_args
        assert args == (fake_qemu_img_binary, "create", "-f", "qcow2", os.path.join(vm.working_dir, "flash.qcow2"), "256M")


@pytest.mark.skipif(sys.platform.startswith("win"), reason="Not supported on Windows")
def test_set_process_priority(vm, loop, fake_qemu_img_binary):

    with asyncio_patch("asyncio.create_subprocess_exec", return_value=MagicMock()) as process:
        vm._process = MagicMock()
        vm._process.pid = 42
        loop.run_until_complete(asyncio.async(vm._set_process_priority()))
        assert process.called
        args, kwargs = process.call_args
        assert args == ("renice", "-n", "5", "-p", "42")


def test_json(vm, project):

    json = vm.__json__()
    assert json["name"] == vm.name
    assert json["project_id"] == project.id


def test_control_vm(vm, loop):

    vm._process = MagicMock()
    reader = MagicMock()
    writer = MagicMock()
    with asyncio_patch("asyncio.open_connection", return_value=(reader, writer)) as open_connect:
        res = loop.run_until_complete(asyncio.async(vm._control_vm("test")))
        assert writer.write.called_with("test")
    assert res is None


def test_control_vm_expect_text(vm, loop, running_subprocess_mock):

    vm._process = running_subprocess_mock
    reader = MagicMock()
    writer = MagicMock()
    with asyncio_patch("asyncio.open_connection", return_value=(reader, writer)) as open_connect:

        future = asyncio.Future()
        future.set_result(b"epic product")
        reader.readline.return_value = future

        vm._monitor = 4242
        res = loop.run_until_complete(asyncio.async(vm._control_vm("test", [b"epic"])))
        assert writer.write.called_with("test")

    assert res == "epic product"


def test_build_command(vm, loop, fake_qemu_binary, port_manager):

    os.environ["DISPLAY"] = "0:0"
    with asyncio_patch("asyncio.create_subprocess_exec", return_value=MagicMock()) as process:
        cmd = loop.run_until_complete(asyncio.async(vm._build_command()))
        assert cmd == [
            fake_qemu_binary,
            "-name",
            "test",
            "-m",
            "256",
            "-hda",
            os.path.join(vm.working_dir, "flash.qcow2"),
            "-serial",
            "telnet:127.0.0.1:{},server,nowait".format(vm.console),
            "-net",
            "none",
            "-device",
            "e1000,mac=00:00:ab:0e:0f:00"
        ]


@pytest.mark.skipif(sys.platform.startswith("win"), reason="Not supported on Windows")
def test_build_command_without_display(vm, loop, fake_qemu_binary):

    os.environ["DISPLAY"] = ""
    with asyncio_patch("asyncio.create_subprocess_exec", return_value=MagicMock()) as process:
        cmd = loop.run_until_complete(asyncio.async(vm._build_command()))
        assert "-nographic" in cmd


# Windows accept this kind of mistake
@pytest.mark.skipif(sys.platform.startswith("win"), reason="Not supported on Windows")
def test_build_command_with_invalid_options(vm, loop, fake_qemu_binary):

    vm.options = "'test"
    with pytest.raises(QemuError):
        cmd = loop.run_until_complete(asyncio.async(vm._build_command()))


def test_hda_disk_image(vm, tmpdir):

    with patch("gns3server.config.Config.get_section_config", return_value={"images_path": str(tmpdir)}):
        vm.hda_disk_image = "/tmp/test"
        assert vm.hda_disk_image == "/tmp/test"
        vm.hda_disk_image = "test"
        assert vm.hda_disk_image == str(tmpdir / "QEMU" / "test")


def test_hdb_disk_image(vm, tmpdir):

    with patch("gns3server.config.Config.get_section_config", return_value={"images_path": str(tmpdir)}):
        vm.hdb_disk_image = "/tmp/test"
        assert vm.hdb_disk_image == "/tmp/test"
        vm.hdb_disk_image = "test"
        assert vm.hdb_disk_image == str(tmpdir / "QEMU" / "test")


def test_hdc_disk_image(vm, tmpdir):

    with patch("gns3server.config.Config.get_section_config", return_value={"images_path": str(tmpdir)}):
        vm.hdc_disk_image = "/tmp/test"
        assert vm.hdc_disk_image == "/tmp/test"
        vm.hdc_disk_image = "test"
        assert vm.hdc_disk_image == str(tmpdir / "QEMU" / "test")


def test_hdd_disk_image(vm, tmpdir):

    with patch("gns3server.config.Config.get_section_config", return_value={"images_path": str(tmpdir)}):
        vm.hdd_disk_image = "/tmp/test"
        assert vm.hdd_disk_image == "/tmp/test"
        vm.hdd_disk_image = "test"
        assert vm.hdd_disk_image == str(tmpdir / "QEMU" / "test")
