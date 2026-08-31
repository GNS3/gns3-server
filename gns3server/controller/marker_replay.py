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

"""
Tag-keyed aggregate replay over paused markers' pcap files.

Markers on different links sharing a ``tag`` form one distributed capture
session. This module merges their per-marker pcaps
(``<project>/project-files/markers/{node_id}_{link_id}_{name}.pcap``) into a
single timestamp-ordered timeline and decodes individual frames on demand.

Two deliberately separated performance regimes:

* the timeline path reads only the 16-byte pcap record headers — tshark is
  never invoked, so browsing works even where tshark is not installed;
* the detail path runs one ``tshark -T pdml`` per frame the caller asks about
  (call count = user clicks) and maps the XML to JSON isomorphically — every
  PDML attribute survives as a JSON key, values stay strings, nothing is
  selected out or interpreted.

Timestamps are uBridge's userspace ``gettimeofday`` at match time (µs, a
value measured after the packet has crossed the kernel twice — the last
digit or two are scheduling noise). A timestamp is NOT a unique key: the
merge sorts by ``(ts, source file, frame number)`` and index structures must
never use ts alone as a dict key, or same-microsecond frames silently
overwrite each other.
"""

import asyncio
import logging
import os
import shutil
import struct
import tempfile
import xml.etree.ElementTree as ET

from .controller_error import ControllerError, ControllerNotFoundError, ControllerBadRequestError

log = logging.getLogger(__name__)

# Full frame list is embedded in the range response while under this cap;
# above it the response degrades to start/end + per-second buckets so the
# client is never flooded by a high-traffic BPF.
FRAME_LIST_CAP = 5000

# One tshark decode per user click: a generous ceiling, not a rate limiter.
TSHARK_TIMEOUT_SECONDS = 10.0


class TsharkMissingError(ControllerError):
    """tshark is not installed (or not on PATH) — frame detail unavailable."""


class TsharkError(ControllerError):
    """tshark exited non-zero / timed out / produced unusable output."""


# ---------------------------------------------------------------------------
# pcap record-header scanning (timeline path — no tshark)
# ---------------------------------------------------------------------------

# magic → (byte order, timestamp unit). Both pcap families uBridge can write
# (libpcap default µs; ns variant accepted defensively) and both endiannesses.
_PCAP_MAGICS = {
    0xA1B2C3D4: ("<", 1),      # little-endian, microseconds
    0xD4C3B2A1: (">", 1),      # big-endian, microseconds
    0xA1B23C4D: ("<", 1000),   # little-endian, nanoseconds
    0x4D3CB2A1: (">", 1000),   # big-endian, nanoseconds
}


def _format_ts(sec: int, usec: int) -> str:
    """Canonical ts string — the exact form clients must round-trip back."""

    return f"{sec}.{usec:06d}"


def _parse_ts(ts: str) -> int:
    """Parse a round-tripped ts string to integer microseconds (exact, no floats)."""

    try:
        sec, _, frac = ts.partition(".")
        usec = int(frac.ljust(6, "0")[:6]) if frac else 0
        return int(sec) * 1_000_000 + usec
    except ValueError:
        raise ControllerBadRequestError(f"Invalid timestamp: {ts!r}")


def scan_pcap_frames(path):
    """
    Walk a pcap file reading only record headers.

    :returns: list of ``(ts_sec, ts_usec, incl_len)`` per frame, 1-based order.
    Tolerates a truncated tail (stops when a record header claims more bytes
    than the file holds) so a snapshot mid-write never raises.
    """

    frames = []
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError as e:
        raise ControllerError(f"Cannot read marker pcap {path}: {e}")

    if len(data) < 24:
        return frames  # not even a global header — zero frames
    magic = struct.unpack("<I", data[:4])[0]
    spec = _PCAP_MAGICS.get(magic)
    if spec is None:
        raise ControllerError(f"Unrecognized pcap magic in {path}")
    byteorder, unit = spec

    pos = 24
    while pos + 16 <= len(data):
        ts_sec, ts_frac, incl_len, _orig_len = struct.unpack(
            byteorder + "IIII", data[pos:pos + 16]
        )
        if incl_len > 0xFFFF or pos + 16 + incl_len > len(data):
            break  # truncated tail (snapshot mid-write / torn final record)
        # Normalize ns pcaps to µs by truncation — uBridge writes µs anyway.
        frames.append((ts_sec, ts_frac // unit if unit > 1 else ts_frac, incl_len))
        pos += 16 + incl_len
    return frames


def read_frame_bytes(path, frame_number):
    """
    Read one frame's raw bytes (hex view) straight from the pcap — never via
    tshark. ``frame_number`` is 1-based (the same number tshark's
    ``frame.number`` filter uses).
    """

    frames = scan_pcap_frames(path)
    if not 1 <= frame_number <= len(frames):
        return None
    # Offset arithmetic mirrors the header scan: global header + every full
    # record before the target + the target's own record header.
    offset = 24 + sum(16 + incl for _s, _u, incl in frames[:frame_number - 1]) + 16
    incl_len = frames[frame_number - 1][2]
    with open(path, "rb") as f:
        f.seek(offset)
        return f.read(incl_len).hex()


# ---------------------------------------------------------------------------
# Tag gate + timeline assembly
# ---------------------------------------------------------------------------

def _tag_markers(project, tag):
    """
    Every marker entry in the project carrying ``tag`` (flat
    ``project.markers`` values: link_id / node_id / name keys included).
    """

    entries = []
    for key, info in project.markers.items():
        if info.get("tag") == tag:
            link_id, _, name = key.partition("/")
            entries.append({
                "node_id": info["node_id"],
                "link_id": link_id,
                "marker": name,
                "enabled": info.get("enabled", True),
                "data_link_type": info.get("data_link_type", "DLT_EN10MB"),
            })
    return entries


def gate_tag(project, tag):
    """
    Replay reads append-only pcaps, so it is only available while the data is
    at rest: every marker under the tag must be paused. Raises 409 listing
    the still-running markers, 404 when the tag has no markers at all.
    """

    entries = _tag_markers(project, tag)
    if not entries:
        raise ControllerNotFoundError(f"No markers with tag {tag} in project")
    running = [f"{e['marker']} on link {e['link_id']}" for e in entries if e["enabled"]]
    if running:
        raise ControllerError(
            f"Cannot replay tag {tag} while markers are capturing: {', '.join(running)}. "
            "Pause every marker under the tag first."
        )
    return entries


def _merged_frames(project, entries):
    """
    Scan every source pcap and merge into one list sorted by
    ``(ts, source file, frame number)`` — ts alone is not unique (two links
    can hit the same microsecond); the tiebreaker yields a stable, determined
    order instead of a fictional one.
    """

    markers_dir = project.markers_directory
    merged = []
    sources = []
    for entry in entries:
        pcap = os.path.join(
            markers_dir, f"{entry['node_id']}_{entry['link_id']}_{entry['marker']}.pcap"
        )
        frames = scan_pcap_frames(pcap) if os.path.exists(pcap) else []
        sources.append({**{k: entry[k] for k in ("node_id", "link_id", "marker", "data_link_type")},
                        "count": len(frames)})
        for frame_number, (sec, usec, incl_len) in enumerate(frames, start=1):
            merged.append({
                "ts": _format_ts(sec, usec),
                "ts_us": sec * 1_000_000 + usec,
                "len": incl_len,
                "node_id": entry["node_id"],
                "link_id": entry["link_id"],
                "marker": entry["marker"],
                "frame_number": frame_number,
                "_source": f"{entry['node_id']}_{entry['link_id']}_{entry['marker']}",
            })
    merged.sort(key=lambda f: (f["ts_us"], f["_source"], f["frame_number"]))
    for frame in merged:
        del frame["ts_us"]
        del frame["_source"]
    return merged, sources


def build_timeline(project, tag, frame_cap=FRAME_LIST_CAP):
    """
    The ``range`` response: timeline bounds, per-source stats, and (under
    ``frame_cap``) the full merged frame list for one-request timeline
    layout. Over the cap the list is replaced by per-second buckets.
    """

    entries = gate_tag(project, tag)
    frames, sources = _merged_frames(project, entries)

    response = {
        "tag": tag,
        "start": frames[0]["ts"] if frames else None,
        "end": frames[-1]["ts"] if frames else None,
        "frame_count": len(frames),
        "truncated": len(frames) > frame_cap,
        "sources": sources,
    }
    if len(frames) <= frame_cap:
        response["frames"] = frames
    else:
        buckets = {}
        for frame in frames:
            second = _parse_ts(frame["ts"]) // 1_000_000
            buckets[second] = buckets.get(second, 0) + 1
        response["buckets"] = [
            {"ts": _format_ts(second, 0), "count": count}
            for second, count in sorted(buckets.items())
        ]
    return response


def query_frames(project, tag, ts, window_ms=100, limit=1000):
    """
    Frames with ts in ``[T, T+window_ms]`` merged across sources. A time with
    no frames is a normal, successful answer — ``{"frames": []}``.
    """

    entries = gate_tag(project, tag)
    frames, _sources = _merged_frames(project, entries)

    start_us = _parse_ts(ts)
    end_us = start_us + max(window_ms, 0) * 1000
    hits = [f for f in frames if start_us <= _parse_ts(f["ts"]) <= end_us]
    return {"frames": hits[:max(limit, 0)]}


# ---------------------------------------------------------------------------
# Frame detail (tshark path — lazy, one frame per call)
# ---------------------------------------------------------------------------

async def _tshark_version():
    try:
        proc = await asyncio.create_subprocess_exec(
            "tshark", "--version",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=TSHARK_TIMEOUT_SECONDS)
        return stdout.decode(errors="replace").splitlines()[0].strip()
    except (OSError, asyncio.TimeoutError, IndexError):
        raise TsharkMissingError("tshark is not available on this server")


def _tshark_scratch_copy(pcap):
    """
    Copy the pcap to a scratch file under the system temp dir for tshark to
    read. Hardened tshark profiles (AppArmor &c.) can deny it access to the
    project directory / the user's home while still allowing /tmp — a real
    copy, deliberately not a symlink, since the profile resolves real paths.
    Caller must unlink the returned path.
    """

    fd, scratch = tempfile.mkstemp(suffix=".pcap", prefix="gns3-replay-")
    os.close(fd)
    shutil.copyfile(pcap, scratch)
    return scratch


def _tshark_env():
    """Scratch HOME so tshark never even tries to read the user's home."""

    env = dict(os.environ)
    env["HOME"] = tempfile.gettempdir()
    return env


def _pdml_to_nodes(element):
    """
    Isomorphic PDML → JSON mapping: every XML attribute becomes a JSON key
    verbatim (values stay strings), children nest under ``children``. The
    element tag ("proto"/"field") is carried as ``element`` — the one
    structural key beyond the attributes, so a renderer can tell a protocol
    group from a leaf field (geninfo's tagless names make names unreliable).
    """

    return {
        "element": element.tag,
        **element.attrib,
        "children": [_pdml_to_nodes(child) for child in element],
    }


def _count_nodes(nodes):
    return 1 + sum(_count_nodes(child) for child in nodes.get("children", []))


async def decode_frame(project, tag, ts, node_id, link_id, marker):
    """
    Decode exactly one frame: locate its pcap by source identity, verify the
    round-tripped ts still matches the file (guards a rebuild between the
    timeline view and this click), read the raw bytes for the hex view, and
    map tshark's PDML of that single frame to JSON.
    """

    entries = gate_tag(project, tag)
    entry = next(
        (e for e in entries
         if e["node_id"] == node_id and e["link_id"] == link_id and e["marker"] == marker),
        None,
    )
    if entry is None:
        raise ControllerNotFoundError(
            f"No marker '{marker}' with tag {tag} on link {link_id} captured by {node_id}"
        )

    pcap = os.path.join(project.markers_directory, f"{node_id}_{link_id}_{marker}.pcap")
    if not os.path.exists(pcap):
        raise ControllerNotFoundError(f"No capture file for marker '{marker}' (nothing ever matched)")

    frames = scan_pcap_frames(pcap)
    # The ts must be the exact string the timeline returned; find the frame
    # it identifies rather than trusting any position hint from the client.
    frame_number = next(
        (i for i, (sec, usec, _len) in enumerate(frames, start=1)
         if _format_ts(sec, usec) == ts),
        None,
    )
    if frame_number is None:
        raise ControllerNotFoundError(
            f"No frame at ts {ts} in marker '{marker}' (the capture may have been rebuilt)"
        )

    raw_hex = read_frame_bytes(pcap, frame_number)

    if shutil.which("tshark") is None:
        raise TsharkMissingError("tshark is not installed — frame detail is unavailable")
    version = await _tshark_version()

    # Hand tshark a scratch copy under the temp dir: hardened profiles may
    # deny it the project directory even though this process can read it
    # (the hex view above reads the original directly).
    scratch = _tshark_scratch_copy(pcap)
    try:
        try:
            proc = await asyncio.create_subprocess_exec(
                "tshark", "-r", scratch, "-T", "pdml", "-Y", f"frame.number == {frame_number}",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                env=_tshark_env(),
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=TSHARK_TIMEOUT_SECONDS
            )
        except OSError as e:
            raise TsharkError(f"Could not run tshark: {e}")
        except asyncio.TimeoutError:
            raise TsharkError(f"tshark timed out after {TSHARK_TIMEOUT_SECONDS:.0f}s")
        if proc.returncode != 0 or not stdout.strip():
            # Never feed truncated/failed output to the mapper.
            raise TsharkError(f"tshark failed: {stderr.decode(errors='replace').strip()[:500]}")
    finally:
        try:
            os.unlink(scratch)
        except OSError:
            pass

    try:
        root = ET.fromstring(stdout)
    except ET.ParseError as e:
        raise TsharkError(f"Malformed PDML from tshark: {e}")

    packet = root.find("./packet")
    tree = [_pdml_to_nodes(child) for child in packet] if packet is not None else []
    return {
        "ts": ts,
        "source": {"node_id": node_id, "link_id": link_id, "marker": marker,
                   "frame_number": frame_number},
        "tshark_version": version,
        "field_count": sum(_count_nodes(node) for node in tree),
        "hex": raw_hex,
        "tree": tree,
    }
