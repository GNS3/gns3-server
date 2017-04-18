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
from tests.utils import asyncio_patch, AsyncioMagicMock


from unittest import mock
from unittest.mock import patch, MagicMock

from gns3server.compute.qemu.qemu_vm import QemuVM
from gns3server.compute.qemu.qemu_error import QemuError
from gns3server.compute.qemu import Qemu
from gns3server.utils import force_unix_path, macaddress_to_int, int_to_macaddress
from gns3server.compute.notification_manager import NotificationManager


@pytest.fixture
def manager(port_manager):
    m = Qemu.instance()
    m.port_manager = port_manager
    return m


@pytest.fixture
def fake_qemu_img_binary():

    bin_path = os.path.join(os.environ["PATH"], "qemu-img")
    with open(bin_path, "w+") as f:
        f.write("1")
    os.chmod(bin_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    return bin_path


@pytest.fixture
def fake_qemu_binary():

    if sys.platform.startswith("win"):
        bin_path = os.path.join(os.environ["PATH"], "qemu-system-x86_64w.exe")
    else:
        bin_path = os.path.join(os.environ["PATH"], "qemu-system-x86_64")
    with open(bin_path, "w+") as f:
        f.write("1")
    os.chmod(bin_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    return bin_path


@pytest.fixture(scope="function")
def vm(project, manager, fake_qemu_binary, fake_qemu_img_binary):
    manager.port_manager.console_host = "127.0.0.1"
    vm = QemuVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", project, manager, qemu_path=fake_qemu_binary)
    vm._process_priority = "normal"  # Avoid complexity for Windows tests
    return vm


@pytest.fixture(scope="function")
def running_subprocess_mock():
    mm = MagicMock()
    mm.returncode = None
    return mm


def test_vm(project, manager, fake_qemu_binary):
    vm = QemuVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", project, manager, qemu_path=fake_qemu_binary)
    assert vm.name == "test"
    assert vm.id == "00010203-0405-0607-0809-0a0b0c0d0e0f"


def test_vm_invalid_qemu_with_platform(project, manager, fake_qemu_binary):

    vm = QemuVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", project, manager, qemu_path="/usr/fake/bin/qemu-system-64", platform="x86_64")

    assert vm.qemu_path == fake_qemu_binary
    assert vm.platform == "x86_64"


def test_vm_invalid_qemu_without_platform(project, manager, fake_qemu_binary):

    vm = QemuVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", project, manager, qemu_path="/usr/fake/bin/qemu-system-x86_64")

    assert vm.qemu_path == fake_qemu_binary
    assert vm.platform == "x86_64"


def test_is_running(vm, running_subprocess_mock):

    vm._process = None
    assert vm.is_running() is False
    vm._process = running_subprocess_mock
    assert vm.is_running()
    vm._process.returncode = -1
    assert vm.is_running() is False


def test_start(loop, vm, running_subprocess_mock):
    with asyncio_patch("gns3server.compute.qemu.QemuVM.start_wrap_console"):
        with asyncio_patch("asyncio.create_subprocess_exec", return_value=running_subprocess_mock) as mock:
            loop.run_until_complete(asyncio.async(vm.start()))
            assert vm.is_running()
            assert vm.command_line == ' '.join(mock.call_args[0])


def test_stop(loop, vm, running_subprocess_mock):
    process = running_subprocess_mock

    # Wait process kill success
    future = asyncio.Future()
    future.set_result(True)
    process.wait.return_value = future

    with asyncio_patch("gns3server.compute.qemu.QemuVM.start_wrap_console"):
        with asyncio_patch("asyncio.create_subprocess_exec", return_value=process):
            nio = Qemu.instance().create_nio({"type": "nio_udp", "lport": 4242, "rport": 4243, "rhost": "127.0.0.1"})
            vm.adapter_add_nio_binding(0, nio)
            loop.run_until_complete(asyncio.async(vm.start()))
            assert vm.is_running()
            loop.run_until_complete(asyncio.async(vm.stop()))
            assert vm.is_running() is False
            process.terminate.assert_called_with()


def test_termination_callback(vm, async_run):

    vm.status = "started"

    with NotificationManager.instance().queue() as queue:
        async_run(vm._termination_callback(0))
        assert vm.status == "stopped"

        async_run(queue.get(0))  #  Ping

        (action, event, kwargs) = async_run(queue.get(0))
        assert action == "node.updated"
        assert event == vm


@pytest.mark.skipif(sys.platform.startswith("win"), reason="Not supported on Windows")
def test_termination_callback_error(vm, tmpdir, async_run):

    with open(str(tmpdir / "qemu.log"), "w+") as f:
        f.write("BOOMM")

    vm.status = "started"
    vm._stdout_file = str(tmpdir / "qemu.log")

    with NotificationManager.instance().queue() as queue:
        async_run(vm._termination_callback(1))
        assert vm.status == "stopped"

        async_run(queue.get(0))  # Ping

        (action, event, kwargs) = queue.get_nowait()
        assert action == "node.updated"
        assert event == vm

        (action, event, kwargs) = queue.get_nowait()
        assert action == "log.error"
        assert event["message"] == "QEMU process has stopped, return code: 1\nBOOMM"


def test_reload(loop, vm):

    with asyncio_patch("gns3server.compute.qemu.QemuVM._control_vm") as mock:
        loop.run_until_complete(asyncio.async(vm.reload()))
        assert mock.called_with("system_reset")


def test_suspend(loop, vm):

    control_vm_result = MagicMock()
    control_vm_result.match.group.decode.return_value = "running"
    with asyncio_patch("gns3server.compute.qemu.QemuVM._control_vm", return_value=control_vm_result) as mock:
        loop.run_until_complete(asyncio.async(vm.suspend()))
        assert mock.called_with("system_reset")


def test_add_nio_binding_udp(vm, loop):
    nio = Qemu.instance().create_nio({"type": "nio_udp", "lport": 4242, "rport": 4243, "rhost": "127.0.0.1"})
    loop.run_until_complete(asyncio.async(vm.adapter_add_nio_binding(0, nio)))
    assert nio.lport == 4242


@pytest.mark.skipif(sys.platform.startswith("win"), reason="Not supported on Windows")
def test_add_nio_binding_ethernet(vm, loop, ethernet_device):
    with patch("gns3server.compute.base_manager.BaseManager.has_privileged_access", return_value=True):
        nio = Qemu.instance().create_nio({"type": "nio_ethernet", "ethernet_device": ethernet_device})
        loop.run_until_complete(asyncio.async(vm.adapter_add_nio_binding(0, nio)))
        assert nio.ethernet_device == ethernet_device


def test_port_remove_nio_binding(vm, loop):
    nio = Qemu.instance().create_nio({"type": "nio_udp", "lport": 4242, "rport": 4243, "rhost": "127.0.0.1"})
    loop.run_until_complete(asyncio.async(vm.adapter_add_nio_binding(0, nio)))
    loop.run_until_complete(asyncio.async(vm.adapter_remove_nio_binding(0)))
    assert vm._ethernet_adapters[0].ports[0] is None


def test_close(vm, port_manager, loop):
    with asyncio_patch("gns3server.compute.qemu.QemuVM.start_wrap_console"):
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
    if sys.platform.startswith("win"):
        path = str(tmpdir / "\u62FF" / "qemu-system-mipsw.exe")
    else:
        path = str(tmpdir / "\u62FF" / "qemu-system-mips")

    os.makedirs(str(tmpdir / "\u62FF"))

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
    assert vm.platform == "mips"


def test_set_qemu_path_environ(vm, tmpdir, fake_qemu_binary):

    # It should find the binary in the path
    vm.qemu_path = "qemu-system-x86_64"

    assert vm.qemu_path == fake_qemu_binary
    assert vm.platform == "x86_64"


def test_set_qemu_path_windows(vm, tmpdir):

    bin_path = os.path.join(os.environ["PATH"], "qemu-system-x86_64w.EXE")
    open(bin_path, "w+").close()
    if not sys.platform.startswith("win"):
        os.chmod(bin_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)

    vm.qemu_path = bin_path

    assert vm.qemu_path == bin_path
    assert vm.platform == "x86_64"


def test_set_qemu_path_old_windows(vm, tmpdir):

    bin_path = os.path.join(os.environ["PATH"], "qemu.exe")
    open(bin_path, "w+").close()
    if not sys.platform.startswith("win"):
        os.chmod(bin_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)

    vm.qemu_path = bin_path

    assert vm.qemu_path == bin_path
    assert vm.platform == "i386"


@pytest.mark.skipif(sys.platform.startswith("win"), reason="Not supported on Windows")
def test_set_qemu_path_kvm_binary(vm, tmpdir, fake_qemu_binary):

    bin_path = os.path.join(os.environ["PATH"], "qemu-kvm")
    with open(bin_path, "w+") as f:
        f.write("1")
    os.chmod(bin_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)

    # It should find the binary in the path
    vm.qemu_path = "qemu-kvm"

    assert vm.qemu_path.endswith("qemu-kvm")
    assert vm.platform == "x86_64"


def test_set_platform(project, manager):

    with patch("shutil.which", return_value="/bin/qemu-system-x86_64") as which_mock:
        with patch("gns3server.compute.qemu.QemuVM._check_qemu_path"):
            vm = QemuVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", project, manager, platform="x86_64")
            if sys.platform.startswith("win"):
                which_mock.assert_called_with("qemu-system-x86_64w.exe", path=mock.ANY)
            else:
                which_mock.assert_called_with("qemu-system-x86_64", path=mock.ANY)
    assert vm.platform == "x86_64"
    assert vm.qemu_path == "/bin/qemu-system-x86_64"


def test_disk_options(vm, tmpdir, loop, fake_qemu_img_binary):

    vm._hda_disk_image = str(tmpdir / "test.qcow2")
    open(vm._hda_disk_image, "w+").close()

    with asyncio_patch("asyncio.create_subprocess_exec", return_value=MagicMock()) as process:
        options = loop.run_until_complete(asyncio.async(vm._disk_options()))
        assert process.called
        args, kwargs = process.call_args
        assert args == (fake_qemu_img_binary, "create", "-o", "backing_file={}".format(vm._hda_disk_image), "-f", "qcow2", os.path.join(vm.working_dir, "hda_disk.qcow2"))

    assert options == ['-drive', 'file=' + os.path.join(vm.working_dir, "hda_disk.qcow2") + ',if=ide,index=0,media=disk']


def test_cdrom_option(vm, tmpdir, loop, fake_qemu_img_binary):

    vm._cdrom_image = str(tmpdir / "test.iso")
    open(vm._cdrom_image, "w+").close()

    options = loop.run_until_complete(asyncio.async(vm._build_command()))

    assert ' '.join(['-cdrom', str(tmpdir / "test.iso")]) in ' '.join(options)


def test_bios_option(vm, tmpdir, loop, fake_qemu_img_binary):

    vm._bios_image = str(tmpdir / "test.img")
    open(vm._bios_image, "w+").close()

    options = loop.run_until_complete(asyncio.async(vm._build_command()))

    assert ' '.join(['-bios', str(tmpdir / "test.img")]) in ' '.join(options)


def test_disk_options_multiple_disk(vm, tmpdir, loop, fake_qemu_img_binary):

    vm._hda_disk_image = str(tmpdir / "test0.qcow2")
    vm._hdb_disk_image = str(tmpdir / "test1.qcow2")
    vm._hdc_disk_image = str(tmpdir / "test2.qcow2")
    vm._hdd_disk_image = str(tmpdir / "test3.qcow2")
    open(vm._hda_disk_image, "w+").close()
    open(vm._hdb_disk_image, "w+").close()
    open(vm._hdc_disk_image, "w+").close()
    open(vm._hdd_disk_image, "w+").close()

    with asyncio_patch("asyncio.create_subprocess_exec", return_value=MagicMock()) as process:
        options = loop.run_until_complete(asyncio.async(vm._disk_options()))

    assert options == [
        '-drive', 'file=' + os.path.join(vm.working_dir, "hda_disk.qcow2") + ',if=ide,index=0,media=disk',
        '-drive', 'file=' + os.path.join(vm.working_dir, "hdb_disk.qcow2") + ',if=ide,index=1,media=disk',
        '-drive', 'file=' + os.path.join(vm.working_dir, "hdc_disk.qcow2") + ',if=ide,index=2,media=disk',
        '-drive', 'file=' + os.path.join(vm.working_dir, "hdd_disk.qcow2") + ',if=ide,index=3,media=disk'
    ]


@pytest.mark.skipif(sys.platform.startswith("win"), reason="Not supported on Windows")
def test_set_process_priority(vm, loop, fake_qemu_img_binary):

    with asyncio_patch("asyncio.create_subprocess_exec", return_value=MagicMock()) as process:
        vm._process = MagicMock()
        vm._process.pid = 42
        vm._process_priority = "low"
        loop.run_until_complete(asyncio.async(vm._set_process_priority()))
        assert process.called
        args, kwargs = process.call_args
        assert args == ("renice", "-n", "5", "-p", "42")


@pytest.mark.skipif(sys.platform.startswith("win"), reason="Not supported on Windows")
def test_set_process_priority_normal(vm, loop, fake_qemu_img_binary):

    with asyncio_patch("asyncio.create_subprocess_exec", return_value=MagicMock()) as process:
        vm._process = MagicMock()
        vm._process.pid = 42
        loop.run_until_complete(asyncio.async(vm._set_process_priority()))
        assert not process.called


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
            "256M",
            "-smp",
            "cpus=1",
            "-boot",
            "order=c",
            "-uuid",
            vm.id,
            "-serial",
            "telnet:127.0.0.1:{},server,nowait".format(vm._internal_console_port),
            "-net",
            "none",
            "-device",
            "e1000,mac={}".format(vm._mac_address)
        ]


def test_build_command_manual_uuid(vm, loop, fake_qemu_binary, port_manager):
    """
    If user has set a uuid we keep it
    """

    vm.options = "-uuid e1c307a4-896f-11e6-81a5-3c07547807cc"
    os.environ["DISPLAY"] = "0:0"
    with asyncio_patch("asyncio.create_subprocess_exec", return_value=MagicMock()) as process:
        cmd = loop.run_until_complete(asyncio.async(vm._build_command()))
        assert "e1c307a4-896f-11e6-81a5-3c07547807cc" in cmd
        assert vm.id not in cmd


def test_build_command_kvm(linux_platform, vm, loop, fake_qemu_binary, port_manager):
    """
    Qemu 2.4 introduce an issue with KVM
    """
    vm._run_with_kvm = MagicMock(return_value=True)
    vm.manager.get_qemu_version = AsyncioMagicMock(return_value="2.3.2")
    os.environ["DISPLAY"] = "0:0"
    with asyncio_patch("asyncio.create_subprocess_exec", return_value=MagicMock()) as process:
        cmd = loop.run_until_complete(asyncio.async(vm._build_command()))
        assert cmd == [
            fake_qemu_binary,
            "-name",
            "test",
            "-m",
            "256M",
            "-smp",
            "cpus=1",
            "-enable-kvm",
            "-boot",
            "order=c",
            "-uuid",
            vm.id,
            "-serial",
            "telnet:127.0.0.1:{},server,nowait".format(vm._internal_console_port),
            "-net",
            "none",
            "-device",
            "e1000,mac={}".format(vm._mac_address)
        ]


def test_build_command_kvm_2_4(linux_platform, vm, loop, fake_qemu_binary, port_manager):
    """
    Qemu 2.4 introduce an issue with KVM
    """
    vm._run_with_kvm = MagicMock(return_value=True)
    vm.manager.get_qemu_version = AsyncioMagicMock(return_value="2.4.2")
    os.environ["DISPLAY"] = "0:0"
    with asyncio_patch("asyncio.create_subprocess_exec", return_value=MagicMock()) as process:
        cmd = loop.run_until_complete(asyncio.async(vm._build_command()))
        assert cmd == [
            fake_qemu_binary,
            "-name",
            "test",
            "-m",
            "256M",
            "-smp",
            "cpus=1",
            "-enable-kvm",
            "-machine",
            "smm=off",
            "-boot",
            "order=c",
            "-uuid",
            vm.id,
            "-serial",
            "telnet:127.0.0.1:{},server,nowait".format(vm._internal_console_port),
            "-net",
            "none",
            "-device",
            "e1000,mac={}".format(vm._mac_address)
        ]


@pytest.mark.skipif(sys.platform.startswith("win"), reason="Not supported on Windows")
def test_build_command_without_display(vm, loop, fake_qemu_binary):

    os.environ["DISPLAY"] = ""
    with asyncio_patch("asyncio.create_subprocess_exec", return_value=MagicMock()) as process:
        cmd = loop.run_until_complete(asyncio.async(vm._build_command()))
        assert "-nographic" in cmd


def test_build_command_two_adapters(vm, loop, fake_qemu_binary, port_manager):

    os.environ["DISPLAY"] = "0:0"
    vm.adapters = 2
    with asyncio_patch("asyncio.create_subprocess_exec", return_value=MagicMock()) as process:
        cmd = loop.run_until_complete(asyncio.async(vm._build_command()))
        assert cmd == [
            fake_qemu_binary,
            "-name",
            "test",
            "-m",
            "256M",
            "-smp",
            "cpus=1",
            "-boot",
            "order=c",
            "-uuid",
            vm.id,
            "-serial",
            "telnet:127.0.0.1:{},server,nowait".format(vm._internal_console_port),
            "-net",
            "none",
            "-device",
            "e1000,mac={}".format(vm.mac_address),
            "-device",
            "e1000,mac={}".format(int_to_macaddress(macaddress_to_int(vm._mac_address) + 1))
        ]


def test_build_command_two_adapters_mac_address(vm, loop, fake_qemu_binary, port_manager):
    """
    Should support multiple base vmac address
    """

    vm.adapters = 2
    vm.mac_address = "00:00:ab:0e:0f:09"
    mac_0 = vm._mac_address
    mac_1 = int_to_macaddress(macaddress_to_int(vm._mac_address))
    assert mac_0[:8] == "00:00:ab"
    with asyncio_patch("asyncio.create_subprocess_exec", return_value=MagicMock()) as process:
        cmd = loop.run_until_complete(asyncio.async(vm._build_command()))
        assert "e1000,mac={}".format(mac_0) in cmd
        assert "e1000,mac={}".format(mac_1) in cmd

    vm.mac_address = "00:42:ab:0e:0f:0a"
    mac_0 = vm._mac_address
    mac_1 = int_to_macaddress(macaddress_to_int(vm._mac_address))
    assert mac_0[:8] == "00:42:ab"
    with asyncio_patch("asyncio.create_subprocess_exec", return_value=MagicMock()) as process:
        cmd = loop.run_until_complete(asyncio.async(vm._build_command()))
        assert "e1000,mac={}".format(mac_0) in cmd
        assert "e1000,mac={}".format(mac_1) in cmd


# Windows accept this kind of mistake
@pytest.mark.skipif(sys.platform.startswith("win"), reason="Not supported on Windows")
def test_build_command_with_invalid_options(vm, loop, fake_qemu_binary):

    vm.options = "'test"
    with pytest.raises(QemuError):
        cmd = loop.run_until_complete(asyncio.async(vm._build_command()))


def test_hda_disk_image(vm, images_dir):

    open(os.path.join(images_dir, "test1"), "w+").close()
    vm.hda_disk_image = os.path.join(images_dir, "test1")
    assert vm.hda_disk_image == force_unix_path(os.path.join(images_dir, "test1"))
    open(os.path.join(images_dir, "QEMU", "test2"), "w+").close()
    vm.hda_disk_image = "test2"
    assert vm.hda_disk_image == force_unix_path(os.path.join(images_dir, "QEMU", "test2"))


def test_hda_disk_image_non_linked_clone(vm, images_dir, project, manager, fake_qemu_binary, fake_qemu_img_binary):
    """
    Two non linked can't use the same image at the same time
    """

    open(os.path.join(images_dir, "test1"), "w+").close()
    vm.linked_clone = False
    vm.hda_disk_image = os.path.join(images_dir, "test1")
    vm.manager._nodes[vm.id] = vm

    vm2 = QemuVM("test", "00010203-0405-0607-0809-0a0b0c0d0eaa", project, manager, qemu_path=fake_qemu_binary)
    vm2.linked_clone = False
    with pytest.raises(QemuError):
        vm2.hda_disk_image = os.path.join(images_dir, "test1")


def test_hda_disk_image_ova(vm, images_dir):

    os.makedirs(os.path.join(images_dir, "QEMU", "test.ovf"))
    open(os.path.join(images_dir, "QEMU", "test.ovf", "test.vmdk"), "w+").close()
    vm.hda_disk_image = "test.ovf/test.vmdk"
    assert vm.hda_disk_image == force_unix_path(os.path.join(images_dir, "QEMU", "test.ovf", "test.vmdk"))


def test_hdb_disk_image(vm, images_dir):

    open(os.path.join(images_dir, "test1"), "w+").close()
    vm.hdb_disk_image = os.path.join(images_dir, "test1")
    assert vm.hdb_disk_image == force_unix_path(os.path.join(images_dir, "test1"))
    open(os.path.join(images_dir, "QEMU", "test2"), "w+").close()
    vm.hdb_disk_image = "test2"
    assert vm.hdb_disk_image == force_unix_path(os.path.join(images_dir, "QEMU", "test2"))


def test_hdc_disk_image(vm, images_dir):

    open(os.path.join(images_dir, "test1"), "w+").close()
    vm.hdc_disk_image = os.path.join(images_dir, "test1")
    assert vm.hdc_disk_image == force_unix_path(os.path.join(images_dir, "test1"))
    open(os.path.join(images_dir, "QEMU", "test2"), "w+").close()
    vm.hdc_disk_image = "test2"
    assert vm.hdc_disk_image == force_unix_path(os.path.join(images_dir, "QEMU", "test2"))


def test_hdd_disk_image(vm, images_dir):

    open(os.path.join(images_dir, "test1"), "w+").close()
    vm.hdd_disk_image = os.path.join(images_dir, "test1")
    assert vm.hdd_disk_image == force_unix_path(os.path.join(images_dir, "test1"))
    open(os.path.join(images_dir, "QEMU", "test2"), "w+").close()
    vm.hdd_disk_image = "test2"
    assert vm.hdd_disk_image == force_unix_path(os.path.join(images_dir, "QEMU", "test2"))


def test_initrd(vm, images_dir):

    open(os.path.join(images_dir, "test1"), "w+").close()
    vm.initrd = os.path.join(images_dir, "test1")
    assert vm.initrd == force_unix_path(os.path.join(images_dir, "test1"))
    open(os.path.join(images_dir, "QEMU", "test2"), "w+").close()
    vm.initrd = "test2"
    assert vm.initrd == force_unix_path(os.path.join(images_dir, "QEMU", "test2"))


def test_initrd_asa(vm, images_dir):

    with patch("gns3server.compute.project.Project.emit") as mock:
        open(os.path.join(images_dir, "asa842-initrd.gz"), "w+").close()
        vm.initrd = os.path.join(images_dir, "asa842-initrd.gz")
        assert vm.initrd == force_unix_path(os.path.join(images_dir, "asa842-initrd.gz"))
        assert mock.called


def test_options(linux_platform, vm):
    vm.kvm = False
    vm.options = "-usb"
    assert vm.options == "-usb"
    assert vm.kvm is False

    vm.options = "-no-kvm"
    assert vm.options == "-no-kvm"

    vm.options = "-enable-kvm"
    assert vm.options == "-enable-kvm"

    vm.options = "-icount 12"
    assert vm.options == "-no-kvm -icount 12"

    vm.options = "-icount 12 -no-kvm"
    assert vm.options == "-icount 12 -no-kvm"


def test_options_windows(windows_platform, vm):
    vm.options = "-no-kvm"
    assert vm.options == ""

    vm.options = "-enable-kvm"
    assert vm.options == ""


def test_get_qemu_img(vm, tmpdir):

    open(str(tmpdir / "qemu-sytem-x86_64"), "w+").close()
    open(str(tmpdir / "qemu-img"), "w+").close()
    vm._qemu_path = str(tmpdir / "qemu-sytem-x86_64")
    assert vm._get_qemu_img() == str(tmpdir / "qemu-img")


def test_get_qemu_img_not_exist(vm, tmpdir):

    open(str(tmpdir / "qemu-sytem-x86_64"), "w+").close()
    vm._qemu_path = str(tmpdir / "qemu-sytem-x86_64")
    with pytest.raises(QemuError):
        vm._get_qemu_img()


def test_run_with_kvm_darwin(darwin_platform, vm):

    vm.manager.config.set("Qemu", "enable_kvm", False)
    assert vm._run_with_kvm("qemu-system-x86_64", "") is False


def test_run_with_kvm_windows(windows_platform, vm):

    vm.manager.config.set("Qemu", "enable_kvm", False)
    assert vm._run_with_kvm("qemu-system-x86_64.exe", "") is False


def test_run_with_kvm_linux(linux_platform, vm):

    with patch("os.path.exists", return_value=True) as os_path:
        vm.manager.config.set("Qemu", "enable_kvm", True)
        assert vm._run_with_kvm("qemu-system-x86_64", "") is True
        os_path.assert_called_with("/dev/kvm")


def test_run_with_kvm_linux_options_no_kvm(linux_platform, vm):

    with patch("os.path.exists", return_value=True) as os_path:
        vm.manager.config.set("Qemu", "enable_kvm", True)
        assert vm._run_with_kvm("qemu-system-x86_64", "-no-kvm") is False


def test_run_with_kvm_not_x86(linux_platform, vm):

    with patch("os.path.exists", return_value=True) as os_path:
        vm.manager.config.set("Qemu", "enable_kvm", True)
        assert vm._run_with_kvm("qemu-system-arm", "") is False


def test_run_with_kvm_linux_dev_kvm_missing(linux_platform, vm):

    with patch("os.path.exists", return_value=False) as os_path:
        vm.manager.config.set("Qemu", "enable_kvm", True)
        with pytest.raises(QemuError):
            vm._run_with_kvm("qemu-system-x86_64", "")
