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


@pytest_asyncio.fixture(scope="function")
async def vm(app: FastAPI, compute_client: AsyncClient, compute_project: Project, vmx_path: str) -> dict:

    params = {
        "name": "VMTEST",
        "vmx_path": vmx_path,
        "linked_clone": False
    }

    with asyncio_patch("gns3server.compute.vmware.vmware_vm.VMwareVM.create", return_value=True) as mock:
        response = await compute_client.post(app.url_path_for("compute:create_vmware_node", project_id=compute_project.id),
                                     json=params)
        assert mock.called
        assert response.status_code == status.HTTP_201_CREATED
        return response.json()


@pytest.fixture
def vmx_path(tmpdir: str) -> str:
    """
    Return a fake VMX file
    """

    path = str(tmpdir / "test.vmx")
    with open(path, 'w+') as f:
        f.write("1")
    return path


async def test_vmware_create(app: FastAPI, compute_client: AsyncClient, compute_project: Project, vmx_path: str) -> None:

    params = {
        "name": "VM1",
        "vmx_path": vmx_path,
        "linked_clone": False
    }

    with asyncio_patch("gns3server.compute.vmware.vmware_vm.VMwareVM.create", return_value=True):
        response = await compute_client.post(app.url_path_for("compute:create_vmware_node", project_id=compute_project.id),
                                     json=params)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["name"] == "VM1"
        assert response.json()["project_id"] == compute_project.id


async def test_vmware_get(app: FastAPI, compute_client: AsyncClient, compute_project: Project, vm: dict) -> None:

    response = await compute_client.get(app.url_path_for("compute:get_vmware_node", project_id=vm["project_id"], node_id=vm["node_id"]))
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["name"] == "VMTEST"
    assert response.json()["project_id"] == compute_project.id


async def test_vmware_start(app: FastAPI, compute_client: AsyncClient, vm: dict) -> None:

    with asyncio_patch("gns3server.compute.vmware.vmware_vm.VMwareVM.start", return_value=True) as mock:
        response = await compute_client.post(app.url_path_for("compute:start_vmware_node",
                                                      project_id=vm["project_id"],
                                                      node_id=vm["node_id"]))
        assert mock.called
        assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_vmware_stop(app: FastAPI, compute_client: AsyncClient, vm: dict) -> None:

    with asyncio_patch("gns3server.compute.vmware.vmware_vm.VMwareVM.stop", return_value=True) as mock:
        response = await compute_client.post(app.url_path_for("compute:stop_vmware_node",
                                                      project_id=vm["project_id"],
                                                      node_id=vm["node_id"]))
        assert mock.called
        assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_vmware_suspend(app: FastAPI, compute_client: AsyncClient, vm: dict) -> None:

    with asyncio_patch("gns3server.compute.vmware.vmware_vm.VMwareVM.suspend", return_value=True) as mock:
        response = await compute_client.post(app.url_path_for("compute:suspend_vmware_node",
                                                      project_id=vm["project_id"],
                                                      node_id=vm["node_id"]))
        assert mock.called
        assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_vmware_resume(app: FastAPI, compute_client: AsyncClient, vm: dict) -> None:

    with asyncio_patch("gns3server.compute.vmware.vmware_vm.VMwareVM.resume", return_value=True) as mock:
        response = await compute_client.post(app.url_path_for("compute:resume_vmware_node",
                                                      project_id=vm["project_id"],
                                                      node_id=vm["node_id"]))
        assert mock.called
        assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_vmware_reload(app: FastAPI, compute_client: AsyncClient, vm: dict) -> None:

    with asyncio_patch("gns3server.compute.vmware.vmware_vm.VMwareVM.reload", return_value=True) as mock:
        response = await compute_client.post(app.url_path_for("compute:reload_vmware_node",
                                                      project_id=vm["project_id"],
                                                      node_id=vm["node_id"]))
        assert mock.called
        assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_vmware_nio_create_udp(app: FastAPI, compute_client: AsyncClient, vm: dict) -> None:

    params = {
        "type": "nio_udp",
        "lport": 4242,
        "rport": 4343,
        "rhost": "127.0.0.1"
    }

    url = app.url_path_for("compute:create_vmware_node_nio",
                           project_id=vm["project_id"],
                           node_id=vm["node_id"],
                           adapter_number="0",
                           port_number="0")

    with asyncio_patch('gns3server.compute.vmware.vmware_vm.VMwareVM.adapter_add_nio_binding') as mock:
        response = await compute_client.post(url, json=params)
        assert mock.called
        args, kwgars = mock.call_args
        assert args[0] == 0

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["type"] == "nio_udp"


# @pytest.mark.asyncio
# async def test_vmware_nio_update_udp(app: FastAPI, compute_client: AsyncClient, vm):
#
#     params = {
#         "type": "nio_udp",
#         "lport": 4242,
#         "rport": 4343,
#         "rhost": "127.0.0.1",
#         "filters": {}
#     }
#
#     with asyncio_patch('gns3server.compute.vmware.vmware_vm.VMwareVM._ubridge_send'):
#         with asyncio_patch('gns3server.compute.vmware.vmware_vm.VMwareVM.ethernet_adapters'):
#             with patch('gns3server.compute.vmware.vmware_vm.VMwareVM._get_vnet') as mock:
#                 response = await compute_client.put("/projects/{project_id}/vmware/nodes/{node_id}/adapters/0/ports/0/nio".format(project_id=vm["project_id"], node_id=vm["node_id"]), params)
#                 assert response.status_code == status.HTTP_201_CREATED
#                 assert response.json()["type"] == "nio_udp"


async def test_vmware_delete_nio(app: FastAPI, compute_client: AsyncClient, vm: dict) -> None:

    url = app.url_path_for("compute:delete_vmware_node_nio",
                           project_id=vm["project_id"],
                           node_id=vm["node_id"],
                           adapter_number="0",
                           port_number="0")

    with asyncio_patch('gns3server.compute.vmware.vmware_vm.VMwareVM.adapter_remove_nio_binding') as mock:
        response = await compute_client.delete(url)
        assert mock.called
        args, kwgars = mock.call_args
        assert args[0] == 0

    assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_vmware_update(app: FastAPI, compute_client: AsyncClient, vm: dict, free_console_port: int) -> None:

    params = {
        "name": "test",
        "console": free_console_port
    }

    response = await compute_client.put(app.url_path_for("compute:update_vmware_node",
                                                 project_id=vm["project_id"],
                                                 node_id=vm["node_id"]), json=params)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["name"] == "test"
    assert response.json()["console"] == free_console_port


async def test_vmware_start_capture(app: FastAPI, compute_client: AsyncClient, vm: dict) -> None:

    params = {
        "capture_file_name": "test.pcap",
        "data_link_type": "DLT_EN10MB"
    }

    url = app.url_path_for("compute:start_vmware_node_capture",
                           project_id=vm["project_id"],
                           node_id=vm["node_id"],
                           adapter_number="0",
                           port_number="0")

    with patch("gns3server.compute.vmware.vmware_vm.VMwareVM.is_running", return_value=True):
        with asyncio_patch("gns3server.compute.vmware.vmware_vm.VMwareVM.start_capture") as mock:

            response = await compute_client.post(url, json=params)
            assert response.status_code == status.HTTP_200_OK
            assert mock.called
            assert "test.pcap" in response.json()["pcap_file_path"]


async def test_vmware_stop_capture(app: FastAPI, compute_client: AsyncClient, vm: dict) -> None:

    url = app.url_path_for("compute:stop_vmware_node_capture",
                           project_id=vm["project_id"],
                           node_id=vm["node_id"],
                           adapter_number="0",
                           port_number="0")

    with patch("gns3server.compute.vmware.vmware_vm.VMwareVM.is_running", return_value=True):
        with asyncio_patch("gns3server.compute.vmware.vmware_vm.VMwareVM.stop_capture") as mock:
            response = await compute_client.post(url)
            assert response.status_code == status.HTTP_204_NO_CONTENT
            assert mock.called


# @pytest.mark.asyncio
# async def test_vmware_pcap(app: FastAPI, compute_client: AsyncClient, vm, compute_project):
#
#     with asyncio_patch("gns3server.compute.vmware.vmware_vm.VMwareVM.get_nio"):
#         with asyncio_patch("gns3server.compute.vmware.VMware.stream_pcap_file"):
#             response = await compute_client.get("/projects/{project_id}/vmware/nodes/{node_id}/adapters/0/ports/0/pcap".format(project_id=compute_project.id, node_id=vm["node_id"]), raw=True)
#             assert response.status_code == status.HTTP_200_OK
