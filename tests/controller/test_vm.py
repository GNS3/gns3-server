#!/usr/bin/env python
#
# Copyright (C) 2016 GNS3 Technologies Inc.
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
from unittest.mock import MagicMock


from gns3server.controller.vm import VM
from gns3server.controller.project import Project


@pytest.fixture
def hypervisor():
    s = MagicMock()
    s.id = "http://test.com:42"
    return s


@pytest.fixture
def vm(hypervisor):
    project = Project(str(uuid.uuid4()))
    vm = VM(project, hypervisor,
            name="demo",
            vm_id=str(uuid.uuid4()),
            vm_type="vpcs",
            console_type="vnc",
            properties={"startup_script": "echo test"})
    return vm


def test_json(vm, hypervisor):
    assert vm.__json__() == {
        "hypervisor_id": hypervisor.id,
        "project_id": vm.project.id,
        "vm_id": vm.id,
        "vm_type": vm.vm_type,
        "name": "demo",
        "console": vm.console,
        "console_type": vm.console_type,
        "properties": vm.properties
    }


def test_init_without_uuid(project, hypervisor):
    vm = VM(project, hypervisor,
            vm_type="vpcs",
            console_type="vnc")
    assert vm.id is not None


def test_create(vm, hypervisor, project, async_run):
    async_run(vm.create())
    data = {
        "console": None,
        "console_type": "vnc",
        "vm_id": vm.id,
        "startup_script": "echo test",
        "name": "demo"
    }
    hypervisor.post.assert_called_with("/projects/{}/vpcs/vms".format(vm.project.id), data=data)


def test_post(vm, hypervisor, async_run):
    async_run(vm.post("/test", {"a": "b"}))
    hypervisor.post.assert_called_with("/projects/{}/vpcs/vms/{}/test".format(vm.project.id, vm.id), data={"a": "b"})


def test_delete(vm, hypervisor, async_run):
    async_run(vm.delete("/test"))
    hypervisor.delete.assert_called_with("/projects/{}/vpcs/vms/{}/test".format(vm.project.id, vm.id))
