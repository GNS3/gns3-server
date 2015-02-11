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
def fake_iou_bin(tmpdir):
    """Create a fake IOU image on disk"""

    path = str(tmpdir / "iou.bin")
    with open(path, "w+") as f:
        f.write('\x7fELF\x01\x01\x01')
    os.chmod(path, stat.S_IREAD | stat.S_IEXEC)
    return path


@pytest.fixture
def base_params(tmpdir, fake_iou_bin):
    """Return standard parameters"""
    return {"name": "PC TEST 1", "iou_path": fake_iou_bin, "iourc_path": str(tmpdir / "iourc")}


@pytest.fixture
def vm(server, project, base_params):
    response = server.post("/projects/{project_id}/iou/vms".format(project_id=project.id), base_params)
    assert response.status == 201
    return response.json


def test_iou_create(server, project, base_params):
    response = server.post("/projects/{project_id}/iou/vms".format(project_id=project.id), base_params, example=True)
    assert response.status == 201
    assert response.route == "/projects/{project_id}/iou/vms"
    assert response.json["name"] == "PC TEST 1"
    assert response.json["project_id"] == project.id


def test_iou_get(server, project, vm):
    response = server.get("/projects/{project_id}/iou/vms/{vm_id}".format(project_id=vm["project_id"], vm_id=vm["vm_id"]), example=True)
    assert response.status == 200
    assert response.route == "/projects/{project_id}/iou/vms/{vm_id}"
    assert response.json["name"] == "PC TEST 1"
    assert response.json["project_id"] == project.id


def test_iou_start(server, vm):
    with asyncio_patch("gns3server.modules.iou.iou_vm.IOUVM.start", return_value=True) as mock:
        response = server.post("/projects/{project_id}/iou/vms/{vm_id}/start".format(project_id=vm["project_id"], vm_id=vm["vm_id"]))
        assert mock.called
        assert response.status == 204


def test_iou_stop(server, vm):
    with asyncio_patch("gns3server.modules.iou.iou_vm.IOUVM.stop", return_value=True) as mock:
        response = server.post("/projects/{project_id}/iou/vms/{vm_id}/stop".format(project_id=vm["project_id"], vm_id=vm["vm_id"]))
        assert mock.called
        assert response.status == 204


def test_iou_reload(server, vm):
    with asyncio_patch("gns3server.modules.iou.iou_vm.IOUVM.reload", return_value=True) as mock:
        response = server.post("/projects/{project_id}/iou/vms/{vm_id}/reload".format(project_id=vm["project_id"], vm_id=vm["vm_id"]))
        assert mock.called
        assert response.status == 204


def test_iou_delete(server, vm):
    with asyncio_patch("gns3server.modules.iou.IOU.delete_vm", return_value=True) as mock:
        response = server.delete("/projects/{project_id}/iou/vms/{vm_id}".format(project_id=vm["project_id"], vm_id=vm["vm_id"]))
        assert mock.called
        assert response.status == 204


def test_iou_update(server, vm, tmpdir, free_console_port):
    response = server.put("/projects/{project_id}/iou/vms/{vm_id}".format(project_id=vm["project_id"], vm_id=vm["vm_id"]), {"name": "test",
                                                                                                                            "console": free_console_port})
    assert response.status == 200
    assert response.json["name"] == "test"
    assert response.json["console"] == free_console_port
