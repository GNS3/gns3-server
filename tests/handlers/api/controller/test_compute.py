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

import unittest
from tests.utils import asyncio_patch


async def test_compute_create_without_id(controller_api, controller):

    params = {
        "protocol": "http",
        "host": "localhost",
        "port": 84,
        "user": "julien",
        "password": "secure"}

    response = await controller_api.post("/computes", params)
    assert response.status == 201
    assert response.route == "/computes"
    assert response.json["user"] == "julien"
    assert response.json["compute_id"] is not None
    assert "password" not in response.json
    assert len(controller.computes) == 1
    assert controller.computes[response.json["compute_id"]].host == "localhost"


async def test_compute_create_with_id(controller_api, controller):

    params = {
        "compute_id": "my_compute_id",
        "protocol": "http",
        "host": "localhost",
        "port": 84,
        "user": "julien",
        "password": "secure"}

    response = await controller_api.post("/computes", params)
    assert response.status == 201
    assert response.route == "/computes"
    assert response.json["user"] == "julien"
    assert "password" not in response.json

    assert len(controller.computes) == 1
    assert controller.computes["my_compute_id"].host == "localhost"


async def test_compute_get(controller_api):

    params = {
        "compute_id": "my_compute_id",
        "protocol": "http",
        "host": "localhost",
        "port": 84,
        "user": "julien",
        "password": "secure"
    }

    response = await controller_api.post("/computes", params)
    assert response.status == 201

    response = await controller_api.get("/computes/my_compute_id")
    assert response.status == 200
    assert response.json["protocol"] == "http"


async def test_compute_update(controller_api):

    params = {
        "compute_id": "my_compute_id",
        "protocol": "http",
        "host": "localhost",
        "port": 84,
        "user": "julien",
        "password": "secure"
    }

    response = await controller_api.post("/computes", params)
    assert response.status == 201

    response = await controller_api.get("/computes/my_compute_id")
    assert response.status == 200
    assert response.json["protocol"] == "http"

    params["protocol"] = "https"
    response = await controller_api.put("/computes/my_compute_id", params)

    assert response.status == 200
    assert response.json["protocol"] == "https"


async def test_compute_list(controller_api):

    params = {
        "compute_id": "my_compute_id",
        "protocol": "http",
        "host": "localhost",
        "port": 84,
        "user": "julien",
        "password": "secure",
        "name": "My super server"
    }

    response = await controller_api.post("/computes", params)
    assert response.status == 201
    assert response.route == "/computes"
    assert response.json["user"] == "julien"
    assert "password" not in response.json

    response = await controller_api.get("/computes")
    for compute in response.json:
        if compute['compute_id'] != 'local':
            assert compute == {
                'compute_id': 'my_compute_id',
                'connected': False,
                'host': 'localhost',
                'port': 84,
                'protocol': 'http',
                'user': 'julien',
                'name': 'My super server',
                'cpu_usage_percent': None,
                'memory_usage_percent': None,
                'last_error': None,
                'capabilities': {
                    'version': None,
                    'node_types': []
                }
            }


async def test_compute_delete(controller_api):

    params = {
        "compute_id": "my_compute_id",
        "protocol": "http",
        "host": "localhost",
        "port": 84,
        "user": "julien",
        "password": "secure"
    }
    response = await controller_api.post("/computes", params)
    assert response.status == 201

    response = await controller_api.get("/computes")
    assert len(response.json) == 1

    response = await controller_api.delete("/computes/my_compute_id")
    assert response.status == 204

    response = await controller_api.get("/computes")
    assert len(response.json) == 0


async def test_compute_list_images(controller_api):

    params = {
        "compute_id": "my_compute",
        "protocol": "http",
        "host": "localhost",
        "port": 84,
        "user": "julien",
        "password": "secure"
    }
    response = await controller_api.post("/computes", params)
    assert response.status == 201

    with asyncio_patch("gns3server.controller.compute.Compute.images", return_value=[{"filename": "linux.qcow2"}, {"filename": "asav.qcow2"}]) as mock:
        response = await controller_api.get("/computes/my_compute/qemu/images")
        assert response.json == [{"filename": "linux.qcow2"}, {"filename": "asav.qcow2"}]
        mock.assert_called_with("qemu")


async def test_compute_list_vms(controller_api):

    params = {
        "compute_id": "my_compute",
        "protocol": "http",
        "host": "localhost",
        "port": 84,
        "user": "julien",
        "password": "secure"
    }
    response = await controller_api.post("/computes", params)
    assert response.status == 201

    with asyncio_patch("gns3server.controller.compute.Compute.forward", return_value=[]) as mock:
        response = await controller_api.get("/computes/my_compute/virtualbox/vms")
        assert response.json == []
        mock.assert_called_with("GET", "virtualbox", "vms")


async def test_compute_create_img(controller_api):

    params = {
        "compute_id": "my_compute",
        "protocol": "http",
        "host": "localhost",
        "port": 84,
        "user": "julien",
        "password": "secure"
    }

    response = await controller_api.post("/computes", params)
    assert response.status == 201

    params = {"path": "/test"}
    with asyncio_patch("gns3server.controller.compute.Compute.forward", return_value=[]) as mock:
        response = await controller_api.post("/computes/my_compute/qemu/img", params)
        assert response.json == []
        mock.assert_called_with("POST", "qemu", "img", data=unittest.mock.ANY)


async def test_compute_autoidlepc(controller_api):

    params = {
        "compute_id": "my_compute_id",
        "protocol": "http",
        "host": "localhost",
        "port": 84,
        "user": "julien",
        "password": "secure"
    }

    await controller_api.post("/computes", params)

    params = {
        "platform": "c7200",
        "image": "test.bin",
        "ram": 512
    }

    with asyncio_patch("gns3server.controller.Controller.autoidlepc", return_value={"idlepc": "0x606de20c"}) as mock:
        response = await controller_api.post("/computes/my_compute_id/auto_idlepc", params)
    assert mock.called
    assert response.status == 200


async def test_compute_endpoint(controller_api):

    params = {
        "compute_id": "my_compute",
        "protocol": "http",
        "host": "localhost",
        "port": 84,
        "user": "julien",
        "password": "secure"
    }

    response = await controller_api.post("/computes", params)
    assert response.status == 201

    response = await controller_api.get("/computes/endpoint/my_compute/virtualbox/images")
    assert response.status == 200
    assert response.json['endpoint'] == 'http://localhost:84/v2/compute/virtualbox/images'
