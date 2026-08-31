#!/usr/bin/env python
#
# Copyright (C) 2024 GNS3 Technologies Inc.
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

import asyncio
import pytest

from gns3server.compute.marker.marker_manager import MarkerManager
from gns3server.compute.marker.marker_listener import MarkerListener


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class TestMarkerRegistry:

    def test_register_and_lookup(self):
        MarkerManager.reset()
        mgr = MarkerManager.instance()
        mgr.register("proj1", "node1", "filter1", "link1", tag=5)
        pid, lid, tag = mgr.lookup("node1", "filter1")
        assert pid == "proj1"
        assert lid == "link1"
        assert tag == 5

    def test_miss_returns_none(self):
        MarkerManager.reset()
        mgr = MarkerManager.instance()
        pid, lid, tag = mgr.lookup("no-such-node", "no-such-filter")
        assert pid is None

    def test_reregister_updates(self):
        MarkerManager.reset()
        mgr = MarkerManager.instance()
        mgr.register("p", "n", "f", "l", tag=1)
        mgr.register("p", "n", "f", "l", tag=99)
        _, _, tag = mgr.lookup("n", "f")
        assert tag == 99

    def test_unregister(self):
        MarkerManager.reset()
        mgr = MarkerManager.instance()
        mgr.register("p", "n", "f", "l")
        assert mgr.unregister("n", "f") is True
        pid, _, _ = mgr.lookup("n", "f")
        assert pid is None
        assert mgr.unregister("n", "f") is False

    def test_unregister_project(self):
        MarkerManager.reset()
        mgr = MarkerManager.instance()
        mgr.register("p1", "n1", "f1", "l1")
        mgr.register("p1", "n2", "f2", "l2")
        mgr.register("p2", "n3", "f3", "l3")
        mgr.unregister_project("p1")
        assert mgr.lookup("n1", "f1") == (None, None, None)
        assert mgr.lookup("n2", "f2") == (None, None, None)
        assert mgr.lookup("n3", "f3")[0] == "p2"

    def test_re_add_after_project_clear(self):
        MarkerManager.reset()
        mgr = MarkerManager.instance()
        mgr.register("p", "n", "f", "l")
        mgr.unregister_project("p")
        mgr.register("p", "n", "f", "l2", tag=42)
        pid, lid, tag = mgr.lookup("n", "f")
        assert pid == "p" and lid == "l2" and tag == 42


# ---------------------------------------------------------------------------
# MarkerListener parsing
# ---------------------------------------------------------------------------

class FakeMarkerManager:
    def __init__(self):
        self.events = []
        self._entries = {}

    def lookup(self, node_id, filter_name):
        e = self._entries.get((node_id, filter_name))
        if e is None:
            return None, None, None
        return e["project_id"], e["link_id"], e["tag"]

    def emit_match(self, project_id, event):
        self.events.append((project_id, event))

    def register(self, project_id, node_id, filter_name, link_id, tag):
        self._entries[(node_id, filter_name)] = {
            "project_id": project_id, "link_id": link_id, "tag": tag
        }


class TestMarkerListener:

    def test_parses_valid_mark_datagram(self):
        fmgr = FakeMarkerManager()
        fmgr.register("p1", "n1", "f1", "l1", tag=7)
        lis = MarkerListener(fmgr)
        lis.connection_made(None)
        lis.datagram_received(
            b"MARK 1700000000.123456 node=n1 filter=f1 tag=7 len=98\n",
            ("127.0.0.1", 9999),
        )
        assert len(fmgr.events) == 1
        _, ev = fmgr.events[0]
        assert ev["node_id"] == "n1"
        assert ev["link_id"] == "l1"
        assert ev["filter"] == "f1"
        assert ev["tag"] == "7"
        assert ev["ts"] == pytest.approx(1700000000.123456)
        assert ev["len"] == 98
        # No dir= in the signal (legacy uBridge) → undirected.
        assert ev["dir"] is None

    def test_unknown_node_dropped(self):
        fmgr = FakeMarkerManager()
        lis = MarkerListener(fmgr)
        lis.connection_made(None)
        lis.datagram_received(b"MARK 1.0 node=bad filter=bad len=10\n", None)
        assert fmgr.events == []

    def test_bad_timestamp_ignored(self):
        fmgr = FakeMarkerManager()
        lis = MarkerListener(fmgr)
        lis.connection_made(None)
        lis.datagram_received(b"MARK badts node=n filter=f len=1\n", None)
        assert fmgr.events == []

    def test_not_mark_line_ignored(self):
        fmgr = FakeMarkerManager()
        lis = MarkerListener(fmgr)
        lis.connection_made(None)
        lis.datagram_received(b"HELLO world\n", None)
        assert fmgr.events == []

    def test_missing_node_ignored(self):
        fmgr = FakeMarkerManager()
        lis = MarkerListener(fmgr)
        lis.connection_made(None)
        lis.datagram_received(b"MARK 1.0 filter=f len=1\n", None)
        assert fmgr.events == []

    def test_tag_dash_falls_back_to_registered(self):
        fmgr = FakeMarkerManager()
        fmgr.register("p", "n", "f", "l", tag=42)
        lis = MarkerListener(fmgr)
        lis.connection_made(None)
        lis.datagram_received(b"MARK 2.0 node=n filter=f tag=- len=20\n", None)
        assert fmgr.events[0][1]["tag"] == 42

    def test_link_in_signal_overrides_registry_link(self):
        # Per-link attribution (contract §3.2/§3.3): the signal's `link=` is
        # authoritative and must disambiguate links sharing a node+filter —
        # e.g. several links on one IOU node under the same global marker name.
        fmgr = FakeMarkerManager()
        fmgr.register("p", "n", "f", "registry-link", tag=1)
        lis = MarkerListener(fmgr)
        lis.connection_made(None)
        lis.datagram_received(
            b"MARK 3.0 node=n filter=f link=signal-link tag=1 len=42\n", None
        )
        assert fmgr.events[0][1]["link_id"] == "signal-link"

    def test_link_dash_falls_back_to_registry_link(self):
        # Legacy signals that carry no link fall back to the registry's link_id.
        fmgr = FakeMarkerManager()
        fmgr.register("p", "n", "f", "registry-link", tag=1)
        lis = MarkerListener(fmgr)
        lis.connection_made(None)
        lis.datagram_received(b"MARK 3.0 node=n filter=f link=- tag=1 len=42\n", None)
        assert fmgr.events[0][1]["link_id"] == "registry-link"

    def test_dir_tx_passthrough(self):
        # dir=tx = capture node sending (matched packet ingressed the device-side NIO).
        fmgr = FakeMarkerManager()
        fmgr.register("p", "n", "f", "l", tag=1)
        lis = MarkerListener(fmgr)
        lis.connection_made(None)
        lis.datagram_received(b"MARK 1.0 node=n filter=f tag=1 len=10 dir=tx\n", None)
        assert fmgr.events[0][1]["dir"] == "tx"

    def test_dir_rx_passthrough(self):
        # dir=rx = capture node receiving (matched packet ingressed the link-side NIO).
        fmgr = FakeMarkerManager()
        fmgr.register("p", "n", "f", "l", tag=1)
        lis = MarkerListener(fmgr)
        lis.connection_made(None)
        lis.datagram_received(b"MARK 1.0 node=n filter=f tag=1 len=10 dir=rx\n", None)
        assert fmgr.events[0][1]["dir"] == "rx"

    def test_dir_absent_is_none(self):
        # Older uBridge builds omit dir; the event then carries None so the UI
        # falls back to undirected rendering.
        fmgr = FakeMarkerManager()
        fmgr.register("p", "n", "f", "l", tag=1)
        lis = MarkerListener(fmgr)
        lis.connection_made(None)
        lis.datagram_received(b"MARK 1.0 node=n filter=f tag=1 len=10\n", None)
        assert fmgr.events[0][1]["dir"] is None

    def test_exception_does_not_kill_listener(self):
        fmgr = FakeMarkerManager()
        lis = MarkerListener(fmgr)
        lis.connection_made(None)
        # Non-decodable bytes
        lis.datagram_received(b"\xff\xfe\xfd", None)
        # The listener swallows exceptions; reaching here proves it survived.
        assert True


# ---------------------------------------------------------------------------
# UDP round-trip
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestMarkerManagerUDP:

    async def test_listener_receives_and_dispatches(self):
        MarkerManager.reset()
        mgr = MarkerManager.instance()

        captured = []
        original_emit = mgr.emit_match
        mgr.emit_match = lambda pid, ev: captured.append((pid, ev))

        await mgr.start("127.0.0.1", 0)
        assert mgr.running
        assert mgr.port is not None

        mgr.register("proj-rt", "node-rt", "filt-rt", "link-rt", tag=10)

        loop = asyncio.get_running_loop()

        class SendProto(asyncio.DatagramProtocol):
            def connection_made(self, transport):
                self.transport = transport

        sp = SendProto()
        transport, _ = await loop.create_datagram_endpoint(
            lambda: sp, remote_addr=("127.0.0.1", mgr.port)
        )
        transport.sendto(
            b"MARK 123.456 node=node-rt filter=filt-rt tag=10 len=88\n"
        )
        await asyncio.sleep(0.15)
        transport.close()

        mgr.emit_match = original_emit
        await mgr.stop()

        assert len(captured) == 1
        pid, ev = captured[0]
        assert pid == "proj-rt"
        assert ev["link_id"] == "link-rt"
        assert ev["len"] == 88
