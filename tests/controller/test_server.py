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

import pytest

from gns3server.controller.server import Server


@pytest.fixture
def server():
    return Server("my_server_id", protocol="https", host="example.com", port=84, user="test", password="secure")


def test_init(server):
    assert server.id == "my_server_id"


def test_json(server):
    assert server.__json__() == {
        "server_id": "my_server_id",
        "protocol": "https",
        "host": "example.com",
        "port": 84,
        "user": "test",
        "connected": False,
        "version": None
    }


def test__eq__(server):
    assert server != 1
    assert server == server
    assert server == Server("my_server_id")
    assert server != Server("test")
