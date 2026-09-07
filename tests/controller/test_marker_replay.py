#!/usr/bin/env python
#
# Copyright (C) 2025 GNS3 Technologies Inc.
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
Unit tests for the tag-keyed aggregate replay module (sharkd edition):

* pcap record-header scanning (ts extraction, truncated-tail tolerance,
  nanosecond-magic normalization) and raw-bytes reads for the hex view
* the tag gate (404 unknown tag, 409 while any marker captures) — engine-free
* timeline assembly with injected columns: cross-source merge ordered by
  (ts, source, frame number), same-microsecond tiebreak, frame-cap
  degradation to buckets, display-filter application before count/slice
* the tree key renaming (closed census key set, values untouched, unknown
  keys pass through verbatim, internal hf ids dropped)
* the resident sharkd sessions — spawn/load/reuse, (mtime, size)
  invalidation, LRU bound — against the real sharkd where installed, plus
  the frame detail end-to-end (hex + renamed tree + filter expressions).
"""

import os
import shutil
import struct
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from gns3server.controller.controller_error import (
    ControllerBadRequestError,
    ControllerError,
    ControllerNotFoundError,
)
from gns3server.controller import marker_replay
from gns3server.controller.marker_replay import (
    FilterError,
    SharkdMissingError,
    build_timeline,
    decode_frame,
    query_frames,
    read_frame_bytes,
    scan_pcap_frames,
    _count_tree_nodes,
    _format_ts,
    _parse_ts,
    _rename_value,
)

pytestmark = pytest.mark.asyncio

PCAP_MAGIC_US = 0xA1B2C3D4
PCAP_MAGIC_NS = 0xA1B23C4D

sharkd_present = pytest.mark.skipif(shutil.which("sharkd") is None, reason="sharkd not installed")


def _write_pcap(path, frames, magic=PCAP_MAGIC_US, snaplen=65535):
    """frames: list of (sec, frac, payload bytes); frac is µs (or ns for the ns magic)."""

    with open(path, "wb") as f:
        f.write(struct.pack("<IHHiIII", magic, 2, 4, 0, 0, snaplen, 1))
        for sec, frac, payload in frames:
            f.write(struct.pack("<IIII", sec, frac, len(payload), len(payload)))
            f.write(payload)


def _cksum(data):
    if len(data) % 2:
        data = data + b"\x00"  # RFC 1071 odd-length padding
    s = 0
    for i in range(0, len(data), 2):
        s += (data[i] << 8) + data[i + 1]
    while s >> 16:
        s = (s & 0xFFFF) + (s >> 16)
    return (~s) & 0xFFFF


def _icmp_frame():
    """A minimal well-formed ICMP echo request (10.0.0.1 → 10.0.0.3)."""

    icmp = bytes([8, 0, 0, 0]) + struct.pack(">HHH", 1, 1, 0) + b"payload12"
    icmp = icmp[:2] + struct.pack(">H", _cksum(icmp)) + icmp[4:]
    ip0 = struct.pack(">BBHHHBBH4s4s", 0x45, 0, 20 + len(icmp), 1, 0, 64, 1, 0,
                      bytes([10, 0, 0, 1]), bytes([10, 0, 0, 3]))
    ip = ip0[:10] + struct.pack(">H", _cksum(ip0)) + ip0[12:]
    return bytes.fromhex("0200000000020200000000010800") + ip + icmp


def _tcp_syn_frame():
    """A minimal TCP SYN (10.0.0.1:472 → 10.0.0.3:22)."""

    tcp = struct.pack(">HHIIBBHHH", 472, 22, 0, 0, 0x50, 0x02, 64240, 0, 0)
    ip0 = struct.pack(">BBHHHBBH4s4s", 0x45, 0, 20 + len(tcp), 2, 0, 64, 6, 0,
                      bytes([10, 0, 0, 1]), bytes([10, 0, 0, 3]))
    ip = ip0[:10] + struct.pack(">H", _cksum(ip0)) + ip0[12:]
    tcp = tcp[:16] + struct.pack(">H", _cksum(ip0[12:] + tcp)) + tcp[18:]
    return bytes.fromhex("0200000000020200000000010800") + ip + tcp


def _fake_project(tmp_path, markers, markers_dir=None):
    """markers: the flat project.markers shape ({'link/name': {..., node_id}})."""

    return SimpleNamespace(markers=markers, markers_directory=str(markers_dir or tmp_path))


def _marker_entry(tag, enabled=True, node_id="node-1"):
    return {"bpf": "icmp", "tag": tag, "enabled": enabled, "color": None,
            "highlight_duration": None, "capture_node_id": node_id,
            "direction": None, "data_link_type": "DLT_EN10MB",
            "node_id": node_id}


def _fake_columns(monkeypatch, mapping):
    """Inject canned sharkd columns: mapping pcap-basename → {frame#: cols or None}.

    Frames absent from the dict get no columns; when the caller passes a
    filter, the injected set IS the matching set (mirroring the real engine).
    """

    async def fake_columns_for(pcap, filter_expr):
        return mapping.get(os.path.basename(pcap), {})

    monkeypatch.setattr(marker_replay, "_columns_for", fake_columns_for)


def _cols(src="10.0.0.1", dst="10.0.0.3", proto="ICMP", info="Echo (ping) request"):
    return {"src": src, "dst": dst, "proto": proto, "info": info,
            "bg": "ffffff", "fg": "000000"}


# ---------------------------------------------------------------------------
# pcap scanning (engine-free backbone)
# ---------------------------------------------------------------------------

class TestScanPcap:

    async def test_scans_frames_and_truncated_tail(self, tmp_path):
        pcap = tmp_path / "a.pcap"
        _write_pcap(pcap, [
            (1693472000, 123456, b"x" * 60),
            (1693472001, 654321, b"y" * 40),
        ])
        # Tear the final record in half: a snapshot mid-write must not raise.
        data = bytearray(pcap.read_bytes())
        pcap.write_bytes(data[:len(data) - 20])

        frames = scan_pcap_frames(str(pcap))
        assert frames == [(1693472000, 123456, 60)]

    async def test_ns_magic_normalized_to_us(self, tmp_path):
        pcap = tmp_path / "ns.pcap"
        _write_pcap(pcap, [(1693472000, 1500000, b"z" * 10)], magic=PCAP_MAGIC_NS)
        assert scan_pcap_frames(str(pcap)) == [(1693472000, 1500, 10)]  # 1.5 ms in µs

    async def test_read_frame_bytes_offsets(self, tmp_path):
        pcap = tmp_path / "b.pcap"
        _write_pcap(pcap, [
            (100, 0, b"first" + b"0" * 55),   # 60 bytes
            (200, 0, b"second"),               # 6 bytes
        ])
        assert read_frame_bytes(str(pcap), 2) == b"second".hex()
        assert read_frame_bytes(str(pcap), 1) == (b"first" + b"0" * 55).hex()
        assert read_frame_bytes(str(pcap), 3) is None

    async def test_ts_string_round_trip_is_exact(self):
        ts = _format_ts(1693472000, 5)
        assert ts == "1693472000.000005"
        assert _parse_ts(ts) == 1693472000000005
        assert _parse_ts(_format_ts(1693472000, 123456)) == 1693472000123456


# ---------------------------------------------------------------------------
# Tag gate (engine-free — raised before any sharkd work)
# ---------------------------------------------------------------------------

class TestGate:

    async def test_unknown_tag_404(self, tmp_path):
        project = _fake_project(tmp_path, {"linkA/icmp": _marker_entry(tag=1)})
        with pytest.raises(ControllerNotFoundError):
            await build_timeline(project, tag=7)

    async def test_gate_409_while_capturing(self, tmp_path):
        project = _fake_project(tmp_path, {
            "linkA/icmp": _marker_entry(tag=7, enabled=False, node_id="n1"),
            "linkB/icmp": _marker_entry(tag=7, enabled=True, node_id="n2"),
        })
        with pytest.raises(ControllerError, match="linkB"):
            await build_timeline(project, tag=7)

    async def test_filter_length_capped(self, tmp_path, monkeypatch):
        _fake_columns(monkeypatch, {})
        project = _fake_project(tmp_path, {"linkA/icmp": _marker_entry(tag=7, enabled=False)})
        with pytest.raises(ControllerBadRequestError, match="too long"):
            await build_timeline(project, tag=7, filter_expr="x" * (marker_replay.FILTER_MAX_LENGTH + 1))


# ---------------------------------------------------------------------------
# Timeline assembly (columns injected — no engine needed)
# ---------------------------------------------------------------------------

class TestTimeline:

    async def test_merge_orders_by_ts_with_stable_tiebreak(self, tmp_path, monkeypatch):
        # Two sources, deliberately interleaved in time, colliding on one µs.
        _write_pcap(tmp_path / "n1_linkA_icmp.pcap", [
            (1693472000, 500000, b"a" * 60),   # t1 sourceA
            (1693472002, 000000, b"a" * 60),   # t3 sourceA
        ])
        _write_pcap(tmp_path / "n2_linkB_icmp.pcap", [
            (1693472001, 000000, b"b" * 60),   # t2 sourceB
            (1693472002, 000000, b"b" * 60),   # t3 sourceB — same µs as t3 sourceA
        ])
        _fake_columns(monkeypatch, {
            "n1_linkA_icmp.pcap": {1: _cols(), 2: _cols()},
            "n2_linkB_icmp.pcap": {1: _cols(src="10.0.0.2"), 2: _cols(src="10.0.0.2")},
        })
        project = _fake_project(tmp_path, {
            "linkA/icmp": _marker_entry(tag=7, enabled=False, node_id="n1"),
            "linkB/icmp": _marker_entry(tag=7, enabled=False, node_id="n2"),
        })

        timeline = await build_timeline(project, tag=7)
        assert timeline["frame_count"] == 4
        assert timeline["start"] == "1693472000.500000"
        assert timeline["end"] == "1693472002.000000"
        assert [f["node_id"] for f in timeline["frames"]] == ["n1", "n2", "n1", "n2"]
        # Same-microsecond pair keeps both frames (a ts dict key would drop one).
        assert [f["ts"] for f in timeline["frames"]][2:] == ["1693472002.000000"] * 2
        assert [f["frame_number"] for f in timeline["frames"]] == [1, 1, 2, 2]
        # Columns ride along verbatim.
        assert timeline["frames"][0]["src"] == "10.0.0.1"
        assert timeline["frames"][1]["src"] == "10.0.0.2"
        assert timeline["frames"][0]["proto"] == "ICMP"
        assert {s["count"] for s in timeline["sources"]} == {2}

    async def test_columns_missing_for_a_frame_still_lists_it(self, tmp_path, monkeypatch):
        # A frame the (injected) engine did not describe keeps its place with
        # null columns — the timeline backbone never depends on the engine.
        _write_pcap(tmp_path / "n1_linkA_icmp.pcap", [(1693472000, 0, b"a" * 60)])
        _fake_columns(monkeypatch, {})  # engine describes nothing
        project = _fake_project(tmp_path, {"linkA/icmp": _marker_entry(tag=7, enabled=False, node_id="n1")})

        timeline = await build_timeline(project, tag=7)
        frame = timeline["frames"][0]
        assert frame["ts"] == "1693472000.000000"
        assert frame["src"] is None and frame["info"] is None

    async def test_missing_pcap_is_zero_count_source(self, tmp_path, monkeypatch):
        _fake_columns(monkeypatch, {})
        project = _fake_project(tmp_path, {"linkA/icmp": _marker_entry(tag=7, enabled=False)})
        timeline = await build_timeline(project, tag=7)
        assert timeline["frame_count"] == 0
        assert timeline["start"] is None and timeline["end"] is None
        assert timeline["frames"] == []
        assert timeline["sources"][0]["count"] == 0

    async def test_over_cap_degrades_to_buckets(self, tmp_path, monkeypatch):
        _write_pcap(tmp_path / "n1_linkA_icmp.pcap", [
            (1693472000, 0, b"a" * 60), (1693472000, 500000, b"a" * 60),
            (1693472001, 0, b"a" * 60),
        ])
        _fake_columns(monkeypatch, {"n1_linkA_icmp.pcap": {1: _cols(), 2: _cols(), 3: _cols()}})
        project = _fake_project(tmp_path, {"linkA/icmp": _marker_entry(tag=7, enabled=False, node_id="n1")})

        timeline = await build_timeline(project, tag=7, frame_cap=2)
        assert timeline["truncated"] is True
        assert "frames" not in timeline
        assert timeline["buckets"] == [
            {"ts": "1693472000.000000", "count": 2},
            {"ts": "1693472001.000000", "count": 1},
        ]

    async def test_filter_applies_before_count_and_slice(self, tmp_path, monkeypatch):
        # Three frames; the injected "matching set" (what a real engine would
        # return for the filter) contains only frames 1 and 3.
        _write_pcap(tmp_path / "n1_linkA_icmp.pcap", [
            (1693472000, 0, b"a" * 60),
            (1693472001, 0, b"a" * 60),
            (1693472002, 0, b"a" * 60),
        ])
        _fake_columns(monkeypatch, {"n1_linkA_icmp.pcap": {1: _cols(), 3: _cols(proto="TCP")}})
        project = _fake_project(tmp_path, {"linkA/icmp": _marker_entry(tag=7, enabled=False, node_id="n1")})

        timeline = await build_timeline(project, tag=7, filter_expr="tcp")
        assert timeline["frame_count"] == 2
        assert timeline["start"] == "1693472000.000000"
        assert timeline["end"] == "1693472002.000000"
        # frame numbers keep their ORIGINAL pcap identity through the filter.
        assert [f["frame_number"] for f in timeline["frames"]] == [1, 3]
        assert timeline["sources"][0]["count"] == 2


class TestQueryFrames:

    def _project(self, tmp_path, monkeypatch):
        _write_pcap(tmp_path / "n1_linkA_icmp.pcap", [
            (1693472000, 0, b"a" * 60),
            (1693472000, 150000, b"a" * 60),
            (1693472005, 0, b"a" * 60),
        ])
        _fake_columns(monkeypatch, {"n1_linkA_icmp.pcap": {i: _cols() for i in (1, 2, 3)}})
        return _fake_project(tmp_path, {"linkA/icmp": _marker_entry(tag=7, enabled=False, node_id="n1")})

    async def test_window_inclusive_bounds(self, tmp_path, monkeypatch):
        result = await query_frames(self._project(tmp_path, monkeypatch), tag=7,
                                    ts="1693472000.000000", window_ms=150)
        assert [f["ts"] for f in result["frames"]] == ["1693472000.000000", "1693472000.150000"]

    async def test_window_miss_is_empty_success(self, tmp_path, monkeypatch):
        result = await query_frames(self._project(tmp_path, monkeypatch), tag=7,
                                    ts="1693472001.000000", window_ms=100)
        assert result == {"frames": []}

    async def test_limit_applies(self, tmp_path, monkeypatch):
        result = await query_frames(self._project(tmp_path, monkeypatch), tag=7,
                                    ts="1693472000.000000", window_ms=150, limit=1)
        assert len(result["frames"]) == 1


# ---------------------------------------------------------------------------
# Tree key renaming
# ---------------------------------------------------------------------------

class TestRename:

    async def test_renames_closed_key_set_and_drops_hf_id(self):
        node = {
            "t": "proto", "l": "Time to Live: 64", "fn": "ip.ttl",
            "f": "ip.ttl == 64", "h": [22, 1], "s": None, "g": False,
            "e": 8472,
            "n": [{"l": "nested", "h": [23, 2], "n": []}],
        }
        renamed = _rename_value(node)
        assert renamed == {
            "element": "proto", "label": "Time to Live: 64", "name": "ip.ttl",
            "filter_expr": "ip.ttl == 64", "pos": 22, "size": 1,
            "expert": None, "generated": False,
            "children": [{"label": "nested", "pos": 23, "size": 2, "children": []}],
        }

    async def test_unknown_keys_pass_through_verbatim(self):
        # A future Wireshark adding a key must never silently lose data.
        node = {"l": "x", "future_key": {"deep": [1, 2]}, "n": []}
        renamed = _rename_value(node)
        assert renamed["future_key"] == {"deep": [1, 2]}

    async def test_count_tree_nodes_counts_dicts_only(self):
        assert _count_tree_nodes({"a": [{"b": 1}, "str", 3]}) == 2


# ---------------------------------------------------------------------------
# sharkd sessions + engine-backed behaviour
# ---------------------------------------------------------------------------

class TestSessions:

    async def test_missing_sharkd_raises_501_error(self, tmp_path):
        _write_pcap(tmp_path / "n1_linkA_icmp.pcap", [(1693472000, 0, b"a" * 60)])
        project = _fake_project(tmp_path, {"linkA/icmp": _marker_entry(tag=7, enabled=False, node_id="n1")})
        with patch("gns3server.controller.marker_replay.shutil.which", return_value=None):
            with pytest.raises(SharkdMissingError):
                await build_timeline(project, tag=7)

    async def test_lru_bound_evicts_least_recently_used(self, tmp_path):
        manager = marker_replay._SharkdManager()

        class FakeSession:
            def __init__(self, pcap, used):
                self.pcap, self.last_used = pcap, used
                self.closed = False
                self.mtime_ns, self.size = 0, 0

            def matches(self, stat):
                return False  # always respawn → exercises the eviction path

            def alive(self):
                return False

            def touch(self):
                pass

            async def close(self):
                self.closed = True

        fake_by_pcap = {}

        async def fake_spawn(pcap, stat):
            session = FakeSession(pcap, 0)
            fake_by_pcap[pcap] = session
            return session

        with patch.object(manager, "_spawn", side_effect=fake_spawn):
            for i in range(marker_replay.SESSION_MAX + 2):
                pcap = tmp_path / f"pcap{i}"
                _write_pcap(pcap, [(1693472000, 0, b"a" * 60)])
                await manager.session_for(str(pcap))
        # Bounded to SESSION_MAX; the earliest (least recently used) got evicted.
        assert len(manager._sessions) == marker_replay.SESSION_MAX
        assert fake_by_pcap[str(tmp_path / "pcap0")].closed is True
        assert fake_by_pcap[str(tmp_path / "pcap1")].closed is True

    @sharkd_present
    async def test_real_session_columns_and_filter(self, tmp_path):
        _write_pcap(tmp_path / "n1_linkA_icmp.pcap", [
            (1693472000, 123456, _icmp_frame()),
            (1693472001, 0, _tcp_syn_frame()),
        ])
        manager = marker_replay._get_manager()
        try:
            columns = await marker_replay._columns_for(str(tmp_path / "n1_linkA_icmp.pcap"), None)
            assert columns[1]["src"] == "10.0.0.1"
            assert columns[1]["proto"] == "ICMP"
            assert "Echo" in columns[1]["info"]
            assert columns[2]["proto"] == "TCP"

            only_tcp = await marker_replay._columns_for(str(tmp_path / "n1_linkA_icmp.pcap"), "tcp")
            assert set(only_tcp) == {2}
        finally:
            await manager.close_all()

    @sharkd_present
    async def test_real_session_invalid_filter_raises_filter_error(self, tmp_path):
        _write_pcap(tmp_path / "n1_linkA_icmp.pcap", [(1693472000, 123456, _icmp_frame())])
        manager = marker_replay._get_manager()
        try:
            with pytest.raises(FilterError):
                await marker_replay._columns_for(str(tmp_path / "n1_linkA_icmp.pcap"), "this is (not valid")
        finally:
            await manager.close_all()

    @sharkd_present
    async def test_real_session_respawns_on_stat_change(self, tmp_path):
        pcap = tmp_path / "n1_linkA_icmp.pcap"
        _write_pcap(pcap, [(1693472000, 123456, _icmp_frame())])
        manager = marker_replay._get_manager()
        try:
            first = await manager.session_for(str(pcap))
            assert await manager.session_for(str(pcap)) is first  # warm reuse
            # Rewrite the file (simulating a truncated/rebuilt capture).
            _write_pcap(pcap, [(1693473000, 0, _icmp_frame())])
            second = await manager.session_for(str(pcap))
            assert second is not first
            columns = await marker_replay._columns_for(str(pcap), None)
            assert set(columns) == {1}
        finally:
            await manager.close_all()


class TestDecodeFrame:

    def _project(self, tmp_path):
        _write_pcap(tmp_path / "n1_linkA_icmp.pcap", [
            (1693472000, 123456, _icmp_frame()),
        ])
        return _fake_project(tmp_path, {
            "linkA/icmp": _marker_entry(tag=7, enabled=False, node_id="n1"),
        })

    async def test_ts_mismatch_guard_404(self, tmp_path):
        project = self._project(tmp_path)
        with pytest.raises(ControllerNotFoundError, match="rebuilt"):
            await decode_frame(project, tag=7, ts="1.000000",
                               node_id="n1", link_id="linkA", marker="icmp")

    async def test_unknown_source_404(self, tmp_path):
        project = self._project(tmp_path)
        with pytest.raises(ControllerNotFoundError):
            await decode_frame(project, tag=7, ts="1693472000.123456",
                               node_id="nobody", link_id="linkA", marker="icmp")

    @sharkd_present
    async def test_decode_end_to_end(self, tmp_path):
        manager = marker_replay._get_manager()
        try:
            project = self._project(tmp_path)
            detail = await decode_frame(project, tag=7, ts="1693472000.123456",
                                        node_id="n1", link_id="linkA", marker="icmp")
        finally:
            await manager.close_all()

        assert detail["source"]["frame_number"] == 1
        assert detail["hex"] == _icmp_frame().hex()
        assert detail["field_count"] > 10

        # Renamed tree: every label/name present, filter expressions with
        # values baked in, byte ranges for hex highlighting.
        def find(node, name):
            for child in node if isinstance(node, list) else node.get("children", []):
                if child.get("name") == name:
                    return child
                deep = find(child, name)
                if deep is not None:
                    return deep
            return None

        ttl = find(detail["tree"], "ip.ttl")
        assert ttl is not None
        assert ttl["label"] == "Time to Live: 64"
        assert ttl["filter_expr"] == "ip.ttl == 64"
        assert ttl["pos"] == 22 and ttl["size"] == 1

    @sharkd_present
    async def test_key_census_closed_set(self, tmp_path):
        """The rename correctness guarantee: across protocol-diverse real
        trees, sharkd's raw key set stays within the census-known keys."""

        pcap = tmp_path / "proto_mix.pcap"
        _write_pcap(pcap, [
            (1693472000, 100000, _icmp_frame()),
            (1693472001, 0, _tcp_syn_frame()),
        ])
        manager = marker_replay._get_manager()
        try:
            session = await manager.session_for(str(pcap))
            known = set(marker_replay._KEY_RENAME) | {"h", "e"}
            seen = set()

            def walk(value):
                if isinstance(value, dict):
                    seen.update(value.keys())
                    for item in value.values():
                        walk(item)
                elif isinstance(value, list):
                    for item in value:
                        walk(item)

            for frame_number in (1, 2):
                result = await session.rpc("frame", {"frame": frame_number, "proto": True})
                walk(result.get("tree", []))
            assert seen <= known, f"unknown sharkd keys appeared: {seen - known}"
        finally:
            await manager.close_all()
