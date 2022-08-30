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

import uuid
import pytest
import pytest_asyncio
from unittest.mock import MagicMock, patch, call

from gns3server.compute.builtin.nodes.cloud import Cloud
from gns3server.compute.nios.nio_udp import NIOUDP
from tests.utils import asyncio_patch


@pytest.fixture
def nio():

    return NIOUDP(4242, "127.0.0.1", 4343)


@pytest_asyncio.fixture
async def manager():

    m = MagicMock()
    m.module_name = "builtins"
    return m


@pytest.mark.asyncio
async def test_json_with_ports(on_gns3vm, compute_project, manager):

    ports = [
        {
            "interface": "virbr0",
            "name": "virbr0",
            "port_number": 0,
            "type": "ethernet",
        }
    ]
    cloud = Cloud("cloud1", str(uuid.uuid4()), compute_project, manager, ports=ports)
    assert cloud.asdict() == {
        "name": "cloud1",
        "usage": "",
        "node_id": cloud.id,
        "project_id": compute_project.id,
        "remote_console_host": "",
        "remote_console_http_path": "/",
        "remote_console_port": 23,
        "remote_console_type": "none",
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


def test_json_without_ports(on_gns3vm, compute_project, manager):
    """
    If no interface is provide the cloud is pre-fill with non special interfaces
    """

    cloud = Cloud("cloud1", str(uuid.uuid4()), compute_project, manager, ports=None)
    assert cloud.asdict() == {
        "name": "cloud1",
        "usage": "",
        "node_id": cloud.id,
        "project_id": compute_project.id,
        "remote_console_host": "",
        "remote_console_http_path": "/",
        "remote_console_port": 23,
        "remote_console_type": "none",
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


@pytest.mark.asyncio
async def test_update_port_mappings(on_gns3vm, compute_project):
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
    cloud = Cloud("cloud1", str(uuid.uuid4()), compute_project, MagicMock(), ports=ports1)
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
    cloud = Cloud("cloud2", str(uuid.uuid4()), compute_project, MagicMock(), ports=ports2)
    assert cloud.ports_mapping == ports1


@pytest.mark.asyncio
async def test_linux_ethernet_raw_add_nio(linux_platform, compute_project, nio):
    ports = [
        {
            "interface": "eth0",
            "name": "eth0",
            "port_number": 0,
            "type": "ethernet"
        }
    ]
    cloud = Cloud("cloud1", str(uuid.uuid4()), compute_project, MagicMock(), ports=ports)
    cloud.status = "started"

    with patch("shutil.which", return_value="/bin/ubridge"):
        with patch("gns3server.compute.base_manager.BaseManager.has_privileged_access", return_value=True):
            with asyncio_patch("gns3server.compute.builtin.nodes.cloud.Cloud._ubridge_send") as ubridge_mock:
                with patch("gns3server.compute.builtin.nodes.cloud.Cloud._interfaces", return_value=[{"name": "eth0"}]):
                    await cloud.add_nio(nio, 0)

    ubridge_mock.assert_has_calls([
        call("bridge create {}-0".format(cloud._id)),
        call("bridge add_nio_udp {}-0 4242 127.0.0.1 4343".format(cloud._id)),
        call('bridge reset_packet_filters {}-0'.format(cloud._id)),
        call("bridge add_nio_linux_raw {}-0 \"eth0\"".format(cloud._id)),
        call("bridge start {}-0".format(cloud._id)),
    ])


@pytest.mark.asyncio
async def test_linux_ethernet_raw_add_nio_bridge(linux_platform, compute_project, nio):
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
    cloud = Cloud("cloud1", str(uuid.uuid4()), compute_project, MagicMock(), ports=ports)
    cloud.status = "started"

    with patch("shutil.which", return_value="/bin/ubridge"):
        with patch("gns3server.compute.base_manager.BaseManager.has_privileged_access", return_value=True):
            with asyncio_patch("gns3server.compute.builtin.nodes.cloud.Cloud._ubridge_send") as ubridge_mock:
                with patch("gns3server.compute.builtin.nodes.cloud.Cloud._interfaces", return_value=[{"name": "bridge0"}]):
                    with patch("gns3server.utils.interfaces.is_interface_bridge", return_value=True):
                        await cloud.add_nio(nio, 0)

    tap = "gns3tap0-0"
    ubridge_mock.assert_has_calls([
        call("bridge create {}-0".format(cloud._id)),
        call("bridge add_nio_udp {}-0 4242 127.0.0.1 4343".format(cloud._id)),
        call('bridge reset_packet_filters {}-0'.format(cloud._id)),
        call("bridge add_nio_tap \"{}-0\" \"{}\"".format(cloud._id, tap)),
        call("brctl addif \"bridge0\" \"{}\"".format(tap)),
        call("bridge start {}-0".format(cloud._id)),
    ])
