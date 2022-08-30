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

from tests.utils import asyncio_patch
from gns3server.utils.asyncio import wait_run_in_executor

from gns3server.controller.gns3vm.virtualbox_gns3_vm import VirtualBoxGNS3VM


@pytest_asyncio.fixture
async def gns3vm(controller):

    vm = VirtualBoxGNS3VM(controller)
    vm.vmname = "GNS3 VM"
    return vm


@pytest.mark.asyncio
async def test_look_for_interface(gns3vm):

    showvminfo = """
nic1="hostonly"
nictype1="82540EM"
nicspeed1="0"
nic2="nat"
nictype2="82540EM"
nicspeed2="0"
nic3="none"
nic4="none"
nic5="none"
nic6="none"
nic7="none"
nic8="none"
vcpwidth=1024
vcpheight=768
vcprate=512
vcpfps=25
GuestMemoryBalloon=0
    """

    with asyncio_patch("gns3server.controller.gns3vm.virtualbox_gns3_vm.VirtualBoxGNS3VM._execute", return_value=showvminfo) as mock:
        res = await gns3vm._look_for_interface("nat")
        mock.assert_called_with('showvminfo', ['GNS3 VM', '--machinereadable'])
        assert res == 2

    # with asyncio_patch("gns3server.controller.gns3vm.virtualbox_gns3_vm.VirtualBoxGNS3VM._execute") as mock:
    #     mock.side_effect = execute_mock
    #     res = await gns3vm._look_for_interface("dummy")
    # assert mock.called
    # assert res == -1


@pytest.mark.asyncio
async def test_cpu_vendor_id(gns3vm):

    from cpuinfo import get_cpu_info
    cpu_info = await wait_run_in_executor(get_cpu_info)
    vendor_id = cpu_info.get('vendor_id_raw')
    assert vendor_id  # vendor id should not be empty
