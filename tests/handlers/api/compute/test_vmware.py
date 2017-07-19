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
from tests.utils import asyncio_patch
from unittest.mock import patch


@pytest.yield_fixture(scope="function")
def vm(http_compute, project, vmx_path):

    with asyncio_patch("gns3server.compute.vmware.vmware_vm.VMwareVM.create", return_value=True) as mock:
        response = http_compute.post("/projects/{project_id}/vmware/nodes".format(project_id=project.id), {
            "name": "VMTEST",
            "vmx_path": vmx_path,
            "linked_clone": False})
    assert mock.called
    assert response.status == 201, response.body.decode()
    return response.json


@pytest.yield_fixture
def vmx_path(tmpdir):
    """
    Return a fake VMX file
    """
    path = str(tmpdir / "test.vmx")
    with open(path, 'w+') as f:
        f.write("1")
    return path


def test_vmware_create(http_compute, project, vmx_path):

    with asyncio_patch("gns3server.compute.vmware.vmware_vm.VMwareVM.create", return_value=True):
        response = http_compute.post("/projects/{project_id}/vmware/nodes".format(project_id=project.id), {
            "name": "VM1",
            "vmx_path": vmx_path,
            "linked_clone": False},
            example=True)
        assert response.status == 201, response.body.decode()
        assert response.json["name"] == "VM1"
        assert response.json["project_id"] == project.id


def test_vmware_get(http_compute, project, vm):
    response = http_compute.get("/projects/{project_id}/vmware/nodes/{node_id}".format(project_id=vm["project_id"], node_id=vm["node_id"]), example=True)
    assert response.status == 200
    assert response.route == "/projects/{project_id}/vmware/nodes/{node_id}"
    assert response.json["name"] == "VMTEST"
    assert response.json["project_id"] == project.id


def test_vmware_start(http_compute, vm):
    with asyncio_patch("gns3server.compute.vmware.vmware_vm.VMwareVM.check_hw_virtualization", return_value=True) as mock:
        with asyncio_patch("gns3server.compute.vmware.vmware_vm.VMwareVM.start", return_value=True) as mock:
            response = http_compute.post("/projects/{project_id}/vmware/nodes/{node_id}/start".format(project_id=vm["project_id"], node_id=vm["node_id"]), example=True)
            assert mock.called
            assert response.status == 204


def test_vmware_stop(http_compute, vm):
    with asyncio_patch("gns3server.compute.vmware.vmware_vm.VMwareVM.stop", return_value=True) as mock:
        response = http_compute.post("/projects/{project_id}/vmware/nodes/{node_id}/stop".format(project_id=vm["project_id"], node_id=vm["node_id"]), example=True)
        assert mock.called
        assert response.status == 204


def test_vmware_suspend(http_compute, vm):
    with asyncio_patch("gns3server.compute.vmware.vmware_vm.VMwareVM.suspend", return_value=True) as mock:
        response = http_compute.post("/projects/{project_id}/vmware/nodes/{node_id}/suspend".format(project_id=vm["project_id"], node_id=vm["node_id"]), example=True)
        assert mock.called
        assert response.status == 204


def test_vmware_resume(http_compute, vm):
    with asyncio_patch("gns3server.compute.vmware.vmware_vm.VMwareVM.resume", return_value=True) as mock:
        response = http_compute.post("/projects/{project_id}/vmware/nodes/{node_id}/resume".format(project_id=vm["project_id"], node_id=vm["node_id"]), example=True)
        assert mock.called
        assert response.status == 204


def test_vmware_reload(http_compute, vm):
    with asyncio_patch("gns3server.compute.vmware.vmware_vm.VMwareVM.reload", return_value=True) as mock:
        response = http_compute.post("/projects/{project_id}/vmware/nodes/{node_id}/reload".format(project_id=vm["project_id"], node_id=vm["node_id"]), example=True)
        assert mock.called
        assert response.status == 204


def test_vmware_nio_create_udp(http_compute, vm):

    with asyncio_patch('gns3server.compute.vmware.vmware_vm.VMwareVM.adapter_add_nio_binding') as mock:
        response = http_compute.post("/projects/{project_id}/vmware/nodes/{node_id}/adapters/0/ports/0/nio".format(project_id=vm["project_id"],
                                                                                                                   node_id=vm["node_id"]), {"type": "nio_udp",
                                                                                                                                            "lport": 4242,
                                                                                                                                            "rport": 4343,
                                                                                                                                            "rhost": "127.0.0.1"},
                                     example=True)

        assert mock.called
        args, kwgars = mock.call_args
        assert args[0] == 0

    assert response.status == 201
    assert response.route == "/projects/{project_id}/vmware/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio"
    assert response.json["type"] == "nio_udp"


def test_vmware_nio_update_udp(http_compute, vm):
    with asyncio_patch('gns3server.compute.vmware.vmware_vm.VMwareVM._ubridge_send'):
        with asyncio_patch('gns3server.compute.vmware.vmware_vm.VMwareVM.ethernet_adapters'):
            with patch('gns3server.compute.vmware.vmware_vm.VMwareVM._get_vnet') as mock:
                response = http_compute.put("/projects/{project_id}/vmware/nodes/{node_id}/adapters/0/ports/0/nio".format(
                    project_id=vm["project_id"],
                    node_id=vm["node_id"]),
                    {
                        "type": "nio_udp",
                        "lport": 4242,
                        "rport": 4343,
                        "rhost": "127.0.0.1",
                        "filters": {}},
                    example=True)
                assert response.status == 201, response.body.decode()
                assert response.route == "/projects/{project_id}/vmware/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio"
                assert response.json["type"] == "nio_udp"


def test_vmware_delete_nio(http_compute, vm):

    with asyncio_patch('gns3server.compute.vmware.vmware_vm.VMwareVM.adapter_remove_nio_binding') as mock:
        response = http_compute.delete("/projects/{project_id}/vmware/nodes/{node_id}/adapters/0/ports/0/nio".format(project_id=vm["project_id"], node_id=vm["node_id"]), example=True)

        assert mock.called
        args, kwgars = mock.call_args
        assert args[0] == 0

    assert response.status == 204
    assert response.route == "/projects/{project_id}/vmware/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio"


def test_vmware_update(http_compute, vm, free_console_port):
    response = http_compute.put("/projects/{project_id}/vmware/nodes/{node_id}".format(project_id=vm["project_id"], node_id=vm["node_id"]), {"name": "test",
                                                                                                                                             "console": free_console_port},
                                example=True)
    assert response.status == 200
    assert response.json["name"] == "test"
    assert response.json["console"] == free_console_port
