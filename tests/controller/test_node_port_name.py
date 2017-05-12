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
import uuid

from tests.utils import AsyncioMagicMock

from gns3server.controller.node import Node
from gns3server.controller.project import Project
from gns3server.controller.ports.ethernet_port import EthernetPort


@pytest.fixture
def compute():
    s = AsyncioMagicMock()
    s.id = "http://test.com:42"
    return s


@pytest.fixture
def project(controller):
    return Project(str(uuid.uuid4()), controller=controller)


@pytest.fixture
def node(compute, project):
    node = Node(project, compute, "demo",
                node_id=str(uuid.uuid4()),
                node_type="qemu",
                console_type="vnc",
                properties={"startup_script": "echo test"})
    return node


def test_list_ports(node):
    """
    List port by default
    """
    assert node.__json__()["ports"] == [
        {
            "name": "Ethernet0",
            "short_name": "e0/0",
            "data_link_types": {"Ethernet": "DLT_EN10MB"},
            "port_number": 0,
            "adapter_number": 0,
            "link_type": "ethernet"
        }
    ]


def test_list_ports_vpcs(node):
    """
    List port by default
    """
    node._node_type = "vpcs"
    assert node.__json__()["ports"] == [
        {
            "name": "Ethernet0",
            "short_name": "e0",
            "data_link_types": {"Ethernet": "DLT_EN10MB"},
            "port_number": 0,
            "adapter_number": 0,
            "link_type": "ethernet"
        }
    ]


def test_list_ports_docker(node):
    """
    List port by default
    """
    node._node_type = "docker"
    node._properties["adapters"] = 2
    assert node.__json__()["ports"] == [
        {
            "name": "eth0",
            "short_name": "eth0",
            "data_link_types": {"Ethernet": "DLT_EN10MB"},
            "port_number": 0,
            "adapter_number": 0,
            "link_type": "ethernet"
        },
        {
            "name": "eth1",
            "short_name": "eth1",
            "data_link_types": {"Ethernet": "DLT_EN10MB"},
            "port_number": 0,
            "adapter_number": 1,
            "link_type": "ethernet"
        }
    ]


def test_list_ports_port_name_format(node):
    """
    Support port name format
    """
    node._first_port_name = None
    node._port_name_format = "eth{}"
    node._list_ports()
    assert node.__json__()["ports"][0]["name"] == "eth0"
    node._port_name_format = "eth{port0}"
    node._list_ports()
    assert node.__json__()["ports"][0]["name"] == "eth0"
    node._port_name_format = "eth{port1}"
    node._list_ports()
    assert node.__json__()["ports"][0]["name"] == "eth1"

    node._first_port_name = ""
    node._port_segment_size = 2
    node._port_name_format = "eth{segment0}/{port0}"
    node.properties["adapters"] = 8
    node._list_ports()
    assert node.__json__()["ports"][6]["name"] == "eth3/0"
    assert node.__json__()["ports"][7]["name"] == "eth3/1"

    node._first_port_name = "mgnt0"
    node._list_ports()
    assert node.__json__()["ports"][0]["name"] == "mgnt0"
    assert node.__json__()["ports"][1]["name"] == "eth0/0"


def test_list_ports_adapters(node):
    """
    List port using adapters properties
    """
    node.properties["adapters"] = 2
    assert node.__json__()["ports"] == [
        {
            "name": "Ethernet0",
            "short_name": "e0/0",
            "data_link_types": {"Ethernet": "DLT_EN10MB"},
            "port_number": 0,
            "adapter_number": 0,
            "link_type": "ethernet"
        },
        {
            "name": "Ethernet1",
            "short_name": "e1/0",
            "data_link_types": {"Ethernet": "DLT_EN10MB"},
            "port_number": 0,
            "adapter_number": 1,
            "link_type": "ethernet"
        }
    ]


def test_list_ports_adapters_cloud(project, compute):
    """
    List port using adapters properties
    """
    node = Node(project, compute, "demo",
                node_id=str(uuid.uuid4()),
                node_type="cloud")
    node.properties["ports_mapping"] = [
        {
            "interface": "eth0",
            "name": "eth0",
            "port_number": 0,
            "type": "ethernet"
        }
    ]

    assert node.__json__()["ports"] == [
        {
            "name": "eth0",
            "short_name": "eth0",
            "data_link_types": {"Ethernet": "DLT_EN10MB"},
            "port_number": 0,
            "adapter_number": 0,
            "link_type": "ethernet"
        }
    ]


def test_list_ports_ethernet_hub(project, compute):
    """
    List port for atm switch
    """
    node = Node(project, compute, "demo",
                node_id=str(uuid.uuid4()),
                node_type="ethernet_hub")
    node.properties["ports_mapping"] = [
        {
            "name": "Ethernet0",
            "port_number": 0
        },
        {
            "name": "Ethernet1",
            "port_number": 1
        }
    ]

    assert node.__json__()["ports"] == [
        {
            "name": "Ethernet0",
            "short_name": "e0",
            "data_link_types": {"Ethernet": "DLT_EN10MB"},
            "port_number": 0,
            "adapter_number": 0,
            "link_type": "ethernet"
        },
        {
            "name": "Ethernet1",
            "short_name": "e1",
            "data_link_types": {"Ethernet": "DLT_EN10MB"},
            "port_number": 1,
            "adapter_number": 0,
            "link_type": "ethernet"
        }
    ]


def test_list_ports_atm_switch(project, compute):
    """
    List port for atm switch
    """
    node = Node(project, compute, "demo",
                node_id=str(uuid.uuid4()),
                node_type="atm_switch")
    node.properties["mappings"] = {
        "1:0:100": "10:0:200"
    }

    assert node.__json__()["ports"] == [
        {
            "name": "1",
            "short_name": "1",
            "data_link_types": {"ATM": "DLT_ATM_RFC1483"},
            "port_number": 1,
            "adapter_number": 0,
            "link_type": "serial"
        },
        {
            "name": "10",
            "short_name": "10",
            "data_link_types": {"ATM": "DLT_ATM_RFC1483"},
            "port_number": 10,
            "adapter_number": 0,
            "link_type": "serial"
        }
    ]


def test_list_ports_frame_relay_switch(project, compute):
    """
    List port for frame relay switch
    """
    node = Node(project, compute, "demo",
                node_id=str(uuid.uuid4()),
                node_type="frame_relay_switch")
    node.properties["mappings"] = {
        "1:101": "10:202",
        "2:102": "11:203"
    }

    assert node.__json__()["ports"] == [
        {
            "name": "1",
            "short_name": "1",
            "data_link_types": {"Frame Relay": "DLT_FRELAY"},
            "port_number": 1,
            "adapter_number": 0,
            "link_type": "serial"
        },
        {
            "name": "2",
            "short_name": "2",
            "data_link_types": {"Frame Relay": "DLT_FRELAY"},
            "port_number": 2,
            "adapter_number": 0,
            "link_type": "serial"
        },
        {
            "name": "10",
            "short_name": "10",
            "data_link_types": {"Frame Relay": "DLT_FRELAY"},
            "port_number": 10,
            "adapter_number": 0,
            "link_type": "serial"
        },
        {
            "name": "11",
            "short_name": "11",
            "data_link_types": {"Frame Relay": "DLT_FRELAY"},
            "port_number": 11,
            "adapter_number": 0,
            "link_type": "serial"
        }
    ]


def test_list_ports_iou(compute, project):
    """
    IOU has a special behavior 4 port by adapters
    """
    node = Node(project, compute, "demo",
                node_id=str(uuid.uuid4()),
                node_type="iou")
    node.properties["serial_adapters"] = 2
    node.properties["ethernet_adapters"] = 3
    assert node.__json__()["ports"] == [
        {
            "name": "Ethernet0/0",
            "short_name": "e0/0",
            "data_link_types": {"Ethernet": "DLT_EN10MB"},
            "port_number": 0,
            "adapter_number": 0,
            "link_type": "ethernet"
        },
        {
            "name": "Ethernet0/1",
            "short_name": "e0/1",
            "data_link_types": {"Ethernet": "DLT_EN10MB"},
            "port_number": 1,
            "adapter_number": 0,
            "link_type": "ethernet"
        },
        {
            "name": "Ethernet0/2",
            "short_name": "e0/2",
            "data_link_types": {"Ethernet": "DLT_EN10MB"},
            "port_number": 2,
            "adapter_number": 0,
            "link_type": "ethernet"
        },
        {
            "name": "Ethernet0/3",
            "short_name": "e0/3",
            "data_link_types": {"Ethernet": "DLT_EN10MB"},
            "port_number": 3,
            "adapter_number": 0,
            "link_type": "ethernet"
        },
        {
            "name": "Ethernet1/0",
            "short_name": "e1/0",
            "data_link_types": {"Ethernet": "DLT_EN10MB"},
            "port_number": 0,
            "adapter_number": 1,
            "link_type": "ethernet"
        },
        {
            "name": "Ethernet1/1",
            "short_name": "e1/1",
            "data_link_types": {"Ethernet": "DLT_EN10MB"},
            "port_number": 1,
            "adapter_number": 1,
            "link_type": "ethernet"
        },
        {
            "name": "Ethernet1/2",
            "short_name": "e1/2",
            "data_link_types": {"Ethernet": "DLT_EN10MB"},
            "port_number": 2,
            "adapter_number": 1,
            "link_type": "ethernet"
        },
        {
            "name": "Ethernet1/3",
            "short_name": "e1/3",
            "data_link_types": {"Ethernet": "DLT_EN10MB"},
            "port_number": 3,
            "adapter_number": 1,
            "link_type": "ethernet"
        },
        {
            "name": "Ethernet2/0",
            "short_name": "e2/0",
            "data_link_types": {"Ethernet": "DLT_EN10MB"},
            "port_number": 0,
            "adapter_number": 2,
            "link_type": "ethernet"
        },
        {
            "name": "Ethernet2/1",
            "short_name": "e2/1",
            "data_link_types": {"Ethernet": "DLT_EN10MB"},
            "port_number": 1,
            "adapter_number": 2,
            "link_type": "ethernet"
        },
        {
            "name": "Ethernet2/2",
            "short_name": "e2/2",
            "data_link_types": {"Ethernet": "DLT_EN10MB"},
            "port_number": 2,
            "adapter_number": 2,
            "link_type": "ethernet"
        },
        {
            "name": "Ethernet2/3",
            "short_name": "e2/3",
            "data_link_types": {"Ethernet": "DLT_EN10MB"},
            "port_number": 3,
            "adapter_number": 2,
            "link_type": "ethernet"
        },
        {
            "name": "Serial3/0",
            "short_name": "s3/0",
            "data_link_types": {
                "Frame Relay": "DLT_FRELAY",
                "Cisco HDLC": "DLT_C_HDLC",
                "Cisco PPP": "DLT_PPP_SERIAL"
            },
            "port_number": 0,
            "adapter_number": 3,
            "link_type": "serial"
        },
        {
            "name": "Serial3/1",
            "short_name": "s3/1",
            "data_link_types": {
                "Frame Relay": "DLT_FRELAY",
                "Cisco HDLC": "DLT_C_HDLC",
                "Cisco PPP": "DLT_PPP_SERIAL"
            },
            "port_number": 1,
            "adapter_number": 3,
            "link_type": "serial"
        },
        {
            "name": "Serial3/2",
            "short_name": "s3/2",
            "data_link_types": {
                "Frame Relay": "DLT_FRELAY",
                "Cisco HDLC": "DLT_C_HDLC",
                "Cisco PPP": "DLT_PPP_SERIAL"
            },
            "port_number": 2,
            "adapter_number": 3,
            "link_type": "serial"
        },
        {
            "name": "Serial3/3",
            "short_name": "s3/3",
            "data_link_types": {
                "Frame Relay": "DLT_FRELAY",
                "Cisco HDLC": "DLT_C_HDLC",
                "Cisco PPP": "DLT_PPP_SERIAL"
            },
            "port_number": 3,
            "adapter_number": 3,
            "link_type": "serial"
        },
        {
            "name": "Serial4/0",
            "short_name": "s4/0",
            "data_link_types": {
                "Frame Relay": "DLT_FRELAY",
                "Cisco HDLC": "DLT_C_HDLC",
                "Cisco PPP": "DLT_PPP_SERIAL"
            },
            "port_number": 0,
            "adapter_number": 4,
            "link_type": "serial"
        },
        {
            "name": "Serial4/1",
            "short_name": "s4/1",
            "data_link_types": {
                "Frame Relay": "DLT_FRELAY",
                "Cisco HDLC": "DLT_C_HDLC",
                "Cisco PPP": "DLT_PPP_SERIAL"
            },
            "port_number": 1,
            "adapter_number": 4,
            "link_type": "serial"
        },
        {
            "name": "Serial4/2",
            "short_name": "s4/2",
            "data_link_types": {
                "Frame Relay": "DLT_FRELAY",
                "Cisco HDLC": "DLT_C_HDLC",
                "Cisco PPP": "DLT_PPP_SERIAL"
            },
            "port_number": 2,
            "adapter_number": 4,
            "link_type": "serial"
        },
        {
            "name": "Serial4/3",
            "short_name": "s4/3",
            "data_link_types": {
                "Frame Relay": "DLT_FRELAY",
                "Cisco HDLC": "DLT_C_HDLC",
                "Cisco PPP": "DLT_PPP_SERIAL"
            },
            "port_number": 3,
            "adapter_number": 4,
            "link_type": "serial"
        }
    ]


def test_list_ports_dynamips(project, compute):
    """
    List port for dynamips
    """
    node = Node(project, compute, "demo",
                node_id=str(uuid.uuid4()),
                node_type="dynamips")
    node.properties["slot0"] = "C7200-IO-FE"
    node.properties["slot1"] = "GT96100-FE"
    node.properties["wic0"] = "WIC-2T"
    node.properties["wic1"] = "WIC-2T"

    assert node.__json__()["ports"] == [
        {
            "name": "FastEthernet0/0",
            "short_name": "f0/0",
            "data_link_types": {"Ethernet": "DLT_EN10MB"},
            "port_number": 0,
            "adapter_number": 0,
            "link_type": "ethernet"
        },
        {
            "name": "FastEthernet1/0",
            "short_name": "f1/0",
            "data_link_types": {"Ethernet": "DLT_EN10MB"},
            "port_number": 0,
            "adapter_number": 1,
            "link_type": "ethernet"
        },
        {
            "name": "FastEthernet1/1",
            "short_name": "f1/1",
            "data_link_types": {"Ethernet": "DLT_EN10MB"},
            "port_number": 1,
            "adapter_number": 1,
            "link_type": "ethernet"
        },
        {
            "name": "Serial0/0",
            "short_name": "s0/0",
            "data_link_types": {
                "Cisco HDLC": "DLT_C_HDLC",
                "Cisco PPP": "DLT_PPP_SERIAL",
                "Frame Relay": "DLT_FRELAY"},
            "port_number": 16,
            "adapter_number": 0,
            "link_type": "serial"
        },
        {
            "name": "Serial0/1",
            "short_name": "s0/1",
            "data_link_types": {
                "Cisco HDLC": "DLT_C_HDLC",
                "Cisco PPP": "DLT_PPP_SERIAL",
                "Frame Relay": "DLT_FRELAY"},
            "port_number": 17,
            "adapter_number": 0,
            "link_type": "serial"
        },
        {
            "name": "Serial0/2",
            "short_name": "s0/2",
            "data_link_types": {
                "Cisco HDLC": "DLT_C_HDLC",
                "Cisco PPP": "DLT_PPP_SERIAL",
                "Frame Relay": "DLT_FRELAY"},
            "port_number": 32,
            "adapter_number": 0,
            "link_type": "serial"
        },
        {
            "name": "Serial0/3",
            "short_name": "s0/3",
            "data_link_types": {
                "Cisco HDLC": "DLT_C_HDLC",
                "Cisco PPP": "DLT_PPP_SERIAL",
                "Frame Relay": "DLT_FRELAY"},
            "port_number": 33,
            "adapter_number": 0,
            "link_type": "serial"
        }
    ]


def test_short_name():
    # If no customization of port name format return the default short name
    assert EthernetPort("Ethernet0", 0, 0, 0).short_name == "e0/0"
    assert EthernetPort("Ethernet0", 0, 0, 0, short_name="mgmt").short_name == "mgmt"
    # If port name format has change we use the port name as the short name (1.X behavior)
    assert EthernetPort("eth0", 0, 0, 0).short_name == "eth0"
