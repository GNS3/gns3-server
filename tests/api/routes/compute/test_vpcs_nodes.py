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

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def vm(app: FastAPI, compute_client: AsyncClient, compute_project: Project) -> None:

    params = {"name": "PC TEST 1"}
    response = await compute_client.post(app.url_path_for("compute:create_vpcs_node", project_id=compute_project.id), json=params)
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()


async def test_vpcs_create(app: FastAPI, compute_client: AsyncClient, compute_project: Project) -> None:

    params = {"name": "PC TEST 1"}
    response = await compute_client.post(app.url_path_for("compute:create_vpcs_node", project_id=compute_project.id), json=params)
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["name"] == "PC TEST 1"
    assert response.json()["project_id"] == compute_project.id


async def test_vpcs_get(app: FastAPI, compute_client: AsyncClient, compute_project: Project, vm: dict) -> None:

    response = await compute_client.get(app.url_path_for("compute:get_vpcs_node", project_id=vm["project_id"], node_id=vm["node_id"]))
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["name"] == "PC TEST 1"
    assert response.json()["project_id"] == compute_project.id
    assert response.json()["status"] == "stopped"


async def test_vpcs_create_startup_script(app: FastAPI, compute_client: AsyncClient, compute_project: Project) -> None:

    params = {
        "name": "PC TEST 1",
        "startup_script": "ip 192.168.1.2\necho TEST"
    }

    response = await compute_client.post(app.url_path_for("compute:create_vpcs_node", project_id=compute_project.id), json=params)
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["name"] == "PC TEST 1"
    assert response.json()["project_id"] == compute_project.id


async def test_vpcs_create_port(app: FastAPI,
                                compute_client: AsyncClient,
                                compute_project: Project,
                                free_console_port: int) -> None:

    params = {
        "name": "PC TEST 1",
        "console": free_console_port
    }

    response = await compute_client.post(app.url_path_for("compute:create_vpcs_node", project_id=compute_project.id), json=params)
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["name"] == "PC TEST 1"
    assert response.json()["project_id"] == compute_project.id
    assert response.json()["console"] == free_console_port


async def test_vpcs_nio_create_udp(app: FastAPI, compute_client: AsyncClient, vm: dict) -> None:

    params = {
        "type": "nio_udp",
        "lport": 4242,
        "rport": 4343,
        "rhost": "127.0.0.1"
    }

    url = app.url_path_for("compute:create_vpcs_node_nio",
                           project_id=vm["project_id"],
                           node_id=vm["node_id"],
                           adapter_number="0",
                           port_number="0")

    with asyncio_patch("gns3server.compute.vpcs.vpcs_vm.VPCSVM.add_ubridge_udp_connection"):
        response = await compute_client.post(url, json=params)
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["type"] == "nio_udp"


async def test_vpcs_nio_update_udp(app: FastAPI, compute_client: AsyncClient, vm: dict) -> None:

    params = {
        "type": "nio_udp",
        "lport": 4242,
        "rport": 4343,
        "rhost": "127.0.0.1"
    }

    url = app.url_path_for("compute:create_vpcs_node_nio",
                           project_id=vm["project_id"],
                           node_id=vm["node_id"],
                           adapter_number="0",
                           port_number="0")

    with asyncio_patch("gns3server.compute.vpcs.vpcs_vm.VPCSVM.add_ubridge_udp_connection"):
        response = await compute_client.post(url, json=params)
    assert response.status_code == status.HTTP_201_CREATED

    params["filters"] = {}
    url = app.url_path_for("compute:update_vpcs_node_nio",
                           project_id=vm["project_id"],
                           node_id=vm["node_id"],
                           adapter_number="0",
                           port_number="0")
    response = await compute_client.put(url, json=params)
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["type"] == "nio_udp"


async def test_vpcs_delete_nio(app: FastAPI, compute_client: AsyncClient, vm: dict) -> None:

    params = {
        "type": "nio_udp",
        "lport": 4242,
        "rport": 4343,
        "rhost": "127.0.0.1"
    }

    with asyncio_patch("gns3server.compute.vpcs.vpcs_vm.VPCSVM._ubridge_send"):
        url = app.url_path_for("compute:create_vpcs_node_nio",
                               project_id=vm["project_id"],
                               node_id=vm["node_id"],
                               adapter_number="0",
                               port_number="0")
        await compute_client.post(url, json=params)

        url = app.url_path_for("compute:delete_vpcs_node_nio",
                               project_id=vm["project_id"],
                               node_id=vm["node_id"],
                               adapter_number="0",
                               port_number="0")
        response = await compute_client.delete(url)
    assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_vpcs_start(app: FastAPI, compute_client: AsyncClient, vm: dict) -> None:

    with asyncio_patch("gns3server.compute.vpcs.vpcs_vm.VPCSVM.start", return_value=True) as mock:
        response = await compute_client.post(app.url_path_for("compute:start_vpcs_node",
                                                      project_id=vm["project_id"],
                                                      node_id=vm["node_id"]))
        assert mock.called
        assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_vpcs_stop(app: FastAPI, compute_client: AsyncClient, vm: dict) -> None:

    with asyncio_patch("gns3server.compute.vpcs.vpcs_vm.VPCSVM.stop", return_value=True) as mock:

        response = await compute_client.post(app.url_path_for("compute:stop_vpcs_node",
                                                      project_id=vm["project_id"],
                                                      node_id=vm["node_id"]))
        assert mock.called
        assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_vpcs_reload(app: FastAPI, compute_client: AsyncClient, vm: dict) -> None:

    with asyncio_patch("gns3server.compute.vpcs.vpcs_vm.VPCSVM.reload", return_value=True) as mock:
        response = await compute_client.post(app.url_path_for("compute:reload_vpcs_node",
                                                      project_id=vm["project_id"],
                                                      node_id=vm["node_id"]))
        assert mock.called
        assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_vpcs_delete(app: FastAPI, compute_client: AsyncClient, vm: dict) -> None:

    with asyncio_patch("gns3server.compute.vpcs.VPCS.delete_node", return_value=True) as mock:
        response = await compute_client.delete(app.url_path_for("compute:delete_vpcs_node",
                                                        project_id=vm["project_id"],
                                                        node_id=vm["node_id"]))
        assert mock.called
        assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_vpcs_duplicate(app: FastAPI, compute_client: AsyncClient, compute_project: Project, vm: dict) -> None:

    # create destination node first
    params = {"name": "PC TEST 1"}
    response = await compute_client.post(app.url_path_for("compute:create_vpcs_node", project_id=compute_project.id), json=params)
    assert response.status_code == status.HTTP_201_CREATED

    params = {"destination_node_id": response.json()["node_id"]}
    response = await compute_client.post(app.url_path_for("compute:duplicate_vpcs_node",
                                                  project_id=vm["project_id"],
                                                  node_id=vm["node_id"]), json=params)
    assert response.status_code == status.HTTP_201_CREATED


async def test_vpcs_update(app: FastAPI, compute_client: AsyncClient, vm: dict, free_console_port: int) -> None:

    console_port = free_console_port
    params = {
        "name": "test",
        "console": console_port
    }

    response = await compute_client.put(app.url_path_for("compute:update_vpcs_node",
                                                  project_id=vm["project_id"],
                                                  node_id=vm["node_id"]), json=params)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["name"] == "test"
    assert response.json()["console"] == console_port


async def test_vpcs_start_capture(app: FastAPI, compute_client: AsyncClient, vm: dict) -> None:

    params = {
        "capture_file_name": "test.pcap",
        "data_link_type": "DLT_EN10MB"
    }

    url = app.url_path_for("compute:start_vpcs_node_capture",
                           project_id=vm["project_id"],
                           node_id=vm["node_id"],
                           adapter_number="0",
                           port_number="0")

    with patch("gns3server.compute.vpcs.vpcs_vm.VPCSVM.is_running", return_value=True):
        with asyncio_patch("gns3server.compute.vpcs.vpcs_vm.VPCSVM.start_capture") as mock:
            response = await compute_client.post(url, json=params)
            assert response.status_code == status.HTTP_200_OK
            assert mock.called
            assert "test.pcap" in response.json()["pcap_file_path"]


async def test_vpcs_stop_capture(app: FastAPI, compute_client: AsyncClient, vm: dict) -> None:

    url = app.url_path_for("compute:stop_vpcs_node_capture",
                           project_id=vm["project_id"],
                           node_id=vm["node_id"],
                           adapter_number="0",
                           port_number="0")

    with patch("gns3server.compute.vpcs.vpcs_vm.VPCSVM.is_running", return_value=True):
        with asyncio_patch("gns3server.compute.vpcs.vpcs_vm.VPCSVM.stop_capture") as mock:
            response = await compute_client.post(url)
            assert response.status_code == status.HTTP_204_NO_CONTENT
            assert mock.called


# @pytest.mark.asyncio
# async def test_vpcs_pcap(app: FastAPI, compute_client: AsyncClient, vm, compute_project: Project):
#
#     with asyncio_patch("gns3server.compute.vpcs.vpcs_vm.VPCSVM.get_nio"):
#         with asyncio_patch("gns3server.compute.vpcs.VPCS.stream_pcap_file"):
#             response = await compute_client.get("/projects/{project_id}/vpcs/nodes/{node_id}/adapters/0/ports/0/pcap".format(project_id=compute_project.id, node_id=vm["node_id"]), raw=True)
#             assert response.status_code == status.HTTP_200_OK
