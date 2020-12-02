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

from fastapi import FastAPI, status
from httpx import AsyncClient
from tests.utils import asyncio_patch

pytestmark = pytest.mark.asyncio


async def test_list_vms(app: FastAPI, client: AsyncClient) -> None:

    with asyncio_patch("gns3server.controller.gns3vm.vmware_gns3_vm.VMwareGNS3VM.list", return_value=[{"vmname": "test"}]):
        response = await client.get(app.url_path_for("get_vms", engine="vmware"))
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == [
        {
            "vmname": "test"
        }
    ]


async def test_engines(app: FastAPI, client: AsyncClient) -> None:

    response = await client.get(app.url_path_for("get_engines"))
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()) > 0


async def test_put_gns3vm(app: FastAPI, client: AsyncClient) -> None:

    response = await client.put(app.url_path_for("update_gns3vm_settings"), json={"vmname": "TEST VM"})
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["vmname"] == "TEST VM"


async def test_get_gns3vm(app: FastAPI, client: AsyncClient) -> None:
    response = await client.get(app.url_path_for("get_gns3vm_settings"))
    assert response.status_code == status.HTTP_200_OK
