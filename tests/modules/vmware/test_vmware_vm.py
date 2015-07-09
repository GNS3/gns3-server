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

from gns3server.modules.vmware.vmware_vm import VMwareVM
from gns3server.modules.vmware.vmware_error import VMwareError
from gns3server.modules.vmware import VMware


@pytest.fixture(scope="module")
def manager(port_manager):
    m = VMware.instance()
    m.port_manager = port_manager
    return m


@pytest.fixture(scope="function")
def vm(project, manager, tmpdir):
    fake_vmx = str(tmpdir / "test.vmx")
    open(fake_vmx, "w+").close()

    return VMwareVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", project, manager, fake_vmx, False)


def test_vm(project, manager, vm):
    assert vm.name == "test"
    assert vm.id == "00010203-0405-0607-0809-0a0b0c0d0e0f"


def test_json(vm, tmpdir, project):
    assert vm.__json__()["vm_directory"] is not None
    project._path = str(tmpdir)
    vm._linked_clone = True
    assert vm.__json__()["vm_directory"] is not None
