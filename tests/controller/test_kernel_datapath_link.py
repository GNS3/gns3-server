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
#

"""
Controller-side kernel-datapath link selection: eligibility of Docker-to-
Docker links, NIO emission and the filters/markers guards.
"""

import pytest
from unittest.mock import MagicMock, patch

from gns3server.config import Config
from gns3server.controller.udp_link import UDPLink
from gns3server.controller.ports.ethernet_port import EthernetPort
from gns3server.controller.node import Node
from gns3server.controller.controller_error import ControllerError


def _node(project, compute, name, node_type="docker", status="stopped", environment=None):
    node = Node(project, compute, name, node_type=node_type)
    node._ports = [EthernetPort("eth0", 0, 0, 0)]
    node._status = status
    if environment is not None:
        node._properties = {"environment": environment}
    return node


async def _kernel_link(project, **kwargs):
    compute = MagicMock()
    compute.id = "compute-1"
    node1 = _node(project, compute, "docker1", **kwargs)
    node2 = _node(project, compute, "docker2", **kwargs)
    link = UDPLink(project)
    # batch=True: skip the interactive create() (the test drives _prepare()
    # itself) — matches the project-open bulk path.
    await link.add_node(node1, 0, 0, batch=True, dump=False)
    await link.add_node(node2, 0, 0, batch=True, dump=False)
    return link, node1, node2


@pytest.mark.asyncio
async def test_kernel_datapath_eligible(project):

    link, node1, node2 = await _kernel_link(project)
    assert link._kernel_datapath_eligible(node1, node2) is True


@pytest.mark.asyncio
async def test_kernel_datapath_not_eligible_for_other_node_types(project):

    compute = MagicMock()
    compute.id = "compute-1"
    node1 = _node(project, compute, "docker1")
    node2 = _node(project, compute, "qemu1", node_type="qemu")
    link = UDPLink(project)
    await link.add_node(node1, 0, 0, batch=True, dump=False)
    await link.add_node(node2, 0, 0, batch=True, dump=False)
    assert link._kernel_datapath_eligible(node1, node2) is False


@pytest.mark.asyncio
async def test_kernel_datapath_not_eligible_across_computes(project):

    compute1 = MagicMock()
    compute1.id = "compute-1"
    compute2 = MagicMock()
    compute2.id = "compute-2"
    node1 = _node(project, compute1, "docker1")
    node2 = _node(project, compute2, "docker2")
    link = UDPLink(project)
    await link.add_node(node1, 0, 0, batch=True, dump=False)
    await link.add_node(node2, 0, 0, batch=True, dump=False)
    assert link._kernel_datapath_eligible(node1, node2) is False


@pytest.mark.asyncio
async def test_kernel_datapath_eligible_with_netem_filters(project):
    """
    Impairment filters with a tc netem equivalent (delay, packet_loss,
    corrupt) no longer disqualify the kernel datapath — they become one
    netem qdisc per veth host end.
    """

    link, node1, node2 = await _kernel_link(project)
    link._filters = {"delay": [10, 0], "packet_loss": [5], "corrupt": [1]}
    assert link._kernel_datapath_eligible(node1, node2) is True


@pytest.mark.asyncio
async def test_kernel_datapath_not_eligible_with_relay_only_filters(project):
    """
    frequency_drop and bpf only exist in the uBridge userspace relay — a
    link carrying one stays on the relay.
    """

    link, node1, node2 = await _kernel_link(project)
    link._filters = {"delay": [10, 0], "frequency_drop": [7]}
    assert link._kernel_datapath_eligible(node1, node2) is False

    link._filters = {"bpf": ["icmp"]}
    assert link._kernel_datapath_eligible(node1, node2) is False


@pytest.mark.asyncio
async def test_kernel_datapath_eligible_when_suspended(project):
    """
    A suspended link reports the synthetic frequency_drop emulation through
    get_active_filters() — that is relay-only mechanics and must not flip a
    kernel link to the relay on reopen/reset (suspend is carrier-driven).
    """

    link, node1, node2 = await _kernel_link(project)
    link._suspended = True
    assert link.get_active_filters() == {"frequency_drop": [-1]}
    assert link._kernel_datapath_eligible(node1, node2) is True


@pytest.mark.asyncio
async def test_kernel_datapath_eligible_with_markers(project):
    """
    Markers no longer disqualify the kernel datapath: they attach to the veth
    host end via uBridge's AF_PACKET marker module (marker add_kernel).
    """

    link, node1, node2 = await _kernel_link(project)
    link._markers = {"m": {"bpf": "icmp"}}
    assert link._kernel_datapath_eligible(node1, node2) is True


@pytest.mark.asyncio
async def test_kernel_datapath_eligible_with_project_marker_definitions(project):
    """
    Project-level marker definitions are inherited by every new link and ride
    the kernel datapath like private markers.
    """

    link, node1, node2 = await _kernel_link(project)
    project._marker_definitions = {"global-m": {"bpf": "icmp"}}
    try:
        assert link._kernel_datapath_eligible(node1, node2) is True
    finally:
        project._marker_definitions = {}


@pytest.mark.asyncio
async def test_kernel_datapath_eligible_for_running_nodes(project):
    """
    Docker adapters are born as veths (unified interface), so links attach
    to running containers too — no stopped-node requirement.
    """

    link, node1, node2 = await _kernel_link(project)
    node1._status = "started"
    node2._status = "started"
    assert link._kernel_datapath_eligible(node1, node2) is True


@pytest.mark.asyncio
async def test_kernel_datapath_not_eligible_for_unix_socket_containers(project):

    link, node1, node2 = await _kernel_link(project)
    node2._properties = {"environment": "GNS3_UNIX_SOCKET_NIO=1"}
    assert link._kernel_datapath_eligible(node1, node2) is False


@pytest.mark.asyncio
async def test_kernel_datapath_disabled_by_config(project):

    settings = Config.instance().settings.Server
    settings.enable_kernel_datapath = False
    try:
        link, node1, node2 = await _kernel_link(project)
        assert link._kernel_datapath_eligible(node1, node2) is False
    finally:
        settings.enable_kernel_datapath = True


@pytest.mark.asyncio
async def test_prepare_kernel_link_emits_bridge_nios(project):

    compute = MagicMock()
    compute.id = "compute-1"
    node1 = _node(project, compute, "docker1")
    node2 = _node(project, compute, "docker2")
    link = UDPLink(project)
    await link.add_node(node1, 0, 0, batch=True, dump=False)
    await link.add_node(node2, 0, 0, batch=True, dump=False)

    entries = await link._prepare()

    assert len(entries) == 2
    expected_bridge = "gns3" + link.id.replace("-", "")[:11]
    assert len(expected_bridge) == 15
    for entry in entries:
        assert entry[3]["type"] == "nio_bridge"
        assert entry[3]["bridge"] == expected_bridge
    # no UDP port reservation on the kernel datapath
    compute.post.assert_not_called()


@pytest.mark.asyncio
async def test_prepare_relay_link_allocates_udp_ports(project):

    compute1 = MagicMock()
    compute1.id = "compute-1"
    compute2 = MagicMock()
    compute2.id = "compute-2"

    async def subnet_callback(other):
        return ("192.168.1.1", "192.168.1.2")

    compute1.get_ip_on_same_subnet.side_effect = subnet_callback

    async def port_callback(path, data=None, **kwargs):
        response = MagicMock()
        response.json = {"udp_port": 1024}
        return response

    compute1.post.side_effect = port_callback
    compute2.post.side_effect = port_callback

    node1 = _node(project, compute1, "docker1")
    node2 = _node(project, compute2, "docker2")
    link = UDPLink(project)
    await link.add_node(node1, 0, 0, batch=True, dump=False)
    await link.add_node(node2, 0, 0, batch=True, dump=False)

    entries = await link._prepare()

    for entry in entries:
        assert entry[3]["type"] == "nio_udp"


@pytest.mark.asyncio
async def test_update_netem_filters_accepted_on_kernel_link(project):

    link, node1, node2 = await _kernel_link(project)
    await link._prepare()

    await link.update_filters({"delay": [10, 0], "packet_loss": [5]})
    assert link.filters == {"delay": [10, 0], "packet_loss": [5]}
    # both endpoints carry the filters (one netem qdisc per veth host end)
    by_node = {entry[0].id: entry[3] for entry in (await link._prepare())}
    assert by_node[node1.id]["filters"] == {"delay": [10, 0], "packet_loss": [5]}
    assert by_node[node2.id]["filters"] == {"delay": [10, 0], "packet_loss": [5]}


@pytest.mark.asyncio
async def test_update_relay_only_filters_rejected_on_kernel_link(project):

    link, _n1, _n2 = await _kernel_link(project)
    await link._prepare()

    with pytest.raises(ControllerError, match="kernel-datapath"):
        await link.update_filters({"frequency_drop": [10]})
    with pytest.raises(ControllerError, match="kernel-datapath"):
        await link.update_filters({"bpf": ["icmp"]})


@pytest.mark.asyncio
async def test_prepare_kernel_link_carries_markers(project):
    """
    Markers on a kernel link ride the capture node's NIO (routed by
    capture_node_id) exactly like on the relay datapath.
    """

    link, node1, node2 = await _kernel_link(project)
    link._markers = {"icmp": {"bpf": "icmp", "tag": 1, "capture_node_id": node1.id, "direction": None}}

    entries = await link._prepare()

    by_node = {entry[0].id: entry[3] for entry in entries}
    assert by_node[node1.id]["type"] == "nio_bridge"
    assert by_node[node1.id]["markers"]["icmp"]["bpf"] == "icmp"
    assert by_node[node1.id]["markers"]["icmp"]["tag"] == 1
    assert by_node[node2.id]["markers"] == {}


@pytest.mark.asyncio
async def test_start_marker_on_kernel_link_pushes_nio(project):
    """
    start_marker works on kernel links: the marker is stored and pushed via
    the NIO update like on the relay datapath (no kernel guard anymore).
    """

    link, node1, node2 = await _kernel_link(project)
    await link._prepare()
    link._created = True

    bodies = []

    async def put1(path, data=None, **kwargs):
        bodies.append((node1, data))

    async def put2(path, data=None, **kwargs):
        bodies.append((node2, data))

    node1.put = put1
    node2.put = put2

    with patch("gns3server.controller.udp_link.validate_bpf_syntax", return_value={"valid": True, "error": None}):
        await link.start_marker("icmp", "icmp", tag=3)

    entry = link._markers["icmp"]
    assert entry["bpf"] == "icmp"
    assert entry["capture_node_id"] == node1.id  # auto-picked: first marker-capable node
    n1_data = next(data for node, data in bodies if node is node1)
    n2_data = next(data for node, data in bodies if node is node2)
    assert n1_data["type"] == "nio_bridge"
    assert n1_data["filters"] == {}
    assert n1_data["markers"]["icmp"]["tag"] == 3
    assert n2_data["markers"] == {}


@pytest.mark.asyncio
async def test_kernel_datapath_property(project):

    link, _n1, _n2 = await _kernel_link(project)
    assert link.kernel_datapath is False
    await link._prepare()
    assert link.kernel_datapath is True


@pytest.mark.asyncio
async def test_update_suspend_kernel_link_sends_no_synthetic_filter(project):
    """
    Suspend is emulated on the relay datapath via a synthetic frequency_drop
    filter (get_active_filters); kernel links implement it natively via
    interface carrier and must push empty filters — the compute-side guard
    rejects non-empty filters on kernel NIOs.
    """

    link, node1, node2 = await _kernel_link(project)
    await link._prepare()

    bodies = []

    async def capture_put(path, data=None, **kwargs):
        bodies.append(data)

    node1.put = capture_put
    node2.put = capture_put

    await link.update_suspend(True)

    assert link._suspended is True
    assert len(bodies) == 2
    for body in bodies:
        assert body["filters"] == {}
        assert body["suspend"] is True
