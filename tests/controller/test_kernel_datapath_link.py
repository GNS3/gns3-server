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


def _mock_compute_http(compute):
    """Wire the async compute HTTP callbacks the relay paths need: POST
    (port reservation, NIO creation) and PUT (filter updates — without an
    awaitable put, a relay filter update blows up on the sync MagicMock,
    which is what made this file fail when run alone: some other module's
    fixtures happened to mask it in a full run)."""

    async def subnet_callback(other):
        return ("192.168.1.1", "192.168.1.2")

    compute.get_ip_on_same_subnet.side_effect = subnet_callback

    async def post_callback(path, data=None, **kwargs):
        response = MagicMock()
        response.json = {"udp_port": 1024}
        return response

    compute.post.side_effect = post_callback

    async def put_callback(path, data=None, **kwargs):
        response = MagicMock()
        response.json = {}
        return response

    compute.put.side_effect = put_callback


async def _relay_link(project):
    """A docker↔qemu link (mixed node types) — never kernel-eligible, so the
    relay _prepare path runs (UDP ports reserved through the mocked compute)."""

    compute = MagicMock()
    compute.id = "compute-1"
    _mock_compute_http(compute)
    node1 = _node(project, compute, "docker1")
    node2 = _node(project, compute, "qemu1", node_type="qemu")
    link = UDPLink(project)
    await link.add_node(node1, 0, 0, batch=True, dump=False)
    await link.add_node(node2, 0, 0, batch=True, dump=False)
    return link, node1, node2


@pytest.mark.asyncio
async def test_kernel_datapath_eligible(project):

    link, node1, node2 = await _kernel_link(project)
    assert link._kernel_datapath_eligible(node1, node2) is True


def _tap_capable_compute(tap_support=True, compute_id="compute-1"):
    compute = MagicMock()
    compute.id = compute_id
    compute.capabilities = {"ubridge_tap": tap_support}
    return compute


async def _link(project, node1, node2):
    link = UDPLink(project)
    await link.add_node(node1, 0, 0, batch=True, dump=False)
    await link.add_node(node2, 0, 0, batch=True, dump=False)
    return link


@pytest.mark.asyncio
async def test_kernel_datapath_not_eligible_for_other_node_types(project):
    """
    A node type with no anchor of its own (VPCS, cloud, ...) keeps the relay
    however capable the compute is — and a QEMU node on a compute whose
    uBridge cannot create persistent TAPs does too, because it runs on the
    legacy relay datapath there.
    """

    compute = _tap_capable_compute(tap_support=None)
    node1 = _node(project, compute, "docker1")
    node2 = _node(project, compute, "qemu1", node_type="qemu")
    link = await _link(project, node1, node2)
    assert link._kernel_datapath_eligible(node1, node2) is False

    compute = _tap_capable_compute()
    node1 = _node(project, compute, "vpcs1", node_type="vpcs")
    node2 = _node(project, compute, "docker1")
    link = await _link(project, node1, node2)
    assert link._kernel_datapath_eligible(node1, node2) is False


@pytest.mark.asyncio
async def test_kernel_datapath_eligible_for_iou_with_iol_tap_support(project):
    """
    IOU's Ethernet bays anchor on persistent TAPs bound to the IOL fabric
    (iol_bridge add_nio_tap) — its own capability, asked per compute like
    QEMU's, and mixable with docker/qemu endpoints on the same compute.
    """

    compute = MagicMock()
    compute.id = "compute-1"
    compute.capabilities = {"ubridge_tap": True, "ubridge_iol_tap": True}
    node1 = _node(project, compute, "iou1", node_type="iou")
    node2 = _node(project, compute, "iou2", node_type="iou")
    link = await _link(project, node1, node2)
    assert link._kernel_datapath_eligible(node1, node2) is True

    for peer in (_node(project, compute, "docker1"), _node(project, compute, "qemu1", node_type="qemu")):
        link = await _link(project, node1, peer)
        assert link._kernel_datapath_eligible(node1, peer) is True


@pytest.mark.asyncio
async def test_iou_eligibility_is_its_own_capability(project):
    """
    The tap module and the IOL-port TAP command land independently: a
    compute reporting only one of them keeps IOU on the relay (an old
    uBridge without add_nio_tap), and an unreported/failed probe does too.
    """

    compute = _tap_capable_compute()  # ubridge_tap only, no ubridge_iol_tap
    node1 = _node(project, compute, "iou1", node_type="iou")
    node2 = _node(project, compute, "docker1")
    link = await _link(project, node1, node2)
    assert link._kernel_datapath_eligible(node1, node2) is False

    compute = MagicMock()
    compute.id = "compute-1"
    compute.capabilities = {"ubridge_tap": True, "ubridge_iol_tap": None}
    node1 = _node(project, compute, "iou1", node_type="iou")
    link = await _link(project, node1, node2)
    assert link._kernel_datapath_eligible(node1, node2) is False


@pytest.mark.asyncio
async def test_kernel_datapath_eligible_for_dynamips_with_tap_support(project):
    """
    Dynamips Ethernet slot ports anchor on persistent TAPs the hypervisor
    opens (nio create_tap on a uBridge-created device), so they gate on the
    tap module like QEMU — no Dynamips-specific capability — and mix with
    docker/qemu/iou endpoints on the same compute.
    """

    compute = MagicMock()
    compute.id = "compute-1"
    compute.capabilities = {"ubridge_tap": True, "ubridge_iol_tap": True}
    node1 = _node(project, compute, "r1", node_type="dynamips")
    node2 = _node(project, compute, "r2", node_type="dynamips")
    link = await _link(project, node1, node2)
    assert link._kernel_datapath_eligible(node1, node2) is True

    for peer in (
        _node(project, compute, "docker1"),
        _node(project, compute, "qemu1", node_type="qemu"),
        _node(project, compute, "iou1", node_type="iou"),
    ):
        link = await _link(project, node1, peer)
        assert link._kernel_datapath_eligible(node1, peer) is True


@pytest.mark.asyncio
async def test_dynamips_eligibility_follows_the_tap_capability(project):
    """
    A compute whose uBridge cannot create persistent TAPs keeps Dynamips on
    the relay (the hypervisor would have nothing to open), and so does an
    unreported/failed probe.
    """

    node2 = _node(project, _tap_capable_compute(), "docker1")
    for tap_support in (None, False):
        compute = _tap_capable_compute(tap_support=tap_support)
        node1 = _node(project, compute, "r1", node_type="dynamips")
        link = await _link(project, node1, node2)
        assert link._kernel_datapath_eligible(node1, node2) is False


@pytest.mark.asyncio
async def test_kernel_datapath_not_eligible_for_dynamips_serial_ports(project):
    """
    A Dynamips serial port (NM-4T, WIC-2T, ...) stays on the relay whatever
    the compute's capabilities — the same per-port exclusion as IOU serial,
    decided by the controller's port matrix.
    """

    from gns3server.controller.ports.serial_port import SerialPort

    compute = MagicMock()
    compute.id = "compute-1"
    compute.capabilities = {"ubridge_tap": True}

    node1 = _node(project, compute, "r1", node_type="dynamips")
    node1._ports = [SerialPort("Serial0/0", 0, 0, 0)]
    node2 = _node(project, compute, "r2", node_type="dynamips")
    node2._ports = [SerialPort("Serial0/0", 0, 0, 0)]
    link = await _link(project, node1, node2)
    assert link._kernel_datapath_eligible(node1, node2) is False


@pytest.mark.asyncio
async def test_kernel_datapath_not_eligible_for_serial_ports(project):
    """
    A kernel link is an Ethernet segment: an IOU serial port stays on the
    relay whatever the compute's capabilities — dispatching it to the
    kernel path would fail at the compute (no anchor on a serial bay).
    """

    from gns3server.controller.ports.serial_port import SerialPort

    compute = MagicMock()
    compute.id = "compute-1"
    compute.capabilities = {"ubridge_tap": True, "ubridge_iol_tap": True}

    node1 = _node(project, compute, "iou1", node_type="iou")
    node1._ports = [SerialPort("Serial0/0", 0, 0, 0)]
    node2 = _node(project, compute, "iou2", node_type="iou")
    node2._ports = [SerialPort("Serial0/0", 0, 0, 0)]
    link = await _link(project, node1, node2)
    assert link._kernel_datapath_eligible(node1, node2) is False


@pytest.mark.asyncio
async def test_kernel_datapath_eligible_for_qemu_with_tap_support(project):
    """
    QEMU adapters anchor on a persistent TAP, so a compute whose uBridge has
    the tap module gets kernel links too — including the mixed docker-to-qemu
    case (both anchors end up in the same per-link kernel bridge).
    """

    compute = _tap_capable_compute()
    node1 = _node(project, compute, "qemu1", node_type="qemu")
    node2 = _node(project, compute, "qemu2", node_type="qemu")
    link = await _link(project, node1, node2)
    assert link._kernel_datapath_eligible(node1, node2) is True

    node2 = _node(project, compute, "docker1")
    link = await _link(project, node1, node2)
    assert link._kernel_datapath_eligible(node1, node2) is True


@pytest.mark.asyncio
async def test_kernel_datapath_capability_is_asked_per_compute(project):
    """
    A QEMU node on a compute without the tap module keeps the link on the
    relay even when its peer sits on a capable compute — the link needs both
    endpoints anchored, so the capability is a two-end AND.
    """

    capable = _tap_capable_compute(compute_id="compute-1")
    plain = _tap_capable_compute(tap_support=None, compute_id="compute-2")
    node1 = _node(project, capable, "qemu1", node_type="qemu")
    node2 = _node(project, plain, "qemu2", node_type="qemu")
    link = await _link(project, node1, node2)
    assert link._kernel_datapath_eligible(node1, node2) is False

    # same compute, but the compute cannot anchor: still the relay
    node2 = _node(project, _tap_capable_compute(tap_support=None), "qemu2", node_type="qemu")
    link = await _link(project, node1, node2)
    assert link._kernel_datapath_eligible(node1, node2) is False


@pytest.mark.asyncio
async def test_prepare_qemu_kernel_link_emits_bridge_nios(project):
    """
    The prepared link data is the same NIOBridge spec Docker links use — no
    UDP ports, no peer resolution — so nothing else in the controller has to
    know which node type the endpoint is.
    """

    compute = _tap_capable_compute()
    node1 = _node(project, compute, "qemu1", node_type="qemu")
    node2 = _node(project, compute, "qemu2", node_type="qemu")
    link = await _link(project, node1, node2)

    await link._prepare()

    assert link.kernel_datapath is True
    assert [d["type"] for d in link._link_data] == ["nio_bridge", "nio_bridge"]
    assert link._link_data[0]["bridge"] == link._link_data[1]["bridge"]


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
async def test_kernel_datapath_eligible_with_frequency_drop(project):
    """
    frequency_drop runs on the kernel datapath too (the eBPF classifier's
    exact every-Nth mode) — no filter type forces the relay anymore; only
    topology does (mixed node types, cross-compute, unix-socket
    containers, config off).
    """

    link, node1, node2 = await _kernel_link(project)
    link._filters = {"delay": [10, 0], "frequency_drop": [7], "quota": [1000000, 100]}
    assert link._kernel_datapath_eligible(node1, node2) is True


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
async def test_kernel_datapath_not_eligible_for_iol_runner_containers(project):
    """
    The IOL runner marker is the other way into the unix-socket datapath: the
    compute selects IOLDockerVM on GNS3_IOL_RUNNER and that class wires the
    adapters through AF_UNIX socket pairs whatever the generic
    GNS3_UNIX_SOCKET_NIO knob says — and the documented environment for
    those nodes carries only the marker. Matching the knob alone let them
    through to a kernel link their compute cannot serve.
    """

    link, node1, node2 = await _kernel_link(project)
    node2._properties = {"environment": "GNS3_IOL_RUNNER=1"}
    assert link._kernel_datapath_eligible(node1, node2) is False

    # the marker travels in a multi-line environment like any other knob
    node2._properties = {"environment": "GNS3_IOL_RUNNER=1\nGNS3_IOL_STARTUP_CONFIG=cfg.txt"}
    assert link._kernel_datapath_eligible(node1, node2) is False


@pytest.mark.asyncio
async def test_kernel_datapath_not_eligible_for_an_iol_runner_container_on_a_switch(project):
    """
    The switch fast path absorbs the peer's anchor, and a container bridged
    through unix sockets has none — nor will it ever. The switch defers a
    join against a stopped peer by design (it must not fail the link), so
    such a cable would be silently dead instead of merely slow: the gate has
    to run before the switch branch, keeping the link on the relay the
    switch's own port TAP serves.
    """

    compute = MagicMock()
    compute.id = "compute-1"
    compute.capabilities = {"ubridge_tap": True, "ubridge_iol_tap": True}
    switch = _node(project, compute, "sw1", node_type="ethernet_switch")
    peer = _node(project, compute, "iol1", environment="GNS3_IOL_RUNNER=1")
    link = await _link(project, switch, peer)

    assert link._kernel_datapath_eligible(switch, peer) is False


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
async def test_update_frequency_drop_accepted_on_kernel_link(project):
    """
    frequency_drop rides the kernel NIO to both endpoints like every other
    filter type — the compute translates it to the eBPF every-Nth mode.
    """

    link, node1, node2 = await _kernel_link(project)
    await link._prepare()

    await link.update_filters({"frequency_drop": [10]})
    assert link.filters == {"frequency_drop": [10]}
    by_node = {entry[0].id: entry[3] for entry in (await link._prepare())}
    assert by_node[node1.id]["filters"] == {"frequency_drop": [10]}
    assert by_node[node2.id]["filters"] == {"frequency_drop": [10]}


@pytest.mark.asyncio
async def test_update_bpf_filters_accepted_on_kernel_link(project):
    """
    bpf expressions ride the kernel NIO to BOTH endpoints (each end's
    cls_bpf classifiers cover the traffic entering that container — the
    same both-directions-once net effect as the relay's single filtered
    bridge).
    """

    link, node1, node2 = await _kernel_link(project)
    await link._prepare()

    await link.update_filters({"bpf": ["icmp\nudp port 53"]})
    assert link.filters == {"bpf": ["icmp\nudp port 53"]}
    by_node = {entry[0].id: entry[3] for entry in (await link._prepare())}
    assert by_node[node1.id]["filters"] == {"bpf": ["icmp\nudp port 53"]}
    assert by_node[node2.id]["filters"] == {"bpf": ["icmp\nudp port 53"]}


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


# ---------------------------------------------------------------------------
# P6a: netem-extension filters (rate / reorder / gemodel / duplicate / seed /
# limit / distribution / correlation)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_kernel_datapath_eligible_with_netem_extension_filters(project):
    """
    All netem-extension types have a tc netem equivalent — they keep the
    link kernel-eligible (kernel/relay is a purely topological choice).
    """

    link, node1, node2 = await _kernel_link(project)
    link._filters = {
        "delay": [100, 20, "normal"],
        "packet_loss": [5, 25],
        "duplicate": [10],
        "reorder": [25, 0, 5],
        "rate": ["512kbit"],
        "gemodel": [100, 0, 30],
        "seed": [42],
        "limit": [5000],
        "quota": [1000000, 100],
        "window_drop": [0, 800, 100, 2400, 200],
    }
    # gemodel/packet_loss are mutually exclusive — drop packet_loss for the
    # eligibility check (validation rejects the mix elsewhere)
    link._filters.pop("packet_loss")
    assert link._kernel_datapath_eligible(node1, node2) is True


@pytest.mark.asyncio
async def test_update_netem_extension_filters_accepted_on_kernel_link(project):
    """
    The extension filters ride the kernel NIO to both endpoints like the
    base netem surface.
    """

    link, node1, node2 = await _kernel_link(project)
    await link._prepare()

    filters = {"delay": [100, 20, "normal"], "rate": ["512kbit"], "reorder": [25, 0, 5]}
    await link.update_filters(filters)
    assert link.filters == filters
    by_node = {entry[0].id: entry[3] for entry in (await link._prepare())}
    assert by_node[node1.id]["filters"] == filters
    assert by_node[node2.id]["filters"] == filters


@pytest.mark.asyncio
async def test_update_kernel_only_filters_rejected_on_relay_link(project):
    """
    Netem-extension / quota / window_drop filters have no relay equivalent:
    setting them on a created relay link is a 409. (The link is relay-wired
    because the endpoints are mixed node types.)
    """

    link, _n1, _n2 = await _relay_link(project)
    await link._prepare()
    assert link.kernel_datapath is False
    link._created = True  # the computes hold the UDP NIOs

    with pytest.raises(ControllerError, match="kernel-datapath"):
        await link.update_filters({"rate": ["512kbit"]})
    with pytest.raises(ControllerError, match="kernel-datapath"):
        await link.update_filters({"window_drop": [0, 800, 100, 2400]})
    with pytest.raises(ControllerError, match="period must be greater than or equal"):
        # cross-parameter rule mirrors the tc window grammar
        await link.update_filters({"window_drop": [0, 2000, 100, 1000]})
    # the stored filters are untouched
    assert link.filters == {}

    # frequency_drop still runs on the relay (its uBridge userspace filter)
    await link.update_filters({"frequency_drop": [7]})
    assert link.filters == {"frequency_drop": [7]}


@pytest.mark.asyncio
async def test_update_window_drop_accepted_on_kernel_link(project):
    """
    window_drop rides the kernel NIO to both endpoints — including the
    start=0 form (an immediate outage is NOT an "inactive" filter).
    """

    link, node1, node2 = await _kernel_link(project)
    await link._prepare()

    filters = {"window_drop": [0, 800, 100, 2400, 200]}
    await link.update_filters(filters)
    assert link.filters == filters
    by_node = {entry[0].id: entry[3] for entry in (await link._prepare())}
    assert by_node[node1.id]["filters"] == filters
    assert by_node[node2.id]["filters"] == filters


@pytest.mark.asyncio
async def test_update_kernel_only_filters_accepted_before_creation(project):
    """
    While loading a project the datapath is not decided yet (update_filters
    runs before _prepare) — a link that will be kernel-wired must accept the
    extension filters. Only _prepare decides, dropping what the relay cannot
    run.
    """

    link, _n1, _n2 = await _kernel_link(project)
    await link.update_filters({"rate": ["512kbit"], "reorder": [25, 0, 5], "delay": [100, 10]})
    assert link.filters["rate"] == ["512kbit"]


@pytest.mark.asyncio
async def test_prepare_relay_link_strips_kernel_only_filters(project):
    """
    A relay-wired link (mixed node types) built from a topology carrying
    extension filters drops them with a warning instead of pushing an
    unknown filter type to uBridge. frequency_drop stays — the relay's
    userspace filter still serves it.
    """

    link, node1, node2 = await _relay_link(project)
    link._filters = {"frequency_drop": [7], "rate": ["512kbit"], "delay": [100, 20, "normal"], "packet_loss": [5, 25]}
    entries = await link._prepare()
    assert link.kernel_datapath is False
    by_node = {entry[0].id: entry[3] for entry in entries}
    assert by_node[node1.id]["type"] == "nio_udp"
    # the relay's filter node keeps what it can run; rate, the distribution
    # and the loss correlation are kernel-only and stripped (the far side
    # carries no filters — the relay filters one bridge)
    assert by_node[node1.id]["filters"] == {"frequency_drop": [7], "delay": [100, 20], "packet_loss": [5]}
    assert by_node[node2.id]["filters"] == {}


@pytest.mark.asyncio
async def test_available_filters_gated_by_compute_capabilities(project):
    """
    Kernel links only offer the filter types the endpoints' computes report
    a uBridge able to run (ebpf_modes tokens, cbpf, netem keywords).
    """

    link, node1, _node2 = await _kernel_link(project)
    link._link_data = [{"type": "nio_bridge"}]
    node1.compute.capabilities = {
        "ubridge_tc": {
            "netem": ["delay", "jitter", "loss", "rate"],
            "ebpf": True,
            "ebpf_modes": ["nth", "quota"],
            "cbpf": False,
        }
    }
    types = [f["type"] for f in link.available_filters()]
    assert "frequency_drop" in types  # nth declared
    assert "quota" in types  # quota declared
    assert "window_drop" not in types  # token missing
    assert "bpf" not in types  # cbpf off
    assert "rate" in types  # netem keyword present
    assert "gemodel" not in types  # netem keyword missing
    assert "delay" in types  # core netem runs on any tc-module build


@pytest.mark.asyncio
async def test_available_filters_unconstrained_without_report(project):
    """
    Computes that report no uBridge tc capabilities (older servers, failed
    probe) impose no constraint: the full list stays offered and apply-time
    validation is the guard.
    """

    from gns3server.controller.link import FILTERS

    link, _node1, _node2 = await _kernel_link(project)
    link._link_data = [{"type": "nio_bridge"}]
    assert [f["type"] for f in link.available_filters()] == [f["type"] for f in FILTERS]


# ---------------------------------------------------------------------------
# Ethernet switch fast path: the switch absorbs the peer's anchor
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_switch_links_select_the_kernel_fast_path(project):
    """
    A link with an Ethernet switch endpoint rides the kernel fast path when
    the *peer* can anchor — the switch side needs no anchoring capability
    (its bridge exists by construction). A switch peer cascades through a
    veth pair (one end per bridge — a kernel interface belongs to exactly
    one bridge, so the pair is the only cable shape); anchor-less peers
    stay on the relay.
    """

    compute = MagicMock()
    compute.id = "compute-1"
    compute.capabilities = {"ubridge_tap": True, "ubridge_iol_tap": True}
    switch = _node(project, compute, "sw1", node_type="ethernet_switch")

    for peer in (
        _node(project, compute, "docker1"),
        _node(project, compute, "qemu1", node_type="qemu"),
        _node(project, compute, "iou1", node_type="iou"),
        _node(project, compute, "r1", node_type="dynamips"),
    ):
        link = await _link(project, switch, peer)
        assert link._kernel_datapath_eligible(switch, peer) is True, peer.node_type

    # a switch peer: cascade — the veth pair joins the two kernel bridges
    switch2 = _node(project, compute, "sw2", node_type="ethernet_switch")
    link = await _link(project, switch, switch2)
    assert link._kernel_datapath_eligible(switch, switch2) is True

    # an anchor-less peer
    vpcs = _node(project, compute, "pc1", node_type="vpcs")
    link = await _link(project, switch, vpcs)
    assert link._kernel_datapath_eligible(switch, vpcs) is False

    # a peer whose compute cannot anchor stays relay too
    compute_no_tap = _tap_capable_compute(tap_support=None)
    qemu = _node(project, compute_no_tap, "qemu1", node_type="qemu")
    switch3 = _node(project, compute_no_tap, "sw3", node_type="ethernet_switch")
    link = await _link(project, switch3, qemu)
    assert link._kernel_datapath_eligible(switch3, qemu) is False


@pytest.mark.asyncio
async def test_switch_link_prepare_emits_anchor_and_external_bridge(project):
    """
    The fast path's wire format: the switch receives ``nio_anchor`` naming
    the peer's anchor (the shared naming contract, computable while the
    node is stopped), the peer receives ``nio_bridge`` with no bridge —
    its anchor is bridged by the switch. The link's tc impairments are
    owned by exactly one end (the switch): both would hit the same
    interface.
    """

    from gns3server.utils.kernel_anchor import kernel_anchor_name

    compute = MagicMock()
    compute.id = "compute-1"
    switch = _node(project, compute, "sw1", node_type="ethernet_switch")
    peer = _node(project, compute, "docker1")
    link = await _link(project, switch, peer)
    link._filters = {"delay": [10]}

    entries = await link._prepare()
    switch_nio = entries[0][3]
    peer_nio = entries[1][3]

    assert switch_nio["type"] == "nio_anchor"
    assert switch_nio["anchor"] == kernel_anchor_name("docker", peer.id, 0, 0)
    assert switch_nio["filters"] == {"delay": [10]}
    assert peer_nio["type"] == "nio_bridge"
    assert peer_nio["bridge"] is None
    assert peer_nio["filters"] == {}
    assert link.kernel_datapath is True

    # the reverse endpoint order must keep index alignment
    link = await _link(project, peer, switch)
    link._filters = {"delay": [10]}
    entries = await link._prepare()
    assert entries[0][3]["type"] == "nio_bridge"
    assert entries[0][3]["bridge"] is None
    assert entries[0][3]["filters"] == {}
    assert entries[1][3]["type"] == "nio_anchor"
    assert entries[1][3]["filters"] == {"delay": [10]}


@pytest.mark.asyncio
async def test_switch_link_repushes_the_switch_nio_on_node_start(project):
    """
    The switch cannot observe the peer's anchors coming into existence: the
    controller re-pushes the switch's NIO after a node of the link starts,
    which completes a deferred join (or re-joins an anchor a peer restart
    replaced). Relay links do nothing.
    """

    from tests.utils import AsyncioMagicMock

    compute = MagicMock()
    compute.id = "compute-1"
    switch = _node(project, compute, "sw1", node_type="ethernet_switch")
    peer = _node(project, compute, "docker1")
    link = await _link(project, switch, peer)
    entries = await link._prepare()
    link._created = True
    switch.put = AsyncioMagicMock()

    await link.node_started(peer)
    switch.put.assert_called_once_with("/adapters/0/ports/0/nio", data=entries[0][3], timeout=120)

    # a relay link never re-pushes anything
    switch.put.reset_mock()
    compute2 = MagicMock()
    compute2.id = "compute-1"
    relay_switch = _node(project, compute2, "sw2", node_type="ethernet_switch")
    vpcs = _node(project, compute2, "pc1", node_type="vpcs")
    relay_link = await _link(project, relay_switch, vpcs)
    relay_link._created = True
    relay_switch.put = AsyncioMagicMock()
    await relay_link.node_started(vpcs)
    assert not relay_switch.put.called


# ---------------------------------------------------------------------------
# Switch-to-switch cascade: one veth pair joins the two kernel bridges
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prepare_cascade_link_emits_paired_anchor_nios(project):
    """
    A link between two Ethernet switches rides the kernel datapath through
    one veth pair: each side gets an anchor NIO naming its own end and
    carrying the other end's name (both sides create the pair when their
    end is missing, so no ordering between the two NIO posts is needed).
    Unlike the absorbed-anchor fast path, filters are two-sided — each end
    is its own interface, so each direction of the link is impaired exactly
    once like any other kernel link.
    """

    from gns3server.utils.kernel_anchor import kernel_cascade_names

    compute = MagicMock()
    compute.id = "compute-1"
    sw1 = _node(project, compute, "sw1", node_type="ethernet_switch")
    sw2 = _node(project, compute, "sw2", node_type="ethernet_switch")
    link = await _link(project, sw1, sw2)
    link._filters = {"delay": [10]}

    entries = await link._prepare()
    end0, end1 = kernel_cascade_names(link.id)

    assert entries[0][3] == {
        "type": "nio_anchor",
        "anchor": end0,
        "peer": end1,
        "filters": {"delay": [10]},
        "markers": {},
        "suspend": False,
    }
    assert entries[1][3] == {
        "type": "nio_anchor",
        "anchor": end1,
        "peer": end0,
        "filters": {"delay": [10]},
        "markers": {},
        "suspend": False,
    }
    assert link.kernel_datapath is True


@pytest.mark.asyncio
async def test_node_started_repushes_both_cascade_ends(project):
    """
    A cascade link has a switch on both ends and each end is its own veth
    half: whichever switch starts (recreating its bridge and losing its
    half's membership), both ends are re-pushed — each switch's update
    re-checks and re-joins its own half.
    """

    from tests.utils import AsyncioMagicMock

    compute = MagicMock()
    compute.id = "compute-1"
    sw1 = _node(project, compute, "sw1", node_type="ethernet_switch")
    sw2 = _node(project, compute, "sw2", node_type="ethernet_switch")
    link = await _link(project, sw1, sw2)
    entries = await link._prepare()
    link._created = True
    sw1.put = AsyncioMagicMock()
    sw2.put = AsyncioMagicMock()

    await link.node_started(sw1)

    sw1.put.assert_called_once_with("/adapters/0/ports/0/nio", data=entries[0][3], timeout=120)
    sw2.put.assert_called_once_with("/adapters/0/ports/0/nio", data=entries[1][3], timeout=120)
