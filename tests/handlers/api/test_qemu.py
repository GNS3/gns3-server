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
from tests.utils import asyncio_patch
from unittest.mock import patch


@pytest.fixture
def fake_qemu_bin():

    bin_path = os.path.join(os.environ["PATH"], "qemu_x42")
    with open(bin_path, "w+") as f:
        f.write("1")
    os.chmod(bin_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    return bin_path


@pytest.fixture
def base_params(tmpdir, fake_qemu_bin):
    """Return standard parameters"""
    return {"name": "PC TEST 1", "qemu_path": fake_qemu_bin}


@pytest.fixture
def vm(server, project, base_params):
    response = server.post("/projects/{project_id}/qemu/vms".format(project_id=project.id), base_params)
    assert response.status == 201
    return response.json


def test_qemu_create(server, project, base_params):
    response = server.post("/projects/{project_id}/qemu/vms".format(project_id=project.id), base_params)
    assert response.status == 201
    assert response.route == "/projects/{project_id}/qemu/vms"
    assert response.json["name"] == "PC TEST 1"
    assert response.json["project_id"] == project.id


def test_qemu_create_with_params(server, project, base_params):
    params = base_params
    params["ram"] = 1024
    params["hda_disk_image"] = "/tmp/hda"

    response = server.post("/projects/{project_id}/qemu/vms".format(project_id=project.id), params, example=True)
    assert response.status == 201
    assert response.route == "/projects/{project_id}/qemu/vms"
    assert response.json["name"] == "PC TEST 1"
    assert response.json["project_id"] == project.id
    assert response.json["ram"] == 1024
    assert response.json["hda_disk_image"] == "/tmp/hda"


def test_qemu_get(server, project, vm):
    response = server.get("/projects/{project_id}/qemu/vms/{vm_id}".format(project_id=vm["project_id"], vm_id=vm["vm_id"]), example=True)
    assert response.status == 200
    assert response.route == "/projects/{project_id}/qemu/vms/{vm_id}"
    assert response.json["name"] == "PC TEST 1"
    assert response.json["project_id"] == project.id


def test_qemu_start(server, vm):
    with asyncio_patch("gns3server.modules.qemu.qemu_vm.QemuVM.start", return_value=True) as mock:
        response = server.post("/projects/{project_id}/qemu/vms/{vm_id}/start".format(project_id=vm["project_id"], vm_id=vm["vm_id"]), example=True)
        assert mock.called
        assert response.status == 204


def test_qemu_stop(server, vm):
    with asyncio_patch("gns3server.modules.qemu.qemu_vm.QemuVM.stop", return_value=True) as mock:
        response = server.post("/projects/{project_id}/qemu/vms/{vm_id}/stop".format(project_id=vm["project_id"], vm_id=vm["vm_id"]), example=True)
        assert mock.called
        assert response.status == 204


def test_qemu_reload(server, vm):
    with asyncio_patch("gns3server.modules.qemu.qemu_vm.QemuVM.reload", return_value=True) as mock:
        response = server.post("/projects/{project_id}/qemu/vms/{vm_id}/reload".format(project_id=vm["project_id"], vm_id=vm["vm_id"]), example=True)
        assert mock.called
        assert response.status == 204


def test_qemu_suspend(server, vm):
    with asyncio_patch("gns3server.modules.qemu.qemu_vm.QemuVM.suspend", return_value=True) as mock:
        response = server.post("/projects/{project_id}/qemu/vms/{vm_id}/suspend".format(project_id=vm["project_id"], vm_id=vm["vm_id"]), example=True)
        assert mock.called
        assert response.status == 204


def test_qemu_resume(server, vm):
    with asyncio_patch("gns3server.modules.qemu.qemu_vm.QemuVM.resume", return_value=True) as mock:
        response = server.post("/projects/{project_id}/qemu/vms/{vm_id}/resume".format(project_id=vm["project_id"], vm_id=vm["vm_id"]), example=True)
        assert mock.called
        assert response.status == 204


def test_qemu_delete(server, vm):
    with asyncio_patch("gns3server.modules.qemu.Qemu.delete_vm", return_value=True) as mock:
        response = server.delete("/projects/{project_id}/qemu/vms/{vm_id}".format(project_id=vm["project_id"], vm_id=vm["vm_id"]), example=True)
        assert mock.called
        assert response.status == 204


def test_qemu_update(server, vm, tmpdir, free_console_port, project):
    params = {
        "name": "test",
        "console": free_console_port,
        "ram": 1024,
        "hdb_disk_image": "/tmp/hdb"
    }
    response = server.put("/projects/{project_id}/qemu/vms/{vm_id}".format(project_id=vm["project_id"], vm_id=vm["vm_id"]), params, example=True)
    assert response.status == 200
    assert response.json["name"] == "test"
    assert response.json["console"] == free_console_port
    assert response.json["hdb_disk_image"] == "/tmp/hdb"
    assert response.json["ram"] == 1024


def test_qemu_nio_create_udp(server, vm):
    server.put("/projects/{project_id}/qemu/vms/{vm_id}".format(project_id=vm["project_id"], vm_id=vm["vm_id"]), {"adapters": 2})
    response = server.post("/projects/{project_id}/qemu/vms/{vm_id}/adapters/1/ports/0/nio".format(project_id=vm["project_id"], vm_id=vm["vm_id"]), {"type": "nio_udp",
                                                                                                                                                     "lport": 4242,
                                                                                                                                                     "rport": 4343,
                                                                                                                                                     "rhost": "127.0.0.1"},
                           example=True)
    assert response.status == 201
    assert response.route == "/projects/{project_id}/qemu/vms/{vm_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio"
    assert response.json["type"] == "nio_udp"


def test_qemu_nio_create_ethernet(server, vm):
    server.put("/projects/{project_id}/qemu/vms/{vm_id}".format(project_id=vm["project_id"], vm_id=vm["vm_id"]), {"adapters": 2})
    response = server.post("/projects/{project_id}/qemu/vms/{vm_id}/adapters/1/ports/0/nio".format(project_id=vm["project_id"], vm_id=vm["vm_id"]), {"type": "nio_generic_ethernet",
                                                                                                                                                     "ethernet_device": "eth0",
                                                                                                                                                     },
                           example=True)
    assert response.status == 409


def test_qemu_delete_nio(server, vm):
    server.put("/projects/{project_id}/qemu/vms/{vm_id}".format(project_id=vm["project_id"], vm_id=vm["vm_id"]), {"adapters": 2})
    server.post("/projects/{project_id}/qemu/vms/{vm_id}/adapters/1/ports/0/nio".format(project_id=vm["project_id"], vm_id=vm["vm_id"]), {"type": "nio_udp",
                                                                                                                                          "lport": 4242,
                                                                                                                                          "rport": 4343,
                                                                                                                                          "rhost": "127.0.0.1"})
    response = server.delete("/projects/{project_id}/qemu/vms/{vm_id}/adapters/1/ports/0/nio".format(project_id=vm["project_id"], vm_id=vm["vm_id"]), example=True)
    assert response.status == 204
    assert response.route == "/projects/{project_id}/qemu/vms/{vm_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio"


def test_qemu_list_binaries(server, vm):
    ret = [{"path": "/tmp/1", "version": "2.2.0"},
           {"path": "/tmp/2", "version": "2.1.0"}]
    with asyncio_patch("gns3server.modules.qemu.Qemu.binary_list", return_value=ret) as mock:
        response = server.get("/qemu/binaries".format(project_id=vm["project_id"]), example=True)
        assert mock.called
        assert response.status == 200
        assert response.json == ret
