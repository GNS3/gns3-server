#!/usr/bin/env python
#
# Copyright (C) 2026 GNS3 Technologies Inc.
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
Tests for the shared GNS3 REST client layer (gns3_copilot.gns3_client):

- project_inventory: the nodes/links aggregation feeding the topology
  context and the Nornir inventory — its output shape is consumer-visible
  and must stay field-for-field stable
- get_gns3_device_port: netmiko device_type resolution and per-node
  credentials over the topology inventory
"""

import pytest


# ── project_inventory ────────────────────────────────────────────────────


def test_nodes_inventory_emits_default_credentials():
    """
    The inventory dict consumed by get_device_ports_from_topology must
    carry the per-node default credentials.
    """
    pytest.importorskip("jwt", reason="ai-features extras not installed")
    from gns3server.agent.gns3_copilot.gns3_client.project_inventory import (
        build_nodes_inventory,
    )

    nodes = [
        {
            "name": "R1",
            "node_id": "0d15c2e6-8f83-4b79-8875-9dbc3e5f2f1e",
            "node_type": "dynamips",
            "console": 5000,
            "console_type": "telnet",
            "status": "started",
            "x": 0,
            "y": 0,
            "default_username": "admin",
            "default_password": "admin123",
        },
    ]

    inventory = build_nodes_inventory(nodes, "127.0.0.1")
    assert inventory["R1"]["default_username"] == "admin"
    assert inventory["R1"]["default_password"] == "admin123"
    assert inventory["R1"]["console_port"] == 5000
    assert inventory["R1"]["type"] == "dynamips"
    assert inventory["R1"]["server"] == "127.0.0.1"
    assert inventory["R1"]["tags"] == []


def test_links_summary_resolves_names_and_ports():
    """
    links_summary maps raw link endpoint lists to
    {link_id, node_a, port_a, node_b, port_b} using port/adapter numbers.
    """
    pytest.importorskip("jwt", reason="ai-features extras not installed")
    from gns3server.agent.gns3_copilot.gns3_client.project_inventory import (
        build_links_summary,
    )

    nodes = [
        {
            "name": "R1",
            "node_id": "n1",
            "ports": [
                {"name": "GigabitEthernet0/0", "port_number": 0, "adapter_number": 0},
                {"name": "GigabitEthernet0/1", "port_number": 1, "adapter_number": 0},
            ],
        },
        {
            "name": "R2",
            "node_id": "n2",
            "ports": [
                {"name": "Ethernet0", "port_number": 0, "adapter_number": 0},
            ],
        },
    ]
    links = [
        {
            "link_id": "l1",
            "nodes": [
                {"node_id": "n1", "port_number": 0, "adapter_number": 0},
                {"node_id": "n2", "port_number": 0, "adapter_number": 0},
            ],
        },
        # endpoint not resolvable → skipped, not an error
        {
            "link_id": "l2",
            "nodes": [
                {"node_id": "missing", "port_number": 0, "adapter_number": 0},
                {"node_id": "n2", "port_number": 0, "adapter_number": 0},
            ],
        },
    ]

    summary = build_links_summary(nodes, links)
    assert summary == [
        {
            "link_id": "l1",
            "node_a": "R1",
            "port_a": "GigabitEthernet0/0",
            "node_b": "R2",
            "port_b": "Ethernet0",
        }
    ]


# ── get_gns3_device_port (over the topology inventory) ──────────────────


def test_device_ports_prefer_netmiko_field_over_tag(monkeypatch):
    """
    netmiko_device_type on the node wins over the device_type:<type> tag;
    the tag stays as fallback when the field is missing.
    """
    pytest.importorskip("jwt", reason="ai-features extras not installed")
    from gns3server.agent.gns3_copilot.utils import get_gns3_device_port
    from gns3server.agent.gns3_copilot import gns3_client

    class _FakeTopology:
        def _run(self, project_id=None, jwt_token=None, url=None):
            return {
                "nodes": {
                    "SR1": {
                        "console_port": 5000,
                        "tags": ["device_type:cisco_ios_telnet"],
                        "netmiko_device_type": "nokia_srl",
                    },
                    "R1": {
                        "console_port": 5001,
                        "tags": ["device_type:cisco_ios_telnet", "platform:cisco_ios"],
                        "netmiko_device_type": None,
                    },
                }
            }

    # the function does a lazy from-import inside the body
    monkeypatch.setattr(gns3_client, "GNS3TopologyTool", _FakeTopology)
    hosts = get_gns3_device_port.get_device_ports_from_topology(["SR1", "R1"])

    # field wins over tag
    assert hosts["SR1"]["connection_options"]["netmiko"]["extras"]["device_type"] == "nokia_srl"
    # tag fallback when the field is absent
    assert hosts["R1"]["connection_options"]["netmiko"]["extras"]["device_type"] == "cisco_ios_telnet"
    assert hosts["R1"]["platform"] == "cisco_ios"


def test_device_ports_error_without_any_device_type(monkeypatch):
    pytest.importorskip("jwt", reason="ai-features extras not installed")
    from gns3server.agent.gns3_copilot.utils import get_gns3_device_port
    from gns3server.agent.gns3_copilot import gns3_client

    class _FakeTopology:
        def _run(self, project_id=None, jwt_token=None, url=None):
            return {
                "nodes": {
                    "R2": {
                        "console_port": 5002,
                        "tags": ["platform:cisco_ios"],
                    },
                }
            }

    # the function does a lazy from-import inside the body
    monkeypatch.setattr(gns3_client, "GNS3TopologyTool", _FakeTopology)
    hosts = get_gns3_device_port.get_device_ports_from_topology(["R2"])

    assert "error" in hosts["R2"]
    assert "netmiko_device_type" in hosts["R2"]["error"]


def test_device_ports_inject_default_credentials(monkeypatch):
    """
    Per-node default credentials become host-level nornir values (which
    override the group's empty fallback); missing or cleared ("") values
    keep inheriting from the group.
    """
    pytest.importorskip("jwt", reason="ai-features extras not installed")
    from gns3server.agent.gns3_copilot.utils import get_gns3_device_port
    from gns3server.agent.gns3_copilot import gns3_client

    class _FakeTopology:
        def _run(self, project_id=None, jwt_token=None, url=None):
            return {
                "nodes": {
                    "R1": {
                        "console_port": 5000,
                        "tags": [],
                        "netmiko_device_type": "cisco_ios_telnet",
                        "default_username": "admin",
                        "default_password": "admin123",
                    },
                    # credentials cleared via PUT arrive as empty strings
                    "R2": {
                        "console_port": 5001,
                        "tags": [],
                        "netmiko_device_type": "cisco_ios_telnet",
                        "default_username": "",
                        "default_password": "",
                    },
                    # never seeded
                    "R3": {
                        "console_port": 5002,
                        "tags": [],
                        "netmiko_device_type": "cisco_ios_telnet",
                    },
                }
            }

    monkeypatch.setattr(gns3_client, "GNS3TopologyTool", _FakeTopology)
    hosts = get_gns3_device_port.get_device_ports_from_topology(["R1", "R2", "R3"])

    # set credentials land at host level
    assert hosts["R1"]["username"] == "admin"
    assert hosts["R1"]["password"] == "admin123"
    # cleared ("") and absent credentials do not override the group fallback
    assert "username" not in hosts["R2"]
    assert "password" not in hosts["R2"]
    assert "username" not in hosts["R3"]
    assert "password" not in hosts["R3"]
