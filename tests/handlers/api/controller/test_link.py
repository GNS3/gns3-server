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

"""
This test suite check /project endpoint
"""

import uuid
import os
import asyncio
import aiohttp
import pytest


from unittest.mock import patch, MagicMock, PropertyMock
from tests.utils import asyncio_patch, AsyncioMagicMock

from gns3server.handlers.api.controller.project_handler import ProjectHandler
from gns3server.controller import Controller
from gns3server.controller.vm import VM
from gns3server.controller.link import Link


@pytest.fixture
def compute(http_controller, async_run):
    compute = MagicMock()
    compute.id = "example.com"
    Controller.instance()._computes = {"example.com": compute}
    return compute


@pytest.fixture
def project(http_controller, async_run):
    return async_run(Controller.instance().addProject())


def test_create_link(http_controller, tmpdir, project, compute, async_run):
    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    vm1 = async_run(project.addVM(compute, None))
    vm2 = async_run(project.addVM(compute, None))

    with asyncio_patch("gns3server.controller.udp_link.UDPLink.create") as mock:
        response = http_controller.post("/projects/{}/links".format(project.id), {
            "vms": [
                {
                    "vm_id": vm1.id,
                    "adapter_number": 0,
                    "port_number": 3
                },
                {
                    "vm_id": vm2.id,
                    "adapter_number": 2,
                    "port_number": 4
                }
            ]
        }, example=True)
    assert mock.called
    assert response.status == 201
    assert response.json["link_id"] is not None
    assert len(response.json["vms"]) == 2


def test_start_capture(http_controller, tmpdir, project, compute, async_run):
    link = Link(project)
    project._links = {link.id: link}
    with asyncio_patch("gns3server.controller.link.Link.start_capture") as mock:
        response = http_controller.post("/projects/{}/links/{}/start_capture".format(project.id, link.id), example=True)
    assert mock.called
    assert response.status == 204


def test_stop_capture(http_controller, tmpdir, project, compute, async_run):
    link = Link(project)
    project._links = {link.id: link}
    with asyncio_patch("gns3server.controller.link.Link.stop_capture") as mock:
        response = http_controller.post("/projects/{}/links/{}/stop_capture".format(project.id, link.id), example=True)
    assert mock.called
    assert response.status == 204


def test_delete_link(http_controller, tmpdir, project, compute, async_run):

    link = Link(project)
    project._links = {link.id: link}
    with asyncio_patch("gns3server.controller.link.Link.delete") as mock:
        response = http_controller.delete("/projects/{}/links/{}".format(project.id, link.id), example=True)
    assert mock.called
    assert response.status == 204
