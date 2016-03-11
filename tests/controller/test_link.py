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

from gns3server.controller.link import Link
from gns3server.controller.vm import VM
from gns3server.controller.hypervisor import Hypervisor
from gns3server.controller.project import Project


@pytest.fixture
def project():
    return Project()


@pytest.fixture
def hypervisor():
    return Hypervisor("example.com")


def test_addVM(async_run, project, hypervisor):
    vm1 = VM(project, hypervisor)

    link = Link(project)
    async_run(link.addVM(vm1, 0, 4))
    assert link._vms == [
        {
            "vm": vm1,
            "adapter_number": 0,
            "port_number": 4
        }
    ]


def test_json(async_run, project, hypervisor):
    vm1 = VM(project, hypervisor)
    vm2 = VM(project, hypervisor)

    link = Link(project)
    async_run(link.addVM(vm1, 0, 4))
    async_run(link.addVM(vm2, 1, 3))
    assert link.__json__() == {
        "link_id": link.id,
        "vms": [
            {
                "vm_id": vm1.id,
                "adapter_number": 0,
                "port_number": 4
            },
            {
                "vm_id": vm2.id,
                "adapter_number": 1,
                "port_number": 3
            }
        ]
    }
