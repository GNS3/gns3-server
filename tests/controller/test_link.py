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
import pytest_asyncio
from unittest.mock import MagicMock

from gns3server.controller.link import Link
from gns3server.controller.node import Node
from gns3server.controller.ports.ethernet_port import EthernetPort
from gns3server.controller.ports.serial_port import SerialPort
from gns3server.controller.controller_error import ControllerError
from tests.utils import AsyncioBytesIO, AsyncioMagicMock


@pytest_asyncio.fixture
async def link(project, compute):

    node1 = Node(project, compute, "node1", node_type="qemu")
    node1._ports = [EthernetPort("E0", 0, 0, 4)]
    node2 = Node(project, compute, "node2", node_type="qemu")
    node2._ports = [EthernetPort("E0", 0, 1, 3)]

    link = Link(project)
    link.create = AsyncioMagicMock()
    await link.add_node(node1, 0, 4)
    await link.add_node(node2, 1, 3)
    return link


def test_eq(project, link):

    assert link == Link(project, link_id=link.id)
    assert link != "a"
    assert link != Link(project)


@pytest.mark.asyncio
async def test_add_node(project, compute):

    node1 = Node(project, compute, "node1", node_type="qemu")
    node1._ports = [EthernetPort("E0", 0, 0, 4)]
    link = Link(project)
    link.create = AsyncioMagicMock()
    link._project.emit_notification = MagicMock()
    project.dump = AsyncioMagicMock()
    await link.add_node(node1, 0, 4)
    assert link._nodes == [
        {
            "node": node1,
            "port": node1._ports[0],
            "adapter_number": 0,
            "port_number": 4,
            'label': {
                'text': '0/4',
                'style': 'font-family: TypeWriter;font-size: 10.0;font-weight: bold;fill: #000000;fill-opacity: 1.0;'
            }
        }
    ]
    assert project.dump.called
    assert not link._project.emit_notification.called
    assert not link.create.called

    # We call link.created only when both side are created
    node2 = Node(project, compute, "node2", node_type="qemu")
    node2._ports = [EthernetPort("E0", 0, 0, 4)]
    await link.add_node(node2, 0, 4)

    assert link.create.called
    link._project.emit_notification.assert_called_with("link.created", link.asdict())
    assert link in node2.links


@pytest.mark.asyncio
async def test_add_node_already_connected(project, compute):
    """
    Raise an error if we try to use an already connected port
    """

    project.dump = AsyncioMagicMock()

    node1 = Node(project, compute, "node1", node_type="qemu")
    node1._ports = [EthernetPort("E0", 0, 0, 4)]

    link = Link(project)
    link.create = AsyncioMagicMock()
    link._project.emit_notification = MagicMock()
    await link.add_node(node1, 0, 4)
    node2 = Node(project, compute, "node2", node_type="qemu")
    node2._ports = [EthernetPort("E0", 0, 0, 4)]
    await link.add_node(node2, 0, 4)

    assert link.create.called
    link2 = Link(project)
    link2.create = AsyncioMagicMock()
    with pytest.raises(ControllerError):
        await link2.add_node(node1, 0, 4)


@pytest.mark.asyncio
async def test_add_node_cloud(project, compute):

    node1 = Node(project, compute, "node1", node_type="qemu")
    node1._ports = [EthernetPort("E0", 0, 0, 4)]
    node2 = Node(project, compute, "node2", node_type="cloud")
    node2._ports = [EthernetPort("E0", 0, 0, 4)]

    link = Link(project)
    link.create = AsyncioMagicMock()
    link._project.emit_notification = MagicMock()

    await link.add_node(node1, 0, 4)
    await link.add_node(node2, 0, 4)


@pytest.mark.asyncio
async def test_add_node_cloud_to_cloud(project, compute):
    """
    Cloud to cloud connection is not allowed
    """

    node1 = Node(project, compute, "node1", node_type="cloud")
    node1._ports = [EthernetPort("E0", 0, 0, 4)]
    node2 = Node(project, compute, "node2", node_type="cloud")
    node2._ports = [EthernetPort("E0", 0, 0, 4)]

    link = Link(project)
    link.create = AsyncioMagicMock()
    link._project.emit_notification = MagicMock()

    await link.add_node(node1, 0, 4)
    with pytest.raises(ControllerError):
        await link.add_node(node2, 0, 4)


@pytest.mark.asyncio
async def test_add_node_same_node(project, compute):
    """
    Connection to the same node is not allowed
    """

    node1 = Node(project, compute, "node1", node_type="qemu")
    node1._ports = [EthernetPort("E0", 0, 0, 4), EthernetPort("E1", 0, 0, 5)]

    link = Link(project)
    link.create = AsyncioMagicMock()
    link._project.emit_notification = MagicMock()

    await link.add_node(node1, 0, 4)
    with pytest.raises(ControllerError):
        await link.add_node(node1, 0, 5)


@pytest.mark.asyncio
async def test_add_node_serial_to_ethernet(project, compute):
    """
    Serial to ethernet connection is not allowed
    """

    node1 = Node(project, compute, "node1", node_type="qemu")
    node1._ports = [EthernetPort("E0", 0, 0, 4)]
    node2 = Node(project, compute, "node2", node_type="qemu")
    node2._ports = [SerialPort("E0", 0, 0, 4)]

    link = Link(project)
    link.create = AsyncioMagicMock()
    link._project.emit_notification = MagicMock()

    await link.add_node(node1, 0, 4)
    with pytest.raises(ControllerError):
        await link.add_node(node2, 0, 4)


@pytest.mark.asyncio
async def test_json(project, compute):

    node1 = Node(project, compute, "node1", node_type="qemu")
    node1._ports = [EthernetPort("E0", 0, 0, 4)]
    node2 = Node(project, compute, "node2", node_type="qemu")
    node2._ports = [EthernetPort("E0", 0, 1, 3)]

    link = Link(project)
    link.create = AsyncioMagicMock()
    await link.add_node(node1, 0, 4)
    await link.add_node(node2, 1, 3)
    assert link.asdict() == {
        "link_id": link.id,
        "project_id": project.id,
        "nodes": [
            {
                "node_id": node1.id,
                "adapter_number": 0,
                "port_number": 4,
                'label': {
                    'text': '0/4',
                    'style': 'font-family: TypeWriter;font-size: 10.0;font-weight: bold;fill: #000000;fill-opacity: 1.0;'
                }
            },
            {
                "node_id": node2.id,
                "adapter_number": 1,
                "port_number": 3,
                'label': {
                    'text': '1/3',
                    'style': 'font-family: TypeWriter;font-size: 10.0;font-weight: bold;fill: #000000;fill-opacity: 1.0;'
                }
            }
        ],
        "filters": {},
        "link_style": {},
        "suspend": False,
        "link_type": "ethernet",
        "capturing": False,
        "capture_file_name": None,
        "capture_file_path": None,
        "capture_compute_id": None
    }
    assert link.asdict(topology_dump=True) == {
        "link_id": link.id,
        "nodes": [
            {
                "node_id": node1.id,
                "adapter_number": 0,
                "port_number": 4,
                'label': {
                    'text': '0/4',
                    'style': 'font-family: TypeWriter;font-size: 10.0;font-weight: bold;fill: #000000;fill-opacity: 1.0;'
                }
            },
            {
                "node_id": node2.id,
                "adapter_number": 1,
                "port_number": 3,
                'label': {
                    'text': '1/3',
                    'style': 'font-family: TypeWriter;font-size: 10.0;font-weight: bold;fill: #000000;fill-opacity: 1.0;'
                }
            }
        ],
        "link_style": {},
        "filters": {},
        "suspend": False
    }


@pytest.mark.asyncio
async def test_json_serial_link(project, compute):

    node1 = Node(project, compute, "node1", node_type="qemu")
    node1._ports = [SerialPort("S0", 0, 0, 4)]
    node2 = Node(project, compute, "node2", node_type="qemu")
    node2._ports = [SerialPort("S0", 0, 1, 3)]

    link = Link(project)
    link.create = AsyncioMagicMock()
    await link.add_node(node1, 0, 4)
    await link.add_node(node2, 1, 3)
    assert link.asdict()["link_type"] == "serial"


@pytest.mark.asyncio
async def test_default_capture_file_name(project, compute):

    node1 = Node(project, compute, "Hello@", node_type="qemu")
    node1._ports = [EthernetPort("E0", 0, 0, 4)]
    node2 = Node(project, compute, "w0.rld", node_type="qemu")
    node2._ports = [EthernetPort("E0", 0, 1, 3)]

    link = Link(project)
    link.create = AsyncioMagicMock()
    await link.add_node(node1, 0, 4)
    await link.add_node(node2, 1, 3)
    assert link.default_capture_file_name() == "Hello_0-4_to_w0rld_1-3.pcap"


@pytest.mark.asyncio
async def test_start_capture(link):


    async def fake_reader():
        return AsyncioBytesIO()

    link.read_pcap_from_source = fake_reader
    link._project.emit_notification = MagicMock()
    await link.start_capture(capture_file_name="test.pcap")
    assert link._capturing
    assert link._capture_file_name == "test.pcap"
    link._project.emit_notification.assert_called_with("link.updated", link.asdict())


@pytest.mark.asyncio
async def test_stop_capture(link):

    link._capturing = True
    link._project.emit_notification = MagicMock()
    await link.stop_capture()
    assert link._capturing is False
    link._project.emit_notification.assert_called_with("link.updated", link.asdict())


@pytest.mark.asyncio
async def test_delete(project, compute):

    node1 = Node(project, compute, "node1", node_type="qemu")
    node1._ports = [EthernetPort("E0", 0, 0, 4)]

    link = Link(project)
    link.create = AsyncioMagicMock()
    link._project.emit_notification = MagicMock()
    project.dump = AsyncioMagicMock()
    await link.add_node(node1, 0, 4)

    node2 = Node(project, compute, "node2", node_type="qemu")
    node2._ports = [EthernetPort("E0", 0, 0, 4)]
    await link.add_node(node2, 0, 4)
    assert link in node2.links
    await link.delete()
    assert link not in node2.links


@pytest.mark.asyncio
async def test_update_filters(project, compute):

    node1 = Node(project, compute, "node1", node_type="qemu")
    node1._ports = [EthernetPort("E0", 0, 0, 4)]

    link = Link(project)
    link.create = AsyncioMagicMock()
    link._project.emit_notification = MagicMock()
    project.dump = AsyncioMagicMock()
    await link.add_node(node1, 0, 4)

    node2 = Node(project, compute, "node2", node_type="qemu")
    node2._ports = [EthernetPort("E0", 0, 0, 4)]
    await link.add_node(node2, 0, 4)

    link.update = AsyncioMagicMock()
    assert link._created
    await link.update_filters({
        "packet_loss": [10],
        "delay": [50, 10],
        "frequency_drop": [0],
        "bpf": [" \n  "]
    })
    assert link.filters == {
        "packet_loss": [10],
        "delay": [50, 10]
    }
    assert link.update.called


@pytest.mark.asyncio
async def test_available_filters(project, compute):

    node1 = Node(project, compute, "node1", node_type="ethernet_switch")
    node1._ports = [EthernetPort("E0", 0, 0, 4)]

    link = Link(project)
    link.create = AsyncioMagicMock()
    assert link.available_filters() == []

    # Ethernet switch is not supported should return 0 filters
    await link.add_node(node1, 0, 4)
    assert link.available_filters() == []

    node2 = Node(project, compute, "node2", node_type="vpcs")
    node2._ports = [EthernetPort("E0", 0, 0, 4)]
    await link.add_node(node2, 0, 4)
    assert len(link.available_filters()) > 0
