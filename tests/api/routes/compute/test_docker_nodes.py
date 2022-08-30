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
import pytest_asyncio

from fastapi import FastAPI, status
from httpx import AsyncClient
from tests.utils import asyncio_patch
from unittest.mock import patch

from gns3server.compute.project import Project

pytestmark = [pytest.mark.asyncio]


@pytest.fixture
def base_params() -> dict:
    """Return standard parameters"""

    params = {
        "name": "DOCKER-TEST-1",
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


@pytest_asyncio.fixture
async def vm(app: FastAPI, compute_client: AsyncClient, compute_project: Project, base_params: dict) -> dict:

    with asyncio_patch("gns3server.compute.docker.Docker.list_images", return_value=[{"image": "nginx"}]):
        with asyncio_patch("gns3server.compute.docker.Docker.query", return_value={"Id": "8bd8153ea8f5"}):
            with asyncio_patch("gns3server.compute.docker.DockerVM._get_container_state", return_value="exited"):
                response = await compute_client.post(app.url_path_for("compute:create_docker_node", project_id=compute_project.id),
                                             json=base_params)
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()


async def test_docker_create(app: FastAPI, compute_client: AsyncClient, compute_project: Project, base_params: dict) -> None:

    with asyncio_patch("gns3server.compute.docker.Docker.list_images", return_value=[{"image": "nginx"}]):
        with asyncio_patch("gns3server.compute.docker.Docker.query", return_value={"Id": "8bd8153ea8f5"}):
            response = await compute_client.post(
                app.url_path_for("compute:create_docker_node", project_id=compute_project.id), json=base_params
            )
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["name"] == "DOCKER-TEST-1"
    assert response.json()["project_id"] == compute_project.id
    assert response.json()["container_id"] == "8bd8153ea8f5"
    assert response.json()["image"] == "nginx:latest"
    assert response.json()["adapters"] == 2
    assert response.json()["environment"] == "YES=1\nNO=0"
    assert response.json()["console_resolution"] == "1280x1024"
    assert response.json()["extra_hosts"] == "test:127.0.0.1"


@pytest.mark.parametrize(
    "name, status_code",
    (
        ("valid-name.com", status.HTTP_201_CREATED),
        ("42name", status.HTTP_201_CREATED),
        ("424242", status.HTTP_409_CONFLICT),
        ("name42", status.HTTP_201_CREATED),
        ("name.424242", status.HTTP_409_CONFLICT),
        ("-name", status.HTTP_409_CONFLICT),
        ("name%-test", status.HTTP_409_CONFLICT),
        ("x" * 63, status.HTTP_201_CREATED),
        ("x" * 64, status.HTTP_409_CONFLICT),
        (("x" * 62 + ".") * 4, status.HTTP_201_CREATED),
        ("xx" + ("x" * 62 + ".") * 4, status.HTTP_409_CONFLICT),
    ),
)
async def test_docker_create_with_invalid_name(
        app: FastAPI,
        compute_client: AsyncClient,
        compute_project: Project,
        base_params: dict,
        name: str,
        status_code: int
) -> None:

    base_params["name"] = name
    with asyncio_patch("gns3server.compute.docker.Docker.list_images", return_value=[{"image": "nginx"}]):
        with asyncio_patch("gns3server.compute.docker.Docker.query", return_value={"Id": "8bd8153ea8f5"}):
            response = await compute_client.post(
                app.url_path_for("compute:create_docker_node", project_id=compute_project.id), json=base_params
            )
    assert response.status_code == status_code


async def test_docker_start(app: FastAPI, compute_client: AsyncClient, vm: dict) -> None:

    with asyncio_patch("gns3server.compute.docker.docker_vm.DockerVM.start", return_value=True) as mock:

        response = await compute_client.post(app.url_path_for("compute:start_docker_node",
                                                      project_id=vm["project_id"],
                                                      node_id=vm["node_id"]))
        assert mock.called
        assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_docker_stop(app: FastAPI, compute_client: AsyncClient, vm: dict) -> None:

    with asyncio_patch("gns3server.compute.docker.docker_vm.DockerVM.stop", return_value=True) as mock:
        response = await compute_client.post(app.url_path_for("compute:stop_docker_node",
                                                      project_id=vm["project_id"],
                                                      node_id=vm["node_id"]))
        assert mock.called
        assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_docker_reload(app: FastAPI, compute_client: AsyncClient, vm: dict) -> None:

    with asyncio_patch("gns3server.compute.docker.docker_vm.DockerVM.restart", return_value=True) as mock:
        response = await compute_client.post(app.url_path_for("compute:reload_docker_node",
                                                      project_id=vm["project_id"],
                                                      node_id=vm["node_id"]))
        assert mock.called
        assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_docker_delete(app: FastAPI, compute_client: AsyncClient, vm: dict) -> None:

    with asyncio_patch("gns3server.compute.docker.docker_vm.DockerVM.delete", return_value=True) as mock:
        response = await compute_client.delete(app.url_path_for("compute:delete_docker_node",
                                                        project_id=vm["project_id"],
                                                        node_id=vm["node_id"]))
        assert mock.called
        assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_docker_pause(app: FastAPI, compute_client: AsyncClient, vm: dict) -> None:

    with asyncio_patch("gns3server.compute.docker.docker_vm.DockerVM.pause", return_value=True) as mock:
        response = await compute_client.post(app.url_path_for("compute:pause_docker_node",
                                                      project_id=vm["project_id"],
                                                      node_id=vm["node_id"]))
        assert mock.called
        assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_docker_unpause(app: FastAPI, compute_client: AsyncClient, vm: dict) -> None:

    with asyncio_patch("gns3server.compute.docker.docker_vm.DockerVM.unpause", return_value=True) as mock:
        response = await compute_client.post(app.url_path_for("compute:unpause_docker_node",
                                                      project_id=vm["project_id"],
                                                      node_id=vm["node_id"]))
        assert mock.called
        assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_docker_nio_create_udp(app: FastAPI, compute_client: AsyncClient, vm: dict) -> None:

    params = {
        "type": "nio_udp",
        "lport": 4242,
        "rport": 4343,
        "rhost": "127.0.0.1"}

    url = app.url_path_for("compute:create_docker_node_nio",
                           project_id=vm["project_id"],
                           node_id=vm["node_id"],
                           adapter_number="0",
                           port_number="0")
    response = await compute_client.post(url, json=params)
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["type"] == "nio_udp"


async def test_docker_update_nio(app: FastAPI, compute_client: AsyncClient, vm: dict) -> None:

    params = {
        "type": "nio_udp",
        "lport": 4242,
        "rport": 4343,
        "rhost": "127.0.0.1"
    }

    url = app.url_path_for("compute:create_docker_node_nio",
                           project_id=vm["project_id"],
                           node_id=vm["node_id"],
                           adapter_number="0",
                           port_number="0")
    response = await compute_client.post(url, json=params)
    assert response.status_code == status.HTTP_201_CREATED

    url = app.url_path_for("compute:update_docker_node_nio",
                           project_id=vm["project_id"],
                           node_id=vm["node_id"],
                           adapter_number="0",
                           port_number="0")
    with asyncio_patch("gns3server.compute.docker.docker_vm.DockerVM.adapter_update_nio_binding"):
        response = await compute_client.put(url, json=params)
    assert response.status_code == status.HTTP_201_CREATED


async def test_docker_delete_nio(app: FastAPI, compute_client: AsyncClient, vm: dict) -> None:

    url = app.url_path_for("compute:delete_docker_node_nio",
                           project_id=vm["project_id"],
                           node_id=vm["node_id"],
                           adapter_number="0",
                           port_number="0")
    with asyncio_patch("gns3server.compute.docker.docker_vm.DockerVM.adapter_remove_nio_binding"):
        response = await compute_client.delete(url)
    assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_docker_update(app: FastAPI, compute_client: AsyncClient, vm: dict, free_console_port: int) -> None:

    params = {
        "name": "test",
        "console": free_console_port,
        "start_command": "yes",
        "environment": "GNS3=1\nGNS4=0",
        "extra_hosts": "test:127.0.0.1"
    }

    with asyncio_patch("gns3server.compute.docker.docker_vm.DockerVM.update") as mock:
        response = await compute_client.put(app.url_path_for("compute:update_docker_node",
                                                     project_id=vm["project_id"],
                                                     node_id=vm["node_id"]), json=params)

    assert response.status_code == 200
    assert mock.called
    assert response.json()["name"] == "test"
    assert response.json()["console"] == free_console_port
    assert response.json()["start_command"] == "yes"
    assert response.json()["environment"] == "GNS3=1\nGNS4=0"
    assert response.json()["extra_hosts"] == "test:127.0.0.1"


async def test_docker_start_capture(app: FastAPI, compute_client: AsyncClient, vm: dict) -> None:

    url = app.url_path_for("compute:start_docker_node_capture",
                           project_id=vm["project_id"],
                           node_id=vm["node_id"],
                           adapter_number="0",
                           port_number="0")

    with patch("gns3server.compute.docker.docker_vm.DockerVM.is_running", return_value=True):
        with asyncio_patch("gns3server.compute.docker.docker_vm.DockerVM.start_capture") as mock:
            params = {"capture_file_name": "test.pcap", "data_link_type": "DLT_EN10MB"}
            response = await compute_client.post(url, json=params)
            assert response.status_code == status.HTTP_200_OK
            assert mock.called
            assert "test.pcap" in response.json()["pcap_file_path"]


async def test_docker_stop_capture(app: FastAPI, compute_client: AsyncClient, vm: dict) -> None:

    url = app.url_path_for("compute:stop_docker_node_capture",
                           project_id=vm["project_id"],
                           node_id=vm["node_id"],
                           adapter_number="0",
                           port_number="0")

    with patch("gns3server.compute.docker.docker_vm.DockerVM.is_running", return_value=True):
        with asyncio_patch("gns3server.compute.docker.docker_vm.DockerVM.stop_capture") as mock:
            response = await compute_client.post(url)
            assert response.status_code == status.HTTP_204_NO_CONTENT
            assert mock.called


async def test_docker_duplicate(app: FastAPI, compute_client: AsyncClient, vm: dict, base_params: dict) -> None:

    # create destination node first
    with asyncio_patch("gns3server.compute.docker.Docker.list_images", return_value=[{"image": "nginx"}]):
        with asyncio_patch("gns3server.compute.docker.Docker.query", return_value={"Id": "8bd8153ea8f5"}):
            response = await compute_client.post(app.url_path_for("compute:create_docker_node",
                                                          project_id=vm["project_id"]), json=base_params)
    assert response.status_code == status.HTTP_201_CREATED

    params = {"destination_node_id": response.json()["node_id"]}
    response = await compute_client.post(app.url_path_for("compute:duplicate_docker_node",
                                                  project_id=vm["project_id"],
                                                  node_id=vm["node_id"]), json=params)
    assert response.status_code == status.HTTP_201_CREATED
