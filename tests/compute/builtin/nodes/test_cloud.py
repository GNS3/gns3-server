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
from unittest.mock import MagicMock, patch, call

from gns3server.compute.builtin.nodes.cloud import Cloud
from gns3server.compute.nios.nio_udp import NIOUDP
from tests.utils import asyncio_patch


@pytest.fixture
def nio():
    return NIOUDP(4242, "127.0.0.1", 4343)


@pytest.fixture
def manager():
    m = MagicMock()
    m.module_name = "builtins"
    return m


def test_json_with_ports(on_gns3vm, project, manager):
    ports = [
        {
            "interface": "virbr0",
            "name": "virbr0",
            "port_number": 0,
            "type": "ethernet",
        }
    ]
    cloud = Cloud("cloud1", str(uuid.uuid4()), project, manager, ports=ports)
    assert cloud.__json__() == {
        "name": "cloud1",
        "node_id": cloud.id,
        "project_id": project.id,
        "status": "stopped",
        "node_directory": cloud.working_dir,
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


def test_json_without_ports(on_gns3vm, project, manager):
    """
    If no interface is provide the cloud is prefill with non special interfaces
    """
    cloud = Cloud("cloud1", str(uuid.uuid4()), project, manager, ports=None)
    assert cloud.__json__() == {
        "name": "cloud1",
        "node_id": cloud.id,
        "project_id": project.id,
        "status": "stopped",
        "node_directory": cloud.working_dir,
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


def test_linux_ethernet_raw_add_nio(linux_platform, project, async_run, nio):
    ports = [
        {
            "interface": "eth0",
            "name": "eth0",
            "port_number": 0,
            "type": "ethernet"
        }
    ]
    cloud = Cloud("cloud1", str(uuid.uuid4()), project, MagicMock(), ports=ports)
    cloud.status = "started"

    with asyncio_patch("gns3server.compute.builtin.nodes.cloud.Cloud._ubridge_send") as ubridge_mock:
        with patch("gns3server.compute.builtin.nodes.cloud.Cloud._interfaces", return_value=[{"name": "eth0"}]):
            async_run(cloud.add_nio(nio, 0))

    ubridge_mock.assert_has_calls([
        call("bridge create {}-0".format(cloud._id)),
        call("bridge add_nio_udp {}-0 4242 127.0.0.1 4343".format(cloud._id)),
        call("bridge add_nio_linux_raw {}-0 \"eth0\"".format(cloud._id)),
        call("bridge start {}-0".format(cloud._id)),
    ])


def test_linux_ethernet_raw_add_nio_bridge(linux_platform, project, async_run, nio):
    """
    Bridge can't be connected directly to a cloud we use a tap in the middle
    """
    ports = [
        {
            "interface": "bridge0",
            "name": "bridge0",
            "port_number": 0,
            "type": "ethernet"
        }
    ]
    cloud = Cloud("cloud1", str(uuid.uuid4()), project, MagicMock(), ports=ports)
    cloud.status = "started"

    with asyncio_patch("gns3server.compute.builtin.nodes.cloud.Cloud._ubridge_send") as ubridge_mock:
        with patch("gns3server.compute.builtin.nodes.cloud.Cloud._interfaces", return_value=[{"name": "bridge0"}]):
            with patch("gns3server.utils.interfaces.is_interface_bridge", return_value=True):
                async_run(cloud.add_nio(nio, 0))

    tap = "gns3tap0-0"
    ubridge_mock.assert_has_calls([
        call("bridge create {}-0".format(cloud._id)),
        call("bridge add_nio_udp {}-0 4242 127.0.0.1 4343".format(cloud._id)),
        call("bridge add_nio_tap \"{}-0\" \"{}\"".format(cloud._id, tap)),
        call("brctl addif \"bridge0\" \"{}\"".format(tap)),
        call("bridge start {}-0".format(cloud._id)),
    ])
