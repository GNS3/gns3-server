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

from unittest.mock import patch, MagicMock
from tests.utils import asyncio_patch, AsyncioMagicMock

from gns3server.controller.ports.ethernet_port import EthernetPort
from gns3server.controller.link import Link, FILTERS


@pytest.fixture
async def nodes(compute, project):

    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    node1 = await project.add_node(compute, "node1", None, node_type="qemu")
    node1._ports = [EthernetPort("E0", 0, 0, 3)]
    node2 = await project.add_node(compute, "node2", None, node_type="qemu")
    node2._ports = [EthernetPort("E0", 0, 2, 4)]
    return node1, node2


async def test_create_link(controller_api, project, nodes):

    node1, node2 = nodes

    filters = {
        "latency": [10],
        "frequency_drop": [50]
    }

    with asyncio_patch("gns3server.controller.udp_link.UDPLink.create") as mock:
        response = await controller_api.post("/projects/{}/links".format(project.id), {
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
            ],
            "filters": filters
        })

    assert mock.called
    assert response.status == 201
    assert response.json["link_id"] is not None
    assert len(response.json["nodes"]) == 2
    assert response.json["nodes"][0]["label"]["x"] == 42
    assert len(project.links) == 1
    assert list(project.links.values())[0].filters == filters


async def test_create_link_failure(controller_api, compute, project):
    """
    Make sure the link is deleted if we failed to create it.

    The failure is triggered by connecting the link to itself
    """

    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    node1 = await project.add_node(compute, "node1", None, node_type="qemu")
    node1._ports = [EthernetPort("E0", 0, 0, 3), EthernetPort("E0", 0, 0, 4)]

    response = await controller_api.post("/projects/{}/links".format(project.id), {
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
    })

    assert response.status == 409
    assert len(project.links) == 0


async def test_get_link(controller_api, project, nodes):

    node1, node2 = nodes
    with asyncio_patch("gns3server.controller.udp_link.UDPLink.create") as mock:
        response = await controller_api.post("/projects/{}/links".format(project.id), {
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

    assert mock.called
    link_id = response.json["link_id"]
    assert response.json["nodes"][0]["label"]["x"] == 42
    response = await controller_api.get("/projects/{}/links/{}".format(project.id, link_id))
    assert response.status == 200
    assert response.json["nodes"][0]["label"]["x"] == 42


async def test_update_link_suspend(controller_api, project, nodes):

    node1, node2 = nodes
    with asyncio_patch("gns3server.controller.udp_link.UDPLink.create") as mock:
        response = await controller_api.post("/projects/{}/links".format(project.id), {
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

    assert mock.called
    link_id = response.json["link_id"]
    assert response.json["nodes"][0]["label"]["x"] == 42

    response = await controller_api.put("/projects/{}/links/{}".format(project.id, link_id), {
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
        ],
        "suspend": True
    })

    assert response.status == 201
    assert response.json["nodes"][0]["label"]["x"] == 64
    assert response.json["suspend"]
    assert response.json["filters"] == {}


async def test_update_link(controller_api, project, nodes):

    filters = {
        "latency": [10],
        "frequency_drop": [50]
    }

    node1, node2 = nodes
    with asyncio_patch("gns3server.controller.udp_link.UDPLink.create") as mock:
        response = await controller_api.post("/projects/{}/links".format(project.id), {
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

    assert mock.called
    link_id = response.json["link_id"]
    assert response.json["nodes"][0]["label"]["x"] == 42

    response = await controller_api.put("/projects/{}/links/{}".format(project.id, link_id), {
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
        ],
        "filters": filters
    })

    assert response.status == 201
    assert response.json["nodes"][0]["label"]["x"] == 64
    assert list(project.links.values())[0].filters == filters


async def test_list_link(controller_api, project, nodes):

    filters = {
        "latency": [10],
        "frequency_drop": [50]
    }

    node1, node2 = nodes
    nodes = [
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
    with asyncio_patch("gns3server.controller.udp_link.UDPLink.create") as mock:
        await controller_api.post("/projects/{}/links".format(project.id), {
            "nodes": nodes,
            "filters": filters
        })

    assert mock.called
    response = await controller_api.get("/projects/{}/links".format(project.id))
    assert response.status == 200
    assert len(response.json) == 1
    assert response.json[0]["filters"] == filters


async def test_start_capture(controller_api, project):

    link = Link(project)
    project._links = {link.id: link}
    with asyncio_patch("gns3server.controller.link.Link.start_capture") as mock:
        response = await controller_api.post("/projects/{}/links/{}/start_capture".format(project.id, link.id))
    assert mock.called
    assert response.status == 201


async def test_stop_capture(controller_api, project):

    link = Link(project)
    project._links = {link.id: link}
    with asyncio_patch("gns3server.controller.link.Link.stop_capture") as mock:
        response = await controller_api.post("/projects/{}/links/{}/stop_capture".format(project.id, link.id))
    assert mock.called
    assert response.status == 201


# async def test_pcap(controller_api, http_client, project):
#
#     async def pcap_capture():
#         async with http_client.get(controller_api.get_url("/projects/{}/links/{}/pcap".format(project.id, link.id))) as response:
#             response.body = await response.content.read(5)
#             print("READ", response.body)
#             return response
#
#     with asyncio_patch("gns3server.controller.link.Link.capture_node") as mock:
#         link = Link(project)
#         link._capture_file_name = "test"
#         link._capturing = True
#         with open(link.capture_file_path, "w+") as f:
#             f.write("hello")
#         project._links = {link.id: link}
#         response = await pcap_capture()
#         assert mock.called
#         assert response.status == 200
#         assert b'hello' == response.body


async def test_delete_link(controller_api, project):

    link = Link(project)
    project._links = {link.id: link}
    with asyncio_patch("gns3server.controller.link.Link.delete") as mock:
        response = await controller_api.delete("/projects/{}/links/{}".format(project.id, link.id))
    assert mock.called
    assert response.status == 204


async def test_list_filters(controller_api, project):

    link = Link(project)
    project._links = {link.id: link}
    with patch("gns3server.controller.link.Link.available_filters", return_value=FILTERS) as mock:
        response = await controller_api.get("/projects/{}/links/{}/available_filters".format(project.id, link.id))
    assert mock.called
    assert response.status == 200
    assert response.json == FILTERS
