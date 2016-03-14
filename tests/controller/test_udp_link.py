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
import asyncio
import aiohttp
from unittest.mock import MagicMock

from gns3server.controller.project import Project
from gns3server.controller.hypervisor import Hypervisor
from gns3server.controller.udp_link import UDPLink
from gns3server.controller.vm import VM


@pytest.fixture
def project():
    return Project()


def test_create(async_run, project):
    hypervisor1 = MagicMock()
    hypervisor2 = MagicMock()

    vm1 = VM(project, hypervisor1, vm_type="vpcs")
    vm2 = VM(project, hypervisor2, vm_type="vpcs")

    link = UDPLink(project)
    async_run(link.addVM(vm1, 0, 4))
    async_run(link.addVM(vm2, 3, 1))

    @asyncio.coroutine
    def hypervisor1_callback(path, data={}):
        """
        Fake server
        """
        if "/ports/udp" in path:
            response = MagicMock()
            response.json = {"udp_port": 1024}
            return response

    @asyncio.coroutine
    def hypervisor2_callback(path, data={}):
        """
        Fake server
        """
        if "/ports/udp" in path:
            response = MagicMock()
            response.json = {"udp_port": 2048}
            return response

    hypervisor1.post.side_effect = hypervisor1_callback
    hypervisor1.host = "example.com"
    hypervisor2.post.side_effect = hypervisor2_callback
    hypervisor2.host = "example.org"
    async_run(link.create())

    hypervisor1.post.assert_any_call("/projects/{}/vpcs/vms/{}/adapters/0/ports/4/nio".format(project.id, vm1.id), data={
        "lport": 1024,
        "rhost": hypervisor2.host,
        "rport": 2048,
        "type": "nio_udp"
    })
    hypervisor2.post.assert_any_call("/projects/{}/vpcs/vms/{}/adapters/3/ports/1/nio".format(project.id, vm2.id), data={
        "lport": 2048,
        "rhost": hypervisor1.host,
        "rport": 1024,
        "type": "nio_udp"
    })



def test_delete(async_run, project):
    hypervisor1 = MagicMock()
    hypervisor2 = MagicMock()

    vm1 = VM(project, hypervisor1, vm_type="vpcs")
    vm2 = VM(project, hypervisor2, vm_type="vpcs")

    link = UDPLink(project)
    async_run(link.addVM(vm1, 0, 4))
    async_run(link.addVM(vm2, 3, 1))

    async_run(link.delete())

    hypervisor1.delete.assert_any_call("/projects/{}/vpcs/vms/{}/adapters/0/ports/4/nio".format(project.id, vm1.id))
    hypervisor2.delete.assert_any_call("/projects/{}/vpcs/vms/{}/adapters/3/ports/1/nio".format(project.id, vm2.id))
