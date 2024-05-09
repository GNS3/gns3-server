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

from gns3server.controller.gns3vm.remote_gns3_vm import RemoteGNS3VM
from gns3server.controller.gns3vm.gns3_vm_error import GNS3VMError


@pytest.fixture
def gns3vm(controller):

    return RemoteGNS3VM(controller)


async def test_list(gns3vm, controller):

    await controller.add_compute("r1", name="R1", host="r1.local", connect=False)
    res = await gns3vm.list()
    assert res == [{"vmname": "R1"}]


async def test_start(gns3vm, controller):

    await controller.add_compute("r1",
                                 name="R1",
                                 protocol="https",
                                 host="r1.local",
                                 port=8484,
                                 user="hello",
                                 password="world",
                                 connect=False)

    gns3vm.vmname = "R1"
    await gns3vm.start()
    assert gns3vm.running
    assert gns3vm.protocol == "https"
    assert gns3vm.ip_address == "r1.local"
    assert gns3vm.port == 8484
    assert gns3vm.user == "hello"
    assert gns3vm.password == "world"


async def test_start_invalid_vm(gns3vm, controller):

    await controller.add_compute("r1",
                                 name="R1",
                                 protocol="https",
                                 host="r1.local",
                                 port=8484,
                                 user="hello",
                                 password="world",
                                 connect=False)

    gns3vm.vmname = "R2"
    with pytest.raises(GNS3VMError):
        await gns3vm.start()
    assert not gns3vm.running
