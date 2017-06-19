# -*- coding: utf-8 -*-
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

from tests.utils import asyncio_patch


def test_list_vms(http_controller):
    with asyncio_patch("gns3server.controller.gns3vm.vmware_gns3_vm.VMwareGNS3VM.list", return_value=[{"vmname": "test"}]):
        response = http_controller.get('/gns3vm/engines/vmware/vms', example=True)
    assert response.status == 200
    assert response.json == [
        {
            "vmname": "test"
        }
    ]


def test_engines(http_controller):
    response = http_controller.get('/gns3vm/engines', example=True)
    assert response.status == 200
    assert len(response.json) > 0


def test_put_gns3vm(http_controller):
    response = http_controller.put('/gns3vm', {
        "vmname": "TEST VM"
    }, example=True)
    assert response.status == 201
    assert response.json["vmname"] == "TEST VM"


def test_get_gns3vm(http_controller):
    response = http_controller.get('/gns3vm', example=True)
    assert response.status == 200
