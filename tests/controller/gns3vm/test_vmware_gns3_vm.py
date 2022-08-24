#!/usr/bin/env python
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

from gns3server.controller.gns3vm.vmware_gns3_vm import VMwareGNS3VM


@pytest_asyncio.fixture
async def gns3vm(controller):

    vm = VMwareGNS3VM(controller)
    vm.vmname = "GNS3 VM"
    return vm


@pytest.fixture
def vmx_path(tmpdir):

    return str(tmpdir / "vmwware_vm.vmx")


@pytest.mark.asyncio
async def test_set_extra_options(gns3vm, vmx_path, windows_platform):

    gns3vm._vmx_path = vmx_path

    # when there is not an entry, we modify it
    with open(vmx_path, 'w') as f:
        f.write("")

    await gns3vm._set_extra_options()

    with open(vmx_path, 'r') as f:
        assert f.read() == 'vhv.enable = "TRUE"\n'

    # when there is an entry, we don't modify it
    with open(vmx_path, 'w') as f:
        f.write('vhv.enable = "FALSE"\n')

    await gns3vm._set_extra_options()

    with open(vmx_path, 'r') as f:
        assert f.read() == 'vhv.enable = "FALSE"\n'

