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
from unittest.mock import patch


@pytest.fixture(scope="function")
async def vm(compute_api, compute_project):

    vboxmanage_path = "/fake/VboxManage"
    params = {
        "name": "VMTEST",
        "vmname": "VMTEST",
        "linked_clone": False
    }

    with asyncio_patch("gns3server.compute.virtualbox.virtualbox_vm.VirtualBoxVM.create", return_value=True) as mock:
        response = await compute_api.post("/projects/{project_id}/virtualbox/nodes".format(project_id=compute_project.id), params)
    assert mock.called
    assert response.status == 201

    with patch("gns3server.compute.virtualbox.VirtualBox.find_vboxmanage", return_value=vboxmanage_path):
        return response.json


async def test_vbox_create(compute_api, compute_project):

    params = {
        "name": "VM1",
        "vmname": "VM1",
        "linked_clone": False
    }

    with asyncio_patch("gns3server.compute.virtualbox.virtualbox_vm.VirtualBoxVM.create", return_value=True):
        response = await compute_api.post("/projects/{project_id}/virtualbox/nodes".format(project_id=compute_project.id), params)
        assert response.status == 201
        assert response.json["name"] == "VM1"
        assert response.json["project_id"] == compute_project.id


async def test_vbox_get(compute_api, compute_project, vm):

    response = await compute_api.get("/projects/{project_id}/virtualbox/nodes/{node_id}".format(project_id=vm["project_id"], node_id=vm["node_id"]))
    assert response.status == 200
    assert response.route == "/projects/{project_id}/virtualbox/nodes/{node_id}"
    assert response.json["name"] == "VMTEST"
    assert response.json["project_id"] == compute_project.id


async def test_vbox_start(compute_api, vm):

    with asyncio_patch("gns3server.compute.virtualbox.virtualbox_vm.VirtualBoxVM.check_hw_virtualization", return_value=True):
        with asyncio_patch("gns3server.compute.virtualbox.virtualbox_vm.VirtualBoxVM.start", return_value=True) as mock:
            response = await compute_api.post("/projects/{project_id}/virtualbox/nodes/{node_id}/start".format(project_id=vm["project_id"], node_id=vm["node_id"]))
            assert mock.called
            assert response.status == 204


async def test_vbox_stop(compute_api, vm):

    with asyncio_patch("gns3server.compute.virtualbox.virtualbox_vm.VirtualBoxVM.stop", return_value=True) as mock:
        response = await compute_api.post("/projects/{project_id}/virtualbox/nodes/{node_id}/stop".format(project_id=vm["project_id"], node_id=vm["node_id"]))
        assert mock.called
        assert response.status == 204


async def test_vbox_suspend(compute_api, vm):
    with asyncio_patch("gns3server.compute.virtualbox.virtualbox_vm.VirtualBoxVM.suspend", return_value=True) as mock:
        response = await compute_api.post("/projects/{project_id}/virtualbox/nodes/{node_id}/suspend".format(project_id=vm["project_id"], node_id=vm["node_id"]))
        assert mock.called
        assert response.status == 204


async def test_vbox_resume(compute_api, vm):

    with asyncio_patch("gns3server.compute.virtualbox.virtualbox_vm.VirtualBoxVM.resume", return_value=True) as mock:
        response = await compute_api.post("/projects/{project_id}/virtualbox/nodes/{node_id}/resume".format(project_id=vm["project_id"], node_id=vm["node_id"]))
        assert mock.called
        assert response.status == 204


async def test_vbox_reload(compute_api, vm):

    with asyncio_patch("gns3server.compute.virtualbox.virtualbox_vm.VirtualBoxVM.reload", return_value=True) as mock:
        response = await compute_api.post("/projects/{project_id}/virtualbox/nodes/{node_id}/reload".format(project_id=vm["project_id"], node_id=vm["node_id"]))
        assert mock.called
        assert response.status == 204


async def test_vbox_nio_create_udp(compute_api, vm):

    params = {
        "type": "nio_udp",
        "lport": 4242,
        "rport": 4343,
        "rhost": "127.0.0.1"
    }

    with asyncio_patch('gns3server.compute.virtualbox.virtualbox_vm.VirtualBoxVM.adapter_add_nio_binding') as mock:
        response = await compute_api.post("/projects/{project_id}/virtualbox/nodes/{node_id}/adapters/0/ports/0/nio".format(project_id=vm["project_id"], node_id=vm["node_id"]), params)
        assert mock.called
        args, kwgars = mock.call_args
        assert args[0] == 0

    assert response.status == 201
    assert response.route == r"/projects/{project_id}/virtualbox/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio"
    assert response.json["type"] == "nio_udp"


async def test_virtualbox_nio_update_udp(compute_api, vm):

    params = {
        "type": "nio_udp",
        "lport": 4242,
        "rport": 4343,
        "rhost": "127.0.0.1",
        "filters": {}
    }

    with asyncio_patch('gns3server.compute.virtualbox.virtualbox_vm.VirtualBoxVM.ethernet_adapters'):
        with asyncio_patch('gns3server.compute.virtualbox.virtualbox_vm.VirtualBoxVM.adapter_remove_nio_binding'):
            response = await compute_api.put("/projects/{project_id}/virtualbox/nodes/{node_id}/adapters/0/ports/0/nio".format(project_id=vm["project_id"], node_id=vm["node_id"]), params)

    assert response.status == 201, response.body.decode()
    assert response.route == r"/projects/{project_id}/virtualbox/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio"
    assert response.json["type"] == "nio_udp"


async def test_vbox_delete_nio(compute_api, vm):

    with asyncio_patch('gns3server.compute.virtualbox.virtualbox_vm.VirtualBoxVM.adapter_remove_nio_binding') as mock:
        response = await compute_api.delete("/projects/{project_id}/virtualbox/nodes/{node_id}/adapters/0/ports/0/nio".format(project_id=vm["project_id"], node_id=vm["node_id"]))
        assert mock.called
        args, kwgars = mock.call_args
        assert args[0] == 0

    assert response.status == 204
    assert response.route == r"/projects/{project_id}/virtualbox/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio"


async def test_vbox_update(compute_api, vm, free_console_port):

    params = {
        "name": "test",
        "console": free_console_port
    }

    response = await compute_api.put("/projects/{project_id}/virtualbox/nodes/{node_id}".format(project_id=vm["project_id"], node_id=vm["node_id"]), params)
    assert response.status == 200
    assert response.json["name"] == "test"
    assert response.json["console"] == free_console_port


async def test_virtualbox_start_capture(compute_api, vm):

    params = {
        "capture_file_name": "test.pcap",
        "data_link_type": "DLT_EN10MB"
    }

    with patch("gns3server.compute.virtualbox.virtualbox_vm.VirtualBoxVM.is_running", return_value=True):
        with asyncio_patch("gns3server.compute.virtualbox.virtualbox_vm.VirtualBoxVM.start_capture") as mock:
            response = await compute_api.post("/projects/{project_id}/virtualbox/nodes/{node_id}/adapters/0/ports/0/start_capture".format(project_id=vm["project_id"], node_id=vm["node_id"]), params)
            assert response.status == 200
            assert mock.called
            assert "test.pcap" in response.json["pcap_file_path"]


async def test_virtualbox_stop_capture(compute_api, vm):

    with patch("gns3server.compute.virtualbox.virtualbox_vm.VirtualBoxVM.is_running", return_value=True):
        with asyncio_patch("gns3server.compute.virtualbox.virtualbox_vm.VirtualBoxVM.stop_capture") as mock:
            response = await compute_api.post("/projects/{project_id}/virtualbox/nodes/{node_id}/adapters/0/ports/0/stop_capture".format(project_id=vm["project_id"], node_id=vm["node_id"]))
            assert response.status == 204
            assert mock.called


async def test_virtualbox_pcap(compute_api, vm, compute_project):

    with asyncio_patch("gns3server.compute.virtualbox.virtualbox_vm.VirtualBoxVM.get_nio"):
        with asyncio_patch("gns3server.compute.virtualbox.VirtualBox.stream_pcap_file"):
            response = await compute_api.get("/projects/{project_id}/virtualbox/nodes/{node_id}/adapters/0/ports/0/pcap".format(project_id=compute_project.id, node_id=vm["node_id"]), raw=True)
            assert response.status == 200
