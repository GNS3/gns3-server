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
from gns3server.controller.ports.ethernet_port import EthernetPort
from gns3server.controller.node import Node
from gns3server.controller.link import Link


@pytest.fixture
def compute(http_controller, async_run):
    compute = MagicMock()
    compute.id = "example.com"
    Controller.instance()._computes = {"example.com": compute}
    return compute


@pytest.fixture
def project(http_controller, async_run):
    return async_run(Controller.instance().add_project(name="Test"))


def test_create_link(http_controller, tmpdir, project, compute, async_run):
    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    node1 = async_run(project.add_node(compute, "node1", None, node_type="qemu"))
    node1._ports = [EthernetPort("E0", 0, 0, 3)]
    node2 = async_run(project.add_node(compute, "node2", None, node_type="qemu"))
    node2._ports = [EthernetPort("E0", 0, 2, 4)]

    with asyncio_patch("gns3server.controller.udp_link.UDPLink.create") as mock:
        response = http_controller.post("/projects/{}/links".format(project.id), {
            "nodes": [
                {
                    "node_id": node1.id,
                    "adapter_number": 0,
                    "port_number": 3,
                    "label": {
                        "text": "Text",
                        "x": 42,
                        "y": 0
                    }
                },
                {
                    "node_id": node2.id,
                    "adapter_number": 2,
                    "port_number": 4
                }
            ]
        }, example=True)
    assert mock.called
    assert response.status == 201
    assert response.json["link_id"] is not None
    assert len(response.json["nodes"]) == 2
    assert response.json["nodes"][0]["label"]["x"] == 42
    assert len(project.links) == 1


def test_create_link_failure(http_controller, tmpdir, project, compute, async_run):
    """
    Make sure the link is deleted if we failed to create the link.

    The failure is trigger by connecting the link to himself
    """
    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    node1 = async_run(project.add_node(compute, "node1", None, node_type="qemu"))
    node1._ports = [EthernetPort("E0", 0, 0, 3), EthernetPort("E0", 0, 0, 4)]

    with asyncio_patch("gns3server.controller.udp_link.UDPLink.create") as mock:
        response = http_controller.post("/projects/{}/links".format(project.id), {
            "nodes": [
                {
                    "node_id": node1.id,
                    "adapter_number": 0,
                    "port_number": 3,
                    "label": {
                        "text": "Text",
                        "x": 42,
                        "y": 0
                    }
                },
                {
                    "node_id": node1.id,
                    "adapter_number": 0,
                    "port_number": 4
                }
            ]
        }, example=True)
    #assert mock.called
    assert response.status == 409
    assert len(project.links) == 0


def test_update_link(http_controller, tmpdir, project, compute, async_run):
    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    node1 = async_run(project.add_node(compute, "node1", None, node_type="qemu"))
    node1._ports = [EthernetPort("E0", 0, 0, 3)]
    node2 = async_run(project.add_node(compute, "node2", None, node_type="qemu"))
    node2._ports = [EthernetPort("E0", 0, 2, 4)]

    with asyncio_patch("gns3server.controller.udp_link.UDPLink.create") as mock:
        response = http_controller.post("/projects/{}/links".format(project.id), {
            "nodes": [
                {
                    "node_id": node1.id,
                    "adapter_number": 0,
                    "port_number": 3,
                    "label": {
                        "text": "Text",
                        "x": 42,
                        "y": 0
                    }
                },
                {
                    "node_id": node2.id,
                    "adapter_number": 2,
                    "port_number": 4
                }
            ]
        })
    link_id = response.json["link_id"]
    assert response.json["nodes"][0]["label"]["x"] == 42
    response = http_controller.put("/projects/{}/links/{}".format(project.id, link_id), {
        "nodes": [
            {
                "node_id": node1.id,
                "adapter_number": 0,
                "port_number": 3,
                "label": {
                    "text": "Hello",
                    "x": 64,
                    "y": 0
                }
            },
            {
                "node_id": node2.id,
                "adapter_number": 2,
                "port_number": 4
            }
        ]
    })
    assert response.status == 201
    assert response.json["nodes"][0]["label"]["x"] == 64


def test_list_link(http_controller, tmpdir, project, compute, async_run):
    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    node1 = async_run(project.add_node(compute, "node1", None, node_type="qemu"))
    node1._ports = [EthernetPort("E0", 0, 0, 3)]
    node2 = async_run(project.add_node(compute, "node2", None, node_type="qemu"))
    node2._ports = [EthernetPort("E0", 0, 2, 4)]

    with asyncio_patch("gns3server.controller.udp_link.UDPLink.create") as mock:
        response = http_controller.post("/projects/{}/links".format(project.id), {
            "nodes": [
                {
                    "node_id": node1.id,
                    "adapter_number": 0,
                    "port_number": 3
                },
                {
                    "node_id": node2.id,
                    "adapter_number": 2,
                    "port_number": 4
                }
            ]
        })
    response = http_controller.get("/projects/{}/links".format(project.id), example=True)
    assert response.status == 200
    assert len(response.json) == 1


def test_start_capture(http_controller, tmpdir, project, compute, async_run):
    link = Link(project)
    project._links = {link.id: link}
    with asyncio_patch("gns3server.controller.link.Link.start_capture") as mock:
        response = http_controller.post("/projects/{}/links/{}/start_capture".format(project.id, link.id), example=True)
    assert mock.called
    assert response.status == 201


def test_stop_capture(http_controller, tmpdir, project, compute, async_run):
    link = Link(project)
    project._links = {link.id: link}
    with asyncio_patch("gns3server.controller.link.Link.stop_capture") as mock:
        response = http_controller.post("/projects/{}/links/{}/stop_capture".format(project.id, link.id), example=True)
    assert mock.called
    assert response.status == 201


def test_pcap(http_controller, tmpdir, project, compute, loop):
    @asyncio.coroutine
    def go(future):
        response = yield from aiohttp.request("GET", http_controller.get_url("/projects/{}/links/{}/pcap".format(project.id, link.id)))
        response.body = yield from response.content.read(5)
        response.close()
        future.set_result(response)

    link = Link(project)
    link._capture_file_name = "test"
    link._capturing = True
    with open(link.capture_file_path, "w+") as f:
        f.write("hello")
    project._links = {link.id: link}

    future = asyncio.Future()
    asyncio.async(go(future))
    response = loop.run_until_complete(future)
    assert response.status == 200
    assert b'hello' == response.body


def test_delete_link(http_controller, tmpdir, project, compute, async_run):

    link = Link(project)
    project._links = {link.id: link}
    with asyncio_patch("gns3server.controller.link.Link.delete") as mock:
        response = http_controller.delete("/projects/{}/links/{}".format(project.id, link.id), example=True)
    assert mock.called
    assert response.status == 204
