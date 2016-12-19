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
import os
import stat
import sys
import uuid
import aiohttp

from tests.utils import asyncio_patch
from unittest.mock import patch, MagicMock, PropertyMock
from gns3server.compute.docker import Docker

pytestmark = pytest.mark.skipif(sys.platform.startswith("win"), reason="Not supported on Windows")


@pytest.fixture
def base_params():
    """Return standard parameters"""
    return {"name": "PC TEST 1", "image": "nginx", "start_command": "nginx-daemon", "adapters": 2, "environment": "YES=1\nNO=0", "console_type": "telnet", "console_resolution": "1280x1024"}


@pytest.yield_fixture(autouse=True)
def mock_connection():
    docker = Docker.instance()
    docker._connected = True
    docker._connector = MagicMock()
    yield
    Docker._instance = None


@pytest.fixture
def vm(http_compute, project, base_params):
    with asyncio_patch("gns3server.compute.docker.Docker.list_images", return_value=[{"image": "nginx"}]) as mock_list:
        with asyncio_patch("gns3server.compute.docker.Docker.query", return_value={"Id": "8bd8153ea8f5"}) as mock:
            with asyncio_patch("gns3server.compute.docker.DockerVM._get_container_state", return_value="exited") as mock:
                response = http_compute.post("/projects/{project_id}/docker/nodes".format(project_id=project.id), base_params)
    if response.status != 201:
        print(response.body)
    assert response.status == 201
    return response.json


def test_docker_create(http_compute, project, base_params):
    with asyncio_patch("gns3server.compute.docker.Docker.list_images", return_value=[{"image": "nginx"}]) as mock_list:
        with asyncio_patch("gns3server.compute.docker.Docker.query", return_value={"Id": "8bd8153ea8f5"}) as mock:
            response = http_compute.post("/projects/{project_id}/docker/nodes".format(project_id=project.id), base_params)
    assert response.status == 201
    assert response.route == "/projects/{project_id}/docker/nodes"
    assert response.json["name"] == "PC TEST 1"
    assert response.json["project_id"] == project.id
    assert response.json["container_id"] == "8bd8153ea8f5"
    assert response.json["image"] == "nginx:latest"
    assert response.json["adapters"] == 2
    assert response.json["environment"] == "YES=1\nNO=0"
    assert response.json["console_resolution"] == "1280x1024"


def test_docker_start(http_compute, vm):
    with asyncio_patch("gns3server.compute.docker.docker_vm.DockerVM.start", return_value=True) as mock:
        response = http_compute.post("/projects/{project_id}/docker/nodes/{node_id}/start".format(project_id=vm["project_id"], node_id=vm["node_id"]))
        assert mock.called
        assert response.status == 204


def test_docker_stop(http_compute, vm):
    with asyncio_patch("gns3server.compute.docker.docker_vm.DockerVM.stop", return_value=True) as mock:
        response = http_compute.post("/projects/{project_id}/docker/nodes/{node_id}/stop".format(project_id=vm["project_id"], node_id=vm["node_id"]))
        assert mock.called
        assert response.status == 204


def test_docker_reload(http_compute, vm):
    with asyncio_patch("gns3server.compute.docker.docker_vm.DockerVM.restart", return_value=True) as mock:
        response = http_compute.post("/projects/{project_id}/docker/nodes/{node_id}/reload".format(project_id=vm["project_id"], node_id=vm["node_id"]))
        assert mock.called
        assert response.status == 204


def test_docker_delete(http_compute, vm):
    with asyncio_patch("gns3server.compute.docker.docker_vm.DockerVM.delete", return_value=True) as mock:
        response = http_compute.delete("/projects/{project_id}/docker/nodes/{node_id}".format(project_id=vm["project_id"], node_id=vm["node_id"]))
        assert mock.called
        assert response.status == 204


def test_docker_pause(http_compute, vm):
    with asyncio_patch("gns3server.compute.docker.docker_vm.DockerVM.pause", return_value=True) as mock:
        response = http_compute.post("/projects/{project_id}/docker/nodes/{node_id}/pause".format(project_id=vm["project_id"], node_id=vm["node_id"]))
        assert mock.called
        assert response.status == 204


def test_docker_unpause(http_compute, vm):
    with asyncio_patch("gns3server.compute.docker.docker_vm.DockerVM.unpause", return_value=True) as mock:
        response = http_compute.post("/projects/{project_id}/docker/nodes/{node_id}/unpause".format(project_id=vm["project_id"], node_id=vm["node_id"]))
        assert mock.called
        assert response.status == 204


def test_docker_nio_create_udp(http_compute, vm):
    response = http_compute.post("/projects/{project_id}/docker/nodes/{node_id}/adapters/0/ports/0/nio".format(project_id=vm["project_id"], node_id=vm["node_id"]), {"type": "nio_udp",
                                                                                                                                                                     "lport": 4242,
                                                                                                                                                                     "rport": 4343,
                                                                                                                                                                     "rhost": "127.0.0.1"},
                                 example=True)
    assert response.status == 201
    assert response.route == "/projects/{project_id}/docker/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio"
    assert response.json["type"] == "nio_udp"


def test_docker_delete_nio(http_compute, vm):
    with asyncio_patch("gns3server.compute.docker.docker_vm.DockerVM.adapter_remove_nio_binding") as mock:
        response = http_compute.delete("/projects/{project_id}/docker/nodes/{node_id}/adapters/0/ports/0/nio".format(project_id=vm["project_id"], node_id=vm["node_id"]), example=True)
    assert response.status == 204
    assert response.route == "/projects/{project_id}/docker/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio"


def test_docker_update(http_compute, vm, tmpdir, free_console_port):
    with asyncio_patch("gns3server.compute.docker.docker_vm.DockerVM.update") as mock:
        response = http_compute.put("/projects/{project_id}/docker/nodes/{node_id}".format(project_id=vm["project_id"], node_id=vm["node_id"]), {"name": "test",
                                                                                                                                                 "console": free_console_port,
                                                                                                                                                 "start_command": "yes",
                                                                                                                                                 "environment": "GNS3=1\nGNS4=0"},
                                    example=True)
    assert mock.called
    assert response.status == 200
    assert response.json["name"] == "test"
    assert response.json["console"] == free_console_port
    assert response.json["start_command"] == "yes"
    assert response.json["environment"] == "GNS3=1\nGNS4=0"


def test_docker_start_capture(http_compute, vm, tmpdir, project):

    with patch("gns3server.compute.docker.docker_vm.DockerVM.is_running", return_value=True) as mock:
        with asyncio_patch("gns3server.compute.docker.docker_vm.DockerVM.start_capture") as start_capture:

            params = {"capture_file_name": "test.pcap", "data_link_type": "DLT_EN10MB"}
            response = http_compute.post("/projects/{project_id}/docker/nodes/{node_id}/adapters/0/ports/0/start_capture".format(project_id=vm["project_id"], node_id=vm["node_id"]), body=params, example=True)

            assert response.status == 200

            assert start_capture.called
            assert "test.pcap" in response.json["pcap_file_path"]


def test_docker_stop_capture(http_compute, vm, tmpdir, project):

    with patch("gns3server.compute.docker.docker_vm.DockerVM.is_running", return_value=True) as mock:
        with asyncio_patch("gns3server.compute.docker.docker_vm.DockerVM.stop_capture") as stop_capture:

            response = http_compute.post("/projects/{project_id}/docker/nodes/{node_id}/adapters/0/ports/0/stop_capture".format(project_id=vm["project_id"], node_id=vm["node_id"]), example=True)

            assert response.status == 204

            assert stop_capture.called
