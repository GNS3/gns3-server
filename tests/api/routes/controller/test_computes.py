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

from fastapi import FastAPI, status
from httpx import AsyncClient

from gns3server.controller import Controller

pytestmark = pytest.mark.asyncio

import unittest
from tests.utils import asyncio_patch


async def test_compute_create_without_id(app: FastAPI, client: AsyncClient, controller: Controller) -> None:

    params = {
        "protocol": "http",
        "host": "localhost",
        "port": 84,
        "user": "julien",
        "password": "secure"}

    response = await client.post(app.url_path_for("create_compute"), json=params)
    assert response.status_code == status.HTTP_201_CREATED
    response_content = response.json()
    assert response_content["user"] == "julien"
    assert response_content["compute_id"] is not None
    assert "password" not in response_content
    assert len(controller.computes) == 1
    assert controller.computes[response_content["compute_id"]].host == "localhost"


async def test_compute_create_with_id(app: FastAPI, client: AsyncClient, controller: Controller) -> None:

    params = {
        "compute_id": "my_compute_id",
        "protocol": "http",
        "host": "localhost",
        "port": 84,
        "user": "julien",
        "password": "secure"}

    response = await client.post(app.url_path_for("create_compute"), json=params)
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["user"] == "julien"
    assert "password" not in response.json()
    assert len(controller.computes) == 1
    assert controller.computes["my_compute_id"].host == "localhost"


async def test_compute_get(app: FastAPI, client: AsyncClient, controller: Controller) -> None:

    params = {
        "compute_id": "my_compute_id",
        "protocol": "http",
        "host": "localhost",
        "port": 84,
        "user": "julien",
        "password": "secure"
    }

    response = await client.post(app.url_path_for("create_compute"), json=params)
    assert response.status_code == status.HTTP_201_CREATED

    response = await client.get(app.url_path_for("update_compute", compute_id="my_compute_id"))
    assert response.status_code == status.HTTP_200_OK


async def test_compute_update(app: FastAPI, client: AsyncClient) -> None:

    params = {
        "compute_id": "my_compute_id",
        "protocol": "http",
        "host": "localhost",
        "port": 84,
        "user": "julien",
        "password": "secure"
    }

    response = await client.post(app.url_path_for("create_compute"), json=params)
    assert response.status_code == status.HTTP_201_CREATED
    response = await client.get(app.url_path_for("get_compute", compute_id="my_compute_id"))
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["protocol"] == "http"

    params["protocol"] = "https"
    response = await client.put(app.url_path_for("update_compute", compute_id="my_compute_id"), json=params)

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["protocol"] == "https"


async def test_compute_list(app: FastAPI, client: AsyncClient, controller: Controller) -> None:

    params = {
        "compute_id": "my_compute_id",
        "protocol": "http",
        "host": "localhost",
        "port": 84,
        "user": "julien",
        "password": "secure",
        "name": "My super server"
    }

    response = await client.post(app.url_path_for("create_compute"), json=params)
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["user"] == "julien"
    assert "password" not in response.json()

    response = await client.get(app.url_path_for("get_computes"))
    for compute in response.json():
        if compute['compute_id'] != 'local':
            assert compute == {
                'compute_id': 'my_compute_id',
                'connected': False,
                'host': 'localhost',
                'port': 84,
                'protocol': 'http',
                'user': 'julien',
                'name': 'My super server',
                'cpu_usage_percent': 0.0,
                'memory_usage_percent': 0.0,
                'disk_usage_percent': 0.0,
                'last_error': None,
                'capabilities': {
                    'version': '',
                    'platform': '',
                    'cpus': 0,
                    'memory': 0,
                    'disk_size': 0,
                    'node_types': []
                }
            }


async def test_compute_delete(app: FastAPI, client: AsyncClient, controller: Controller) -> None:

    params = {
        "compute_id": "my_compute_id",
        "protocol": "http",
        "host": "localhost",
        "port": 84,
        "user": "julien",
        "password": "secure"
    }

    response = await client.post(app.url_path_for("create_compute"), json=params)
    assert response.status_code == status.HTTP_201_CREATED

    response = await client.get(app.url_path_for("get_computes"))
    assert len(response.json()) == 1

    response = await client.delete(app.url_path_for("delete_compute", compute_id="my_compute_id"))
    assert response.status_code == status.HTTP_204_NO_CONTENT

    response = await client.get(app.url_path_for("get_computes"))
    assert len(response.json()) == 0


async def test_compute_list_images(app: FastAPI, client: AsyncClient) -> None:

    params = {
        "compute_id": "my_compute_id",
        "protocol": "http",
        "host": "localhost",
        "port": 84,
        "user": "julien",
        "password": "secure"
    }
    response = await client.post(app.url_path_for("create_compute"), json=params)
    assert response.status_code == status.HTTP_201_CREATED

    with asyncio_patch("gns3server.controller.compute.Compute.images", return_value=[{"filename": "linux.qcow2"}, {"filename": "asav.qcow2"}]) as mock:
        response = await client.get(app.url_path_for("delete_compute", compute_id="my_compute_id") + "/qemu/images")
        assert response.json() == [{"filename": "linux.qcow2"}, {"filename": "asav.qcow2"}]
        mock.assert_called_with("qemu")


async def test_compute_list_vms(app: FastAPI, client: AsyncClient) -> None:

    params = {
        "compute_id": "my_compute",
        "protocol": "http",
        "host": "localhost",
        "port": 84,
        "user": "julien",
        "password": "secure"
    }
    response = await client.post(app.url_path_for("get_computes"), json=params)
    assert response.status_code == status.HTTP_201_CREATED

    with asyncio_patch("gns3server.controller.compute.Compute.forward", return_value=[]) as mock:
        response = await client.get(app.url_path_for("get_compute", compute_id="my_compute_id") + "/virtualbox/vms")
        mock.assert_called_with("GET", "virtualbox", "vms")
        assert response.json() == []


async def test_compute_create_img(app: FastAPI, client: AsyncClient) -> None:

    params = {
        "compute_id": "my_compute",
        "protocol": "http",
        "host": "localhost",
        "port": 84,
        "user": "julien",
        "password": "secure"
    }

    response = await client.post(app.url_path_for("get_computes"), json=params)
    assert response.status_code == status.HTTP_201_CREATED

    params = {"path": "/test"}
    with asyncio_patch("gns3server.controller.compute.Compute.forward", return_value=[]) as mock:
        response = await client.post(app.url_path_for("get_compute", compute_id="my_compute_id") + "/qemu/img", json=params)
        assert response.json() == []
        mock.assert_called_with("POST", "qemu", "img", data=unittest.mock.ANY)


async def test_compute_autoidlepc(app: FastAPI, client: AsyncClient) -> None:

    params = {
        "compute_id": "my_compute_id",
        "protocol": "http",
        "host": "localhost",
        "port": 84,
        "user": "julien",
        "password": "secure"
    }

    await client.post(app.url_path_for("get_computes"), json=params)

    params = {
        "platform": "c7200",
        "image": "test.bin",
        "ram": 512
    }

    with asyncio_patch("gns3server.controller.Controller.autoidlepc", return_value={"idlepc": "0x606de20c"}) as mock:
        response = await client.post(app.url_path_for("get_compute", compute_id="my_compute_id") + "/auto_idlepc", json=params)
    assert mock.called
    assert response.status_code == status.HTTP_200_OK


# FIXME
# @pytest.mark.asyncio
# async def test_compute_endpoint(controller_api):
#
#     params = {
#         "compute_id": "my_compute",
#         "protocol": "http",
#         "host": "localhost",
#         "port": 84,
#         "user": "julien",
#         "password": "secure"
#     }
#
#     response = await controller_api.post("/computes", params)
#     assert response.status_code == 201
#
#     response = await controller_api.get("/computes/endpoint/my_compute/qemu/images")
#     assert response.status_code == 200
#     assert response.json['endpoint'] == 'http://localhost:84/v2/compute/qemu/images'
