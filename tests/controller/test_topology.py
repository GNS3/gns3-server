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

from unittest.mock import MagicMock
from tests.utils import asyncio_patch

from gns3server.controller.project import Project
from gns3server.controller.compute import Compute
from gns3server.controller.topology import project_to_topology
from gns3server.version import __version__


def test_project_to_topology_empty(tmpdir):
    project = Project(name="Test")
    topo = project_to_topology(project)
    assert topo == {
        "project_id": project.id,
        "name": "Test",
        "revision": 5,
        "topology": {
            "nodes": [],
            "links": [],
            "computes": []
        },
        "type": "topology",
        "version": __version__
    }


def test_basic_topology(tmpdir, async_run, controller):
    project = Project(name="Test", controller=controller)
    compute = Compute("my_compute", controller)
    compute.http_query = MagicMock()

    with asyncio_patch("gns3server.controller.node.Node.create"):
        node1 = async_run(project.add_node(compute, "Node 1", "node_1"))
        node2 = async_run(project.add_node(compute, "Node 2", "node_2"))

    link = async_run(project.add_link())
    async_run(link.add_node(node1, 0, 0))
    async_run(link.add_node(node2, 0, 0))

    topo = project_to_topology(project)
    assert len(topo["topology"]["nodes"]) == 2
    assert node1.__json__() in topo["topology"]["nodes"]
    assert topo["topology"]["links"][0] == link.__json__()
    assert topo["topology"]["computes"][0] == compute.__json__()

