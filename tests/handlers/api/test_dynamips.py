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
from unittest.mock import patch

from tests.utils import asyncio_patch


# @pytest.yield_fixture(scope="module")
# def vm(server, project):
#
#     dynamips_path = "/fake/dynamips"
#     with asyncio_patch("gns3server.modules.dynamips.nodes.router.Router.create", return_value=True) as mock:
#         response = server.post("/projects/{project_id}/dynamips/vms".format(project_id=project.id), {"name": "My router",
#                                                                                                      "platform": "c3745",
#                                                                                                      "image": "somewhere",
#                                                                                                      "ram": 128})
#     assert mock.called
#     assert response.status == 201
#
#     with asyncio_patch("gns3server.modules.dynamips.Dynamips.find_dynamips", return_value=dynamips_path):
#         yield response.json
#
#
# def test_dynamips_vm_create(server, project):
#
#     with asyncio_patch("gns3server.modules.dynamips.nodes.router.Router.create", return_value=True):
#         response = server.post("/projects/{project_id}/dynamips/vms".format(project_id=project.id), {"name": "My router",
#                                                                                                      "platform": "c3745",
#                                                                                                      "image": "somewhere",
#                                                                                                      "ram": 128},
#                                example=True)
#         assert response.status == 201
#         assert response.json["name"] == "My router"
#         assert response.json["project_id"] == project.id
#         assert response.json["dynamips_id"]
#
#
# def test_dynamips_vm_get(server, project, vm):
#     response = server.get("/projects/{project_id}/dynamips/vms/{vm_id}".format(project_id=vm["project_id"], vm_id=vm["vm_id"]), example=True)
#     assert response.status == 200
#     assert response.route == "/projects/{project_id}/dynamips/vms/{vm_id}"
#     assert response.json["name"] == "My router"
#     assert response.json["project_id"] == project.id
#
#
# def test_dynamips_vm_start(server, vm):
#     with asyncio_patch("gns3server.modules.dynamips.nodes.router.Router.start", return_value=True) as mock:
#         response = server.post("/projects/{project_id}/dynamips/vms/{vm_id}/start".format(project_id=vm["project_id"], vm_id=vm["vm_id"]))
#         assert mock.called
#         assert response.status == 204
#
#
# def test_dynamips_vm_stop(server, vm):
#     with asyncio_patch("gns3server.modules.dynamips.nodes.router.Router.stop", return_value=True) as mock:
#         response = server.post("/projects/{project_id}/dynamips/vms/{vm_id}/stop".format(project_id=vm["project_id"], vm_id=vm["vm_id"]))
#         assert mock.called
#         assert response.status == 204
#
#
# def test_dynamips_vm_suspend(server, vm):
#     with asyncio_patch("gns3server.modules.dynamips.nodes.router.Router.suspend", return_value=True) as mock:
#         response = server.post("/projects/{project_id}/dynamips/vms/{vm_id}/suspend".format(project_id=vm["project_id"], vm_id=vm["vm_id"]))
#         assert mock.called
#         assert response.status == 204
#
#
# def test_dynamips_vm_resume(server, vm):
#     with asyncio_patch("gns3server.modules.dynamips.nodes.router.Router.resume", return_value=True) as mock:
#         response = server.post("/projects/{project_id}/dynamips/vms/{vm_id}/resume".format(project_id=vm["project_id"], vm_id=vm["vm_id"]))
#         assert mock.called
#         assert response.status == 204


# def test_vbox_nio_create_udp(server, vm):
#
#     with asyncio_patch('gns3server.modules.virtualbox.virtualbox_vm.VirtualBoxVM.adapter_add_nio_binding') as mock:
#         response = server.post("/projects/{project_id}/virtualbox/vms/{vm_id}/adapters/0/nio".format(project_id=vm["project_id"],
#                                                                                                      vm_id=vm["vm_id"]), {"type": "nio_udp",
#                                                                                                                           "lport": 4242,
#                                                                                                                           "rport": 4343,
#                                                                                                                           "rhost": "127.0.0.1"},
#                                example=True)
#
#         assert mock.called
#         args, kwgars = mock.call_args
#         assert args[0] == 0
#
#     assert response.status == 201
#     assert response.route == "/projects/{project_id}/virtualbox/vms/{vm_id}/adapters/{adapter_id:\d+}/nio"
#     assert response.json["type"] == "nio_udp"
#
#
# def test_vbox_delete_nio(server, vm):
#
#     with asyncio_patch('gns3server.modules.virtualbox.virtualbox_vm.VirtualBoxVM.adapter_remove_nio_binding') as mock:
#         response = server.delete("/projects/{project_id}/virtualbox/vms/{vm_id}/adapters/0/nio".format(project_id=vm["project_id"], vm_id=vm["vm_id"]), example=True)
#
#         assert mock.called
#         args, kwgars = mock.call_args
#         assert args[0] == 0
#
#     assert response.status == 204
#     assert response.route == "/projects/{project_id}/virtualbox/vms/{vm_id}/adapters/{adapter_id:\d+}/nio"
#
#
# def test_vbox_update(server, vm, free_console_port):
#     response = server.put("/projects/{project_id}/virtualbox/vms/{vm_id}".format(project_id=vm["project_id"], vm_id=vm["vm_id"]), {"name": "test",
#                                                                                                                                    "console": free_console_port})
#     assert response.status == 200
#     assert response.json["name"] == "test"
#     assert response.json["console"] == free_console_port


@pytest.fixture
def fake_dynamips(tmpdir):
    """Create a fake Dynamips image on disk"""

    path = str(tmpdir / "7200.bin")
    with open(path, "wb+") as f:
        f.write(b'\x7fELF\x01\x02\x01')
    os.chmod(path, stat.S_IREAD)
    return path


@pytest.fixture
def fake_file(tmpdir):
    """Create a fake file disk"""

    path = str(tmpdir / "7200.txt")
    with open(path, "w+") as f:
        f.write('1')
    os.chmod(path, stat.S_IREAD)
    return path


def test_vms(server, tmpdir, fake_dynamips, fake_file):

    with patch("gns3server.modules.Dynamips.get_images_directory", return_value=str(tmpdir), example=True):
        response = server.get("/dynamips/vms")
    assert response.status == 200
    assert response.json == [{"filename": "7200.bin", "path": "7200.bin"}]


def test_upload_vm(server, tmpdir):
    with patch("gns3server.modules.Dynamips.get_images_directory", return_value=str(tmpdir),):
        response = server.post("/dynamips/vms/test2", body="TEST", raw=True)
        assert response.status == 204

    with open(str(tmpdir / "test2")) as f:
        assert f.read() == "TEST"

    with open(str(tmpdir / "test2.md5sum")) as f:
        checksum = f.read()
        assert checksum == "033bd94b1168d7e4f0d644c3c95e35bf"


def test_upload_vm_permission_denied(server, tmpdir):
    with open(str(tmpdir / "test2.tmp"), "w+") as f:
        f.write("")
    os.chmod(str(tmpdir / "test2.tmp"), 0)

    with patch("gns3server.modules.Dynamips.get_images_directory", return_value=str(tmpdir),):
        response = server.post("/dynamips/vms/test2", body="TEST", raw=True)
        assert response.status == 409
