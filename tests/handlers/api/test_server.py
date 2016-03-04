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


def test_server_create(server, controller):

    params = {
        "server_id": "my_server_id",
        "protocol": "http",
        "host": "example.com",
        "port": 84,
        "user": "julien",
        "password": "secure"
    }
    response = server.post("/servers", params, example=True)
    assert response.status == 201
    assert response.route == "/servers"
    assert response.json["user"] == "julien"
    assert "password" not in response.json

    assert len(controller.servers) == 1
    assert controller.servers["my_server_id"].host == "example.com"
