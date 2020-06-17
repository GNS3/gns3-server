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

from tests.utils import asyncio_patch


@pytest.fixture(scope="function")
async def vm(compute_api, compute_project, on_gns3vm):

    with asyncio_patch("gns3server.compute.builtin.nodes.cloud.Cloud._start_ubridge"):
        response = await compute_api.post("/projects/{project_id}/cloud/nodes".format(project_id=compute_project.id), {"name": "Cloud 1"})
    assert response.status == 201
    return response.json


async def test_cloud_create(compute_api, compute_project):

    with asyncio_patch("gns3server.compute.builtin.nodes.cloud.Cloud._start_ubridge"):
        response = await compute_api.post("/projects/{project_id}/cloud/nodes".format(project_id=compute_project.id), {"name": "Cloud 1"})
    assert response.status == 201
    assert response.route == "/projects/{project_id}/cloud/nodes"
    assert response.json["name"] == "Cloud 1"
    assert response.json["project_id"] == compute_project.id


async def test_cloud_get(compute_api, compute_project, vm):

    response = await compute_api.get("/projects/{project_id}/cloud/nodes/{node_id}".format(project_id=vm["project_id"], node_id=vm["node_id"]))
    assert response.status == 200
    assert response.route == "/projects/{project_id}/cloud/nodes/{node_id}"
    assert response.json["name"] == "Cloud 1"
    assert response.json["project_id"] == compute_project.id
    assert response.json["status"] == "started"


async def test_cloud_nio_create_udp(compute_api, vm):

    params = {"type": "nio_udp",
              "lport": 4242,
              "rport": 4343,
              "rhost": "127.0.0.1"}

    response = await compute_api.post("/projects/{project_id}/cloud/nodes/{node_id}/adapters/0/ports/0/nio".format(project_id=vm["project_id"], node_id=vm["node_id"]), params)
    assert response.status == 201
    assert response.route == r"/projects/{project_id}/cloud/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio"
    assert response.json["type"] == "nio_udp"


async def test_cloud_nio_update_udp(compute_api, vm):

    params = {"type": "nio_udp",
              "lport": 4242,
              "rport": 4343,
              "rhost": "127.0.0.1"}

    await compute_api.post("/projects/{project_id}/cloud/nodes/{node_id}/adapters/0/ports/0/nio".format(project_id=vm["project_id"], node_id=vm["node_id"]), params)
    params["filters"] = {}
    response = await compute_api.put("/projects/{project_id}/cloud/nodes/{node_id}/adapters/0/ports/0/nio".format(project_id=vm["project_id"], node_id=vm["node_id"]), params)
    assert response.status == 201, response.body.decode()
    assert response.route == r"/projects/{project_id}/cloud/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio"
    assert response.json["type"] == "nio_udp"


async def test_cloud_delete_nio(compute_api, vm):

    params = {"type": "nio_udp",
              "lport": 4242,
              "rport": 4343,
              "rhost": "127.0.0.1"}

    await compute_api.post("/projects/{project_id}/cloud/nodes/{node_id}/adapters/0/ports/0/nio".format(project_id=vm["project_id"], node_id=vm["node_id"]), params)
    with asyncio_patch("gns3server.compute.builtin.nodes.cloud.Cloud._start_ubridge"):
        response = await compute_api.delete("/projects/{project_id}/cloud/nodes/{node_id}/adapters/0/ports/0/nio".format(project_id=vm["project_id"], node_id=vm["node_id"]))
    assert response.status == 204
    assert response.route == r"/projects/{project_id}/cloud/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio"


async def test_cloud_delete(compute_api, vm):

    response = await compute_api.delete("/projects/{project_id}/cloud/nodes/{node_id}".format(project_id=vm["project_id"], node_id=vm["node_id"]))
    assert response.status == 204


async def test_cloud_update(compute_api, vm):

    response = await compute_api.put("/projects/{project_id}/cloud/nodes/{node_id}".format(project_id=vm["project_id"], node_id=vm["node_id"]), {"name": "test"})
    assert response.status == 200
    assert response.json["name"] == "test"


async def test_cloud_start_capture(compute_api, vm):

    params = {
        "capture_file_name": "test.pcap",
        "data_link_type": "DLT_EN10MB"
    }

    with asyncio_patch("gns3server.compute.builtin.nodes.cloud.Cloud.start_capture") as mock:
        response = await compute_api.post("/projects/{project_id}/cloud/nodes/{node_id}/adapters/0/ports/0/start_capture".format(project_id=vm["project_id"], node_id=vm["node_id"]), params)
        assert response.status == 200
        assert mock.called
        assert "test.pcap" in response.json["pcap_file_path"]


async def test_cloud_stop_capture(compute_api, vm):

    with asyncio_patch("gns3server.compute.builtin.nodes.cloud.Cloud.stop_capture") as mock:
        response = await compute_api.post("/projects/{project_id}/cloud/nodes/{node_id}/adapters/0/ports/0/stop_capture".format(project_id=vm["project_id"], node_id=vm["node_id"]))
        assert response.status == 204
        assert mock.called


async def test_cloud_pcap(compute_api, vm, compute_project):

    with asyncio_patch("gns3server.compute.builtin.nodes.cloud.Cloud.get_nio"):
        with asyncio_patch("gns3server.compute.builtin.Builtin.stream_pcap_file"):
            response = await compute_api.get("/projects/{project_id}/cloud/nodes/{node_id}/adapters/0/ports/0/pcap".format(project_id=compute_project.id, node_id=vm["node_id"]), raw=True)
            assert response.status == 200
