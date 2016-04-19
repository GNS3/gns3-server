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


def test_compute_create(http_controller, controller):

    params = {
        "compute_id": "my_compute_id",
        "protocol": "http",
        "host": "example.com",
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
    assert controller.computes["my_compute_id"].host == "example.com"


def test_compute_list(http_controller, controller):

    params = {
        "compute_id": "my_compute_id",
        "protocol": "http",
        "host": "example.com",
        "port": 84,
        "user": "julien",
        "password": "secure"
    }
    response = http_controller.post("/computes", params)
    assert response.status == 201
    assert response.route == "/computes"
    assert response.json["user"] == "julien"
    assert "password" not in response.json

    response = http_controller.get("/computes", example=True)
    assert response.json == [
        {
            'compute_id': 'my_compute_id',
            'connected': False,
            'host': 'example.com',
            'port': 84,
            'protocol': 'http',
            'user': 'julien'
        }
    ]

