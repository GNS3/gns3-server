#!/usr/bin/env python
#
# Copyright (C) 2021 GNS3 Technologies Inc.
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

import os
import pytest
import shutil

from fastapi import FastAPI, status
from httpx import AsyncClient
from gns3server.controller import Controller

pytestmark = pytest.mark.asyncio


class TestApplianceRoutes:

    @pytest.fixture(autouse=True)
    def _install_builtin_appliances(self, controller: Controller):

        controller.appliance_manager.install_builtin_appliances()
        controller.appliance_manager.load_appliances()

    async def test_appliances_list(self, app: FastAPI, client: AsyncClient) -> None:

        response = await client.get(app.url_path_for("get_appliances"))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) > 0

    async def test_get_appliance(self, app: FastAPI, client: AsyncClient) -> None:

        appliance_id = "3bf492b6-5717-4257-9bfd-b34617c6f133"  # Cisco IOSv appliance
        response = await client.get(app.url_path_for("get_appliance", appliance_id=appliance_id))
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["appliance_id"] == appliance_id

    async def test_docker_appliance_install(self, app: FastAPI, client: AsyncClient) -> None:

        appliance_id = "fc520ae2-a4e5-48c3-9a13-516bb2e94668"  # Alpine Linux appliance
        response = await client.post(app.url_path_for("install_appliance", appliance_id=appliance_id))
        assert response.status_code == status.HTTP_204_NO_CONTENT

    async def test_docker_appliance_install_with_version(self, app: FastAPI, client: AsyncClient) -> None:

        appliance_id = "fc520ae2-a4e5-48c3-9a13-516bb2e94668"  # Alpine Linux appliance
        params = {"version": "123"}
        response = await client.post(app.url_path_for("install_appliance", appliance_id=appliance_id), params=params)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_qemu_appliance_install_with_version(self, app: FastAPI, client: AsyncClient, images_dir: str) -> None:

        shutil.copy("tests/resources/empty8G.qcow2", os.path.join(images_dir, "QEMU", "empty8G.qcow2"))
        appliance_id = "1cfdf900-7c30-4cb7-8f03-3f61d2581633"  # Empty VM appliance
        params = {"version": "8G"}
        response = await client.post(app.url_path_for("install_appliance", appliance_id=appliance_id), params=params)
        assert response.status_code == status.HTTP_204_NO_CONTENT

    async def test_qemu_appliance_install_without_version(self, app: FastAPI, client: AsyncClient, images_dir: str) -> None:

        appliance_id = "1cfdf900-7c30-4cb7-8f03-3f61d2581633"  # Empty VM appliance
        response = await client.post(app.url_path_for("install_appliance", appliance_id=appliance_id))
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_add_version_appliance(self, app: FastAPI, client: AsyncClient) -> None:

        appliance_id = "1cfdf900-7c30-4cb7-8f03-3f61d2581633"  # Empty VM appliance
        new_version = {
            "name": "99G",
            "images": {
                "hda_disk_image": "empty99G.qcow2"
            }
        }
        response = await client.post(app.url_path_for("add_appliance_version", appliance_id=appliance_id), json=new_version)
        assert response.status_code == status.HTTP_201_CREATED
        assert new_version in response.json()["versions"]

    async def test_add_existing_version_appliance(self, app: FastAPI, client: AsyncClient) -> None:

        appliance_id = "1cfdf900-7c30-4cb7-8f03-3f61d2581633"  # Empty VM appliance
        new_version = {
            "name": "8G",
            "images": {
                "hda_disk_image": "empty8G.qcow2"
            }
        }
        response = await client.post(app.url_path_for("add_appliance_version", appliance_id=appliance_id), json=new_version)
        assert response.status_code == status.HTTP_409_CONFLICT
