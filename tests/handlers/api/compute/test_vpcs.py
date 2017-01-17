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
    response = http_compute.post("/projects/{project_id}/vpcs/nodes".format(project_id=project.id), {"name": "PC TEST 1"})
    assert response.status == 201
    return response.json


def test_vpcs_create(http_compute, project):
    response = http_compute.post("/projects/{project_id}/vpcs/nodes".format(project_id=project.id), {"name": "PC TEST 1"}, example=True)
    assert response.status == 201
    assert response.route == "/projects/{project_id}/vpcs/nodes"
    assert response.json["name"] == "PC TEST 1"
    assert response.json["project_id"] == project.id


def test_vpcs_get(http_compute, project, vm):
    response = http_compute.get("/projects/{project_id}/vpcs/nodes/{node_id}".format(project_id=vm["project_id"], node_id=vm["node_id"]), example=True)
    assert response.status == 200
    assert response.route == "/projects/{project_id}/vpcs/nodes/{node_id}"
    assert response.json["name"] == "PC TEST 1"
    assert response.json["project_id"] == project.id
    assert response.json["startup_script_path"] is None
    assert response.json["status"] == "stopped"


def test_vpcs_create_startup_script(http_compute, project):
    response = http_compute.post("/projects/{project_id}/vpcs/nodes".format(project_id=project.id), {"name": "PC TEST 1", "startup_script": "ip 192.168.1.2\necho TEST"})
    assert response.status == 201
    assert response.route == "/projects/{project_id}/vpcs/nodes"
    assert response.json["name"] == "PC TEST 1"
    assert response.json["project_id"] == project.id
    assert response.json["startup_script"] == os.linesep.join(["ip 192.168.1.2", "echo TEST"])
    assert response.json["startup_script_path"] == "startup.vpc"


def test_vpcs_create_port(http_compute, project, free_console_port):
    response = http_compute.post("/projects/{project_id}/vpcs/nodes".format(project_id=project.id), {"name": "PC TEST 1", "console": free_console_port})
    assert response.status == 201
    assert response.route == "/projects/{project_id}/vpcs/nodes"
    assert response.json["name"] == "PC TEST 1"
    assert response.json["project_id"] == project.id
    assert response.json["console"] == free_console_port


def test_vpcs_nio_create_udp(http_compute, vm):
    response = http_compute.post("/projects/{project_id}/vpcs/nodes/{node_id}/adapters/0/ports/0/nio".format(project_id=vm["project_id"], node_id=vm["node_id"]), {"type": "nio_udp",
                                                                                                                                                                   "lport": 4242,
                                                                                                                                                                   "rport": 4343,
                                                                                                                                                                   "rhost": "127.0.0.1"},
                                 example=True)
    assert response.status == 201
    assert response.route == "/projects/{project_id}/vpcs/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio"
    assert response.json["type"] == "nio_udp"


@pytest.mark.skipif(sys.platform.startswith("win"), reason="Not supported on Windows")
def test_vpcs_nio_create_tap(http_compute, vm, ethernet_device):
    with patch("gns3server.compute.base_manager.BaseManager.has_privileged_access", return_value=True):
        response = http_compute.post("/projects/{project_id}/vpcs/nodes/{node_id}/adapters/0/ports/0/nio".format(project_id=vm["project_id"], node_id=vm["node_id"]), {"type": "nio_tap",
                                                                                                                                                                       "tap_device": ethernet_device})
        assert response.status == 201
        assert response.route == "/projects/{project_id}/vpcs/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio"
        assert response.json["type"] == "nio_tap"


def test_vpcs_delete_nio(http_compute, vm):
    http_compute.post("/projects/{project_id}/vpcs/nodes/{node_id}/adapters/0/ports/0/nio".format(project_id=vm["project_id"], node_id=vm["node_id"]), {"type": "nio_udp",
                                                                                                                                                        "lport": 4242,
                                                                                                                                                        "rport": 4343,
                                                                                                                                                        "rhost": "127.0.0.1"})
    response = http_compute.delete("/projects/{project_id}/vpcs/nodes/{node_id}/adapters/0/ports/0/nio".format(project_id=vm["project_id"], node_id=vm["node_id"]), example=True)
    assert response.status == 204
    assert response.route == "/projects/{project_id}/vpcs/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio"


def test_vpcs_start(http_compute, vm):

    with asyncio_patch("gns3server.compute.vpcs.vpcs_vm.VPCSVM.start", return_value=True) as mock:
        response = http_compute.post("/projects/{project_id}/vpcs/nodes/{node_id}/start".format(project_id=vm["project_id"], node_id=vm["node_id"]), example=True)
        assert mock.called
        assert response.status == 200
        assert response.json["name"] == "PC TEST 1"


def test_vpcs_stop(http_compute, vm):
    with asyncio_patch("gns3server.compute.vpcs.vpcs_vm.VPCSVM.stop", return_value=True) as mock:
        response = http_compute.post("/projects/{project_id}/vpcs/nodes/{node_id}/stop".format(project_id=vm["project_id"], node_id=vm["node_id"]), example=True)
        assert mock.called
        assert response.status == 204


def test_vpcs_reload(http_compute, vm):
    with asyncio_patch("gns3server.compute.vpcs.vpcs_vm.VPCSVM.reload", return_value=True) as mock:
        response = http_compute.post("/projects/{project_id}/vpcs/nodes/{node_id}/reload".format(project_id=vm["project_id"], node_id=vm["node_id"]), example=True)
        assert mock.called
        assert response.status == 204


def test_vpcs_delete(http_compute, vm):
    with asyncio_patch("gns3server.compute.vpcs.VPCS.delete_node", return_value=True) as mock:
        response = http_compute.delete("/projects/{project_id}/vpcs/nodes/{node_id}".format(project_id=vm["project_id"], node_id=vm["node_id"]), example=True)
        assert mock.called
        assert response.status == 204


def test_vpcs_update(http_compute, vm, tmpdir, free_console_port):
    response = http_compute.put("/projects/{project_id}/vpcs/nodes/{node_id}".format(project_id=vm["project_id"], node_id=vm["node_id"]), {"name": "test",
                                                                                                                                           "console": free_console_port,
                                                                                                                                           },
                                example=True)
    assert response.status == 200
    assert response.json["name"] == "test"
    assert response.json["console"] == free_console_port
