# -*- coding: utf-8 -*-
#
# Copyright (C) 2018 GNS3 Technologies Inc.
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
import sys
import os
from tests.utils import asyncio_patch
from unittest.mock import patch


@pytest.fixture(scope="function")
def vm(http_compute, project):
    response = http_compute.post("/projects/{project_id}/traceng/nodes".format(project_id=project.id), {"name": "TraceNG TEST 1"})
    assert response.status == 201
    return response.json


def test_traceng_create(http_compute, project):
    response = http_compute.post("/projects/{project_id}/traceng/nodes".format(project_id=project.id), {"name": "TraceNG TEST 1"}, example=True)
    assert response.status == 201
    assert response.route == "/projects/{project_id}/traceng/nodes"
    assert response.json["name"] == "TraceNG TEST 1"
    assert response.json["project_id"] == project.id


def test_traceng_get(http_compute, project, vm):
    response = http_compute.get("/projects/{project_id}/traceng/nodes/{node_id}".format(project_id=vm["project_id"], node_id=vm["node_id"]), example=True)
    assert response.status == 200
    assert response.route == "/projects/{project_id}/traceng/nodes/{node_id}"
    assert response.json["name"] == "TraceNG TEST 1"
    assert response.json["project_id"] == project.id
    assert response.json["status"] == "stopped"


def test_traceng_nio_create_udp(http_compute, vm):
    with asyncio_patch("gns3server.compute.traceng.traceng_vm.TraceNGVM.add_ubridge_udp_connection"):
        response = http_compute.post("/projects/{project_id}/traceng/nodes/{node_id}/adapters/0/ports/0/nio".format(project_id=vm["project_id"], node_id=vm["node_id"]), {"type": "nio_udp",
                                                                                                                                                                       "lport": 4242,
                                                                                                                                                                       "rport": 4343,
                                                                                                                                                                       "rhost": "127.0.0.1"},
                                     example=True)
    assert response.status == 201
    assert response.route == r"/projects/{project_id}/traceng/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio"
    assert response.json["type"] == "nio_udp"


def test_traceng_nio_update_udp(http_compute, vm):

    with asyncio_patch("gns3server.compute.traceng.traceng_vm.TraceNGVM.add_ubridge_udp_connection"):
        response = http_compute.post("/projects/{project_id}/traceng/nodes/{node_id}/adapters/0/ports/0/nio".format(project_id=vm["project_id"], node_id=vm["node_id"]), {"type": "nio_udp",
                                                                                                                                                                       "lport": 4242,
                                                                                                                                                                       "rport": 4343,
                                                                                                                                                                       "rhost": "127.0.0.1"})
    assert response.status == 201
    response = http_compute.put("/projects/{project_id}/traceng/nodes/{node_id}/adapters/0/ports/0/nio".format(project_id=vm["project_id"], node_id=vm["node_id"]),
                                {
                                    "type": "nio_udp",
                                    "lport": 4242,
                                    "rport": 4343,
                                    "rhost": "127.0.0.1",
                                    "filters": {}},
                                example=True)
    assert response.status == 201, response.body.decode("utf-8")
    assert response.route == r"/projects/{project_id}/traceng/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio"
    assert response.json["type"] == "nio_udp"


def test_traceng_delete_nio(http_compute, vm):
    with asyncio_patch("gns3server.compute.traceng.traceng_vm.TraceNGVM._ubridge_send"):
        http_compute.post("/projects/{project_id}/traceng/nodes/{node_id}/adapters/0/ports/0/nio".format(project_id=vm["project_id"], node_id=vm["node_id"]), {"type": "nio_udp",
                                                                                                                                                            "lport": 4242,
                                                                                                                                                            "rport": 4343,
                                                                                                                                                            "rhost": "127.0.0.1"})
        response = http_compute.delete("/projects/{project_id}/traceng/nodes/{node_id}/adapters/0/ports/0/nio".format(project_id=vm["project_id"], node_id=vm["node_id"]), example=True)
    assert response.status == 204, response.body.decode()
    assert response.route == r"/projects/{project_id}/traceng/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio"


def test_traceng_start(http_compute, vm):

    with asyncio_patch("gns3server.compute.traceng.traceng_vm.TraceNGVM.start", return_value=True) as mock:
        response = http_compute.post("/projects/{project_id}/traceng/nodes/{node_id}/start".format(project_id=vm["project_id"], node_id=vm["node_id"]), {"destination": "192.168.1.2"}, example=True)
        assert mock.called
        assert response.status == 200
        assert response.json["name"] == "TraceNG TEST 1"


def test_traceng_stop(http_compute, vm):
    with asyncio_patch("gns3server.compute.traceng.traceng_vm.TraceNGVM.stop", return_value=True) as mock:
        response = http_compute.post("/projects/{project_id}/traceng/nodes/{node_id}/stop".format(project_id=vm["project_id"], node_id=vm["node_id"]), example=True)
        assert mock.called
        assert response.status == 204


def test_traceng_reload(http_compute, vm):
    with asyncio_patch("gns3server.compute.traceng.traceng_vm.TraceNGVM.reload", return_value=True) as mock:
        response = http_compute.post("/projects/{project_id}/traceng/nodes/{node_id}/reload".format(project_id=vm["project_id"], node_id=vm["node_id"]), example=True)
        assert mock.called
        assert response.status == 204


def test_traceng_delete(http_compute, vm):
    with asyncio_patch("gns3server.compute.traceng.TraceNG.delete_node", return_value=True) as mock:
        response = http_compute.delete("/projects/{project_id}/traceng/nodes/{node_id}".format(project_id=vm["project_id"], node_id=vm["node_id"]), example=True)
        assert mock.called
        assert response.status == 204


def test_traceng_duplicate(http_compute, vm):
    with asyncio_patch("gns3server.compute.traceng.TraceNG.duplicate_node", return_value=True) as mock:
        response = http_compute.post(
            "/projects/{project_id}/traceng/nodes/{node_id}/duplicate".format(
                project_id=vm["project_id"],
                node_id=vm["node_id"]),
            body={
                "destination_node_id": str(uuid.uuid4())
            },
            example=True)
        assert mock.called
        assert response.status == 201


def test_traceng_update(http_compute, vm, tmpdir, free_console_port):
    response = http_compute.put("/projects/{project_id}/traceng/nodes/{node_id}".format(project_id=vm["project_id"], node_id=vm["node_id"]), {"name": "test",
                                                                                                                                              "ip_address": "192.168.1.1",
                                                                                                                                             },
                                example=True)
    assert response.status == 200
    assert response.json["name"] == "test"
    assert response.json["ip_address"] == "192.168.1.1"


def test_traceng_start_capture(http_compute, vm):

    with patch("gns3server.compute.traceng.traceng_vm.TraceNGVM.is_running", return_value=True):
        with asyncio_patch("gns3server.compute.traceng.traceng_vm.TraceNGVM.start_capture") as start_capture:
            params = {"capture_file_name": "test.pcap", "data_link_type": "DLT_EN10MB"}
            response = http_compute.post("/projects/{project_id}/traceng/nodes/{node_id}/adapters/0/ports/0/start_capture".format(project_id=vm["project_id"], node_id=vm["node_id"]), body=params, example=True)
            assert response.status == 200
            assert start_capture.called
            assert "test.pcap" in response.json["pcap_file_path"]


def test_traceng_stop_capture(http_compute, vm):

    with patch("gns3server.compute.traceng.traceng_vm.TraceNGVM.is_running", return_value=True):
        with asyncio_patch("gns3server.compute.traceng.traceng_vm.TraceNGVM.stop_capture") as stop_capture:
            response = http_compute.post("/projects/{project_id}/traceng/nodes/{node_id}/adapters/0/ports/0/stop_capture".format(project_id=vm["project_id"], node_id=vm["node_id"]), example=True)
            assert response.status == 204
            assert stop_capture.called


def test_traceng_pcap(http_compute, vm, project):

    with asyncio_patch("gns3server.compute.traceng.traceng_vm.TraceNGVM.get_nio"):
        with asyncio_patch("gns3server.compute.traceng.TraceNG.stream_pcap_file"):
            response = http_compute.get("/projects/{project_id}/traceng/nodes/{node_id}/adapters/0/ports/0/pcap".format(project_id=project.id, node_id=vm["node_id"]), raw=True)
            assert response.status == 200
