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


@pytest.fixture(scope="module")
def vm(server, project):
    with asyncio_patch("gns3server.modules.virtualbox.virtualbox_vm.VirtualBoxVM.create", return_value=True) as mock:
        response = server.post("/virtualbox", {"name": "VM1",
                                               "vmname": "VM1",
                                               "linked_clone": False,
                                               "project_uuid": project.uuid})
    assert mock.called
    assert response.status == 201
    return response.json


def test_vbox_create(server, project):

    with asyncio_patch("gns3server.modules.virtualbox.virtualbox_vm.VirtualBoxVM.create", return_value=True):
        response = server.post("/virtualbox", {"name": "VM1",
                                               "vmname": "VM1",
                                               "linked_clone": False,
                                               "project_uuid": project.uuid},
                               example=True)
        assert response.status == 201
        assert response.json["name"] == "VM1"
        assert response.json["project_uuid"] == project.uuid


def test_vbox_start(server, vm):
    with asyncio_patch("gns3server.modules.virtualbox.virtualbox_vm.VirtualBoxVM.start", return_value=True) as mock:
        response = server.post("/virtualbox/{}/start".format(vm["uuid"]))
        assert mock.called
        assert response.status == 204


def test_vbox_stop(server, vm):
    with asyncio_patch("gns3server.modules.virtualbox.virtualbox_vm.VirtualBoxVM.stop", return_value=True) as mock:
        response = server.post("/virtualbox/{}/stop".format(vm["uuid"]))
        assert mock.called
        assert response.status == 204


def test_vbox_suspend(server, vm):
    with asyncio_patch("gns3server.modules.virtualbox.virtualbox_vm.VirtualBoxVM.suspend", return_value=True) as mock:
        response = server.post("/virtualbox/{}/suspend".format(vm["uuid"]))
        assert mock.called
        assert response.status == 204


def test_vbox_resume(server, vm):
    with asyncio_patch("gns3server.modules.virtualbox.virtualbox_vm.VirtualBoxVM.resume", return_value=True) as mock:
        response = server.post("/virtualbox/{}/resume".format(vm["uuid"]))
        assert mock.called
        assert response.status == 204


def test_vbox_reload(server, vm):
    with asyncio_patch("gns3server.modules.virtualbox.virtualbox_vm.VirtualBoxVM.reload", return_value=True) as mock:
        response = server.post("/virtualbox/{}/reload".format(vm["uuid"]))
        assert mock.called
        assert response.status == 204
