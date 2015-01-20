# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 GNS3 Technologies Inc.
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
from tests.api.base import server, loop, project
from tests.utils import asyncio_patch
from unittest.mock import patch


@pytest.fixture(scope="module")
def vm(server, project):
    response = server.post("/vpcs", {"name": "PC TEST 1", "project_uuid": project.uuid})
    assert response.status == 200
    return response.json


@asyncio_patch("gns3server.modules.VPCS.create_vm", return_value="61d61bdd-aa7d-4912-817f-65a9eb54d3ab")
def test_vpcs_create(server, project):
    response = server.post("/vpcs", {"name": "PC TEST 1", "project_uuid": project.uuid}, example=True)
    assert response.status == 200
    assert response.route == "/vpcs"
    assert response.json["name"] == "PC TEST 1"
    assert response.json["uuid"] == "61d61bdd-aa7d-4912-817f-65a9eb54d3ab"
    assert response.json["project_uuid"] == "61d61bdd-aa7d-4912-817f-65a9eb54d3ab"


def test_vpcs_nio_create_udp(server, vm):
    response = server.post("/vpcs/{}/ports/0/nio".format(vm["uuid"]), {"type": "nio_udp",
                                                                       "lport": 4242,
                                                                       "rport": 4343,
                                                                       "rhost": "127.0.0.1"},
                           example=True)
    assert response.status == 200
    assert response.route == "/vpcs/{uuid}/ports/{port_id}/nio"
    assert response.json["type"] == "nio_udp"


@patch("gns3server.modules.vpcs.vpcs_device.has_privileged_access", return_value=True)
def test_vpcs_nio_create_tap(mock, server, vm):
    response = server.post("/vpcs/{}/ports/0/nio".format(vm["uuid"]), {"type": "nio_tap",
                                                                       "tap_device": "test"})
    assert response.status == 200
    assert response.route == "/vpcs/{uuid}/ports/{port_id}/nio"
    assert response.json["type"] == "nio_tap"


def test_vpcs_delete_nio(server, vm):
    response = server.post("/vpcs/{}/ports/0/nio".format(vm["uuid"]), {"type": "nio_udp",
                                                                       "lport": 4242,
                                                                       "rport": 4343,
                                                                       "rhost": "127.0.0.1"})
    response = server.delete("/vpcs/{}/ports/0/nio".format(vm["uuid"]), example=True)
    assert response.status == 200
    assert response.route == "/vpcs/{uuid}/ports/{port_id}/nio"
