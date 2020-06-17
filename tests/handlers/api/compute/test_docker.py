# -*- coding: utf-8 -*-
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
import sys
import uuid

from tests.utils import asyncio_patch
from unittest.mock import patch

pytestmark = pytest.mark.skipif(sys.platform.startswith("win"), reason="Not supported on Windows")


@pytest.fixture
def base_params():
    """Return standard parameters"""

    params = {
        "name": "PC TEST 1",
        "image": "nginx",
        "start_command": "nginx-daemon",
        "adapters": 2,
        "environment": "YES=1\nNO=0",
        "console_type": "telnet",
        "console_resolution": "1280x1024",
        "extra_hosts": "test:127.0.0.1"
    }
    return params


# @pytest.yield_fixture(autouse=True)
# def mock_connection():
#
#     docker = Docker.instance()
#     docker._connected = True
#     docker._connector = MagicMock()
#     yield
#     Docker._instance = None


@pytest.fixture
async def vm(compute_api, compute_project, base_params):

    with asyncio_patch("gns3server.compute.docker.Docker.list_images", return_value=[{"image": "nginx"}]):
        with asyncio_patch("gns3server.compute.docker.Docker.query", return_value={"Id": "8bd8153ea8f5"}):
            with asyncio_patch("gns3server.compute.docker.DockerVM._get_container_state", return_value="exited"):
                response = await compute_api.post("/projects/{project_id}/docker/nodes".format(project_id=compute_project.id), base_params)
    assert response.status == 201
    return response.json


async def test_docker_create(compute_api, compute_project, base_params):

    with asyncio_patch("gns3server.compute.docker.Docker.list_images", return_value=[{"image": "nginx"}]):
        with asyncio_patch("gns3server.compute.docker.Docker.query", return_value={"Id": "8bd8153ea8f5"}):
            response = await compute_api.post("/projects/{project_id}/docker/nodes".format(project_id=compute_project.id), base_params)
    assert response.status == 201
    assert response.route == "/projects/{project_id}/docker/nodes"
    assert response.json["name"] == "PC TEST 1"
    assert response.json["project_id"] == compute_project.id
    assert response.json["container_id"] == "8bd8153ea8f5"
    assert response.json["image"] == "nginx:latest"
    assert response.json["adapters"] == 2
    assert response.json["environment"] == "YES=1\nNO=0"
    assert response.json["console_resolution"] == "1280x1024"
    assert response.json["extra_hosts"] == "test:127.0.0.1"


async def test_docker_start(compute_api, vm):

    with asyncio_patch("gns3server.compute.docker.docker_vm.DockerVM.start", return_value=True) as mock:
        response = await compute_api.post("/projects/{project_id}/docker/nodes/{node_id}/start".format(project_id=vm["project_id"], node_id=vm["node_id"]))
        assert mock.called
        assert response.status == 204


async def test_docker_stop(compute_api, vm):

    with asyncio_patch("gns3server.compute.docker.docker_vm.DockerVM.stop", return_value=True) as mock:
        response = await compute_api.post("/projects/{project_id}/docker/nodes/{node_id}/stop".format(project_id=vm["project_id"], node_id=vm["node_id"]))
        assert mock.called
        assert response.status == 204


async def test_docker_reload(compute_api, vm):

    with asyncio_patch("gns3server.compute.docker.docker_vm.DockerVM.restart", return_value=True) as mock:
        response = await compute_api.post("/projects/{project_id}/docker/nodes/{node_id}/reload".format(project_id=vm["project_id"], node_id=vm["node_id"]))
        assert mock.called
        assert response.status == 204


async def test_docker_delete(compute_api, vm):

    with asyncio_patch("gns3server.compute.docker.docker_vm.DockerVM.delete", return_value=True) as mock:
        response = await compute_api.delete("/projects/{project_id}/docker/nodes/{node_id}".format(project_id=vm["project_id"], node_id=vm["node_id"]))
        assert mock.called
        assert response.status == 204


async def test_docker_pause(compute_api, vm):

    with asyncio_patch("gns3server.compute.docker.docker_vm.DockerVM.pause", return_value=True) as mock:
        response = await compute_api.post("/projects/{project_id}/docker/nodes/{node_id}/pause".format(project_id=vm["project_id"], node_id=vm["node_id"]))
        assert mock.called
        assert response.status == 204


async def test_docker_unpause(compute_api, vm):

    with asyncio_patch("gns3server.compute.docker.docker_vm.DockerVM.unpause", return_value=True) as mock:
        response = await compute_api.post("/projects/{project_id}/docker/nodes/{node_id}/unpause".format(project_id=vm["project_id"], node_id=vm["node_id"]))
        assert mock.called
        assert response.status == 204


async def test_docker_nio_create_udp(compute_api, vm):

    params = {
        "type": "nio_udp",
        "lport": 4242,
        "rport": 4343,
        "rhost": "127.0.0.1"}

    response = await compute_api.post("/projects/{project_id}/docker/nodes/{node_id}/adapters/0/ports/0/nio".format(project_id=vm["project_id"], node_id=vm["node_id"]), params)
    assert response.status == 201
    assert response.route == r"/projects/{project_id}/docker/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio"
    assert response.json["type"] == "nio_udp"


async def test_docker_update_nio(compute_api, vm):

    params = {
        "type": "nio_udp",
        "lport": 4242,
        "rport": 4343,
        "rhost": "127.0.0.1"
    }

    response = await compute_api.post("/projects/{project_id}/docker/nodes/{node_id}/adapters/0/ports/0/nio".format(project_id=vm["project_id"], node_id=vm["node_id"]), params)
    assert response.status == 201
    with asyncio_patch("gns3server.compute.docker.docker_vm.DockerVM.adapter_update_nio_binding"):
        response = await compute_api.put("/projects/{project_id}/docker/nodes/{node_id}/adapters/0/ports/0/nio".format(project_id=vm["project_id"], node_id=vm["node_id"]), params)
    assert response.status == 201, response.body.decode()
    assert response.route == r"/projects/{project_id}/docker/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio"


async def test_docker_delete_nio(compute_api, vm):

    with asyncio_patch("gns3server.compute.docker.docker_vm.DockerVM.adapter_remove_nio_binding"):
        response = await compute_api.delete("/projects/{project_id}/docker/nodes/{node_id}/adapters/0/ports/0/nio".format(project_id=vm["project_id"], node_id=vm["node_id"]))
    assert response.status == 204
    assert response.route == r"/projects/{project_id}/docker/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio"


async def test_docker_update(compute_api, vm, free_console_port):

    params = {
        "name": "test",
        "console": free_console_port,
        "start_command": "yes",
        "environment": "GNS3=1\nGNS4=0",
        "extra_hosts": "test:127.0.0.1"
    }

    with asyncio_patch("gns3server.compute.docker.docker_vm.DockerVM.update") as mock:
        response = await compute_api.put("/projects/{project_id}/docker/nodes/{node_id}".format(project_id=vm["project_id"], node_id=vm["node_id"]), params)
    assert mock.called
    assert response.status == 200
    assert response.json["name"] == "test"
    assert response.json["console"] == free_console_port
    assert response.json["start_command"] == "yes"
    assert response.json["environment"] == "GNS3=1\nGNS4=0"
    assert response.json["extra_hosts"] == "test:127.0.0.1"


async def test_docker_start_capture(compute_api, vm):

    with patch("gns3server.compute.docker.docker_vm.DockerVM.is_running", return_value=True):
        with asyncio_patch("gns3server.compute.docker.docker_vm.DockerVM.start_capture") as mock:
            params = {"capture_file_name": "test.pcap", "data_link_type": "DLT_EN10MB"}
            response = await compute_api.post("/projects/{project_id}/docker/nodes/{node_id}/adapters/0/ports/0/start_capture".format(project_id=vm["project_id"], node_id=vm["node_id"]), body=params)
            assert response.status == 200
            assert mock.called
            assert "test.pcap" in response.json["pcap_file_path"]


async def test_docker_stop_capture(compute_api, vm):

    with patch("gns3server.compute.docker.docker_vm.DockerVM.is_running", return_value=True):
        with asyncio_patch("gns3server.compute.docker.docker_vm.DockerVM.stop_capture") as mock:
            response = await compute_api.post("/projects/{project_id}/docker/nodes/{node_id}/adapters/0/ports/0/stop_capture".format(project_id=vm["project_id"], node_id=vm["node_id"]))
            assert response.status == 204
            assert mock.called


async def test_docker_duplicate(compute_api, vm):

    params = {"destination_node_id": str(uuid.uuid4())}
    with asyncio_patch("gns3server.compute.docker.Docker.duplicate_node", return_value=True) as mock:
        response = await compute_api.post("/projects/{project_id}/docker/nodes/{node_id}/duplicate".format(project_id=vm["project_id"], node_id=vm["node_id"]), params)
        assert mock.called
        assert response.status == 201
