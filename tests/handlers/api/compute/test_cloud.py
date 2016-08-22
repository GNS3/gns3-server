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
import sys
import os
from tests.utils import asyncio_patch
from unittest.mock import patch


@pytest.fixture(scope="function")
def vm(http_compute, project):
    response = http_compute.post("/projects/{project_id}/cloud/nodes".format(project_id=project.id), {"name": "Cloud 1"})
    assert response.status == 201
    return response.json


@pytest.yield_fixture(autouse=True)
def mock_ubridge():
    """
    Avoid all interaction with ubridge
    """
    with asyncio_patch("gns3server.compute.builtin.nodes.cloud.Cloud._start_ubridge"):
        with asyncio_patch("gns3server.compute.builtin.nodes.cloud.Cloud._add_ubridge_connection"):
            with asyncio_patch("gns3server.compute.builtin.nodes.cloud.Cloud._delete_ubridge_connection"):
                yield


def test_cloud_create(http_compute, project):
    response = http_compute.post("/projects/{project_id}/cloud/nodes".format(project_id=project.id), {"name": "Cloud 1"}, example=True)
    assert response.status == 201
    assert response.route == "/projects/{project_id}/cloud/nodes"
    assert response.json["name"] == "Cloud 1"
    assert response.json["project_id"] == project.id


def test_cloud_get(http_compute, project, vm):
    response = http_compute.get("/projects/{project_id}/cloud/nodes/{node_id}".format(project_id=vm["project_id"], node_id=vm["node_id"]), example=True)
    assert response.status == 200
    assert response.route == "/projects/{project_id}/cloud/nodes/{node_id}"
    assert response.json["name"] == "Cloud 1"
    assert response.json["project_id"] == project.id
    assert response.json["status"] == "started"


def test_cloud_nio_create_udp(http_compute, vm):
    response = http_compute.post("/projects/{project_id}/cloud/nodes/{node_id}/adapters/0/ports/0/nio".format(project_id=vm["project_id"], node_id=vm["node_id"]), {"type": "nio_udp",
                                                                                                                                                                    "lport": 4242,
                                                                                                                                                                    "rport": 4343,
                                                                                                                                                                    "rhost": "127.0.0.1"},
                                 example=True)
    assert response.status == 201
    assert response.route == "/projects/{project_id}/cloud/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio"
    assert response.json["type"] == "nio_udp"


def test_cloud_delete_nio(http_compute, vm):
    http_compute.post("/projects/{project_id}/cloud/nodes/{node_id}/adapters/0/ports/0/nio".format(project_id=vm["project_id"], node_id=vm["node_id"]), {"type": "nio_udp",
                                                                                                                                                         "lport": 4242,
                                                                                                                                                         "rport": 4343,
                                                                                                                                                         "rhost": "127.0.0.1"})
    response = http_compute.delete("/projects/{project_id}/cloud/nodes/{node_id}/adapters/0/ports/0/nio".format(project_id=vm["project_id"], node_id=vm["node_id"]), example=True)
    assert response.status == 204
    assert response.route == "/projects/{project_id}/cloud/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio"


def test_cloud_delete(http_compute, vm):
    response = http_compute.delete("/projects/{project_id}/cloud/nodes/{node_id}".format(project_id=vm["project_id"], node_id=vm["node_id"]), example=True)
    assert response.status == 204


def test_cloud_update(http_compute, vm, tmpdir):
    response = http_compute.put("/projects/{project_id}/cloud/nodes/{node_id}".format(project_id=vm["project_id"], node_id=vm["node_id"]), {
        "name": "test"
    },
        example=True)
    assert response.status == 200
    assert response.json["name"] == "test"
