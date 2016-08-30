#!/usr/bin/env python
#
# Copyright (C) 2016 GNS3 Technologies Inc.
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


def test_list(async_run, gns3vm, controller):
    async_run(controller.add_compute("r1", name="R1", host="r1.local", connect=False))
    res = async_run(gns3vm.list())
    assert res == [{"vmname": "R1"}]


def test_start(async_run, gns3vm, controller):
    async_run(controller.add_compute("r1", name="R1",
                                     protocol="https",
                                     host="r1.local",
                                     port=8484,
                                     user="hello",
                                     password="world",
                                     connect=False))
    gns3vm.vmname = "R1"
    res = async_run(gns3vm.start())
    assert gns3vm.running
    assert gns3vm.protocol == "https"
    assert gns3vm.ip_address == "r1.local"
    assert gns3vm.port == 8484
    assert gns3vm.user == "hello"
    assert gns3vm.password == "world"


def test_start_invalid_vm(async_run, gns3vm, controller):
    async_run(controller.add_compute("r1", name="R1",
                                     protocol="https",
                                     host="r1.local",
                                     port=8484,
                                     user="hello",
                                     password="world"))
    gns3vm.vmname = "R2"
    with pytest.raises(GNS3VMError):
        res = async_run(gns3vm.start())
    assert not gns3vm.running
