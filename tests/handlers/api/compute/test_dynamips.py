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
import sys
import os
import stat
from unittest.mock import patch

from tests.utils import asyncio_patch


# @pytest.yield_fixture(scope="module")
# async def vm(compute_api, compute_project, fake_image):
#
#     dynamips_path = "/fake/dynamips"
#     params = {
#         "name": "My router",
#         "platform": "c3745",
#         "image": fake_image,
#         "ram": 128
#     }
#     with asyncio_patch("gns3server.compute.dynamips.nodes.router.Router.create", return_value=True) as mock:
#         response = await compute_api.post("/projects/{project_id}/dynamips/nodes".format(project_id=compute_project.id), params)
#     assert mock.called
#     assert response.status == 201
#
#     #with asyncio_patch("gns3server.compute.dynamips.Dynamips.find_dynamips", return_value=dynamips_path):
#     #    yield response.json


# async def test_dynamips_vm_create(compute_api, compute_project, fake_image):
#
#     params = {
#         "name": "My router",
#         "platform": "c3745",
#         "image": os.path.basename(fake_image),
#         "ram": 128
#     }
#
#     print(fake_image)
#
#     with asyncio_patch("gns3server.compute.dynamips.nodes.router.Router.create", return_value=True):
#         response = await compute_api.post("/projects/{project_id}/dynamips/nodes".format(project_id=compute_project.id), params)
#         assert response.status == 201
#         assert response.json["name"] == "My router"
#         assert response.json["project_id"] == compute_project.id
#         assert response.json["dynamips_id"]


# def test_dynamips_vm_get(compute_api, project, vm):
#     response = compute_api.get("/projects/{project_id}/dynamips/nodes/{node_id}".format(project_id=vm["project_id"], node_id=vm["node_id"]), example=True)
#     assert response.status == 200
#     assert response.route == "/projects/{project_id}/dynamips/nodes/{node_id}"
#     assert response.json["name"] == "My router"
#     assert response.json["project_id"] == project.id
#
#
# def test_dynamips_vm_start(compute_api, vm):
#     with asyncio_patch("gns3server.compute.dynamips.nodes.router.Router.start", return_value=True) as mock:
#         response = compute_api.post("/projects/{project_id}/dynamips/nodes/{node_id}/start".format(project_id=vm["project_id"], node_id=vm["node_id"]))
#         assert mock.called
#         assert response.status == 204
#
#
# def test_dynamips_vm_stop(compute_api, vm):
#     with asyncio_patch("gns3server.compute.dynamips.nodes.router.Router.stop", return_value=True) as mock:
#         response = compute_api.post("/projects/{project_id}/dynamips/nodes/{node_id}/stop".format(project_id=vm["project_id"], node_id=vm["node_id"]))
#         assert mock.called
#         assert response.status == 204
#
#
# def test_dynamips_vm_suspend(compute_api, vm):
#     with asyncio_patch("gns3server.compute.dynamips.nodes.router.Router.suspend", return_value=True) as mock:
#         response = compute_api.post("/projects/{project_id}/dynamips/nodes/{node_id}/suspend".format(project_id=vm["project_id"], node_id=vm["node_id"]))
#         assert mock.called
#         assert response.status == 204
#
#
# def test_dynamips_vm_resume(compute_api, vm):
#     with asyncio_patch("gns3server.compute.dynamips.nodes.router.Router.resume", return_value=True) as mock:
#         response = compute_api.post("/projects/{project_id}/dynamips/nodes/{node_id}/resume".format(project_id=vm["project_id"], node_id=vm["node_id"]))
#         assert mock.called
#         assert response.status == 204


# def test_vbox_nio_create_udp(compute_api, vm):
#
#     with asyncio_patch('gns3server.compute.virtualbox.virtualbox_vm.VirtualBoxVM.adapter_add_nio_binding') as mock:
#         response = compute_api.post("/projects/{project_id}/virtualbox/nodes/{node_id}/adapters/0/nio".format(project_id=vm["project_id"],
#                                                                                                      node_id=vm["node_id"]), {"type": "nio_udp",
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
#     assert response.route == "/projects/{project_id}/virtualbox/nodes/{node_id}/adapters/{adapter_id:\d+}/nio"
#     assert response.json["type"] == "nio_udp"
#
#
# def test_vbox_delete_nio(compute_api, vm):
#
#     with asyncio_patch('gns3server.compute.virtualbox.virtualbox_vm.VirtualBoxVM.adapter_remove_nio_binding') as mock:
#         response = compute_api.delete("/projects/{project_id}/virtualbox/nodes/{node_id}/adapters/0/nio".format(project_id=vm["project_id"], node_id=vm["node_id"]), example=True)
#
#         assert mock.called
#         args, kwgars = mock.call_args
#         assert args[0] == 0
#
#     assert response.status == 204
#     assert response.route == "/projects/{project_id}/virtualbox/nodes/{node_id}/adapters/{adapter_id:\d+}/nio"
#
#
# def test_vbox_update(compute_api, vm, free_console_port):
#     response = compute_api.put("/projects/{project_id}/virtualbox/nodes/{node_id}".format(project_id=vm["project_id"], node_id=vm["node_id"]), {"name": "test",
#                                                                                                                                    "console": free_console_port})
#     assert response.status == 200
#     assert response.json["name"] == "test"
#     assert response.json["console"] == free_console_port


@pytest.fixture
def fake_image(tmpdir):
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


async def test_images(compute_api, tmpdir, fake_image, fake_file):

    with patch("gns3server.utils.images.default_images_directory", return_value=str(tmpdir)):
        response = await compute_api.get("/dynamips/images")
    assert response.status == 200
    assert response.json == [{"filename": "7200.bin",
                              "path": "7200.bin",
                              "filesize": 7,
                              "md5sum": "b0d5aa897d937aced5a6b1046e8f7e2e"
                              }]


async def test_upload_image(compute_api, images_dir):

    response = await compute_api.post("/dynamips/images/test2", body="TEST", raw=True)
    assert response.status == 204

    with open(os.path.join(images_dir, "IOS", "test2")) as f:
        assert f.read() == "TEST"

    with open(os.path.join(images_dir, "IOS", "test2.md5sum")) as f:
        checksum = f.read()
        assert checksum == "033bd94b1168d7e4f0d644c3c95e35bf"


@pytest.mark.skipif(not sys.platform.startswith("win") and os.getuid() == 0, reason="Root can delete any image")
async def test_upload_image_permission_denied(compute_api, images_dir):

    os.makedirs(os.path.join(images_dir, "IOS"), exist_ok=True)
    with open(os.path.join(images_dir, "IOS", "test2.tmp"), "w+") as f:
        f.write("")
    os.chmod(os.path.join(images_dir, "IOS", "test2.tmp"), 0)

    response = await compute_api.post("/dynamips/images/test2", body="TEST", raw=True)
    assert response.status == 409
