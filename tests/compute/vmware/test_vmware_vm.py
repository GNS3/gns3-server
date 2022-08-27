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

from gns3server.compute.vmware.vmware_vm import VMwareVM
from gns3server.compute.vmware import VMware


@pytest.fixture
async def manager(loop, port_manager):

    m = VMware.instance()
    m.port_manager = port_manager
    return m


@pytest.fixture(scope="function")
async def vm(compute_project, manager, tmpdir):

    fake_vmx = str(tmpdir / "test.vmx")
    open(fake_vmx, "w+").close()
    return VMwareVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", compute_project, manager, fake_vmx, False)


async def test_vm(vm):

    assert vm.name == "test"
    assert vm.id == "00010203-0405-0607-0809-0a0b0c0d0e0f"


async def test_json(vm, tmpdir, compute_project):

    assert vm.__json__()["node_directory"] is not None
    compute_project._path = str(tmpdir)
    vm._linked_clone = True
    assert vm.__json__()["node_directory"] is not None


async def test_start_capture(vm, tmpdir, manager, free_console_port):

    output_file = str(tmpdir / "test.pcap")
    nio = manager.create_nio({"type": "nio_udp", "lport": free_console_port, "rport": free_console_port, "rhost": "127.0.0.1"})
    vm.adapters = 1
    await vm.adapter_add_nio_binding(0, nio)
    await vm.start_capture(0, output_file)
    assert vm._ethernet_adapters[0].get_nio(0).capturing


async def test_stop_capture(vm, tmpdir, manager, free_console_port):

    output_file = str(tmpdir / "test.pcap")
    nio = manager.create_nio({"type": "nio_udp", "lport": free_console_port, "rport": free_console_port, "rhost": "127.0.0.1"})
    vm.adapters = 1
    await vm.adapter_add_nio_binding(0, nio)
    await vm.start_capture(0, output_file)
    assert vm._ethernet_adapters[0].get_nio(0).capturing
    await vm.stop_capture(0)
    assert vm._ethernet_adapters[0].get_nio(0).capturing is False
