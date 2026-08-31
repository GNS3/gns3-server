# -*- coding: utf-8 -*-
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

import os
from collections import OrderedDict

import pytest
import pytest_asyncio

from tests.utils import asyncio_patch, AsyncioMagicMock
from unittest.mock import patch, MagicMock

from gns3server.compute.vpcs.vpcs_vm import VPCSVM
from gns3server.compute.docker.docker_vm import DockerVM
from gns3server.compute.error import NodeError
from gns3server.compute.vpcs import VPCS
from gns3server.compute.nios.nio_udp import NIOUDP


@pytest_asyncio.fixture(scope="function")
async def manager(port_manager):

    m = VPCS.instance()
    m.port_manager = port_manager
    return m


@pytest.fixture(scope="function")
def node(compute_project, manager):

    return VPCSVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", compute_project, manager)


def test_temporary_directory(compute_project, manager):

    node = VPCSVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", compute_project, manager)
    assert isinstance(node.temporary_directory, str)


def test_console(compute_project, manager, port_manager):

    node = VPCSVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", compute_project, manager)
    # pick a port that is actually free on this host: a hardcoded one may be
    # taken by a running gns3server/qemu on a dev machine, and the setter would
    # silently replace it with the next free port
    console_port = port_manager.get_free_tcp_port(node.project)
    port_manager.release_tcp_port(console_port, node.project)
    node.console = console_port
    assert node.console == console_port
    node.console = None
    assert node.console is None


def test_change_console_port(node, port_manager):

    port1 = port_manager.get_free_tcp_port(node.project)
    port2 = port_manager.get_free_tcp_port(node.project)
    port_manager.release_tcp_port(port1, node.project)
    port_manager.release_tcp_port(port2, node.project)
    node.console = port1
    node.console = port2
    assert node.console == port2
    port_manager.reserve_tcp_port(port1, node.project)


def test_console_vnc_invalid(compute_project, manager):

    node = VPCSVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", compute_project, manager)
    node._console_type = "vnc"
    with pytest.raises(NodeError):
        node.console = 2012


@pytest.mark.asyncio
async def test_close(node, port_manager):

    assert node.console is not None
    aux = port_manager.get_free_tcp_port(node.project)
    port_manager.release_tcp_port(aux, node.project)

    node.aux = aux
    port = node.console
    assert await node.close()
    # Raise an exception if the port is not free
    port_manager.reserve_tcp_port(port, node.project)
    # Raise an exception if the port is not free
    port_manager.reserve_tcp_port(aux, node.project)
    assert node.console is None
    assert node.aux is None

    # Called twice closed should return False
    assert await node.close() is False


def test_aux(compute_project, manager, port_manager):

    aux = port_manager.get_free_tcp_port(compute_project)
    port_manager.release_tcp_port(aux, compute_project)

    node = DockerVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", compute_project, manager, "ubuntu", aux=aux, aux_type="telnet")
    assert node.aux == aux
    node.aux = None
    assert node.aux is None


def test_allocate_aux(compute_project, manager):

    node = VPCSVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", compute_project, manager)
    assert node.aux is None

    # Docker has an aux port by default
    node = DockerVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", compute_project, manager, "ubuntu", aux_type="telnet")
    assert node.aux is not None


def test_change_aux_port(compute_project, manager, port_manager):

    node = DockerVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", compute_project, manager, "ubuntu", aux_type="telnet")
    port1 = port_manager.get_free_tcp_port(node.project)
    port2 = port_manager.get_free_tcp_port(node.project)
    port_manager.release_tcp_port(port1, node.project)
    port_manager.release_tcp_port(port2, node.project)
    node.aux = port1
    node.aux = port2
    assert node.aux == port2
    port_manager.reserve_tcp_port(port1, node.project)


@pytest.mark.asyncio
async def test_update_ubridge_udp_connection(node):

    filters = {
        "latency": [10]
    }

    snio = NIOUDP(1245, "localhost", 1246)
    dnio = NIOUDP(1245, "localhost", 1244)
    dnio.filters = filters
    with asyncio_patch("gns3server.compute.base_node.BaseNode._ubridge_apply_filters") as mock:
        await node.update_ubridge_udp_connection('VPCS-10', snio, dnio)
    mock.assert_called_with("VPCS-10", filters)


@pytest.mark.asyncio
async def test_ubridge_apply_filters(node):

    filters = OrderedDict((
        ('latency', [10]),
        ('bpf', ["icmp[icmptype] == 8\ntcp src port 53"])
    ))
    node._ubridge_send = AsyncioMagicMock()
    await node._ubridge_apply_filters("VPCS-10", filters)
    node._ubridge_send.assert_any_call("bridge reset_packet_filters VPCS-10")
    node._ubridge_send.assert_any_call("bridge add_packet_filter VPCS-10 filter0 latency 10")


@pytest.mark.asyncio
async def test_ubridge_apply_bpf_filters(node):

    filters = {
        "bpf": ["icmp[icmptype] == 8\ntcp src port 53"]
    }
    node._ubridge_send = AsyncioMagicMock()
    await node._ubridge_apply_filters("VPCS-10", filters)
    node._ubridge_send.assert_any_call("bridge reset_packet_filters VPCS-10")
    node._ubridge_send.assert_any_call("bridge add_packet_filter VPCS-10 filter0 bpf \"icmp[icmptype] == 8\"")
    node._ubridge_send.assert_any_call("bridge add_packet_filter VPCS-10 filter1 bpf \"tcp src port 53\"")


@pytest.mark.asyncio
async def test_set_marker_filter_state_off(compute_project, manager):

    node = VPCSVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", compute_project, manager)
    node._ubridge_send = AsyncioMagicMock()
    node._marker_filter_bridges["m", "L"] = "VPCS-10"
    await node._ubridge_set_marker_filter_state("m", False)
    node._ubridge_send.assert_called_with("bridge enable_packet_filter VPCS-10 m off")


@pytest.mark.asyncio
async def test_set_marker_filter_state_on(compute_project, manager):

    node = VPCSVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", compute_project, manager)
    node._ubridge_send = AsyncioMagicMock()
    node._marker_filter_bridges["m", "L"] = "VPCS-10"
    await node._ubridge_set_marker_filter_state("m", True)
    node._ubridge_send.assert_called_with("bridge enable_packet_filter VPCS-10 m on")


@pytest.mark.asyncio
async def test_marker_pause_sends_command(compute_project, manager):

    node = VPCSVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", compute_project, manager)
    node._ubridge_hypervisor = AsyncioMagicMock()
    await node._ubridge_marker_pause()
    node._ubridge_hypervisor.send.assert_called_with("marker pause")


@pytest.mark.asyncio
async def test_marker_resume_sends_command(compute_project, manager):

    node = VPCSVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", compute_project, manager)
    node._ubridge_hypervisor = AsyncioMagicMock()
    await node._ubridge_marker_resume()
    node._ubridge_hypervisor.send.assert_called_with("marker resume")


@pytest.mark.asyncio
async def test_apply_markers_turns_disabled_filter_off(compute_project, manager):
    # Part A: a disabled marker is installed (add_packet_filter) then turned off
    # with enable_packet_filter … off, and its bridge is recorded for toggling.

    node = VPCSVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", compute_project, manager)
    node._ubridge_send = AsyncioMagicMock()
    nio = NIOUDP(1234, "127.0.0.1", 4321)
    nio.markers = {"m": {"bpf": "icmp", "tag": None, "link_id": "L1", "direction": None, "enabled": False}}
    with patch("gns3server.compute.marker.marker_manager.MarkerManager") as mm:
        mm.instance.return_value.register = MagicMock()
        await node._ubridge_apply_markers("VPCS-10", nio)
    node._ubridge_send.assert_any_call("bridge enable_packet_filter VPCS-10 m off")
    assert node._marker_filter_bridges["m", "L1"] == "VPCS-10"


def test_marker_linktype_normalizes():
    # Ethernet / unset → None (linktype omitted; uBridge defaults to EN10MB).
    assert VPCSVM._marker_linktype(None) is None
    assert VPCSVM._marker_linktype("") is None
    assert VPCSVM._marker_linktype("DLT_EN10MB") is None
    # Serial DLTs from SerialPort.data_link_types, DLT_ prefix stripped.
    assert VPCSVM._marker_linktype("DLT_C_HDLC") == "C_HDLC"
    assert VPCSVM._marker_linktype("DLT_PPP_SERIAL") == "PPP_SERIAL"
    assert VPCSVM._marker_linktype("DLT_FRELAY") == "FRELAY"
    assert VPCSVM._marker_linktype("DLT_ATM_RFC1483") == "ATM_RFC1483"
    # Case-insensitive input → canonical uppercase (pcap_datalink_name_to_val is
    # case-sensitive and expects the uppercase form). Shared by base_node and IOU.
    assert VPCSVM._marker_linktype("dlt_c_hdlc") == "C_HDLC"


@pytest.mark.asyncio
async def test_apply_markers_appends_linktype_for_serial(compute_project, manager):
    # A serial data_link_type reaches the uBridge mark command as `linktype C_HDLC`
    # so the BPF offsets and pcap decode match the WAN encapsulation.
    node = VPCSVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", compute_project, manager)
    node._ubridge_send = AsyncioMagicMock()
    nio = NIOUDP(1234, "127.0.0.1", 4321)
    nio.markers = {"m": {"bpf": "icmp", "tag": None, "link_id": "L1",
                         "direction": None, "data_link_type": "DLT_C_HDLC", "enabled": True}}
    with patch("gns3server.compute.marker.marker_manager.MarkerManager") as mm:
        mm.instance.return_value.register = MagicMock()
        await node._ubridge_apply_markers("VPCS-10", nio)
    sent = [c.args[0] for c in node._ubridge_send.call_args_list]
    assert any("linktype C_HDLC" in s for s in sent)


@pytest.mark.asyncio
async def test_apply_markers_omits_linktype_for_ethernet(compute_project, manager):
    # Ethernet (DLT_EN10MB) → no linktype keyword; uBridge defaults to EN10MB.
    node = VPCSVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", compute_project, manager)
    node._ubridge_send = AsyncioMagicMock()
    nio = NIOUDP(1234, "127.0.0.1", 4321)
    nio.markers = {"m": {"bpf": "icmp", "tag": None, "link_id": "L1",
                         "direction": None, "data_link_type": "DLT_EN10MB", "enabled": True}}
    with patch("gns3server.compute.marker.marker_manager.MarkerManager") as mm:
        mm.instance.return_value.register = MagicMock()
        await node._ubridge_apply_markers("VPCS-10", nio)
    sent = [c.args[0] for c in node._ubridge_send.call_args_list]
    assert not any("linktype" in s for s in sent)


@pytest.mark.asyncio
async def test_delete_marker_capture_removes_pcap_and_entry(compute_project, manager):
    # Deleting a marker's capture removes its pcap and forgets the bridge entry.
    node = VPCSVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", compute_project, manager)
    markers_dir = compute_project.markers_working_directory()
    os.makedirs(markers_dir, exist_ok=True)
    node._marker_filter_bridges["m", "L1"] = "VPCS-10"
    pcap = os.path.join(markers_dir, f"{node.id}_L1_m.pcap")
    open(pcap, "wb").write(b"data")

    await node.delete_marker_capture("m", "L1")

    assert not os.path.exists(pcap)
    assert ("m", "L1") not in node._marker_filter_bridges


@pytest.mark.asyncio
async def test_delete_marker_capture_idempotent_when_missing(compute_project, manager):
    # No file on disk → must not raise, and still clears the entry.
    node = VPCSVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", compute_project, manager)
    node._marker_filter_bridges["m", "L1"] = "VPCS-10"

    await node.delete_marker_capture("m", "L1")

    assert ("m", "L1") not in node._marker_filter_bridges


@pytest.mark.asyncio
async def test_delete_marker_capture_sends_delete_filter(compute_project, manager):
    # With uBridge running, removing a marker issues a fine-grained
    # delete_packet_filter (not a bridge-wide reset) so sibling pcaps stay open.
    node = VPCSVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", compute_project, manager)
    node._ubridge_send = AsyncioMagicMock()
    node._ubridge_hypervisor = MagicMock()
    node._ubridge_hypervisor.is_running.return_value = True
    node._marker_filter_bridges["m", "L1"] = "VPCS-10"

    await node.delete_marker_capture("m", "L1")

    node._ubridge_send.assert_any_call("bridge delete_packet_filter VPCS-10 m")
    assert ("m", "L1") not in node._marker_filter_bridges


@pytest.mark.asyncio
async def test_delete_marker_capture_drops_from_nio_markers(compute_project, manager):
    # The marker spec cached on the port NIO (nio.markers) is what
    # _ubridge_apply_markers reads on node start. delete_marker_capture must drop
    # it, else deleting a marker while the node is stopped leaves the spec in
    # nio.markers and starting the node reinstalls it (empty pcap reappears).
    node = VPCSVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", compute_project, manager)
    nio = NIOUDP(1234, "127.0.0.1", 4321)
    nio.markers = {"m": {"bpf": "icmp", "tag": None, "link_id": "L1",
                         "direction": None, "enabled": True}}
    await node.delete_marker_capture("m", "L1", nio)
    assert "m" not in nio.markers


@pytest.mark.asyncio
async def test_rebuild_marker_filter_delete_then_add(compute_project, manager):
    # rebuild re-installs a single filter (delete_packet_filter + add) with the
    # new params, no bridge reset; enabled=False turns it off after re-add.
    node = VPCSVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", compute_project, manager)
    node._ubridge_send = AsyncioMagicMock()
    node._ubridge_hypervisor = MagicMock()
    node._ubridge_hypervisor.is_running.return_value = True
    node._marker_filter_bridges["m", "L1"] = "VPCS-10"

    await node.rebuild_marker_filter("m", "L1", "tcp", tag=7, direction="rx", enabled=False)

    cmds = [c.args[0] for c in node._ubridge_send.call_args_list]
    assert any("delete_packet_filter VPCS-10 m" in c for c in cmds)
    assert any("add_packet_filter VPCS-10 m mark" in c and "tcp" in c for c in cmds)
    assert any("enable_packet_filter VPCS-10 m off" in c for c in cmds)


@pytest.mark.asyncio
async def test_apply_markers_skips_already_installed(compute_project, manager):
    # Incremental apply: a marker already in _marker_filter_bridges is not
    # re-added (uBridge keeps it across reset), so its pcap isn't reopened.
    node = VPCSVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", compute_project, manager)
    node._ubridge_send = AsyncioMagicMock()
    node._marker_filter_bridges["m", "L1"] = "VPCS-10"  # already installed
    nio = NIOUDP(1234, "127.0.0.1", 4321)
    nio.markers = {"m": {"bpf": "icmp", "tag": None, "link_id": "L1", "direction": None, "enabled": True}}
    with patch("gns3server.compute.marker.marker_manager.MarkerManager") as mm:
        mm.instance.return_value.register = MagicMock()
        await node._ubridge_apply_markers("VPCS-10", nio)
    cmds = [c.args[0] for c in node._ubridge_send.call_args_list]
    assert not any("add_packet_filter" in c for c in cmds)  # skipped, not re-added


@pytest.mark.asyncio
async def test_apply_markers_deletes_removed(compute_project, manager):
    # Reconcile: a marker no longer in nio.markers is deleted from uBridge
    # (filter + registry), not left as an orphan still matching packets.
    node = VPCSVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", compute_project, manager)
    node._ubridge_send = AsyncioMagicMock()
    node._ubridge_hypervisor = MagicMock()
    node._ubridge_hypervisor.is_running.return_value = True
    node._marker_filter_bridges["m", "L1"] = "VPCS-10"
    node._marker_specs["m", "L1"] = {"bpf": "icmp", "enabled": True}
    nio = NIOUDP(1234, "127.0.0.1", 4321)
    nio.markers = {}  # marker removed
    with patch("gns3server.compute.marker.marker_manager.MarkerManager") as mm:
        mm.instance.return_value.unregister = MagicMock()
        await node._ubridge_apply_markers("VPCS-10", nio)
    cmds = [c.args[0] for c in node._ubridge_send.call_args_list]
    assert any("delete_packet_filter VPCS-10 m" in c for c in cmds)
    assert ("m", "L1") not in node._marker_filter_bridges
    assert ("m", "L1") not in node._marker_specs


@pytest.mark.asyncio
async def test_apply_markers_rebuilds_changed_bpf(compute_project, manager):
    # Reconcile: a marker whose bpf changed is rebuilt (delete + re-add), so
    # uBridge ends up with the new expression — not the stale original.
    node = VPCSVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", compute_project, manager)
    node._ubridge_send = AsyncioMagicMock()
    node._ubridge_hypervisor = MagicMock()
    node._ubridge_hypervisor.is_running.return_value = True
    node._marker_filter_bridges["m", "L1"] = "VPCS-10"
    node._marker_specs["m", "L1"] = {"bpf": "icmp", "tag": None, "direction": None,
                                     "data_link_type": None, "enabled": True}
    nio = NIOUDP(1234, "127.0.0.1", 4321)
    nio.markers = {"m": {"bpf": "tcp", "tag": None, "link_id": "L1",
                         "direction": None, "enabled": True}}
    with patch("gns3server.compute.marker.marker_manager.MarkerManager") as mm:
        mm.instance.return_value.register = MagicMock()
        await node._ubridge_apply_markers("VPCS-10", nio)
    cmds = [c.args[0] for c in node._ubridge_send.call_args_list]
    assert any("delete_packet_filter VPCS-10 m" in c for c in cmds)   # old removed
    assert any("add_packet_filter VPCS-10 m mark" in c and "tcp" in c for c in cmds)  # new added


@pytest.mark.asyncio
async def test_apply_markers_preserves_markers_on_other_bridges(compute_project, manager):
    # Regression: reconciling one NIO must not delete markers installed on this
    # node's OTHER bridges/NIOs. _marker_filter_bridges is node-wide, but
    # `desired` only carries the current NIO's markers — the delete pass must be
    # scoped to the current bridge, or updating one link wipes every other link's
    # markers + pcaps.
    node = VPCSVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", compute_project, manager)
    node._ubridge_send = AsyncioMagicMock()
    node._ubridge_hypervisor = MagicMock()
    node._ubridge_hypervisor.is_running.return_value = True
    # Two links, each with a marker on its own bridge:
    node._marker_filter_bridges["m", "L1"] = "VPCS-10"
    node._marker_specs["m", "L1"] = {"bpf": "icmp", "enabled": True}
    node._marker_filter_bridges["m", "L2"] = "VPCS-20"
    node._marker_specs["m", "L2"] = {"bpf": "tcp", "enabled": True}
    # Update only the VPCS-10 NIO; "m" is gone from this link — but the marker
    # on VPCS-20 (L2) must survive untouched.
    nio = NIOUDP(1234, "127.0.0.1", 4321)
    nio.markers = {}
    with patch("gns3server.compute.marker.marker_manager.MarkerManager") as mm:
        mm.instance.return_value.unregister = MagicMock()
        await node._ubridge_apply_markers("VPCS-10", nio)
    cmds = [c.args[0] for c in node._ubridge_send.call_args_list]
    assert any("delete_packet_filter VPCS-10 m" in c for c in cmds)   # L1 removed on its bridge
    assert not any("VPCS-20" in c for c in cmds)                      # other bridge untouched
    assert ("m", "L1") not in node._marker_filter_bridges
    assert ("m", "L2") in node._marker_filter_bridges                 # L2 preserved


@pytest.mark.asyncio
async def test_stop_ubridge_clears_marker_bridges(compute_project, manager):
    # uBridge stopping drops every marker filter — the map must clear so the next
    # apply re-installs them instead of skipping as "already installed".
    node = VPCSVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", compute_project, manager)
    node._marker_filter_bridges["m", "L1"] = "VPCS-10"
    await node._stop_ubridge()
    assert node._marker_filter_bridges == {}


class _GoneConsoleWebsocket:
    """
    Stand-in for the compute-side WebSocket when the peer (the controller, or a
    browser) is already gone: receive() yields the disconnect message and
    send_bytes raises WebSocketDisconnect — what starlette raises from send
    after the transport reports OSError.
    """

    def __init__(self):
        from types import SimpleNamespace
        self.client = SimpleNamespace(host="127.0.0.1", port=5000)

    async def receive(self):
        return {"type": "websocket.disconnect"}

    async def send_bytes(self, data):
        from starlette.websockets import WebSocketDisconnect
        raise WebSocketDisconnect(code=1006)


@pytest.mark.asyncio
async def test_console_websocket_client_disconnect_while_node_output_streams(
        compute_project, manager, port_manager, monkeypatch, caplog):
    # regression test: the client disconnects while the node is still streaming
    # console output. telnet_forward used to let the (empty-str) WebSocketDisconnect
    # from send_bytes escape, logging a message-less WARNING.
    import asyncio
    import logging

    node = VPCSVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", compute_project, manager)
    node.status = "started"

    telnet_reader = MagicMock()
    telnet_reader.at_eof.return_value = False
    telnet_reader.read = AsyncioMagicMock(return_value=b"device output")
    telnet_writer = MagicMock()
    telnet_writer.wait_closed = AsyncioMagicMock()

    async def fake_open_connection(*args, **kwargs):
        return telnet_reader, telnet_writer

    monkeypatch.setattr(asyncio, "open_connection", fake_open_connection)

    with caplog.at_level(logging.INFO):
        await node.start_websocket_console(_GoneConsoleWebsocket())

    assert telnet_writer.close.called
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert any(
        "has disconnected from compute console WebSocket while node output" in r.message
        for r in caplog.records
    )
