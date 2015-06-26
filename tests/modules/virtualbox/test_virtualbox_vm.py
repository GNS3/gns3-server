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
from tests.utils import asyncio_patch

from gns3server.modules.virtualbox.virtualbox_vm import VirtualBoxVM
from gns3server.modules.virtualbox.virtualbox_error import VirtualBoxError
from gns3server.modules.virtualbox import VirtualBox


@pytest.fixture(scope="module")
def manager(port_manager):
    m = VirtualBox.instance()
    m.port_manager = port_manager
    return m


@pytest.fixture(scope="function")
def vm(project, manager):
    return VirtualBoxVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", project, manager, "test", False)


def test_vm(project, manager):
    vm = VirtualBoxVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", project, manager, "test", False)
    assert vm.name == "test"
    assert vm.id == "00010203-0405-0607-0809-0a0b0c0d0e0f"
    assert vm.vmname == "test"


def test_vm_valid_virtualbox_api_version(loop, project, manager):
    with asyncio_patch("gns3server.modules.virtualbox.VirtualBox.execute", return_value=["API version:  4_3"]):
        vm = VirtualBoxVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", project, manager, "test", False)
        loop.run_until_complete(asyncio.async(vm.create()))


def test_vm_invalid_virtualbox_api_version(loop, project, manager):
    with asyncio_patch("gns3server.modules.virtualbox.VirtualBox.execute", return_value=["API version:  4_2"]):
        with pytest.raises(VirtualBoxError):
            vm = VirtualBoxVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", project, manager, "test", False)
            loop.run_until_complete(asyncio.async(vm.create()))


def test_vm_adapter_add_nio_binding_adapter_not_exist(loop, vm, manager, free_console_port):
    nio = manager.create_nio(manager.vboxmanage_path, {"type": "nio_udp", "lport": free_console_port, "rport": free_console_port, "rhost": "192.168.1.2"})
    with pytest.raises(VirtualBoxError):
        loop.run_until_complete(asyncio.async(vm.adapter_add_nio_binding(15, nio)))


def test_json(vm, tmpdir, project):
    assert vm.__json__()["vm_directory"] is None
    project._path = str(tmpdir)
    vm._linked_clone = True
    assert vm.__json__()["vm_directory"] is not None
