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
Unit tests for the tag-keyed aggregate replay module (controller layer):

* pcap record-header scanning (ts extraction, truncated-tail tolerance,
  nanosecond-magic normalization) and raw-bytes reads for the hex view
* the tag gate (404 unknown tag, 409 while any marker captures)
* timeline assembly: cross-source merge ordered by (ts, source, frame number),
  same-microsecond tiebreak, missing-pcap sources, frame-cap degradation to
  per-second buckets
* window queries (inclusive bounds, empty-window success)
* the lazy frame detail: round-tripped-ts guard, and — where tshark is
  installed — the isomorphic PDML → JSON mapping with a round-trip check
  (element count and attribute coverage).
"""

import os
import shutil
import struct

import pytest
from types import SimpleNamespace

from gns3server.controller.controller_error import ControllerError, ControllerNotFoundError
from gns3server.controller.marker_replay import (
    build_timeline,
    decode_frame,
    query_frames,
    read_frame_bytes,
    scan_pcap_frames,
    _format_ts,
    _parse_ts,
)

pytestmark = pytest.mark.asyncio

PCAP_MAGIC_US = 0xA1B2C3D4
PCAP_MAGIC_NS = 0xA1B23C4D


def _write_pcap(path, frames, magic=PCAP_MAGIC_US, snaplen=65535):
    """frames: list of (sec, frac, payload bytes); frac is µs (or ns for the ns magic)."""

    with open(path, "wb") as f:
        f.write(struct.pack("<IHHiIII", magic, 2, 4, 0, 0, snaplen, 1))
        for sec, frac, payload in frames:
            f.write(struct.pack("<IIII", sec, frac, len(payload), len(payload)))
            f.write(payload)


def _icmp_frame():
    """A minimal well-formed ICMP echo request (10.0.0.1 → 10.0.0.3)."""

    def cksum(data):
        if len(data) % 2:
            data = data + b"\x00"  # RFC 1071 odd-length padding
        s = 0
        for i in range(0, len(data), 2):
            s += (data[i] << 8) + data[i + 1]
        while s >> 16:
            s = (s & 0xFFFF) + (s >> 16)
        return (~s) & 0xFFFF

    icmp = bytes([8, 0, 0, 0]) + struct.pack(">HHH", 1, 1, 0) + b"payload12"
    icmp = icmp[:2] + struct.pack(">H", cksum(icmp)) + icmp[4:]
    ip0 = struct.pack(">BBHHHBBH4s4s", 0x45, 0, 20 + len(icmp), 1, 0, 64, 1, 0,
                      bytes([10, 0, 0, 1]), bytes([10, 0, 0, 3]))
    ip = ip0[:10] + struct.pack(">H", cksum(ip0)) + ip0[12:]
    return bytes.fromhex("0200000000020200000000010800") + ip + icmp


def _fake_project(tmp_path, markers, markers_dir=None):
    """markers: the flat project.markers shape ({'link/name': {..., node_id}})."""

    return SimpleNamespace(markers=markers, markers_directory=str(markers_dir or tmp_path))


def _marker_entry(tag, enabled=True, node_id="node-1"):
    return {"bpf": "icmp", "tag": tag, "enabled": enabled, "color": None,
            "highlight_duration": None, "capture_node_id": node_id,
            "direction": None, "data_link_type": "DLT_EN10MB",
            "node_id": node_id}


# ---------------------------------------------------------------------------
# pcap scanning
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
# Tag gate + timeline
# ---------------------------------------------------------------------------

class TestGateAndTimeline:

    async def test_unknown_tag_404(self, tmp_path):
        project = _fake_project(tmp_path, {"linkA/icmp": _marker_entry(tag=1)})
        with pytest.raises(ControllerNotFoundError):
            build_timeline(project, tag=7)

    async def test_gate_409_while_capturing(self, tmp_path):
        project = _fake_project(tmp_path, {
            "linkA/icmp": _marker_entry(tag=7, enabled=False, node_id="n1"),
            "linkB/icmp": _marker_entry(tag=7, enabled=True, node_id="n2"),
        })
        with pytest.raises(ControllerError, match="linkB"):
            build_timeline(project, tag=7)

    async def test_merge_orders_by_ts_with_stable_tiebreak(self, tmp_path):
        # Two sources, deliberately interleaved in time, colliding on one µs.
        _write_pcap(tmp_path / "n1_linkA_icmp.pcap", [
            (1693472000, 500000, b"a" * 60),   # t1 sourceA
            (1693472002, 000000, b"a" * 60),   # t3 sourceA
        ])
        _write_pcap(tmp_path / "n2_linkB_icmp.pcap", [
            (1693472001, 000000, b"b" * 60),   # t2 sourceB
            (1693472002, 000000, b"b" * 60),   # t3 sourceB — same µs as t3 sourceA
        ])
        project = _fake_project(tmp_path, {
            "linkA/icmp": _marker_entry(tag=7, enabled=False, node_id="n1"),
            "linkB/icmp": _marker_entry(tag=7, enabled=False, node_id="n2"),
        })

        timeline = build_timeline(project, tag=7)
        assert timeline["frame_count"] == 4
        assert timeline["start"] == "1693472000.500000"
        assert timeline["end"] == "1693472002.000000"
        assert [f["node_id"] for f in timeline["frames"]] == ["n1", "n2", "n1", "n2"]
        # Same-microsecond pair keeps both frames (a ts dict key would drop one).
        assert [f["ts"] for f in timeline["frames"]][2:] == ["1693472002.000000"] * 2
        assert [f["frame_number"] for f in timeline["frames"]] == [1, 1, 2, 2]
        assert {s["count"] for s in timeline["sources"]} == {2}

    async def test_missing_pcap_is_zero_count_source(self, tmp_path):
        project = _fake_project(tmp_path, {"linkA/icmp": _marker_entry(tag=7, enabled=False)})
        timeline = build_timeline(project, tag=7)
        assert timeline["frame_count"] == 0
        assert timeline["start"] is None and timeline["end"] is None
        assert timeline["frames"] == []
        assert timeline["sources"][0]["count"] == 0

    async def test_over_cap_degrades_to_buckets(self, tmp_path):
        _write_pcap(tmp_path / "n1_linkA_icmp.pcap", [
            (1693472000, 0, b"a" * 60), (1693472000, 500000, b"a" * 60),
            (1693472001, 0, b"a" * 60),
        ])
        project = _fake_project(tmp_path, {"linkA/icmp": _marker_entry(tag=7, enabled=False, node_id="n1")})

        timeline = build_timeline(project, tag=7, frame_cap=2)
        assert timeline["truncated"] is True
        assert "frames" not in timeline
        assert timeline["buckets"] == [
            {"ts": "1693472000.000000", "count": 2},
            {"ts": "1693472001.000000", "count": 1},
        ]


# ---------------------------------------------------------------------------
# Window query
# ---------------------------------------------------------------------------

class TestQueryFrames:

    def _project(self, tmp_path):
        _write_pcap(tmp_path / "n1_linkA_icmp.pcap", [
            (1693472000, 0, b"a" * 60),
            (1693472000, 150000, b"a" * 60),
            (1693472005, 0, b"a" * 60),
        ])
        return _fake_project(tmp_path, {"linkA/icmp": _marker_entry(tag=7, enabled=False, node_id="n1")})

    async def test_window_inclusive_bounds(self, tmp_path):
        result = query_frames(self._project(tmp_path), tag=7, ts="1693472000.000000", window_ms=150)
        assert [f["ts"] for f in result["frames"]] == ["1693472000.000000", "1693472000.150000"]

    async def test_window_miss_is_empty_success(self, tmp_path):
        result = query_frames(self._project(tmp_path), tag=7, ts="1693472001.000000", window_ms=100)
        assert result == {"frames": []}

    async def test_limit_applies(self, tmp_path):
        result = query_frames(self._project(tmp_path), tag=7, ts="1693472000.000000",
                              window_ms=150, limit=1)
        assert len(result["frames"]) == 1


# ---------------------------------------------------------------------------
# Frame detail (tshark path)
# ---------------------------------------------------------------------------

tshark_present = pytest.mark.skipif(shutil.which("tshark") is None, reason="tshark not installed")


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

    async def test_decode_feeds_tshark_a_scratch_copy(self, tmp_path):
        """Hardened tshark profiles deny the project dir — tshark must read a
        /tmp copy (a real copy, not a symlink) that is unlinked afterwards."""

        import tempfile
        from unittest.mock import patch, AsyncMock

        observed = []
        PDML = (b'<pdml><packet><proto name="frame" showname="Frame 1: 60 bytes">'
                b'<field name="frame.len" show="60" showname="Frame Length: 60"/>'
                b'</proto></packet></pdml>')

        class FakeProc:
            returncode = 0

            async def communicate(self):
                return PDML, b""

        async def fake_exec(*args, **kwargs):
            r_index = args.index("-r")
            observed.append((args[r_index + 1], kwargs.get("env")))
            return FakeProc()

        project = self._project(tmp_path)
        with patch("gns3server.controller.marker_replay.shutil.which", return_value="tshark"), \
             patch("gns3server.controller.marker_replay._tshark_version", AsyncMock(return_value="tshark 4.6.7")), \
             patch("gns3server.controller.marker_replay.asyncio.create_subprocess_exec", side_effect=fake_exec):
            detail = await decode_frame(project, tag=7, ts="1693472000.123456",
                                        node_id="n1", link_id="linkA", marker="icmp")

        assert detail["field_count"] == 2  # proto + field from the canned PDML
        (scratch, env), = observed
        original = str(tmp_path / "n1_linkA_icmp.pcap")
        assert scratch != original
        assert scratch.startswith(tempfile.gettempdir()) and scratch.endswith(".pcap")
        assert env["HOME"] == tempfile.gettempdir()
        assert not os.path.exists(scratch)  # cleaned up after the decode

    @tshark_present
    async def test_decode_isomorphic_mapping(self, tmp_path):
        import asyncio
        import xml.etree.ElementTree as ET

        project = self._project(tmp_path)
        detail = await decode_frame(project, tag=7, ts="1693472000.123456",
                                    node_id="n1", link_id="linkA", marker="icmp")

        assert detail["source"]["frame_number"] == 1
        assert detail["hex"] == _icmp_frame().hex()
        assert detail["field_count"] > 0
        assert "tshark" in detail["tshark_version"].lower()

        # Round-trip fidelity: node count equals the PDML element count
        # (protos + fields, excluding the <packet> container itself)…
        proc = await asyncio.create_subprocess_exec(
            "tshark", "-r", str(tmp_path / "n1_linkA_icmp.pcap"), "-T", "pdml",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await proc.communicate()
        packet = ET.fromstring(stdout).find("./packet")
        xml_elements = [e for e in packet.iter() if e is not packet]
        assert detail["field_count"] == len(xml_elements)

        # …and every XML attribute survives verbatim as a JSON string key.
        def walk(element, node):
            for key, value in element.attrib.items():
                assert node.get(key) == value
            assert all(isinstance(v, str) for k, v in node.items() if k != "children")
            for child, child_node in zip(element, node["children"]):
                walk(child, child_node)

        for element, node in zip(packet, detail["tree"]):
            walk(element, node)

        # Values stay strings (no numeric re-typing).
        ttl = next(
            f for p in detail["tree"] if p.get("name") == "ip"
            for f in p["children"] if f.get("name") == "ip.ttl"
        )
        assert ttl["show"] == "64" and ttl["showname"] == "Time to Live: 64"
