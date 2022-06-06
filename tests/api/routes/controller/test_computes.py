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

import uuid
import pytest

from fastapi import FastAPI, status
from httpx import AsyncClient

from gns3server.schemas.controller.computes import Compute

pytestmark = pytest.mark.asyncio

import unittest
from tests.utils import asyncio_patch


class TestComputeRoutes:

    async def test_compute_create(self, app: FastAPI, client: AsyncClient) -> None:

        params = {
            "protocol": "http",
            "host": "localhost",
            "port": 84,
            "user": "julien",
            "password": "secure"}

        response = await client.post(app.url_path_for("create_compute"), json=params)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["compute_id"] is not None

        del params["password"]
        for param, value in params.items():
            assert response.json()[param] == value

    async def test_compute_create_with_id(self, app: FastAPI, client: AsyncClient) -> None:

        compute_id = str(uuid.uuid4())
        params = {
            "compute_id": compute_id,
            "protocol": "http",
            "host": "localhost",
            "port": 84,
            "user": "julien",
            "password": "secure"}

        response = await client.post(app.url_path_for("create_compute"), json=params)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["compute_id"] == compute_id

        del params["password"]
        for param, value in params.items():
            assert response.json()[param] == value

    async def test_compute_list(self, app: FastAPI, client: AsyncClient) -> None:

        response = await client.get(app.url_path_for("get_computes"))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) > 0

    async def test_compute_get(self, app: FastAPI, client: AsyncClient, test_compute: Compute) -> None:

        response = await client.get(app.url_path_for("get_compute", compute_id=test_compute.compute_id))
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["compute_id"] == str(test_compute.compute_id)

    async def test_compute_update(self, app: FastAPI, client: AsyncClient, test_compute: Compute) -> None:

        params = {
            "protocol": "http",
            "host": "localhost",
            "port": 42,
            "user": "julien",
            "password": "secure"
        }

        response = await client.post(app.url_path_for("create_compute"), json=params)
        assert response.status_code == status.HTTP_201_CREATED
        compute_id = response.json()["compute_id"]

        params["protocol"] = "https"
        response = await client.put(app.url_path_for("update_compute", compute_id=compute_id), json=params)
        assert response.status_code == status.HTTP_200_OK

        del params["password"]
        for param, value in params.items():
            assert response.json()[param] == value

    async def test_compute_delete(self, app: FastAPI, client: AsyncClient, test_compute: Compute) -> None:

        response = await client.delete(app.url_path_for("delete_compute", compute_id=test_compute.compute_id))
        assert response.status_code == status.HTTP_204_NO_CONTENT


class TestComputeFeatures:

    async def test_compute_list_docker_images(self, app: FastAPI, client: AsyncClient) -> None:

        params = {
            "protocol": "http",
            "host": "localhost",
            "port": 84,
            "user": "julien",
            "password": "secure"
        }

        response = await client.post(app.url_path_for("create_compute"), json=params)
        assert response.status_code == status.HTTP_201_CREATED
        compute_id = response.json()["compute_id"]

        with asyncio_patch("gns3server.controller.compute.Compute.forward", return_value=[{"image": "docker1"}, {"image": "docker2"}]) as mock:
            response = await client.get(app.url_path_for("docker_get_images", compute_id=compute_id))
            mock.assert_called_with("GET", "docker", "images")
            assert response.json() == [{"image": "docker1"}, {"image": "docker2"}]

    async def test_compute_list_virtualbox_vms(self, app: FastAPI, client: AsyncClient) -> None:

        params = {
            "protocol": "http",
            "host": "localhost",
            "port": 4242,
            "user": "julien",
            "password": "secure"
        }
        response = await client.post(app.url_path_for("get_computes"), json=params)
        assert response.status_code == status.HTTP_201_CREATED
        compute_id = response.json()["compute_id"]

        with asyncio_patch("gns3server.controller.compute.Compute.forward", return_value=[]) as mock:
            response = await client.get(app.url_path_for("virtualbox_vms", compute_id=compute_id))
            mock.assert_called_with("GET", "virtualbox", "vms")
            assert response.json() == []

    async def test_compute_list_vmware_vms(self, app: FastAPI, client: AsyncClient) -> None:

        params = {
            "protocol": "http",
            "host": "localhost",
            "port": 4243,
            "user": "julien",
            "password": "secure"
        }
        response = await client.post(app.url_path_for("get_computes"), json=params)
        assert response.status_code == status.HTTP_201_CREATED
        compute_id = response.json()["compute_id"]

        with asyncio_patch("gns3server.controller.compute.Compute.forward", return_value=[]) as mock:
            response = await client.get(app.url_path_for("vmware_vms", compute_id=compute_id))
            mock.assert_called_with("GET", "vmware", "vms")
            assert response.json() == []

    async def test_compute_create_img(self, app: FastAPI, client: AsyncClient) -> None:

        params = {
            "protocol": "http",
            "host": "localhost",
            "port": 4284,
            "user": "julien",
            "password": "secure"
        }

        response = await client.post(app.url_path_for("get_computes"), json=params)
        assert response.status_code == status.HTTP_201_CREATED
        compute_id = response.json()["compute_id"]

        params = {"path": "/test"}
        with asyncio_patch("gns3server.controller.compute.Compute.forward", return_value=[]) as mock:
            response = await client.post(app.url_path_for("get_compute", compute_id=compute_id) + "/qemu/img", json=params)
            assert response.json() == []
            mock.assert_called_with("POST", "qemu", "img", data=unittest.mock.ANY)

    # async def test_compute_autoidlepc(self, app: FastAPI, client: AsyncClient) -> None:
    #
    #     params = {
    #         "protocol": "http",
    #         "host": "localhost",
    #         "port": 84,
    #         "user": "julien",
    #         "password": "secure"
    #     }
    #
    #     response = await client.post(app.url_path_for("get_computes"), json=params)
    #     assert response.status_code == status.HTTP_201_CREATED
    #     compute_id = response.json()["compute_id"]
    #
    #     params = {
    #         "platform": "c7200",
    #         "image": "test.bin",
    #         "ram": 512
    #     }
    #
    #     with asyncio_patch("gns3server.controller.Controller.autoidlepc", return_value={"idlepc": "0x606de20c"}) as mock:
    #         response = await client.post(app.url_path_for("autoidlepc", compute_id=compute_id) + "/auto_idlepc", json=params)
    #         assert mock.called
    #         assert response.status_code == status.HTTP_200_OK
