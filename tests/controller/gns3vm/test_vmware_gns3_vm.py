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
