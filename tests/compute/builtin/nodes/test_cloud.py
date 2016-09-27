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

import uuid
import pytest
from unittest.mock import MagicMock

from gns3server.compute.builtin.nodes.cloud import Cloud


def test_json_with_ports(on_gns3vm, project):
    ports = [
        {
            "interface": "virbr0",
            "name": "virbr0",
            "port_number": 0,
            "type": "ethernet"
        }
    ]
    cloud = Cloud("cloud1", str(uuid.uuid4()), project, MagicMock(), ports=ports)
    assert cloud.__json__() == {
        "name": "cloud1",
        "node_id": cloud.id,
        "project_id": project.id,
        "status": "started",
        "ports_mapping": [
            {
                "interface": "virbr0",
                "name": "virbr0",
                "port_number": 0,
                "type": "ethernet"
            }
        ],
        "interfaces": [
            {'name': 'eth0', 'special': False, 'type': 'ethernet'},
            {'name': 'eth1', 'special': False, 'type': 'ethernet'},
            {'name': 'virbr0', 'special': True, 'type': 'ethernet'}
        ]
    }


def test_json_without_ports(on_gns3vm, project):
    """
    If no interface is provide the cloud is prefill with non special interfaces
    """
    cloud = Cloud("cloud1", str(uuid.uuid4()), project, MagicMock(), ports=None)
    assert cloud.__json__() == {
        "name": "cloud1",
        "node_id": cloud.id,
        "project_id": project.id,
        "status": "started",
        "ports_mapping": [
            {
                "interface": "eth0",
                "name": "eth0",
                "port_number": 0,
                "type": "ethernet"
            },
            {
                "interface": "eth1",
                "name": "eth1",
                "port_number": 1,
                "type": "ethernet"
            }
        ],
        "interfaces": [
            {'name': 'eth0', 'special': False, 'type': 'ethernet'},
            {'name': 'eth1', 'special': False, 'type': 'ethernet'},
            {'name': 'virbr0', 'special': True, 'type': 'ethernet'}
        ]
    }


def test_update_port_mappings(on_gns3vm, project):
    """
    We don't allow an empty interface in the middle of port list
    """
    ports1 = [
        {
            "interface": "eth0",
            "name": "eth0",
            "port_number": 0,
            "type": "ethernet"
        },
        {
            "interface": "eth1",
            "name": "eth1",
            "port_number": 1,
            "type": "ethernet"
        }
    ]
    cloud = Cloud("cloud1", str(uuid.uuid4()), project, MagicMock(), ports=ports1)
    assert cloud.ports_mapping == ports1

    ports2 = [
        {
            "interface": "eth0",
            "name": "eth0",
            "port_number": 0,
            "type": "ethernet"
        },
        {
            "interface": "eth1",
            "name": "eth1",
            "port_number": 2,
            "type": "ethernet"
        }
    ]
    cloud = Cloud("cloud2", str(uuid.uuid4()), project, MagicMock(), ports=ports2)
    assert cloud.ports_mapping == ports1
