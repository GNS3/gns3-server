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

import pytest
from unittest.mock import MagicMock
from tests.utils import AsyncioMagicMock

from gns3server.controller.udp_link import UDPLink
from gns3server.controller.ports.ethernet_port import EthernetPort
from gns3server.controller.node import Node
from gns3server.controller.controller_error import ControllerError


@pytest.mark.asyncio
async def test_create(project):

    compute1 = MagicMock()
    compute2 = MagicMock()

    node1 = Node(project, compute1, "node1", node_type="vpcs")
    node1._ports = [EthernetPort("E0", 0, 0, 4)]
    node2 = Node(project, compute2, "node2", node_type="vpcs")
    node2._ports = [EthernetPort("E0", 0, 3, 1)]

    async def subnet_callback(compute2):
        """
        Fake subnet callback
        """
        return ("192.168.1.1", "192.168.1.2")

    compute1.get_ip_on_same_subnet.side_effect = subnet_callback

    link = UDPLink(project)
    await link.add_node(node1, 0, 4)
    await link.update_filters({"latency": [10]})

    async def compute1_callback(path, data={}, **kwargs):
        """
        Fake server
        """
        if "/ports/udp" in path:
            response = MagicMock()
            response.json = {"udp_port": 1024}
            return response

    async def compute2_callback(path, data={}, **kwargs):
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
    await link.add_node(node2, 3, 1)

    compute1.post.assert_any_call("/projects/{}/vpcs/nodes/{}/adapters/0/ports/4/nio".format(project.id, node1.id), data={
        "lport": 1024,
        "rhost": "192.168.1.2",
        "rport": 2048,
        "type": "nio_udp",
        "filters": {"latency": [10]},
        "suspend": False,
    }, timeout=120)

    compute2.post.assert_any_call("/projects/{}/vpcs/nodes/{}/adapters/3/ports/1/nio".format(project.id, node2.id), data={
        "lport": 2048,
        "rhost": "192.168.1.1",
        "rport": 1024,
        "type": "nio_udp",
        "filters": {},
        "suspend": False,
    }, timeout=120)


@pytest.mark.asyncio
async def test_create_one_side_failure(project):

    compute1 = MagicMock()
    compute2 = MagicMock()

    node1 = Node(project, compute1, "node1", node_type="vpcs")
    node1._ports = [EthernetPort("E0", 0, 0, 4)]
    node2 = Node(project, compute2, "node2", node_type="vpcs")
    node2._ports = [EthernetPort("E0", 0, 3, 1)]

    async def subnet_callback(compute2):
        """
        Fake subnet callback
        """
        return ("192.168.1.1", "192.168.1.2")

    compute1.get_ip_on_same_subnet.side_effect = subnet_callback

    link = UDPLink(project)
    await link.add_node(node1, 0, 4)

    async def compute1_callback(path, data={}, **kwargs):
        """
        Fake server
        """
        if "/ports/udp" in path:
            response = MagicMock()
            response.json = {"udp_port": 1024}
            return response

    async def compute2_callback(path, data={}, **kwargs):
        """
        Fake server
        """
        if "/ports/udp" in path:
            response = MagicMock()
            response.json = {"udp_port": 2048}
            return response
        elif "/adapters" in path:
            raise ControllerError("Error when creating the NIO")

    compute1.post.side_effect = compute1_callback
    compute1.host = "example.com"
    compute2.post.side_effect = compute2_callback
    compute2.host = "example.org"
    with pytest.raises(ControllerError):
        await link.add_node(node2, 3, 1)

    compute1.post.assert_any_call("/projects/{}/vpcs/nodes/{}/adapters/0/ports/4/nio".format(project.id, node1.id), data={
        "lport": 1024,
        "rhost": "192.168.1.2",
        "rport": 2048,
        "type": "nio_udp",
        "filters": {},
        "suspend": False,
    }, timeout=120)

    compute2.post.assert_any_call("/projects/{}/vpcs/nodes/{}/adapters/3/ports/1/nio".format(project.id, node2.id), data={
        "lport": 2048,
        "rhost": "192.168.1.1",
        "rport": 1024,
        "type": "nio_udp",
        "filters": {},
        "suspend": False,
    }, timeout=120)
    # The link creation has failed we rollback the nio
    compute1.delete.assert_any_call("/projects/{}/vpcs/nodes/{}/adapters/0/ports/4/nio".format(project.id, node1.id), timeout=120)


@pytest.mark.asyncio
async def test_delete(project):

    compute1 = MagicMock()
    compute2 = MagicMock()

    node1 = Node(project, compute1, "node1", node_type="vpcs")
    node1._ports = [EthernetPort("E0", 0, 0, 4)]
    node2 = Node(project, compute2, "node2", node_type="vpcs")
    node2._ports = [EthernetPort("E0", 0, 3, 1)]

    link = UDPLink(project)
    link.create = AsyncioMagicMock()
    await link.add_node(node1, 0, 4)
    await link.add_node(node2, 3, 1)

    await link.delete()

    compute1.delete.assert_any_call("/projects/{}/vpcs/nodes/{}/adapters/0/ports/4/nio".format(project.id, node1.id), timeout=120)
    compute2.delete.assert_any_call("/projects/{}/vpcs/nodes/{}/adapters/3/ports/1/nio".format(project.id, node2.id), timeout=120)


@pytest.mark.asyncio
async def test_choose_capture_side(project):
    """
    The link capture should run on the optimal node
    """

    compute1 = MagicMock()
    compute2 = MagicMock()
    compute2.id = "local"

    # Capture should run on the local node
    node_vpcs = Node(project, compute1, "node1", node_type="vpcs")
    node_vpcs._status = "started"
    node_vpcs._ports = [EthernetPort("E0", 0, 0, 4)]
    node_iou = Node(project, compute2, "node2", node_type="iou")
    node_iou._status = "started"
    node_iou._ports = [EthernetPort("E0", 0, 3, 1)]

    link = UDPLink(project)
    link.create = AsyncioMagicMock()
    await link.add_node(node_vpcs, 0, 4)
    await link.add_node(node_iou, 3, 1)

    assert link._choose_capture_side()["node"] == node_iou

    # Capture should choose always running node
    node_iou = Node(project, compute1, "node5", node_type="iou")
    node_iou._status = "started"
    node_iou._ports = [EthernetPort("E0", 0, 0, 4)]
    node_switch = Node(project, compute1, "node6", node_type="ethernet_switch")
    node_switch._status = "started"
    node_switch._ports = [EthernetPort("E0", 0, 3, 1)]

    link = UDPLink(project)
    link.create = AsyncioMagicMock()
    await link.add_node(node_iou, 0, 4)
    await link.add_node(node_switch, 3, 1)

    assert link._choose_capture_side()["node"] == node_switch

    # Capture should raise error if node are not started
    node_vpcs = Node(project, compute1, "node1", node_type="vpcs")
    node_vpcs._ports = [EthernetPort("E0", 0, 0, 4)]
    node_iou = Node(project, compute2, "node2", node_type="iou")
    node_iou._ports = [EthernetPort("E0", 0, 3, 1)]

    link = UDPLink(project)
    link.create = AsyncioMagicMock()
    await link.add_node(node_vpcs, 0, 4)
    await link.add_node(node_iou, 3, 1)

    with pytest.raises(ControllerError):
        link._choose_capture_side()
    # If you start a node you can capture on it
    node_vpcs._status = "started"
    assert link._choose_capture_side()["node"] == node_vpcs


@pytest.mark.asyncio
async def test_capture(project):
    compute1 = MagicMock()

    node_vpcs = Node(project, compute1, "V1", node_type="vpcs")
    node_vpcs._status = "started"
    node_vpcs._ports = [EthernetPort("E0", 0, 0, 4)]
    node_iou = Node(project, compute1, "I1", node_type="iou")
    node_iou._ports = [EthernetPort("E0", 0, 3, 1)]

    link = UDPLink(project)
    link.create = AsyncioMagicMock()
    await link.add_node(node_vpcs, 0, 4)
    await link.add_node(node_iou, 3, 1)

    await link.start_capture()
    assert link.capturing

    compute1.post.assert_any_call("/projects/{}/vpcs/nodes/{}/adapters/0/ports/4/capture/start".format(project.id, node_vpcs.id), data={
        "capture_file_name": link.default_capture_file_name(),
        "data_link_type": "DLT_EN10MB"
    })

    await link.stop_capture()
    assert link.capturing is False

    compute1.post.assert_any_call("/projects/{}/vpcs/nodes/{}/adapters/0/ports/4/capture/stop".format(project.id, node_vpcs.id))


@pytest.mark.asyncio
async def test_node_updated(project):
    """
    If a node stop when capturing we stop the capture
    """

    compute1 = MagicMock()
    node_vpcs = Node(project, compute1, "V1", node_type="vpcs")
    node_vpcs._status = "started"

    link = UDPLink(project)
    link._capture_node = {"node": node_vpcs}
    link.stop_capture = AsyncioMagicMock()

    await link.node_updated(node_vpcs)
    assert not link.stop_capture.called

    node_vpcs._status = "stopped"
    await link.node_updated(node_vpcs)
    assert link.stop_capture.called


@pytest.mark.asyncio
async def test_update(project):

    compute1 = MagicMock()
    compute2 = MagicMock()

    node1 = Node(project, compute1, "node1", node_type="vpcs")
    node1._ports = [EthernetPort("E0", 0, 0, 4)]
    node2 = Node(project, compute2, "node2", node_type="vpcs")
    node2._ports = [EthernetPort("E0", 0, 3, 1)]

    async def subnet_callback(compute2):
        """
        Fake subnet callback
        """
        return ("192.168.1.1", "192.168.1.2")

    compute1.get_ip_on_same_subnet.side_effect = subnet_callback

    link = UDPLink(project)
    await link.add_node(node1, 0, 4)
    await link.update_filters({"latency": [10]})

    async def compute1_callback(path, data={}, **kwargs):
        """
        Fake server
        """
        if "/ports/udp" in path:
            response = MagicMock()
            response.json = {"udp_port": 1024}
            return response

    async def compute2_callback(path, data={}, **kwargs):
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
    await link.add_node(node2, 3, 1)

    compute1.post.assert_any_call("/projects/{}/vpcs/nodes/{}/adapters/0/ports/4/nio".format(project.id, node1.id), data={
        "lport": 1024,
        "rhost": "192.168.1.2",
        "rport": 2048,
        "type": "nio_udp",
        "suspend": False,
        "filters": {"latency": [10]}
    }, timeout=120)

    compute2.post.assert_any_call("/projects/{}/vpcs/nodes/{}/adapters/3/ports/1/nio".format(project.id, node2.id), data={
        "lport": 2048,
        "rhost": "192.168.1.1",
        "rport": 1024,
        "type": "nio_udp",
        "suspend": False,
        "filters": {}
    }, timeout=120)

    assert link.created
    await link.update_filters({"drop": [5], "bpf": ["icmp[icmptype] == 8"]})
    compute1.put.assert_any_call("/projects/{}/vpcs/nodes/{}/adapters/0/ports/4/nio".format(project.id, node1.id), data={
        "lport": 1024,
        "rhost": "192.168.1.2",
        "rport": 2048,
        "type": "nio_udp",
        "suspend": False,
        "filters": {
            "drop": [5],
            "bpf": ["icmp[icmptype] == 8"]
        }
    }, timeout=120)


@pytest.mark.asyncio
async def test_update_suspend(project):
    compute1 = MagicMock()
    compute2 = MagicMock()

    node1 = Node(project, compute1, "node1", node_type="vpcs")
    node1._ports = [EthernetPort("E0", 0, 0, 4)]
    node2 = Node(project, compute2, "node2", node_type="vpcs")
    node2._ports = [EthernetPort("E0", 0, 3, 1)]

    async def subnet_callback(compute2):
        """
        Fake subnet callback
        """
        return ("192.168.1.1", "192.168.1.2")

    compute1.get_ip_on_same_subnet.side_effect = subnet_callback

    link = UDPLink(project)
    await link.add_node(node1, 0, 4)
    await link.update_filters({"latency": [10]})
    await link.update_suspend(True)

    async def compute1_callback(path, data={}, **kwargs):
        """
        Fake server
        """
        if "/ports/udp" in path:
            response = MagicMock()
            response.json = {"udp_port": 1024}
            return response

    async def compute2_callback(path, data={}, **kwargs):
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
    await link.add_node(node2, 3, 1)

    compute1.post.assert_any_call("/projects/{}/vpcs/nodes/{}/adapters/0/ports/4/nio".format(project.id, node1.id), data={
        "lport": 1024,
        "rhost": "192.168.1.2",
        "rport": 2048,
        "type": "nio_udp",
        "filters": {"frequency_drop": [-1]},
        "suspend": True
    }, timeout=120)

    compute2.post.assert_any_call("/projects/{}/vpcs/nodes/{}/adapters/3/ports/1/nio".format(project.id, node2.id), data={
        "lport": 2048,
        "rhost": "192.168.1.1",
        "rport": 1024,
        "type": "nio_udp",
        "filters": {},
        "suspend": True
    }, timeout=120)
