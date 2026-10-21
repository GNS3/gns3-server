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

import struct
import uuid
from unittest.mock import MagicMock, call, patch

import pytest
import pytest_asyncio
from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError

from gns3server.compute.base_manager import BaseManager
from gns3server.compute.builtin.nodes.cloud import Cloud
from gns3server.compute.error import NodeError
from gns3server.compute.nios.nio_udp import NIOUDP
from gns3server.compute.ubridge.ubridge_error import UbridgeError
from gns3server.schemas.compute.cloud_nodes import Cloud as CloudSchema
from gns3server.schemas.compute.cloud_nodes import CloudUpdate, TAPPort
from tests.utils import asyncio_patch

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def mock_bridge_detection():
    # Interface inventories are mocked: never mix them with the host's sysfs.
    with patch("gns3server.utils.interfaces.is_interface_bridge", return_value=False):
        yield


@pytest.fixture
def nio():

    return NIOUDP(4242, "127.0.0.1", 4343)


@pytest_asyncio.fixture
async def manager():

    m = MagicMock()
    m.module_name = "builtins"
    return m


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
        "ports_mapping": [{"interface": "virbr0", "name": "virbr0", "port_number": 0, "type": "ethernet"}],
        "interfaces": [
            {
                "name": "eth0",
                "special": False,
                "type": "ethernet",
                "ip_addresses": [],
                "status": "up",
                "speed": 1000,
                "mtu": 1500,
                "flags": ["up", "broadcast", "running", "multicast"],
            },
            {
                "name": "eth1",
                "special": False,
                "type": "ethernet",
                "ip_addresses": [],
                "status": "down",
                "speed": 0,
                "mtu": 1500,
                "flags": ["broadcast"],
            },
            {
                "name": "virbr0",
                "special": True,
                "type": "ethernet",
                "ip_addresses": [],
                "status": "up",
                "speed": 10000,
                "mtu": 1500,
                "flags": ["up", "broadcast", "running", "multicast"],
            },
        ],
    }


async def test_json_without_ports(on_gns3vm, compute_project, manager):
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
            {"interface": "eth0", "name": "eth0", "port_number": 0, "type": "ethernet"},
            {"interface": "eth1", "name": "eth1", "port_number": 1, "type": "ethernet"},
        ],
        "interfaces": [
            {
                "name": "eth0",
                "special": False,
                "type": "ethernet",
                "ip_addresses": [],
                "status": "up",
                "speed": 1000,
                "mtu": 1500,
                "flags": ["up", "broadcast", "running", "multicast"],
            },
            {
                "name": "eth1",
                "special": False,
                "type": "ethernet",
                "ip_addresses": [],
                "status": "down",
                "speed": 0,
                "mtu": 1500,
                "flags": ["broadcast"],
            },
            {
                "name": "virbr0",
                "special": True,
                "type": "ethernet",
                "ip_addresses": [],
                "status": "up",
                "speed": 10000,
                "mtu": 1500,
                "flags": ["up", "broadcast", "running", "multicast"],
            },
        ],
    }


async def test_kernel_datapath_interfaces_are_hidden(linux_platform, compute_project, manager):
    """
    Kernel-datapath interfaces (node anchors, cascade veths, VXLAN devices)
    are neither pre-filled as cloud ports nor listed as host interfaces,
    while look-alike user interfaces survive both.
    """

    host_interfaces = [
        {"name": "eth0", "special": False, "type": "ethernet"},
        {"name": "gv00010203e0p0", "special": False, "type": "ethernet"},  # docker anchor
        {"name": "gq00010203e0p0", "special": False, "type": "ethernet"},  # qemu anchor
        {"name": "gi00010203e0p0", "special": False, "type": "ethernet"},  # iou anchor
        {"name": "gd00010203e0p0", "special": False, "type": "ethernet"},  # dynamips anchor
        {"name": "gx00010203e0p0", "special": False, "type": "ethernet"},  # iol runner anchor
        {"name": "gp00010203e0p0", "special": False, "type": "ethernet"},  # vpcs anchor
        {"name": "gs1a2b3c4d5e0", "special": False, "type": "ethernet"},  # cascade veth end
        {"name": "gvl1a2b3c4d0001", "special": False, "type": "ethernet"},  # VXLAN device
        {"name": "gv0", "special": False, "type": "ethernet"},  # look-alike user interface
        {"name": "gs1a2b3c4d5e", "special": False, "type": "ethernet"},  # look-alike (no side digit)
        {"name": "gvl1a2b3c4d5e", "special": False, "type": "ethernet"},  # look-alike (short tail)
    ]

    with patch("gns3server.utils.interfaces.interfaces", return_value=host_interfaces):
        cloud = Cloud("cloud1", str(uuid.uuid4()), compute_project, manager, ports=None)
        interfaces = [interface["name"] for interface in cloud.asdict()["interfaces"]]

    assert [port["interface"] for port in cloud.ports_mapping] == ["eth0", "gv0", "gs1a2b3c4d5e", "gvl1a2b3c4d5e"]
    assert interfaces == ["eth0", "gv0", "gs1a2b3c4d5e", "gvl1a2b3c4d5e"]


async def test_update_port_mappings(on_gns3vm, compute_project):
    """
    We don't allow an empty interface in the middle of port list
    """

    ports1 = [
        {"interface": "eth0", "name": "eth0", "port_number": 0, "type": "ethernet"},
        {"interface": "eth1", "name": "eth1", "port_number": 1, "type": "ethernet"},
    ]
    cloud = Cloud("cloud1", str(uuid.uuid4()), compute_project, MagicMock(), ports=ports1)
    assert cloud.ports_mapping == ports1

    ports2 = [
        {"interface": "eth0", "name": "eth0", "port_number": 0, "type": "ethernet"},
        {"interface": "eth1", "name": "eth1", "port_number": 2, "type": "ethernet"},
    ]
    cloud = Cloud("cloud2", str(uuid.uuid4()), compute_project, MagicMock(), ports=ports2)
    assert cloud.ports_mapping == ports1


async def test_linux_ethernet_raw_add_nio(linux_platform, compute_project, nio):
    ports = [{"interface": "eth0", "name": "eth0", "port_number": 0, "type": "ethernet"}]
    cloud = Cloud("cloud1", str(uuid.uuid4()), compute_project, MagicMock(), ports=ports)
    cloud.status = "started"

    with patch("shutil.which", return_value="/bin/ubridge"):
        with patch("gns3server.compute.base_manager.BaseManager.has_privileged_access", return_value=True):
            with asyncio_patch("gns3server.compute.builtin.nodes.cloud.Cloud._ubridge_send") as ubridge_mock:
                with patch("gns3server.compute.builtin.nodes.cloud.Cloud._interfaces", return_value=[{"name": "eth0"}]):
                    await cloud.add_nio(nio, 0)

    ubridge_mock.assert_has_calls(
        [
            call(f"bridge create {cloud._id}-0"),
            call(f"bridge add_nio_udp {cloud._id}-0 4242 127.0.0.1 4343"),
            call(f"bridge reset_packet_filters {cloud._id}-0"),
            call(f'bridge add_nio_linux_raw {cloud._id}-0 "eth0"'),
            call(f"bridge start {cloud._id}-0"),
        ]
    )


async def test_linux_ethernet_raw_add_nio_bridge(linux_platform, compute_project, nio):
    """
    Bridge can't be connected directly to a cloud we use a tap in the middle
    """
    ports = [{"interface": "bridge0", "name": "bridge0", "port_number": 0, "type": "ethernet"}]
    cloud = Cloud("cloud1", str(uuid.uuid4()), compute_project, MagicMock(), ports=ports)
    cloud.status = "started"

    with patch("shutil.which", return_value="/bin/ubridge"):
        with patch("gns3server.compute.base_manager.BaseManager.has_privileged_access", return_value=True):
            with asyncio_patch("gns3server.compute.builtin.nodes.cloud.Cloud._ubridge_send") as ubridge_mock:
                with patch(
                    "gns3server.compute.builtin.nodes.cloud.Cloud._interfaces", return_value=[{"name": "bridge0"}]
                ):
                    with patch("gns3server.utils.interfaces.is_interface_bridge", return_value=True):
                        await cloud.add_nio(nio, 0)

    tap = "gns3tap0-0"
    ubridge_mock.assert_has_calls(
        [
            call(f"bridge create {cloud._id}-0"),
            call(f"bridge add_nio_udp {cloud._id}-0 4242 127.0.0.1 4343"),
            call(f"bridge reset_packet_filters {cloud._id}-0"),
            call(f'bridge add_nio_tap "{cloud._id}-0" "{tap}"'),
            call(f'brctl addif "bridge0" "{tap}"'),
            call(f"bridge start {cloud._id}-0"),
        ]
    )


@pytest.mark.parametrize("bridge", [None, "virbr0"])
@pytest.mark.parametrize("existing_master", [False, True])
async def test_tap_bridge_recreated(linux_platform, compute_project, manager, nio, bridge, existing_master):
    ports = [{"interface": "tap0", "name": "tap0", "port_number": 0, "type": "tap"}]
    if bridge:
        ports[0]["bridge"] = bridge
    cloud = Cloud("cloud1", str(uuid.uuid4()), compute_project, manager, ports=ports)
    # Round-trip through the API schema, as happens when a project is restored.
    restored_ports = CloudSchema(**cloud.asdict()).model_dump()["ports_mapping"]
    restored = Cloud("cloud1", cloud.id, compute_project, manager, ports=restored_ports)
    with (
        asyncio_patch("gns3server.compute.builtin.nodes.cloud.Cloud._ubridge_send") as send,
        asyncio_patch("gns3server.compute.builtin.nodes.cloud.Cloud._start_ubridge"),
        patch.object(restored, "_interfaces", return_value=[{"name": "virbr0"}]),
        patch("gns3server.utils.interfaces.is_interface_bridge", return_value=True),
        patch("gns3server.compute.builtin.nodes.cloud.os.path.exists", return_value=existing_master),
        patch("gns3server.compute.builtin.nodes.cloud.os.path.realpath", return_value="/sys/class/net/virbr0"),
    ):
        restored._nios[0] = nio
        await restored.start()
        tap_call = call(f'bridge add_nio_tap {cloud.id}-0 "tap0"')
        assert tap_call in send.call_args_list
        attach_call = call('brctl addif "virbr0" "tap0"')
        if bridge:
            assert send.call_args_list.index(tap_call) < send.call_args_list.index(attach_call)
        else:
            assert attach_call not in send.call_args_list


@pytest.mark.parametrize("failure", ["missing", "not_bridge", "other_master", "invalid_name", "non_linux"])
async def test_tap_bridge_validation(linux_platform, compute_project, manager, nio, failure):
    ports = [{"interface": "tap0", "name": "tap0", "port_number": 0, "type": "tap", "bridge": "virbr0"}]
    if failure == "invalid_name":
        ports[0]["interface"] = 'tap0"\nbridge delete all'
    cloud = Cloud("cloud1", str(uuid.uuid4()), compute_project, manager, ports=ports)
    with (
        asyncio_patch("gns3server.compute.builtin.nodes.cloud.Cloud._ubridge_send") as send,
        patch.object(cloud, "_interfaces", return_value=[] if failure == "missing" else [{"name": "virbr0"}]),
        patch("gns3server.utils.interfaces.is_interface_bridge", return_value=failure != "not_bridge"),
        patch("gns3server.compute.builtin.nodes.cloud.os.path.exists", return_value=failure == "other_master"),
        patch("gns3server.compute.builtin.nodes.cloud.os.path.realpath", return_value="/sys/class/net/another0"),
        patch("gns3server.compute.builtin.nodes.cloud.sys.platform", "darwin" if failure == "non_linux" else "linux"),
    ):
        with pytest.raises(NodeError):
            await cloud._add_ubridge_connection(nio, 0)
        assert not any("add_nio_tap" in c.args[0] or "brctl addif" in c.args[0] for c in send.call_args_list)


async def test_tap_bridge_attachment_failure(linux_platform, compute_project, manager, nio):
    ports = [{"interface": "tap0", "name": "tap0", "port_number": 0, "type": "tap", "bridge": "virbr0"}]
    cloud = Cloud("cloud1", str(uuid.uuid4()), compute_project, manager, ports=ports)
    cloud.status = "started"

    async def send(command):
        if command.startswith("brctl addif"):
            raise UbridgeError("Operation not permitted")

    with (
        asyncio_patch("gns3server.compute.builtin.nodes.cloud.Cloud._ubridge_send", side_effect=send),
        asyncio_patch("gns3server.compute.builtin.nodes.cloud.Cloud._stop_ubridge") as stop,
        patch.object(cloud, "_interfaces", return_value=[{"name": "virbr0"}]),
        patch("gns3server.utils.interfaces.is_interface_bridge", return_value=True),
        patch("gns3server.compute.builtin.nodes.cloud.os.path.exists", return_value=False),
    ):
        await cloud.add_nio(nio, 0)
        stop.assert_called_once()
        assert cloud.status == "stopped"


async def test_cloud_lists_linux_bridges(linux_platform, compute_project, manager):
    cloud = Cloud(
        "cloud1",
        str(uuid.uuid4()),
        compute_project,
        manager,
        ports=[{"interface": "tap0", "name": "tap0", "port_number": 0, "type": "tap"}],
    )
    with (
        patch(
            "gns3server.utils.interfaces.interfaces",
            return_value=[
                {"name": "eth0", "type": "ethernet", "special": False},
                {"name": "virbr0", "type": "ethernet", "special": True},
            ],
        ),
        patch("gns3server.utils.interfaces.is_interface_bridge", side_effect=lambda name: name == "virbr0"),
    ):
        interfaces = CloudSchema(**cloud.asdict()).model_dump()["interfaces"]
    assert [(interface["name"], interface["is_bridge"]) for interface in interfaces] == [
        ("eth0", False),
        ("virbr0", True),
    ]


@pytest.mark.parametrize("stored_bridge", [None, "omitted"])
async def test_connected_tap_mapping_round_trip(compute_project, manager, stored_bridge):
    port = {"interface": "tap0", "name": "tap0", "port_number": 0, "type": "tap"}
    if stored_bridge is None:
        port["bridge"] = None
    cloud = Cloud("cloud1", str(uuid.uuid4()), compute_project, manager, ports=[port])
    response = CloudSchema(**cloud.asdict()).model_dump(mode="json")
    cloud._nios[0] = object()
    ports = jsonable_encoder(CloudUpdate(ports_mapping=response["ports_mapping"]), exclude_unset=True)["ports_mapping"]
    cloud.ports_mapping = ports
    assert cloud.ports_mapping == [{"interface": "tap0", "name": "tap0", "port_number": 0, "type": "tap"}]
    ports[0]["bridge"] = "virbr0"
    with pytest.raises(NodeError, match="already connected"):
        cloud.ports_mapping = ports


@pytest.mark.parametrize("name", ["tap-interface-too-long", "tap bad", 'tap0"\nbridge delete all', "/dev/tap0"])
async def test_bridged_tap_name_validation_preserves_legacy_names(name):
    port = {"interface": name, "name": name, "port_number": 0, "type": "tap"}
    assert TAPPort(**port).interface == name
    with pytest.raises(ValidationError, match="bridged TAP name"):
        TAPPort(**port, bridge="virbr0")


@pytest.mark.parametrize(
    "caps,legacy_allowed,bridge_allowed",
    [
        (0, False, False),
        (1 << 12, False, False),
        (1 << 13, True, False),
        ((1 << 12) | (1 << 13), True, True),
    ],
)
async def test_bridged_tap_requires_net_admin(linux_platform, tmp_path, caps, legacy_allowed, bridge_allowed):
    executable = tmp_path / "ubridge"
    executable.write_text("")
    with (
        patch("os.geteuid", return_value=1000),
        patch("os.listxattr", return_value=["security.capability"]),
        patch("os.getxattr", return_value=struct.pack("<IIIII", 0x2000001, caps, 0, 0, 0)),
    ):
        assert BaseManager.has_privileged_access(executable) is legacy_allowed
        assert BaseManager.has_privileged_access(executable, require_net_admin=True) is bridge_allowed
