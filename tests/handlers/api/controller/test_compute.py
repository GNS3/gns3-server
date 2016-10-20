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

import unittest
from tests.utils import asyncio_patch


def test_compute_create_without_id(http_controller, controller):

    params = {
        "protocol": "http",
        "host": "localhost",
        "port": 84,
        "user": "julien",
        "password": "secure"
    }
    response = http_controller.post("/computes", params, example=True)
    assert response.status == 201
    assert response.route == "/computes"
    assert response.json["user"] == "julien"
    assert response.json["compute_id"] is not None
    assert "password" not in response.json

    assert len(controller.computes) == 1
    assert controller.computes[response.json["compute_id"]].host == "localhost"


def test_compute_create_with_id(http_controller, controller):

    params = {
        "compute_id": "my_compute_id",
        "protocol": "http",
        "host": "localhost",
        "port": 84,
        "user": "julien",
        "password": "secure"
    }
    response = http_controller.post("/computes", params, example=True)
    assert response.status == 201
    assert response.route == "/computes"
    assert response.json["user"] == "julien"
    assert "password" not in response.json

    assert len(controller.computes) == 1
    assert controller.computes["my_compute_id"].host == "localhost"


def test_compute_get(http_controller, controller):

    params = {
        "compute_id": "my_compute_id",
        "protocol": "http",
        "host": "localhost",
        "port": 84,
        "user": "julien",
        "password": "secure"
    }
    response = http_controller.post("/computes", params)
    assert response.status == 201

    response = http_controller.get("/computes/my_compute_id", example=True)
    assert response.status == 200
    assert response.json["protocol"] == "http"


def test_compute_update(http_controller, controller):

    params = {
        "compute_id": "my_compute_id",
        "protocol": "http",
        "host": "localhost",
        "port": 84,
        "user": "julien",
        "password": "secure"
    }
    response = http_controller.post("/computes", params)
    assert response.status == 201

    response = http_controller.get("/computes/my_compute_id")
    assert response.status == 200
    assert response.json["protocol"] == "http"

    params["protocol"] = "https"
    response = http_controller.put("/computes/my_compute_id", params, example=True)

    assert response.status == 200
    assert response.json["protocol"] == "https"


def test_compute_list(http_controller, controller):

    params = {
        "compute_id": "my_compute_id",
        "protocol": "http",
        "host": "localhost",
        "port": 84,
        "user": "julien",
        "password": "secure",
        "name": "My super server"
    }
    response = http_controller.post("/computes", params)
    assert response.status == 201
    assert response.route == "/computes"
    assert response.json["user"] == "julien"
    assert "password" not in response.json

    response = http_controller.get("/computes", example=True)
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
                'capabilities': {
                    'version': None,
                    'node_types': []
                }
            }


def test_compute_delete(http_controller, controller):

    params = {
        "compute_id": "my_compute_id",
        "protocol": "http",
        "host": "localhost",
        "port": 84,
        "user": "julien",
        "password": "secure"
    }
    response = http_controller.post("/computes", params)
    assert response.status == 201

    response = http_controller.get("/computes")
    assert len(response.json) == 1

    response = http_controller.delete("/computes/my_compute_id", example=True)
    assert response.status == 204

    response = http_controller.get("/computes")
    assert len(response.json) == 0


def test_compute_list_images(http_controller, controller):

    params = {
        "compute_id": "my_compute",
        "protocol": "http",
        "host": "localhost",
        "port": 84,
        "user": "julien",
        "password": "secure"
    }
    response = http_controller.post("/computes", params)
    assert response.status == 201

    with asyncio_patch("gns3server.controller.compute.Compute.images", return_value=[{"filename": "linux.qcow2"}, {"filename": "asav.qcow2"}]) as mock:
        response = http_controller.get("/computes/my_compute/qemu/images", example=True)
        assert response.json == [{"filename": "linux.qcow2"}, {"filename": "asav.qcow2"}]
        mock.assert_called_with("qemu")


def test_compute_list_vms(http_controller, controller):

    params = {
        "compute_id": "my_compute",
        "protocol": "http",
        "host": "localhost",
        "port": 84,
        "user": "julien",
        "password": "secure"
    }
    response = http_controller.post("/computes", params)
    assert response.status == 201

    with asyncio_patch("gns3server.controller.compute.Compute.forward", return_value=[]) as mock:
        response = http_controller.get("/computes/my_compute/virtualbox/vms", example=True)
        assert response.json == []
        mock.assert_called_with("GET", "virtualbox", "vms")


def test_compute_create_img(http_controller, controller):

    params = {
        "compute_id": "my_compute",
        "protocol": "http",
        "host": "localhost",
        "port": 84,
        "user": "julien",
        "password": "secure"
    }
    response = http_controller.post("/computes", params)
    assert response.status == 201

    params = {"path": "/test"}
    with asyncio_patch("gns3server.controller.compute.Compute.forward", return_value=[]) as mock:
        response = http_controller.post("/computes/my_compute/qemu/img", params, example=True)
        mock.assert_called_with("POST", "qemu", "img", data=unittest.mock.ANY)
