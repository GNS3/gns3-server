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
import uuid
from tests.utils import asyncio_patch
from unittest.mock import patch


@pytest.fixture
async def vm(compute_api, compute_project):

    params = {"name": "PC TEST 1"}
    response = await compute_api.post("/projects/{project_id}/vpcs/nodes".format(project_id=compute_project.id), params)
    assert response.status == 201
    return response.json


async def test_vpcs_create(compute_api, compute_project):

    params = {"name": "PC TEST 1"}
    response = await compute_api.post("/projects/{project_id}/vpcs/nodes".format(project_id=compute_project.id), params)
    assert response.status == 201
    assert response.route == "/projects/{project_id}/vpcs/nodes"
    assert response.json["name"] == "PC TEST 1"
    assert response.json["project_id"] == compute_project.id


async def test_vpcs_get(compute_api, compute_project, vm):

    response = await compute_api.get("/projects/{project_id}/vpcs/nodes/{node_id}".format(project_id=vm["project_id"], node_id=vm["node_id"]))
    assert response.status == 200
    assert response.route == "/projects/{project_id}/vpcs/nodes/{node_id}"
    assert response.json["name"] == "PC TEST 1"
    assert response.json["project_id"] == compute_project.id
    assert response.json["status"] == "stopped"


async def test_vpcs_create_startup_script(compute_api, compute_project):

    params = {
        "name": "PC TEST 1",
        "startup_script": "ip 192.168.1.2\necho TEST"
    }

    response = await compute_api.post("/projects/{project_id}/vpcs/nodes".format(project_id=compute_project.id), params)
    assert response.status == 201
    assert response.route == "/projects/{project_id}/vpcs/nodes"
    assert response.json["name"] == "PC TEST 1"
    assert response.json["project_id"] == compute_project.id


async def test_vpcs_create_port(compute_api, compute_project, free_console_port):

    params = {
        "name": "PC TEST 1",
        "console": free_console_port
    }

    response = await compute_api.post("/projects/{project_id}/vpcs/nodes".format(project_id=compute_project.id), params)
    assert response.status == 201
    assert response.route == "/projects/{project_id}/vpcs/nodes"
    assert response.json["name"] == "PC TEST 1"
    assert response.json["project_id"] == compute_project.id
    assert response.json["console"] == free_console_port


async def test_vpcs_nio_create_udp(compute_api, vm):

    params = {
        "type": "nio_udp",
        "lport": 4242,
        "rport": 4343,
        "rhost": "127.0.0.1"
    }

    with asyncio_patch("gns3server.compute.vpcs.vpcs_vm.VPCSVM.add_ubridge_udp_connection"):
        response = await compute_api.post("/projects/{project_id}/vpcs/nodes/{node_id}/adapters/0/ports/0/nio".format(project_id=vm["project_id"], node_id=vm["node_id"]), params)
    assert response.status == 201
    assert response.route == r"/projects/{project_id}/vpcs/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio"
    assert response.json["type"] == "nio_udp"


async def test_vpcs_nio_update_udp(compute_api, vm):

    params = {
        "type": "nio_udp",
        "lport": 4242,
        "rport": 4343,
        "rhost": "127.0.0.1"
    }

    with asyncio_patch("gns3server.compute.vpcs.vpcs_vm.VPCSVM.add_ubridge_udp_connection"):
        response = await compute_api.post("/projects/{project_id}/vpcs/nodes/{node_id}/adapters/0/ports/0/nio".format(project_id=vm["project_id"], node_id=vm["node_id"]), params)
    assert response.status == 201

    params["filters"] = {}
    response = await compute_api.put("/projects/{project_id}/vpcs/nodes/{node_id}/adapters/0/ports/0/nio".format(project_id=vm["project_id"], node_id=vm["node_id"]), params)
    assert response.status == 201, response.body.decode("utf-8")
    assert response.route == r"/projects/{project_id}/vpcs/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio"
    assert response.json["type"] == "nio_udp"


async def test_vpcs_delete_nio(compute_api, vm):

    params = {
        "type": "nio_udp",
        "lport": 4242,
        "rport": 4343,
        "rhost": "127.0.0.1"
    }

    with asyncio_patch("gns3server.compute.vpcs.vpcs_vm.VPCSVM._ubridge_send"):
        await compute_api.post("/projects/{project_id}/vpcs/nodes/{node_id}/adapters/0/ports/0/nio".format(project_id=vm["project_id"], node_id=vm["node_id"]), params)
        response = await compute_api.delete("/projects/{project_id}/vpcs/nodes/{node_id}/adapters/0/ports/0/nio".format(project_id=vm["project_id"], node_id=vm["node_id"]))
    assert response.status == 204, response.body.decode()
    assert response.route == r"/projects/{project_id}/vpcs/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio"


async def test_vpcs_start(compute_api, vm):

    with asyncio_patch("gns3server.compute.vpcs.vpcs_vm.VPCSVM.start", return_value=True) as mock:
        response = await compute_api.post("/projects/{project_id}/vpcs/nodes/{node_id}/start".format(project_id=vm["project_id"], node_id=vm["node_id"]))
        assert mock.called
        assert response.status == 200
        assert response.json["name"] == "PC TEST 1"


async def test_vpcs_stop(compute_api, vm):

    with asyncio_patch("gns3server.compute.vpcs.vpcs_vm.VPCSVM.stop", return_value=True) as mock:

        response = await compute_api.post("/projects/{project_id}/vpcs/nodes/{node_id}/stop".format(project_id=vm["project_id"], node_id=vm["node_id"]))
        assert mock.called
        assert response.status == 204


async def test_vpcs_reload(compute_api, vm):

    with asyncio_patch("gns3server.compute.vpcs.vpcs_vm.VPCSVM.reload", return_value=True) as mock:
        response = await compute_api.post("/projects/{project_id}/vpcs/nodes/{node_id}/reload".format(project_id=vm["project_id"], node_id=vm["node_id"]))
        assert mock.called
        assert response.status == 204


async def test_vpcs_delete(compute_api, vm):

    with asyncio_patch("gns3server.compute.vpcs.VPCS.delete_node", return_value=True) as mock:
        response = await compute_api.delete("/projects/{project_id}/vpcs/nodes/{node_id}".format(project_id=vm["project_id"], node_id=vm["node_id"]))
        assert mock.called
        assert response.status == 204


async def test_vpcs_duplicate(compute_api, vm):

    params = {"destination_node_id": str(uuid.uuid4())}
    with asyncio_patch("gns3server.compute.vpcs.VPCS.duplicate_node", return_value=True) as mock:
        response = await compute_api.post("/projects/{project_id}/vpcs/nodes/{node_id}/duplicate".format(project_id=vm["project_id"], node_id=vm["node_id"]), params)
        assert mock.called
        assert response.status == 201


async def test_vpcs_update(compute_api, vm, free_console_port):

    console_port = free_console_port
    params = {
        "name": "test",
        "console": console_port
    }

    response = await compute_api.put("/projects/{project_id}/vpcs/nodes/{node_id}".format(project_id=vm["project_id"], node_id=vm["node_id"]), params)
    assert response.status == 200
    assert response.json["name"] == "test"
    assert response.json["console"] == console_port


async def test_vpcs_start_capture(compute_api, vm):

    params = {
        "capture_file_name": "test.pcap",
        "data_link_type": "DLT_EN10MB"
    }

    with patch("gns3server.compute.vpcs.vpcs_vm.VPCSVM.is_running", return_value=True):
        with asyncio_patch("gns3server.compute.vpcs.vpcs_vm.VPCSVM.start_capture") as mock:
            response = await compute_api.post("/projects/{project_id}/vpcs/nodes/{node_id}/adapters/0/ports/0/start_capture".format(project_id=vm["project_id"], node_id=vm["node_id"]), body=params)
            assert response.status == 200
            assert mock.called
            assert "test.pcap" in response.json["pcap_file_path"]


async def test_vpcs_stop_capture(compute_api, vm):

    with patch("gns3server.compute.vpcs.vpcs_vm.VPCSVM.is_running", return_value=True):
        with asyncio_patch("gns3server.compute.vpcs.vpcs_vm.VPCSVM.stop_capture") as mock:
            response = await compute_api.post("/projects/{project_id}/vpcs/nodes/{node_id}/adapters/0/ports/0/stop_capture".format(project_id=vm["project_id"], node_id=vm["node_id"]))
            assert response.status == 204
            assert mock.called


async def test_vpcs_pcap(compute_api, vm, compute_project):

    with asyncio_patch("gns3server.compute.vpcs.vpcs_vm.VPCSVM.get_nio"):
        with asyncio_patch("gns3server.compute.vpcs.VPCS.stream_pcap_file"):
            response = await compute_api.get("/projects/{project_id}/vpcs/nodes/{node_id}/adapters/0/ports/0/pcap".format(project_id=compute_project.id, node_id=vm["node_id"]), raw=True)
            assert response.status == 200
