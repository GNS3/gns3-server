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

import os
import pytest
from tests.utils import asyncio_patch, AsyncioMagicMock

from gns3server.compute.virtualbox.virtualbox_vm import VirtualBoxVM
from gns3server.compute.virtualbox.virtualbox_error import VirtualBoxError
from gns3server.compute.virtualbox import VirtualBox


@pytest.fixture
async def manager(loop, port_manager):

    m = VirtualBox.instance()
    m.port_manager = port_manager
    return m


@pytest.fixture(scope="function")
async def vm(compute_project, manager):

    return VirtualBoxVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", compute_project, manager, "test", False)


async def test_vm(compute_project, manager):

    vm = VirtualBoxVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", compute_project, manager, "test", False)
    assert vm.name == "test"
    assert vm.id == "00010203-0405-0607-0809-0a0b0c0d0e0f"
    assert vm.vmname == "test"


async def test_rename_vmname(compute_project, manager):
    """
    Rename a VM is not allowed when using a running linked clone
    or if the vm already exists in Vbox
    """

    vm = VirtualBoxVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", compute_project, manager, "test", False)
    vm.manager.list_vms = AsyncioMagicMock(return_value=[{"vmname": "Debian"}])
    vm._linked_clone = True
    vm._modify_vm = AsyncioMagicMock()

    # Vm is running
    vm._node_status = "started"
    with pytest.raises(VirtualBoxError):
        await vm.set_vmname("Arch")
    assert not vm._modify_vm.called

    vm._node_status = "stopped"

    # Name already use
    with pytest.raises(VirtualBoxError):
        await vm.set_vmname("Debian")
    assert not vm._modify_vm.called

    # Work
    await vm.set_vmname("Arch")
    assert vm._modify_vm.called


async def test_vm_valid_virtualbox_api_version(compute_project, manager):

    with asyncio_patch("gns3server.compute.virtualbox.VirtualBox.execute", return_value=["API version:  4_3"]):
        vm = VirtualBoxVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", compute_project, manager, "test", False)
        vm._uuid = "00010203-0405-0607-0809-0a0b0c0d0e0f"
        await vm.create()


async def test_vm_invalid_virtualbox_api_version(compute_project, manager):

    with asyncio_patch("gns3server.compute.virtualbox.VirtualBox.execute", return_value=["API version:  4_2"]):
        with pytest.raises(VirtualBoxError):
            vm = VirtualBoxVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", compute_project, manager, "test", False)
            await vm.create()


async def test_vm_adapter_add_nio_binding_adapter_not_exist(vm, manager, free_console_port):

    nio = manager.create_nio({"type": "nio_udp", "lport": free_console_port, "rport": free_console_port, "rhost": "127.0.0.1"})
    with pytest.raises(VirtualBoxError):
        await vm.adapter_add_nio_binding(15, nio)


def test_json(vm, tmpdir, project):

    assert vm.__json__()["node_directory"] is None
    project._path = str(tmpdir)
    vm._linked_clone = True
    assert vm.__json__()["node_directory"] is not None


def test_patch_vm_uuid(vm):

    xml = """<?xml version="1.0"?>
    <VirtualBox xmlns="http://www.virtualbox.org/" version="1.16-macosx">
        <Machine uuid="{f8138a63-e361-49ee-a5a4-ba0559bc00e2}" name="Debian-1" OSType="Debian_64" currentSnapshot="{8bd00b14-4c14-4992-a165-cb09e80fe8e4    }" snapshotFolder="Snapshots" lastStateChange="2016-10-28T12:54:26Z">
        </Machine>
    </VirtualBox>
    """

    os.makedirs(os.path.join(vm.working_dir, vm._vmname), exist_ok=True)
    with open(vm._linked_vbox_file(), "w+") as f:
        f.write(xml)
    vm._linked_clone = True
    vm._patch_vm_uuid()
    with open(vm._linked_vbox_file()) as f:
        c = f.read()
        assert "{" + vm.id + "}" in c


def test_patch_vm_uuid_with_corrupted_file(vm):

    xml = """<?xml version="1.0"?>
    <VirtualBox>
    """
    os.makedirs(os.path.join(vm.working_dir, vm._vmname), exist_ok=True)
    with open(vm._linked_vbox_file(), "w+") as f:
        f.write(xml)
    vm._linked_clone = True
    with pytest.raises(VirtualBoxError):
        vm._patch_vm_uuid()
