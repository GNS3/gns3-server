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
from tests.utils import asyncio_patch


@pytest.mark.asyncio
async def test_list_vms(controller_api):

    with asyncio_patch("gns3server.controller.gns3vm.vmware_gns3_vm.VMwareGNS3VM.list", return_value=[{"vmname": "test"}]):
        response = await controller_api.get('/gns3vm/engines/vmware/vms')
    assert response.status_code == 200
    assert response.json == [
        {
            "vmname": "test"
        }
    ]


@pytest.mark.asyncio
async def test_engines(controller_api):

    response = await controller_api.get('/gns3vm/engines')
    assert response.status_code == 200
    assert len(response.json) > 0


@pytest.mark.asyncio
async def test_put_gns3vm(controller_api):

    response = await controller_api.put('/gns3vm', {"vmname": "TEST VM"})
    assert response.status_code == 200
    assert response.json["vmname"] == "TEST VM"


@pytest.mark.asyncio
async def test_get_gns3vm(controller_api):
    response = await controller_api.get('/gns3vm')
    assert response.status_code == 200
