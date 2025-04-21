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
import asyncio
import os
import sys
import stat
from tests.utils import asyncio_patch, AsyncioMagicMock


from unittest import mock
from unittest.mock import patch, MagicMock

from gns3server.compute.qemu.qemu_vm import QemuVM
from gns3server.compute.qemu.qemu_error import QemuError
from gns3server.compute.qemu import Qemu
from gns3server.utils import force_unix_path, macaddress_to_int, int_to_macaddress
from gns3server.compute.notification_manager import NotificationManager


@pytest.fixture
async def manager(port_manager):

    m = Qemu.instance()
    m.port_manager = port_manager
    return m


@pytest.fixture
def fake_qemu_img_binary(monkeypatch, tmpdir):

    monkeypatch.setenv("PATH", str(tmpdir))
    if sys.platform.startswith("win"):
        bin_path = os.path.join(os.environ["PATH"], "qemu-img.EXE")
    else:
        bin_path = os.path.join(os.environ["PATH"], "qemu-img")
    with open(bin_path, "w+") as f:
        f.write("1")
    os.chmod(bin_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    return bin_path


@pytest.fixture
def fake_qemu_binary(monkeypatch, tmpdir):

    monkeypatch.setenv("PATH", str(tmpdir))
    if sys.platform.startswith("win"):
        bin_path = os.path.join(os.environ["PATH"], "qemu-system-x86_64w.exe")
    else:
        bin_path = os.path.join(os.environ["PATH"], "qemu-system-x86_64")
    with open(bin_path, "w+") as f:
        f.write("1")
    os.chmod(bin_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    return bin_path


@pytest.fixture(scope="function")
async def vm(compute_project, manager, fake_qemu_binary, fake_qemu_img_binary):

    manager.port_manager.console_host = "127.0.0.1"
    vm = QemuVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", compute_project, manager, qemu_path=fake_qemu_binary)
    vm._process_priority = "normal"  # Avoid complexity for Windows tests
    vm._start_ubridge = AsyncioMagicMock()
    vm._ubridge_hypervisor = MagicMock()
    vm._ubridge_hypervisor.is_running.return_value = True
    vm.manager.get_qemu_version = AsyncioMagicMock(return_value="6.2.0")
    vm.manager.config.set("Qemu", "enable_hardware_acceleration", False)
    return vm


@pytest.fixture(scope="function")
def running_subprocess_mock():

    mm = MagicMock()
    mm.returncode = None
    return mm


async def test_vm(compute_project, manager, fake_qemu_binary):

    vm = QemuVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", compute_project, manager, qemu_path=fake_qemu_binary)
    assert vm.name == "test"
    assert vm.id == "00010203-0405-0607-0809-0a0b0c0d0e0f"


async def test_vm_create(tmpdir, compute_project, manager, fake_qemu_binary):

    fake_img = str(tmpdir / 'hello')

    with open(fake_img, 'w+') as f:
        f.write('hello')

    vm = QemuVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", compute_project, manager, qemu_path=fake_qemu_binary)
    vm._hda_disk_image = fake_img

    await vm.create()

    # tests if `create` created md5sums
    assert os.path.exists(str(tmpdir / 'hello.md5sum'))


async def test_vm_invalid_qemu_with_platform(compute_project, manager, fake_qemu_binary):

    vm = QemuVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", compute_project, manager, qemu_path="/usr/fake/bin/qemu-system-64", platform="x86_64")

    assert vm.qemu_path == fake_qemu_binary
    assert vm.platform == "x86_64"


async def test_vm_invalid_qemu_without_platform(compute_project, manager, fake_qemu_binary):

    vm = QemuVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", compute_project, manager, qemu_path="/usr/fake/bin/qemu-system-x86_64")

    assert vm.qemu_path == fake_qemu_binary
    assert vm.platform == "x86_64"


async def test_is_running(vm, running_subprocess_mock):

    vm._process = None
    assert vm.is_running() is False
    vm._process = running_subprocess_mock
    assert vm.is_running()
    vm._process.returncode = -1
    assert vm.is_running() is False


async def test_start(vm, running_subprocess_mock):

    with asyncio_patch("gns3server.compute.qemu.QemuVM.start_wrap_console"):
        with asyncio_patch("asyncio.create_subprocess_exec", return_value=running_subprocess_mock) as mock:
            await vm.start()
            assert vm.is_running()
            assert vm.command_line == ' '.join(mock.call_args[0])


async def test_stop(vm, running_subprocess_mock):

    process = running_subprocess_mock
    # Wait process kill success
    future = asyncio.Future()
    future.set_result(True)
    process.wait.return_value = future

    with asyncio_patch("gns3server.compute.qemu.QemuVM.start_wrap_console"):
        with asyncio_patch("asyncio.create_subprocess_exec", return_value=process):
            nio = Qemu.instance().create_nio({"type": "nio_udp", "lport": 4242, "rport": 4243, "rhost": "127.0.0.1"})
            await vm.adapter_add_nio_binding(0, nio)
            await vm.start()
            assert vm.is_running()
            await vm.stop()
            assert vm.is_running() is False
            process.terminate.assert_called_with()


async def test_termination_callback(vm):

    vm.status = "started"
    with NotificationManager.instance().queue() as queue:
        await vm._termination_callback(0)
        assert vm.status == "stopped"

        await queue.get(1)  # Ping

        (action, event, kwargs) = await queue.get(1)
        assert action == "node.updated"
        assert event == vm


@pytest.mark.skipif(sys.platform.startswith("win"), reason="Not supported on Windows")
async def test_termination_callback_error(vm, tmpdir):

    with open(str(tmpdir / "qemu.log"), "w+") as f:
        f.write("BOOMM")

    vm.status = "started"
    vm._stdout_file = str(tmpdir / "qemu.log")

    with NotificationManager.instance().queue() as queue:
        await vm._termination_callback(1)
        assert vm.status == "stopped"

        await queue.get(1)  # Ping

        (action, event, kwargs) = queue.get_nowait()
        assert action == "node.updated"
        assert event == vm

        (action, event, kwargs) = queue.get_nowait()
        assert action == "log.error"
        assert event["message"] == "QEMU process has stopped, return code: 1\nBOOMM"


async def test_reload(vm):

    with asyncio_patch("gns3server.compute.qemu.QemuVM._control_vm") as m:
        await vm.reload()
        m.assert_called_with("system_reset")


async def test_suspend(vm, running_subprocess_mock):

    vm._process = running_subprocess_mock
    with asyncio_patch("gns3server.compute.qemu.QemuVM._get_vm_status", return_value="running"):
        with asyncio_patch("gns3server.compute.qemu.QemuVM._control_vm") as m:
            await vm.suspend()
            m.assert_called_with("stop")


async def test_add_nio_binding_udp(vm):

    nio = Qemu.instance().create_nio({"type": "nio_udp", "lport": 4242, "rport": 4243, "rhost": "127.0.0.1", "filters": {}})
    assert nio.lport == 4242
    await vm.adapter_add_nio_binding(0, nio)
    assert nio.lport == 4242


async def test_port_remove_nio_binding(vm):

    nio = Qemu.instance().create_nio({"type": "nio_udp", "lport": 4242, "rport": 4243, "rhost": "127.0.0.1", "filters": {}})
    await vm.adapter_add_nio_binding(0, nio)
    await vm.adapter_remove_nio_binding(0)
    assert vm._ethernet_adapters[0].ports[0] is None


async def test_close(vm, port_manager):

    with asyncio_patch("gns3server.compute.qemu.QemuVM.start_wrap_console"):
        with asyncio_patch("asyncio.create_subprocess_exec", return_value=MagicMock()):
            await vm.start()

            console_port = vm.console

            await vm.close()

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


def test_set_qemu_path_windows(vm):

    bin_path = os.path.join(os.environ["PATH"], "qemu-system-x86_64w.EXE")
    open(bin_path, "w+").close()
    if not sys.platform.startswith("win"):
        os.chmod(bin_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)

    vm.qemu_path = bin_path

    assert vm.qemu_path == bin_path
    assert vm.platform == "x86_64"


def test_set_qemu_path_old_windows(vm):

    bin_path = os.path.join(os.environ["PATH"], "qemu.exe")
    open(bin_path, "w+").close()
    if not sys.platform.startswith("win"):
        os.chmod(bin_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)

    vm.qemu_path = bin_path

    assert vm.qemu_path == bin_path
    assert vm.platform == "i386"


@pytest.mark.skipif(sys.platform.startswith("win"), reason="Not supported on Windows")
def test_set_qemu_path_kvm_binary(vm, fake_qemu_binary):

    bin_path = os.path.join(os.environ["PATH"], "qemu-kvm")
    with open(bin_path, "w+") as f:
        f.write("1")
    os.chmod(bin_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)

    # It should find the binary in the path
    vm.qemu_path = "qemu-kvm"

    assert vm.qemu_path.endswith("qemu-kvm")
    assert vm.platform == "x86_64"


async def test_set_platform(compute_project, manager):

    manager.config_disk = None  # avoids conflict with config.img support
    with patch("shutil.which", return_value="/bin/qemu-system-x86_64") as which_mock:
        with patch("gns3server.compute.qemu.QemuVM._check_qemu_path"):
            vm = QemuVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", compute_project, manager, platform="x86_64")
            if sys.platform.startswith("win"):
                which_mock.assert_called_with("qemu-system-x86_64w.exe", path=mock.ANY)
            else:
                which_mock.assert_called_with("qemu-system-x86_64", path=mock.ANY)
    assert vm.platform == "x86_64"
    assert vm.qemu_path == "/bin/qemu-system-x86_64"


async def test_disk_options(vm, tmpdir, fake_qemu_img_binary):

    vm._hda_disk_image = str(tmpdir / "test.qcow2")
    vm._hda_disk_interface = "ide"
    vm._hdb_disk_image = str(tmpdir / "test2.qcow2")
    open(vm._hda_disk_image, "w+").close()
    open(vm._hdb_disk_image, "w+").close()

    with (asyncio_patch("gns3server.compute.qemu.qemu_vm.QemuVM._find_disk_file_format", return_value="qcow2")):
        with asyncio_patch("asyncio.create_subprocess_exec", return_value=MagicMock()) as process:
            options = await vm._disk_options()
            assert process.called
            args, kwargs = process.call_args
            assert args == (fake_qemu_img_binary, "create", "-o", "backing_file={}".format(vm._hda_disk_image), "-F", "qcow2", "-f", "qcow2", os.path.join(vm.working_dir, "hda_disk.qcow2")) or \
            args == (fake_qemu_img_binary, "create", "-o", "backing_file={}".format(vm._hdb_disk_image), "-F", "qcow2", "-f", "qcow2", os.path.join(vm.working_dir, "hdb_disk.qcow2"))

    assert options == [
        '-drive', 'file=' + os.path.join(vm.working_dir, "hda_disk.qcow2") + ',if=ide,index=0,media=disk,id=drive0',
        '-drive', 'file=' + os.path.join(vm.working_dir, "hdb_disk.qcow2") + ',if=none,index=1,media=disk,id=drive1',
    ]


async def test_cdrom_option(vm, tmpdir, fake_qemu_img_binary):

    vm._cdrom_image = str(tmpdir / "test.iso")
    open(vm._cdrom_image, "w+").close()

    options = await vm._build_command()

    assert ' '.join(['-cdrom', str(tmpdir / "test.iso")]) in ' '.join(options)


async def test_bios_option(vm, tmpdir, fake_qemu_img_binary):

    vm._bios_image = str(tmpdir / "test.img")
    open(vm._bios_image, "w+").close()
    options = await vm._build_command()
    assert ' '.join(['-bios', str(tmpdir / "test.img")]) in ' '.join(options)


@pytest.mark.skipif(sys.platform.startswith("win"), reason="Test not working on Windows")
async def test_uefi_boot_mode_option(vm, tmpdir, images_dir, fake_qemu_img_binary):

    vm._uefi = True

    # create fake OVMF files
    system_ovmf_firmware_path = "/usr/share/OVMF/OVMF_CODE_4M.fd"
    if os.path.exists(system_ovmf_firmware_path):
        ovmf_code_path = system_ovmf_firmware_path
    else:
        ovmf_code_path = os.path.join(images_dir, "OVMF_CODE_4M.fd")
        with open(ovmf_code_path, "w+") as f:
            f.write('1')
    ovmf_vars_path = os.path.join(images_dir, "OVMF_VARS_4M.fd")
    with open(ovmf_vars_path, "w+") as f:
        f.write('1')

    options = await vm._build_command()
    assert ' '.join(["-drive", "if=pflash,format=raw,readonly,file={}".format(ovmf_code_path)]) in ' '.join(options)
    assert ' '.join(["-drive", "if=pflash,format=raw,file={}".format(os.path.join(vm.working_dir, "OVMF_VARS_4M.fd"))]) in ' '.join(options)


async def test_uefi_with_bios_image_already_configured(vm, tmpdir, fake_qemu_img_binary):

    vm._bios_image = str(tmpdir / "test.img")
    vm._uefi = True
    with pytest.raises(QemuError):
        await vm._build_command()


async def test_vnc_option(vm, fake_qemu_img_binary):

    vm._console_type = 'vnc'
    vm._console = 5905
    options = await vm._build_command()
    assert '-vnc 127.0.0.1:5' in ' '.join(options)


async def test_spice_option(vm, fake_qemu_img_binary):

    vm._console_type = 'spice'
    vm._console = 5905
    options = await vm._build_command()
    assert '-spice addr=127.0.0.1,port=5905,disable-ticketing' in ' '.join(options)
    assert '-vga qxl' in ' '.join(options)


async def test_tpm_option(vm, tmpdir, fake_qemu_img_binary):

    vm._tpm = True
    tpm_sock = os.path.join(vm.temporary_directory, "swtpm.sock")
    with patch("os.path.exists", return_value=True) as os_path:
        options = await vm._build_command()
    assert '-chardev socket,id=chrtpm,path={}'.format(tpm_sock) in ' '.join(options)
    assert '-tpmdev emulator,id=tpm0,chardev=chrtpm' in ' '.join(options)
    assert '-device tpm-tis,tpmdev=tpm0' in ' '.join(options)


async def test_disk_options_multiple_disk(vm, tmpdir, fake_qemu_img_binary):

    vm._hda_disk_image = str(tmpdir / "test0.qcow2")
    vm._hda_disk_interface = "ide"
    vm._hdb_disk_image = str(tmpdir / "test1.qcow2")
    vm._hdb_disk_interface = "ide"
    vm._hdc_disk_image = str(tmpdir / "test2.qcow2")
    vm._hdc_disk_interface = "ide"
    vm._hdd_disk_image = str(tmpdir / "test3.qcow2")
    vm._hdd_disk_interface = "ide"
    open(vm._hda_disk_image, "w+").close()
    open(vm._hdb_disk_image, "w+").close()
    open(vm._hdc_disk_image, "w+").close()
    open(vm._hdd_disk_image, "w+").close()

    with asyncio_patch("gns3server.compute.qemu.qemu_vm.QemuVM._find_disk_file_format", return_value="qcow2"):
        with asyncio_patch("asyncio.create_subprocess_exec", return_value=MagicMock()):
            options = await vm._disk_options()

    assert options == [
        '-drive', 'file=' + os.path.join(vm.working_dir, "hda_disk.qcow2") + ',if=ide,index=0,media=disk,id=drive0',
        '-drive', 'file=' + os.path.join(vm.working_dir, "hdb_disk.qcow2") + ',if=ide,index=1,media=disk,id=drive1',
        '-drive', 'file=' + os.path.join(vm.working_dir, "hdc_disk.qcow2") + ',if=ide,index=2,media=disk,id=drive2',
        '-drive', 'file=' + os.path.join(vm.working_dir, "hdd_disk.qcow2") + ',if=ide,index=3,media=disk,id=drive3'
    ]


@pytest.mark.skipif(sys.platform.startswith("win"), reason="Not supported on Windows")
async def test_set_process_priority(vm, fake_qemu_img_binary):

    with asyncio_patch("asyncio.create_subprocess_exec", return_value=MagicMock()) as process:
        vm._process = MagicMock()
        vm._process.pid = 42
        vm._process_priority = "low"
        await vm._set_process_priority()
        assert process.called
        args, kwargs = process.call_args
        assert args == ("renice", "-n", "5", "-p", "42")


@pytest.mark.skipif(sys.platform.startswith("win"), reason="Not supported on Windows")
async def test_set_process_priority_normal(vm, fake_qemu_img_binary):

    with asyncio_patch("asyncio.create_subprocess_exec", return_value=MagicMock()) as process:
        vm._process = MagicMock()
        vm._process.pid = 42
        await vm._set_process_priority()
        assert not process.called


def test_json(vm, compute_project):

    json = vm.__json__()
    assert json["name"] == vm.name
    assert json["project_id"] == compute_project.id


async def test_control_vm(vm, running_subprocess_mock):

    vm._process = running_subprocess_mock
    vm._monitor = 4242
    reader = MagicMock()
    writer = MagicMock()
    with asyncio_patch("asyncio.open_connection", return_value=(reader, writer)):
        res = await vm._control_vm("test")
        writer.write.assert_called_with(b"test\n")
    assert res is None


async def test_control_vm_expect_text(vm, running_subprocess_mock):

    vm._process = running_subprocess_mock
    reader = MagicMock()
    writer = MagicMock()
    with asyncio_patch("asyncio.open_connection", return_value=(reader, writer)):

        future = asyncio.Future()
        future.set_result(b"epic product")
        reader.readline.return_value = future

        vm._monitor = 4242
        res = await vm._control_vm("test", [b"epic"])
        writer.write.assert_called_with(b"test\n")

    assert res == "epic product"


async def test_build_command(vm, fake_qemu_binary):

    os.environ["DISPLAY"] = "0:0"
    with asyncio_patch("asyncio.create_subprocess_exec", return_value=MagicMock()):
        cmd = await vm._build_command()
        nio = vm._local_udp_tunnels[0][0]
        assert cmd == [
            fake_qemu_binary,
            "-name",
            "test",
            "-m",
            "256M",
            "-smp",
            "cpus=1,sockets=1",
            "-boot",
            "order=c",
            "-uuid",
            vm.id,
            "-serial",
            "telnet:127.0.0.1:{},server,nowait".format(vm._internal_console_port),
            "-net",
            "none",
            "-device",
            "e1000,mac={},netdev=gns3-0".format(vm._mac_address),
            "-netdev",
            "socket,id=gns3-0,udp=127.0.0.1:{},localaddr=127.0.0.1:{}".format(nio.rport, nio.lport),
            "-display",
            "none"
        ]


async def test_build_command_manual_uuid(vm):
    """
    If user has set a uuid we keep it
    """

    vm.options = "-uuid e1c307a4-896f-11e6-81a5-3c07547807cc"
    os.environ["DISPLAY"] = "0:0"
    with asyncio_patch("asyncio.create_subprocess_exec", return_value=MagicMock()):
        cmd = await vm._build_command()
        assert "e1c307a4-896f-11e6-81a5-3c07547807cc" in cmd
        assert vm.id not in cmd


async def test_build_command_kvm(linux_platform, vm, fake_qemu_binary):
    """
    Qemu 2.4 introduce an issue with KVM
    """

    vm.manager.get_qemu_version = AsyncioMagicMock(return_value="2.3.2")
    os.environ["DISPLAY"] = "0:0"
    with asyncio_patch("gns3server.compute.qemu.qemu_vm.QemuVM._run_with_hardware_acceleration", return_value=True):
        with asyncio_patch("asyncio.create_subprocess_exec", return_value=MagicMock()) as process:
            cmd = await vm._build_command()
            nio = vm._local_udp_tunnels[0][0]
            assert cmd == [
                fake_qemu_binary,
                "-name",
                "test",
                "-m",
                "256M",
                "-smp",
                "cpus=1,sockets=1",
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
                "e1000,mac={},netdev=gns3-0".format(vm._mac_address),
                "-netdev",
                "socket,id=gns3-0,udp=127.0.0.1:{},localaddr=127.0.0.1:{}".format(nio.rport, nio.lport),
                "-nographic"
            ]


async def test_build_command_kvm_2_4(linux_platform, vm, fake_qemu_binary):
    """
    Qemu 2.4 introduce an issue with KVM
    """

    vm.manager.get_qemu_version = AsyncioMagicMock(return_value="2.4.2")
    os.environ["DISPLAY"] = "0:0"
    with asyncio_patch("gns3server.compute.qemu.qemu_vm.QemuVM._run_with_hardware_acceleration", return_value=True):
        with asyncio_patch("asyncio.create_subprocess_exec", return_value=MagicMock()) as process:
            cmd = await vm._build_command()
            nio = vm._local_udp_tunnels[0][0]
            assert cmd == [
                fake_qemu_binary,
                "-name",
                "test",
                "-m",
                "256M",
                "-smp",
                "cpus=1,sockets=1",
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
                "e1000,mac={},netdev=gns3-0".format(vm._mac_address),
                "-netdev",
                "socket,id=gns3-0,udp=127.0.0.1:{},localaddr=127.0.0.1:{}".format(nio.rport, nio.lport),
                "-nographic"
            ]


@pytest.mark.skipif(sys.platform.startswith("win"), reason="Not supported on Windows")
async def test_build_command_without_display(vm):

    vm.manager.get_qemu_version = AsyncioMagicMock(return_value="2.5.0")
    os.environ["DISPLAY"] = ""
    with asyncio_patch("asyncio.create_subprocess_exec", return_value=MagicMock()):
        cmd = await vm._build_command()
        assert "-nographic" in cmd


async def test_build_command_two_adapters(vm, fake_qemu_binary):

    vm.manager.get_qemu_version = AsyncioMagicMock(return_value="2.5.0")
    os.environ["DISPLAY"] = "0:0"
    vm.adapters = 2
    with asyncio_patch("asyncio.create_subprocess_exec", return_value=MagicMock()):
        cmd = await vm._build_command()
        nio1 = vm._local_udp_tunnels[0][0]
        nio2 = vm._local_udp_tunnels[1][0]
        assert cmd == [
            fake_qemu_binary,
            "-name",
            "test",
            "-m",
            "256M",
            "-smp",
            "cpus=1,sockets=1",
            "-boot",
            "order=c",
            "-uuid",
            vm.id,
            "-serial",
            "telnet:127.0.0.1:{},server,nowait".format(vm._internal_console_port),
            "-net",
            "none",
            "-device",
            "e1000,mac={},netdev=gns3-0".format(vm._mac_address),
            "-netdev",
            "socket,id=gns3-0,udp=127.0.0.1:{},localaddr=127.0.0.1:{}".format(nio1.rport, nio1.lport),
            "-device",
            "e1000,mac={},netdev=gns3-1".format(int_to_macaddress(macaddress_to_int(vm._mac_address) + 1)),
            "-netdev",
            "socket,id=gns3-1,udp=127.0.0.1:{},localaddr=127.0.0.1:{}".format(nio2.rport, nio2.lport),
            "-nographic"
        ]


async def test_build_command_two_adapters_mac_address(vm):
    """
    Should support multiple base vmac address
    """

    vm.adapters = 2
    vm.mac_address = "00:00:ab:0e:0f:09"
    mac_0 = vm._mac_address
    mac_1 = int_to_macaddress(macaddress_to_int(vm._mac_address) + 1)
    assert mac_0[:8] == "00:00:ab"
    with asyncio_patch("asyncio.create_subprocess_exec", return_value=MagicMock()):
        cmd = await vm._build_command()
        assert "e1000,mac={},netdev=gns3-0".format(mac_0) in cmd
        assert "e1000,mac={},netdev=gns3-1".format(mac_1) in cmd

    vm.mac_address = "00:42:ab:0e:0f:0a"
    mac_0 = vm._mac_address
    mac_1 = int_to_macaddress(macaddress_to_int(vm._mac_address) + 1)
    assert mac_0[:8] == "00:42:ab"
    with asyncio_patch("asyncio.create_subprocess_exec", return_value=MagicMock()):

        cmd = await vm._build_command()
        assert "e1000,mac={},netdev=gns3-0".format(mac_0) in cmd
        assert "e1000,mac={},netdev=gns3-1".format(mac_1) in cmd


async def test_build_command_large_number_of_adapters(vm):
    """
    When we have more than 28 interface we need to add a pci bridge for
    additional interfaces (supported only with Qemu 2.4 and later)
    """

    vm.adapters = 100
    vm.mac_address = "00:00:ab:0e:0f:09"
    mac_0 = vm._mac_address
    mac_1 = int_to_macaddress(macaddress_to_int(vm._mac_address) + 1)
    assert mac_0[:8] == "00:00:ab"
    with asyncio_patch("asyncio.create_subprocess_exec", return_value=MagicMock()):
        cmd = await vm._build_command()

    # Count if we have 100 e1000 adapters in the command
    assert len([l for l in cmd if "e1000" in l ]) == 100
    assert len(vm._ethernet_adapters) == 100

    assert "e1000,mac={},netdev=gns3-0".format(mac_0) in cmd
    assert "e1000,mac={},netdev=gns3-1".format(mac_1) in cmd
    assert "pci-bridge,id=pci-bridge0,bus=dmi_pci_bridge0,chassis_nr=0x1,addr=0x0,shpc=off" not in cmd
    assert "pci-bridge,id=pci-bridge1,bus=dmi_pci_bridge1,chassis_nr=0x1,addr=0x1,shpc=off" in cmd
    assert "pci-bridge,id=pci-bridge2,bus=dmi_pci_bridge2,chassis_nr=0x1,addr=0x2,shpc=off" in cmd
    assert "i82801b11-bridge,id=dmi_pci_bridge1" in cmd

    mac_29 = int_to_macaddress(macaddress_to_int(vm._mac_address) + 29)
    assert "e1000,mac={},bus=pci-bridge1,addr=0x04,netdev=gns3-29".format(mac_29) in cmd
    mac_30 = int_to_macaddress(macaddress_to_int(vm._mac_address) + 30)
    assert "e1000,mac={},bus=pci-bridge1,addr=0x05,netdev=gns3-30".format(mac_30) in cmd
    mac_74 = int_to_macaddress(macaddress_to_int(vm._mac_address) + 74)
    assert "e1000,mac={},bus=pci-bridge2,addr=0x11,netdev=gns3-74".format(mac_74) in cmd

    # Qemu < 2.4 doesn't support large number of adapters
    vm.manager.get_qemu_version = AsyncioMagicMock(return_value="2.0.0")
    with pytest.raises(QemuError):
        with asyncio_patch("asyncio.create_subprocess_exec", return_value=MagicMock()):
            await vm._build_command()
    vm.adapters = 5
    with asyncio_patch("asyncio.create_subprocess_exec", return_value=MagicMock()):
        await vm._build_command()


async def test_build_command_with_virtio_net_pci_adapter(vm):
    """
    Test virtio-net-pci adapter which has parameters speed=1000 & duplex=full hard-coded
    """

    vm.adapters = 1
    vm.mac_address = "00:00:ab:0e:0f:09"
    vm._adapter_type = "virtio-net-pci"
    with asyncio_patch("asyncio.create_subprocess_exec", return_value=MagicMock()):
        cmd = await vm._build_command()
    assert "virtio-net-pci,mac=00:00:ab:0e:0f:09,speed=10000,duplex=full,netdev=gns3-0" in cmd


@pytest.mark.skipif(sys.platform.startswith("win"), reason="Not supported on Windows")
async def test_build_command_with_invalid_options(vm):

    vm.options = "'test"
    with pytest.raises(QemuError):
        await vm._build_command()


@pytest.mark.skipif(sys.platform.startswith("win"), reason="Not supported on Windows")
async def test_build_command_with_forbidden_options(vm):

    vm.options = "-blockdev"
    with pytest.raises(QemuError):
        await vm._build_command()


def test_hda_disk_image(vm, images_dir):

    open(os.path.join(images_dir, "test1"), "w+").close()
    vm.hda_disk_image = os.path.join(images_dir, "test1")
    assert vm.hda_disk_image == force_unix_path(os.path.join(images_dir, "test1"))
    open(os.path.join(images_dir, "QEMU", "test2"), "w+").close()
    vm.hda_disk_image = "test2"
    assert vm.hda_disk_image == force_unix_path(os.path.join(images_dir, "QEMU", "test2"))


async def test_hda_disk_image_non_linked_clone(vm, images_dir, compute_project, manager, fake_qemu_binary):
    """
    Two non linked can't use the same image at the same time
    """

    open(os.path.join(images_dir, "test1"), "w+").close()
    vm.linked_clone = False
    vm.hda_disk_image = os.path.join(images_dir, "test1")
    vm.manager._nodes[vm.id] = vm

    vm2 = QemuVM("test", "00010203-0405-0607-0809-0a0b0c0d0eaa", compute_project, manager, qemu_path=fake_qemu_binary)
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
    assert vm.options == "-machine accel=tcg"

    vm.options = "-enable-kvm"
    assert vm.options == "-machine accel=kvm"

    vm.options = "-icount 12"
    assert vm.options == "-icount 12"

    vm.options = "-icount 12 -no-kvm"
    assert vm.options == "-icount 12 -machine accel=tcg"


def test_options_windows(windows_platform, vm):
    vm.options = "-no-kvm"
    assert vm.options == "-machine accel=tcg"

    vm.options = "-enable-kvm"
    assert vm.options == ""


def test_get_qemu_img(vm, tmpdir):

    open(str(tmpdir / "qemu-system-x86_64"), "w+").close()
    open(str(tmpdir / "qemu-img"), "w+").close()
    vm._qemu_path = str(tmpdir / "qemu-system-x86_64")
    if sys.platform.startswith("win"):
        assert vm._get_qemu_img() == str(tmpdir / "qemu-img.EXE")
    else:
        assert vm._get_qemu_img() == str(tmpdir / "qemu-img")


# def test_get_qemu_img_not_exist(vm, tmpdir):
#
#     open(str(tmpdir / "qemu-system-x86_64"), "w+").close()
#     vm._qemu_path = str(tmpdir / "qemu-system-x86_64")
#     with pytest.raises(QemuError):
#         vm._get_qemu_img()


async def test_run_with_hardware_acceleration_darwin(darwin_platform, vm):

    vm.manager.config.set("Qemu", "enable_hardware_acceleration", False)
    assert await vm._run_with_hardware_acceleration("qemu-system-x86_64", "") is False


async def test_run_with_hardware_acceleration_windows(windows_platform, vm):

    vm.manager.config.set("Qemu", "enable_hardware_acceleration", False)
    assert await vm._run_with_hardware_acceleration("qemu-system-x86_64", "") is False


async def test_run_with_kvm_linux(linux_platform, vm):

    with patch("os.path.exists", return_value=True) as os_path:
        vm.manager.config.set("Qemu", "enable_kvm", True)
        assert await vm._run_with_hardware_acceleration("qemu-system-x86_64", "") is True
        os_path.assert_called_with("/dev/kvm")


async def test_run_with_kvm_linux_options_no_kvm(linux_platform, vm):

    with patch("os.path.exists", return_value=True) as os_path:
        vm.manager.config.set("Qemu", "enable_kvm", True)
        assert await vm._run_with_hardware_acceleration("qemu-system-x86_64", "-machine accel=tcg") is False


async def test_run_with_kvm_not_x86(linux_platform, vm):

    with patch("os.path.exists", return_value=True):
        vm.manager.config.set("Qemu", "enable_kvm", True)
        with pytest.raises(QemuError):
            await vm._run_with_hardware_acceleration("qemu-system-arm", "")


async def test_run_with_kvm_linux_dev_kvm_missing(linux_platform, vm):

    with patch("os.path.exists", return_value=False):
        vm.manager.config.set("Qemu", "enable_kvm", True)
        with pytest.raises(QemuError):
            await vm._run_with_hardware_acceleration("qemu-system-x86_64", "")
