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
from gns3server.controller.compute import Compute
from gns3server.controller.udp_link import UDPLink
from gns3server.controller.vm import VM


@pytest.fixture
def project():
    return Project()


def test_create(async_run, project):
    compute1 = MagicMock()
    compute2 = MagicMock()

    vm1 = VM(project, compute1, vm_type="vpcs")
    vm2 = VM(project, compute2, vm_type="vpcs")

    link = UDPLink(project)
    async_run(link.addVM(vm1, 0, 4))
    async_run(link.addVM(vm2, 3, 1))

    @asyncio.coroutine
    def compute1_callback(path, data={}):
        """
        Fake server
        """
        if "/ports/udp" in path:
            response = MagicMock()
            response.json = {"udp_port": 1024}
            return response

    @asyncio.coroutine
    def compute2_callback(path, data={}):
        """
        Fake server
        """
        if "/ports/udp" in path:
            response = MagicMock()
            response.json = {"udp_port": 2048}
            return response

    compute1.post.side_effect = compute1_callback
    compute1.host = "example.com"
    compute2.post.side_effect = compute2_callback
    compute2.host = "example.org"
    async_run(link.create())

    compute1.post.assert_any_call("/projects/{}/vpcs/vms/{}/adapters/0/ports/4/nio".format(project.id, vm1.id), data={
        "lport": 1024,
        "rhost": compute2.host,
        "rport": 2048,
        "type": "nio_udp"
    })
    compute2.post.assert_any_call("/projects/{}/vpcs/vms/{}/adapters/3/ports/1/nio".format(project.id, vm2.id), data={
        "lport": 2048,
        "rhost": compute1.host,
        "rport": 1024,
        "type": "nio_udp"
    })


def test_delete(async_run, project):
    compute1 = MagicMock()
    compute2 = MagicMock()

    vm1 = VM(project, compute1, vm_type="vpcs")
    vm2 = VM(project, compute2, vm_type="vpcs")

    link = UDPLink(project)
    async_run(link.addVM(vm1, 0, 4))
    async_run(link.addVM(vm2, 3, 1))

    async_run(link.delete())

    compute1.delete.assert_any_call("/projects/{}/vpcs/vms/{}/adapters/0/ports/4/nio".format(project.id, vm1.id))
    compute2.delete.assert_any_call("/projects/{}/vpcs/vms/{}/adapters/3/ports/1/nio".format(project.id, vm2.id))


def test_choose_capture_side(async_run, project):
    """
    The link capture should run on the optimal node
    """
    compute1 = MagicMock()
    compute2 = MagicMock()
    compute2.id = "local"

    vm_vpcs = VM(project, compute1, vm_type="vpcs")
    vm_iou = VM(project, compute2, vm_type="iou")

    link = UDPLink(project)
    async_run(link.addVM(vm_vpcs, 0, 4))
    async_run(link.addVM(vm_iou, 3, 1))

    assert link._choose_capture_side()["vm"] == vm_iou

    vm_vpcs = VM(project, compute1, vm_type="vpcs")
    vm_vpcs2 = VM(project, compute1, vm_type="vpcs")

    link = UDPLink(project)
    async_run(link.addVM(vm_vpcs, 0, 4))
    async_run(link.addVM(vm_vpcs2, 3, 1))

    # VPCS doesn't support capture
    with pytest.raises(aiohttp.web.HTTPConflict):
        link._choose_capture_side()["vm"]

    # Capture should run on the local node
    vm_iou = VM(project, compute1, vm_type="iou")
    vm_iou2 = VM(project, compute2, vm_type="iou")

    link = UDPLink(project)
    async_run(link.addVM(vm_iou, 0, 4))
    async_run(link.addVM(vm_iou2, 3, 1))

    assert link._choose_capture_side()["vm"] == vm_iou2


def test_capture(async_run, project):
    compute1 = MagicMock()

    vm_vpcs = VM(project, compute1, vm_type="vpcs", name="V1")
    vm_iou = VM(project, compute1, vm_type="iou", name="I1")

    link = UDPLink(project)
    async_run(link.addVM(vm_vpcs, 0, 4))
    async_run(link.addVM(vm_iou, 3, 1))

    capture = async_run(link.start_capture())

    compute1.post.assert_any_call("/projects/{}/iou/vms/{}/adapters/3/ports/1/start_capture".format(project.id, vm_iou.id), data={
        "capture_file_name": link.capture_file_name(),
        "data_link_type": "DLT_EN10MB"
    })

    capture = async_run(link.stop_capture())

    compute1.post.assert_any_call("/projects/{}/iou/vms/{}/adapters/3/ports/1/stop_capture".format(project.id, vm_iou.id))

