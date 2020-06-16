#!/usr/bin/env python
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


import json
import pytest
import aiohttp

from tests.utils import asyncio_patch

from gns3server.controller.compute import Compute
from gns3server.controller.project import Project


@pytest.fixture
def demo_topology():
    """
    A topology with two VPCS connected and a rectangle
    """

    return {
        "auto_close": True,
        "auto_open": False,
        "auto_start": False,
        "scene_height": 500,
        "scene_width": 700,
        "name": "demo",
        "project_id": "3c1be6f9-b4ba-4737-b209-63c47c23359f",
        "revision": 5,
        "topology": {
            "computes": [
                {
                    "compute_id": "local",
                    "host": "127.0.0.1",
                    "name": "atlantis",
                    "port": 3080,
                    "protocol": "http"
                }
            ],
            "drawings": [
                {
                    "drawing_id": "48bdaa23-326a-4de0-bf7d-cc22709689ec",
                    "rotation": 0,
                    "svg": "<svg height=\"100\" width=\"200\"><rect fill=\"#ffffff\" fill-opacity=\"1.0\" height=\"100\" stroke=\"#000000\" stroke-width=\"2\" width=\"200\" /></svg>",
                    "x": -226,
                    "y": 57,
                    "z": 0
                }
            ],
            "links": [
                {
                    "link_id": "5a3e3a64-e853-4055-9503-4a14e01290f1",
                    "nodes": [
                        {
                            "adapter_number": 0,
                            "label": {
                                "rotation": 0,
                                "style": "font-family: TypeWriter;font-size: 10;font-weight: bold;fill: #000000;fill-opacity: 1.0;",
                                "text": "Ethernet0",
                                "x": 72,
                                "y": 32
                            },
                            "node_id": "64ba8408-afbf-4b66-9cdd-1fd854427478",
                            "port_number": 0
                        },
                        {
                            "adapter_number": 0,
                            "label": {
                                "rotation": 0,
                                "style": "font-family: TypeWriter;font-size: 10;font-weight: bold;fill: #000000;fill-opacity: 1.0;",
                                "text": "Ethernet0",
                                "x": -7,
                                "y": 26
                            },
                            "node_id": "748bcd89-624a-40eb-a8d3-1d2e85c99b51",
                            "port_number": 0
                        }
                    ]
                }
            ],
            "nodes": [
                {
                    "compute_id": "local",
                    "console": 5000,
                    "console_type": "telnet",
                    "height": 59,
                    "label": {
                        "rotation": 0,
                        "style": "font-family: TypeWriter;font-size: 10;font-weight: bold;fill: #000000;fill-opacity: 1.0;",
                        "text": "PC1",
                        "x": 18,
                        "y": -25
                    },
                    "name": "PC1",
                    "node_id": "64ba8408-afbf-4b66-9cdd-1fd854427478",
                    "node_type": "vpcs",
                    "properties": {
                    },
                    "symbol": ":/symbols/computer.svg",
                    "width": 65,
                    "x": -300,
                    "y": -118,
                    "z": 1
                },
                {
                    "compute_id": "vm",
                    "console": 5001,
                    "console_type": "telnet",
                    "height": 59,
                    "label": {
                        "rotation": 0,
                        "style": "font-family: TypeWriter;font-size: 10;font-weight: bold;fill: #000000;fill-opacity: 1.0;",
                        "text": "PC2",
                        "x": 18,
                        "y": -25
                    },
                    "name": "PC2",
                    "node_id": "748bcd89-624a-40eb-a8d3-1d2e85c99b51",
                    "node_type": "vpcs",
                    "properties": {
                    },
                    "symbol": ":/symbols/computer.svg",
                    "width": 65,
                    "x": -71,
                    "y": -98,
                    "z": 1
                }
            ]
        },
        "type": "topology",
        "version": "2.0.0"
    }


# async def test_load_project(controller, tmpdir, demo_topology, http_client):
#
#     with open(str(tmpdir / "demo.gns3"), "w+") as f:
#         json.dump(demo_topology, f)
#
#     controller._computes["local"] = Compute("local", controller=controller, host=http_client.host, port=http_client.port)
#     controller._computes["vm"] = controller._computes["local"]
#
#     with asyncio_patch("gns3server.compute.vpcs.vpcs_vm.VPCSVM.add_ubridge_udp_connection"):
#         project = await controller.load_project(str(tmpdir / "demo.gns3"))
#
#     assert project.status == "opened"
#     assert len(project.computes) == 1
#     assert len(project.nodes) == 2
#     assert project.nodes["64ba8408-afbf-4b66-9cdd-1fd854427478"].name == "PC1"
#     assert len(project.links) == 1
#     assert project.links["5a3e3a64-e853-4055-9503-4a14e01290f1"].created
#     assert len(project.drawings) == 1
#
#     assert project.name == "demo"
#     assert project.scene_height == 500
#     assert project.scene_width == 700


async def test_open(controller, tmpdir):

    simple_topology = {
        "auto_close": True,
        "auto_open": False,
        "auto_start": False,
        "scene_height": 500,
        "scene_width": 700,
        "name": "demo",
        "project_id": "3c1be6f9-b4ba-4737-b209-63c47c23359f",
        "revision": 5,
        "topology": {
            "computes": [],
            "drawings": [],
            "links": [],
            "nodes": []
        },
        "type": "topology",
        "version": "2.0.0"
    }

    with open(str(tmpdir / "demo.gns3"), "w+") as f:
        json.dump(simple_topology, f)

    project = Project(name="demo",
                      project_id="64ba8408-afbf-4b66-9cdd-1fd854427478",
                      path=str(tmpdir),
                      controller=controller,
                      filename="demo.gns3",
                      status="closed")

    await project.open()
    assert project.status == "opened"
    assert project.name == "demo"
    assert project.scene_height == 500
    assert project.scene_width == 700


# async def test_open_missing_compute(controller, tmpdir, demo_topology, http_client):
#     """
#     If a compute is missing the project should not be open and the .gns3 should
#     be the one before opening the project
#     """
#
#     with open(str(tmpdir / "demo.gns3"), "w+") as f:
#         json.dump(demo_topology, f)
#
#     controller._computes["local"] = Compute("local", controller=controller, host=http_client.host, port=http_client.port)
#
#     with pytest.raises(aiohttp.web_exceptions.HTTPNotFound):
#         await controller.load_project(str(tmpdir / "demo.gns3"))
#     assert controller.get_project("3c1be6f9-b4ba-4737-b209-63c47c23359f").status == "closed"
#     with open(str(tmpdir / "demo.gns3"), "r") as f:
#         topo = json.load(f)
#         assert len(topo["topology"]["nodes"]) == 2
