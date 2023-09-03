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
import stat
import socket
import uuid
import shutil

from tests.utils import asyncio_patch, AsyncioMagicMock

from unittest.mock import MagicMock
from gns3server.compute.iou.iou_vm import IOUVM
from gns3server.compute.iou.iou_error import IOUError
from gns3server.compute.iou import IOU


@pytest_asyncio.fixture
async def manager(port_manager):

    m = IOU.instance()
    m.port_manager = port_manager
    return m


@pytest_asyncio.fixture(scope="function")
async def vm(compute_project, manager, config, tmpdir, fake_iou_bin, iourc_file):

    vm = IOUVM("test", str(uuid.uuid4()), compute_project, manager, application_id=1)
    config.settings.IOU.iourc_path = iourc_file
    vm.path = "iou.bin"
    vm._loader = []
    return vm


@pytest.fixture
def iourc_file(tmpdir):

    path = str(tmpdir / "iourc")
    with open(path, "w+") as f:
        hostname = socket.gethostname()
        f.write("[license]\n{} = aaaaaaaaaaaaaaaa;".format(hostname))
    return path


@pytest.fixture
def fake_iou_bin(images_dir):
    """Create a fake IOU image on disk"""

    path = os.path.join(images_dir, "iou.bin")
    with open(path, "w+") as f:
        f.write('\x7fELF\x01\x01\x01')
    os.chmod(path, stat.S_IREAD | stat.S_IEXEC)
    return path


def test_vm(compute_project, manager):

    vm = IOUVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", compute_project, manager)
    assert vm.name == "test"
    assert vm.id == "00010203-0405-0607-0809-0a0b0c0d0e0f"


def test_vm_startup_config_content(compute_project, manager):

    vm = IOUVM("test", "00010203-0405-0607-0808-0a0b0c0d0e0f", compute_project, manager, application_id=1)
    vm.startup_config_content = "hostname %h"
    assert vm.name == "test"
    assert vm.startup_config_content == "hostname test"
    assert vm.id == "00010203-0405-0607-0808-0a0b0c0d0e0f"


@pytest.mark.asyncio
async def test_start(vm):

    mock_process = MagicMock()
    vm._check_requirements = AsyncioMagicMock(return_value=True)
    vm._check_iou_licence = AsyncioMagicMock(return_value=True)
    vm._start_ubridge = AsyncioMagicMock(return_value=True)
    vm._ubridge_send = AsyncioMagicMock()

    with asyncio_patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec:
        mock_process.returncode = None
        mock_process.communicate = AsyncioMagicMock(return_value=(None, None))
        await vm.start()
        assert vm.is_running()
        assert vm.command_line == ' '.join(mock_exec.call_args[0])

    assert vm._check_requirements.called
    assert vm._check_iou_licence.called
    assert vm._start_ubridge.called
    vm._ubridge_send.assert_any_call("iol_bridge delete IOL-BRIDGE-513")
    vm._ubridge_send.assert_any_call("iol_bridge create IOL-BRIDGE-513 513")
    vm._ubridge_send.assert_any_call("iol_bridge start IOL-BRIDGE-513")


@pytest.mark.asyncio
async def test_start_with_iourc(vm, tmpdir, config):

    fake_file = str(tmpdir / "iourc")
    with open(fake_file, "w+") as f:
        f.write("1")
    mock_process = MagicMock()

    vm._check_requirements = AsyncioMagicMock(return_value=True)
    vm._check_iou_licence = AsyncioMagicMock(return_value=True)
    vm._start_ioucon = AsyncioMagicMock(return_value=True)
    vm._start_ubridge = AsyncioMagicMock(return_value=True)
    vm._ubridge_send = AsyncioMagicMock()

    config.settings.IOU.iourc_path = fake_file
    with asyncio_patch("asyncio.create_subprocess_exec", return_value=mock_process) as exec_mock:
        mock_process.returncode = None
        mock_process.communicate = AsyncioMagicMock(return_value=(None, None))
        await vm.start()
        assert vm.is_running()
        arsgs, kwargs = exec_mock.call_args
        assert kwargs["env"]["IOURC"] == fake_file


@pytest.mark.asyncio
async def test_rename_nvram_file(vm):
    """
    It should rename the nvram file to the correct name before launching the VM
    """

    with open(os.path.join(vm.working_dir, "nvram_0000{}".format(vm.application_id + 1)), 'w+') as f:
        f.write("1")

    with open(os.path.join(vm.working_dir, "vlan.dat-0000{}".format(vm.application_id + 1)), 'w+') as f:
        f.write("1")

    vm._rename_nvram_file()
    assert os.path.exists(os.path.join(vm.working_dir, "nvram_0000{}".format(vm.application_id)))
    assert os.path.exists(os.path.join(vm.working_dir, "vlan.dat-0000{}".format(vm.application_id)))


@pytest.mark.asyncio
async def test_stop(vm):

    process = MagicMock()
    vm._check_requirements = AsyncioMagicMock(return_value=True)
    vm._check_iou_licence = AsyncioMagicMock(return_value=True)
    vm._start_ioucon = AsyncioMagicMock(return_value=True)
    vm._start_ubridge = AsyncioMagicMock(return_value=True)
    vm._ubridge_send = AsyncioMagicMock()

    # Wait process kill success
    future = asyncio.Future()
    future.set_result(True)
    process.wait.return_value = future
    process.returncode = None
    process.communicate = AsyncioMagicMock(return_value=(None, None))

    with asyncio_patch("asyncio.create_subprocess_exec", return_value=process):
        with asyncio_patch("gns3server.utils.asyncio.wait_for_process_termination"):
            await vm.start()
            assert vm.is_running()
            await vm.stop()
            assert vm.is_running() is False
            process.terminate.assert_called_with()


@pytest.mark.asyncio
async def test_reload(vm, fake_iou_bin):

    process = MagicMock()
    vm._check_requirements = AsyncioMagicMock(return_value=True)
    vm._check_iou_licence = AsyncioMagicMock(return_value=True)
    vm._start_ioucon = AsyncioMagicMock(return_value=True)
    vm._start_ubridge = AsyncioMagicMock(return_value=True)
    vm._ubridge_send = AsyncioMagicMock()

    # Wait process kill success
    future = asyncio.Future()
    future.set_result(True)
    process.wait.return_value = future
    process.returncode = None
    process.communicate = AsyncioMagicMock(return_value=(None, None))

    with asyncio_patch("asyncio.create_subprocess_exec", return_value=process):
        with asyncio_patch("gns3server.utils.asyncio.wait_for_process_termination"):
            await vm.start()
            assert vm.is_running()
            await vm.reload()
            assert vm.is_running() is True
            process.terminate.assert_called_with()


@pytest.mark.asyncio
async def test_close(vm, port_manager):

    process = MagicMock()
    process.returncode = None
    process.communicate = AsyncioMagicMock(return_value=(None, None))
    vm._start_ubridge = AsyncioMagicMock(return_value=True)
    vm._ubridge_send = AsyncioMagicMock()
    with asyncio_patch("gns3server.compute.iou.iou_vm.IOUVM._check_requirements", return_value=True):
        with asyncio_patch("asyncio.create_subprocess_exec", return_value=process):
            await vm.start()
            port = vm.console
            await vm.close()
            # Raise an exception if the port is not free
            port_manager.reserve_tcp_port(port, vm.project)
            assert vm.is_running() is False


def test_path(vm, fake_iou_bin, config):

    vm.path = fake_iou_bin
    assert vm.path == fake_iou_bin


def test_path_relative(vm, fake_iou_bin):

    vm.path = "iou.bin"
    assert vm.path == fake_iou_bin


@pytest.mark.asyncio
async def test_path_invalid_bin(vm, tmpdir, config):

    config.settings.Server.images_path = str(tmpdir)
    path = str(tmpdir / "test.bin")

    with open(path, "w+") as f:
        f.write("BUG")

    with pytest.raises(IOUError):
        vm.path = path
        await vm._check_requirements()


def test_create_netmap_config(vm):

    vm._create_netmap_config()
    netmap_path = os.path.join(vm.working_dir, "NETMAP")

    with open(netmap_path) as f:
        content = f.read()

    assert "513:0/0    1:0/0" in content
    assert "513:15/3    1:15/3" in content


@pytest.mark.asyncio
async def test_build_command(vm):

    assert await vm._build_command() == [vm.path, str(vm.application_id)]


def test_get_startup_config(vm):

    content = "service timestamps debug datetime msec\nservice timestamps log datetime msec\nno service password-encryption"
    vm.startup_config = content
    assert vm.startup_config == content


def test_update_startup_config(vm):

    content = "service timestamps debug datetime msec\nservice timestamps log datetime msec\nno service password-encryption"
    vm.startup_config_content = content
    filepath = os.path.join(vm.working_dir, "startup-config.cfg")
    assert os.path.exists(filepath)
    with open(filepath) as f:
        assert f.read() == content


def test_update_startup_config_empty(vm):

    content = "service timestamps debug datetime msec\nservice timestamps log datetime msec\nno service password-encryption"
    vm.startup_config_content = content
    filepath = os.path.join(vm.working_dir, "startup-config.cfg")
    assert os.path.exists(filepath)
    with open(filepath) as f:
        assert f.read() == content
    vm.startup_config_content = ""
    with open(filepath) as f:
        assert f.read() == content


def test_update_startup_config_content_hostname(vm):

    content = "hostname %h\n"
    vm.name = "pc1"
    vm.startup_config_content = content
    with open(vm.startup_config_file) as f:
        assert f.read() == "hostname pc1\n"


def test_change_name(vm):

    path = os.path.join(vm.working_dir, "startup-config.cfg")
    vm.name = "world"
    with open(path, 'w+') as f:
        f.write("hostname world")
    vm.name = "hello"
    assert vm.name == "hello"
    with open(path) as f:
        assert f.read() == "hostname hello"
    # support hostname not sync
    vm.name = "alpha"
    with open(path, 'w+') as f:
        f.write("no service password-encryption\nhostname beta\nno ip icmp rate-limit unreachable")
    vm.name = "charlie"
    assert vm.name == "charlie"
    with open(path) as f:
        assert f.read() == "no service password-encryption\nhostname charlie\nno ip icmp rate-limit unreachable"


@pytest.mark.asyncio
async def test_library_check(vm):

    with asyncio_patch("gns3server.utils.asyncio.subprocess_check_output", return_value=""):
        await vm._library_check()

    with asyncio_patch("gns3server.utils.asyncio.subprocess_check_output", return_value="libssl => not found"):
        with pytest.raises(IOUError):
            await vm._library_check()


@pytest.mark.asyncio
async def test_enable_l1_keepalives(vm):

    with asyncio_patch("gns3server.utils.asyncio.subprocess_check_output", return_value="***************************************************************\n\n-l		Enable Layer 1 keepalive messages\n-u <n>		UDP port base for distributed networks\n"):
        command = ["test"]
        await vm._enable_l1_keepalives(command)
        assert command == ["test", "-l"]

    with asyncio_patch("gns3server.utils.asyncio.subprocess_check_output", return_value="***************************************************************\n\n-u <n>		UDP port base for distributed networks\n"):

        command = ["test"]
        with pytest.raises(IOUError):
            await vm._enable_l1_keepalives(command)
            assert command == ["test"]


@pytest.mark.asyncio
async def test_start_capture(vm, tmpdir, manager, free_console_port):

    output_file = str(tmpdir / "test.pcap")
    nio = manager.create_nio({"type": "nio_udp", "lport": free_console_port, "rport": free_console_port, "rhost": "127.0.0.1"})
    await vm.adapter_add_nio_binding(0, 0, nio)
    await vm.start_capture(0, 0, output_file)
    assert vm._adapters[0].get_nio(0).capturing


@pytest.mark.asyncio
async def test_stop_capture(vm, tmpdir, manager, free_console_port):

    output_file = str(tmpdir / "test.pcap")
    nio = manager.create_nio({"type": "nio_udp", "lport": free_console_port, "rport": free_console_port, "rhost": "127.0.0.1"})
    await vm.adapter_add_nio_binding(0, 0, nio)
    await vm.start_capture(0, 0, output_file)
    assert vm._adapters[0].get_nio(0).capturing
    await vm.stop_capture(0, 0)
    assert vm._adapters[0].get_nio(0).capturing is False


def test_get_legacy_vm_workdir():

    assert IOU.get_legacy_vm_workdir(42, "bla") == "iou/device-42"


@pytest.mark.asyncio
async def test_invalid_iou_file(vm, iourc_file):

    hostname = socket.gethostname()
    await vm._check_iou_licence()

    # Missing ;
    with pytest.raises(IOUError):
        with open(iourc_file, "w+") as f:
            f.write("[license]\n{} = aaaaaaaaaaaaaaaa".format(hostname))
        await vm._check_iou_licence()

    # Key too short
    with pytest.raises(IOUError):
        with open(iourc_file, "w+") as f:
            f.write("[license]\n{} = aaaaaaaaaaaaaa;".format(hostname))
        await vm._check_iou_licence()

    # Invalid hostname
    with pytest.raises(IOUError):
        with open(iourc_file, "w+") as f:
            f.write("[license]\nbla = aaaaaaaaaaaaaa;")
        await vm._check_iou_licence()

    # Missing licence section
    with pytest.raises(IOUError):
        with open(iourc_file, "w+") as f:
            f.write("[licensetest]\n{} = aaaaaaaaaaaaaaaa;")
        await vm._check_iou_licence()

    # Broken config file
    with pytest.raises(IOUError):
        with open(iourc_file, "w+") as f:
            f.write("[")
        await vm._check_iou_licence()

    # Missing file
    with pytest.raises(IOUError):
        os.remove(iourc_file)
        await vm._check_iou_licence()


def test_iourc_content(vm):

    vm.iourc_content = "test"

    with open(os.path.join(vm.temporary_directory, "iourc")) as f:
        assert f.read() == "test"


def test_iourc_content_fix_carriage_return(vm):

    vm.iourc_content = "test\r\n12"

    with open(os.path.join(vm.temporary_directory, "iourc")) as f:
        assert f.read() == "test\n12"


def test_extract_configs(vm):
    assert vm.extract_configs() == (None, None)

    with open(os.path.join(vm.working_dir, "nvram_00001"), "w+") as f:
        f.write("CORRUPTED")
        assert vm.extract_configs() == (None, None)

    with open(os.path.join(vm.working_dir, "nvram_00001"), "w+") as f:
        f.write("CORRUPTED")
        assert vm.extract_configs() == (None, None)

    shutil.copy("tests/resources/nvram_iou", os.path.join(vm.working_dir, "nvram_00001"))

    startup_config, private_config = vm.extract_configs()
    assert len(startup_config) == 1392
    assert len(private_config) == 0


def test_application_id(compute_project, manager):
    """
    Checks if uses local manager to get application_id when not set
    """
    vm = IOUVM("test", str(uuid.uuid4()), compute_project, manager, application_id=1)
    assert vm.application_id == 1

    vm.application_id = 3
    assert vm.application_id == 3
