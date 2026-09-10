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
Tag-keyed aggregate replay over paused markers' pcaps, powered by sharkd.

Markers on different links sharing a ``tag`` form one distributed capture
session. This module merges their per-marker pcaps
(``<project>/project-files/markers/{node_id}_{link_id}_{name}.pcap``) into a
single timestamp-ordered timeline and decodes frames on demand.

Engine: **sharkd is a hard requirement** (the Wireshark resident daemon,
driven over one-line JSON-RPC on stdin/stdout). Without it every replay
endpoint returns 501 — there is deliberately no degraded mode. Timeline
assembly (gate, pcap record-header scan, merge ordering, hex reads) is plain
Python, but it is an implementation detail, not an availability promise.

Session model — sharkd loads one file at a time, so there is one resident
session **per source pcap**: spawned lazily on first use, fed a ``/tmp``
scratch directory (hardened profiles deny sharkd the project directory; a
real copy, not a symlink, since the profile resolves real paths) with a
scratch ``HOME`` whose Wireshark preferences pin the packet-list column
layout, validated per request against the original's ``(mtime, size)`` —
a mismatch (e.g. the capture node restarted and uBridge truncated the pcap
while paused) kills and respawns the session. A per-session asyncio lock
serializes RPCs (sharkd serves one request at a time), each with a timeout
and an id check; any transport failure (timeout, dead pipe, malformed or
stale reply) kills the session for good — a desynced session must never
serve shifted results. A single manager lock makes check-spawn atomic (no
double spawn under concurrent requests) and sessions are refcounted while
in use, so the LRU cap only ever evicts idle ones.

Timestamps are uBridge's userspace ``gettimeofday`` at match time (µs, a
value measured after the packet has crossed the kernel twice — the last
digit or two are scheduling noise). A timestamp is NOT a unique key: the
merge sorts by ``(ts, source file, frame number)`` and index structures must
never use ts alone as a dict key, or same-microsecond frames silently
overwrite each other. The canonical ts strings travel to clients verbatim
and must be round-tripped verbatim.
"""

import asyncio
import json
import logging
import os
import shutil
import struct
import tempfile
import time
from contextlib import asynccontextmanager

from .controller_error import ControllerError, ControllerNotFoundError, ControllerBadRequestError

log = logging.getLogger(__name__)

# One JSON-RPC per sharkd session, serialized by a per-session lock.
RPC_TIMEOUT_SECONDS = 10.0

# Resident sharkd sessions are bounded; only IDLE sessions are ever evicted
# (least-recently-used first), so a request's own walk over a tag with more
# sources than the cap never kills a session out from under it — the
# population is trimmed back as uses drop instead.
SESSION_MAX = 16

# Display filters travel as one argv element (never through a shell) and are
# capped to keep absurd expressions off the command line.
FILTER_MAX_LENGTH = 2000

# Batch size when draining sharkd's `frames` RPC (columns / filter matches).
_FRAMES_PAGE = 1000

# A full `frames` page (1000 rows of pinned columns) measures ~190 KB against
# the 64 KB default StreamReader limit — over it, readline() raises and clears
# the stream, failing the request AND desyncing the resident session. Raise
# the ceiling well above any page (or single-frame tree) we can produce.
_STREAM_LIMIT_BYTES = 16 * 1024 * 1024

# sharkd's JSON-RPC error code for a rejected display filter — the only error
# that belongs to the client (400); everything else is an engine fault (502).
_ERR_INVALID_FILTER = -13002


class SharkdMissingError(ControllerError):
    """sharkd is not installed (or not on PATH) — replay is unavailable (501)."""


class SharkdError(ControllerError):
    """sharkd failed, timed out, or produced an unusable response (502)."""


class FilterError(ControllerBadRequestError):
    """sharkd rejected the display filter — its message is carried verbatim
    so the UI can show it inline in the filter bar (400, distinct from the
    409 gate / 404 unknown-tag semantics)."""


class _SharkdRpcError(Exception):
    """Internal: a JSON-RPC error object from sharkd (code + message)."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


# ---------------------------------------------------------------------------
# pcap record-header scanning (timeline backbone — engine-free)
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
    the engine. ``frame_number`` is 1-based (the same number sharkd's frame
    RPC uses).
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
# sharkd: process environment and scratch copies
# ---------------------------------------------------------------------------

# The packet-list layout is pinned through Wireshark preferences in the
# scratch HOME: personal config overrides any system-wide customization
# (/etc/wireshark &c.), so the column indexes in _columns_for are a contract
# we own rather than an environment default. Exactly the four columns the
# frame entries consume — nothing else rides along in every page.
_PINNED_COLUMNS = (
    'gui.column.format: "Source", "%s", "Destination", "%d", '
    '"Protocol", "%p", "Info", "%i"\n'
)


async def _prepare_scratch(pcap):
    """
    Build a scratch directory under the system temp dir holding the pcap copy
    for sharkd to load plus the pinned column preferences. Hardened profiles
    (AppArmor &c.) can deny sharkd the project directory / the user's home
    while still allowing /tmp — a real copy, deliberately not a symlink,
    since the profile resolves real paths. Caller must rmtree the directory.

    :returns: ``(scratch_dir, scratch_pcap_path)``
    """

    scratch_dir = tempfile.mkdtemp(prefix="gns3-replay-")
    scratch = os.path.join(scratch_dir, "capture.pcap")
    # A pcap-sized copy has no business stalling the event loop — a 1 GB
    # capture must not freeze every other request for the duration.
    await asyncio.to_thread(shutil.copyfile, pcap, scratch)
    prefs_dir = os.path.join(scratch_dir, ".config", "wireshark")
    os.makedirs(prefs_dir, exist_ok=True)
    with open(os.path.join(prefs_dir, "preferences"), "w") as f:
        f.write(_PINNED_COLUMNS)
    return scratch_dir, scratch


def _engine_env(scratch_dir):
    """Scratch HOME (and XDG config) so sharkd never even tries to read the
    user's home — and always reads OUR pinned preferences instead."""

    env = dict(os.environ)
    env["HOME"] = scratch_dir
    env["XDG_CONFIG_HOME"] = os.path.join(scratch_dir, ".config")
    return env


# ---------------------------------------------------------------------------
# sharkd: tree key renaming (the only transformation between sharkd and the
# REST contract — a closed, protocol-independent key set; values untouched)
# ---------------------------------------------------------------------------

# Census-verified across ICMP / TCP / VLAN+OSPF trees: sharkd emits exactly
# these structural keys on every node regardless of protocol. Protocol
# semantics live in VALUES (field names, labels, filter expressions), which
# are never touched.
_KEY_RENAME = {
    "t": "element",       # node type ("proto", …)
    "l": "label",         # display text
    "fn": "name",         # field name (e.g. "ip.ttl")
    "f": "filter_expr",   # ready-made display filter with the value baked in
    "s": "expert",        # expert severity name ("Chat", "Warn", …)
    "g": "generated",     # generated-by-wireshark flag
    "n": "children",      # nested fields
}
# "h" → pos + size (byte range for hex highlighting) — handled specially.
# "e" is sharkd's internal header-field registry id — unstable across
# Wireshark versions and useless for rendering, so it is dropped.
_DROPPED_KEYS = {"e"}


def _rename_value(value):
    """Recursive pass-through: rename known keys, drop none but 'e',
    copy unknown keys verbatim (a future Wireshark adding a key never
    silently loses data — the census test flags it for naming)."""

    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if key in _DROPPED_KEYS:
                continue
            if key == "h" and isinstance(item, list) and len(item) == 2:
                out["pos"], out["size"] = item
            else:
                out[_KEY_RENAME.get(key, key)] = _rename_value(item)
        return out
    if isinstance(value, list):
        return [_rename_value(item) for item in value]
    return value


def _count_tree_nodes(value):
    if isinstance(value, dict):
        return 1 + sum(_count_tree_nodes(item) for item in value.values())
    if isinstance(value, list):
        return sum(_count_tree_nodes(item) for item in value)
    return 0


# ---------------------------------------------------------------------------
# sharkd sessions (one resident process per source pcap)
# ---------------------------------------------------------------------------

class _SharkdSession:
    """A resident `sharkd -` process with one pcap loaded, addressed through
    line-oriented JSON-RPC. Serialized by an asyncio lock (sharkd serves one
    request at a time). Any transport-level failure aborts the session for
    good (see _abort) — a timed-out or desynced session must never answer
    later requests with shifted results."""

    def __init__(self, pcap, scratch_dir, scratch, proc, stat):
        self.pcap = pcap
        self.scratch_dir = scratch_dir
        self.scratch = scratch
        self.proc = proc
        self.mtime_ns = stat.st_mtime_ns
        self.size = stat.st_size
        self.last_used = time.monotonic()
        self.lock = asyncio.Lock()
        self._next_id = 0
        # Refcount of in-use holders (the manager's `session` context); the
        # LRU cap only ever evicts sessions with zero uses, and a detached
        # session (replaced in the manager, e.g. its pcap was rebuilt) closes
        # itself when its last holder releases it.
        self._uses = 0
        self._detached = False

    def matches(self, stat):
        """True while the source pcap is byte-identical to what was loaded —
        a fresh (mtime, size) would serve a rebuilt/truncated capture."""

        return stat.st_mtime_ns == self.mtime_ns and stat.st_size == self.size

    def alive(self):
        return self.proc.returncode is None

    def touch(self):
        self.last_used = time.monotonic()

    async def rpc(self, method, params):
        async with self.lock:
            self._next_id += 1
            request_id = self._next_id
            request = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
            try:
                self.proc.stdin.write((json.dumps(request) + "\n").encode())
                await self.proc.stdin.drain()
                raw = await asyncio.wait_for(self.proc.stdout.readline(), RPC_TIMEOUT_SECONDS)
            except asyncio.TimeoutError:
                await self._abort(f"sharkd timed out after {RPC_TIMEOUT_SECONDS:.0f}s on {method!r}")
            except (OSError, ValueError) as e:
                # ValueError: a reply line over the StreamReader limit — the
                # buffer is cleared, so the session is desynced either way.
                await self._abort(f"sharkd session died on {method!r}: {e}")
            if not raw:
                await self._abort(f"sharkd closed the session during {method!r}")
            try:
                response = json.loads(raw)
            except ValueError as e:
                await self._abort(f"Malformed sharkd response: {e}")
            # The echoed id proves this reply belongs to THIS request: a stale
            # reply left over from a timed-out predecessor (or any desync)
            # must never be served as fresh data.
            if response.get("id") != request_id:
                await self._abort(f"sharkd reply id mismatch on {method!r} (session desynchronized)")
            if "error" in response:
                error = response["error"]
                raise _SharkdRpcError(error.get("code"), str(error.get("message", "")))
            return response.get("result")

    async def _abort(self, message):
        """Kill the session for good (process + scratch copy) and raise — the
        manager replaces it on the next acquire. Idempotent with close()."""

        await self.close()
        raise SharkdError(message)

    async def close(self):
        try:
            if self.proc.returncode is None:
                self.proc.kill()
                # Bounded wait: a kill that fails to reap (blocked signals,
                # mocked os.kill in tests, a wedged process) must never hang
                # the caller — leak the process with a log instead.
                try:
                    await asyncio.wait_for(self.proc.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    log.warning("sharkd session for %s did not exit after kill", self.pcap)
        except ProcessLookupError:
            pass
        shutil.rmtree(self.scratch_dir, ignore_errors=True)


class _SharkdManager:
    """Resident sharkd sessions keyed by source pcap path.

    One asyncio lock covers check-spawn-insert-reap: the check-then-spawn
    window spans the pcap copy, the fork and the load RPC, so without it two
    concurrent requests for the same pcap double-spawn and the loser leaks
    (process + scratch copy) forever. Sessions are refcounted while in use
    (the `session` context manager) and the LRU cap only evicts IDLE
    sessions — a tag with more sources than the cap, or a concurrent request,
    can never have its session killed mid-RPC; the population is trimmed
    back to the cap as uses drop (temporary overshoot is allowed)."""

    def __init__(self):
        self._sessions = {}
        self._mu = asyncio.Lock()

    @asynccontextmanager
    async def session(self, pcap):
        session = await self._acquire(pcap)
        try:
            yield session
        finally:
            await self._release(session)

    async def _acquire(self, pcap):
        if shutil.which("sharkd") is None:
            raise SharkdMissingError(
                "sharkd is not available on this server — marker replay requires sharkd "
                "(part of the Wireshark package)"
            )
        try:
            stat = os.stat(pcap)
        except FileNotFoundError:
            # Deleted between the directory listing and here (marker removed,
            # project cleaned up) — not a server fault.
            raise ControllerNotFoundError(f"Capture file {os.path.basename(pcap)} no longer exists")
        async with self._mu:
            session = self._sessions.get(pcap)
            if session is not None and session.matches(stat) and session.alive():
                session._uses += 1
                session.touch()
                return session
            if session is not None:
                # Rebuilt/truncated source or a dead session: replace it. An
                # in-use one closes itself when its last holder releases it.
                del self._sessions[pcap]
                if session._uses == 0:
                    await session.close()
                else:
                    session._detached = True
            spawned = await self._spawn(pcap, stat)
            spawned._uses += 1
            self._sessions[pcap] = spawned
            victims = self._evict_locked()
        for victim in victims:
            await victim.close()
        return spawned

    def _evict_locked(self):
        """Caller holds ``_mu``. Pop (not close — that can block on the reap)
        least-recently-used IDLE sessions down to the cap; if everything is
        in use, allow the overshoot rather than killing a live request."""

        victims = []
        while len(self._sessions) > SESSION_MAX:
            idle = [s for s in self._sessions.values() if s._uses == 0]
            if not idle:
                break
            victim = min(idle, key=lambda s: s.last_used)
            del self._sessions[victim.pcap]
            victims.append(victim)
        return victims

    async def _release(self, session):
        async with self._mu:
            session._uses -= 1
            victims = []
            if session._uses == 0:
                if session._detached:
                    # Replaced in the manager while still held — now orphaned.
                    victims.append(session)
                elif not session.alive():
                    # Failed mid-use (its RPC aborted it) — drop the corpse.
                    if self._sessions.get(session.pcap) is session:
                        del self._sessions[session.pcap]
                else:
                    victims = self._evict_locked()
        for victim in victims:
            await victim.close()

    async def _spawn(self, pcap, stat):
        scratch_dir, scratch = await _prepare_scratch(pcap)
        try:
            proc = await asyncio.create_subprocess_exec(
                "sharkd", "-",
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL, env=_engine_env(scratch_dir),
                limit=_STREAM_LIMIT_BYTES,
            )
        except OSError as e:
            shutil.rmtree(scratch_dir, ignore_errors=True)
            raise SharkdError(f"Could not run sharkd: {e}")
        session = _SharkdSession(pcap, scratch_dir, scratch, proc, stat)
        try:
            await session.rpc("load", {"file": scratch})
        except Exception as e:
            await session.close()
            raise SharkdError(f"sharkd failed to load {os.path.basename(pcap)}: {e}")
        return session

    async def close_all(self):
        async with self._mu:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for session in sessions:
            await session.close()


_manager = None


def _get_manager():
    global _manager
    if _manager is None:
        _manager = _SharkdManager()
    return _manager


async def close_sessions():
    """Server shutdown hook: kill every resident session and drop its scratch
    copy, so nothing leaks into /tmp across restarts."""

    global _manager
    manager = _manager
    if manager is not None:
        await manager.close_all()
    _manager = None


# ---------------------------------------------------------------------------
# Columns + display filter (sharkd `frames` RPC)
# ---------------------------------------------------------------------------

async def _columns_for(pcap, filter_expr):
    """
    One resident `frames` pass over the source pcap. Returns
    ``{frame_number: {src, dst, proto, info, bg, fg}}``; with a
    ``filter_expr`` the keys are exactly the matching frame numbers, so one
    pass both filters and enriches the merge.

    The column layout is pinned by the scratch-HOME preferences (see
    _PINNED_COLUMNS): ``c[0]``=src, ``c[1]``=dst, ``c[2]``=proto, ``c[3]``=info
    is a layout we own, not an environment default. The whole pagination
    loop holds the session so the LRU cap cannot evict it between pages.
    """

    manager = _get_manager()
    async with manager.session(pcap) as session:
        columns = {}
        skip = 0
        while True:
            # sharkd rejects skip=0 ("must be a positive integer") — only send
            # it once there is actually something to skip.
            params = {"limit": _FRAMES_PAGE}
            if skip:
                params["skip"] = skip
            if filter_expr is not None:
                params["filter"] = filter_expr
            try:
                rows = await session.rpc("frames", params)
            except _SharkdRpcError as e:
                if filter_expr is not None and e.code == _ERR_INVALID_FILTER:
                    raise FilterError(f"Invalid display filter: {e.message}")
                # Anything else is an engine fault, not the client's filter.
                raise SharkdError(f"sharkd frames failed on {os.path.basename(pcap)}: {e.message}")
            for row in rows or []:
                try:
                    frame_number = int(row.get("num"))
                except (TypeError, ValueError):
                    continue
                cols = row.get("c") or []
                columns[frame_number] = {
                    "src": cols[0] or None if len(cols) > 0 else None,
                    "dst": cols[1] or None if len(cols) > 1 else None,
                    "proto": cols[2] or None if len(cols) > 2 else None,
                    "info": cols[3] or None if len(cols) > 3 else None,
                    "bg": row.get("bg"),
                    "fg": row.get("fg"),
                }
            if len(rows or []) < _FRAMES_PAGE:
                return columns
            skip += len(rows or [])


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


async def _merged_frames(project, entries, filter_expr=None, link_id=None):
    """
    Scan every source pcap's record headers, ask sharkd for columns (and,
    with a filter, the matching set), and merge into one list sorted by
    ``(ts, source file, frame number)`` — ts alone is not unique (two links
    can hit the same microsecond); the tiebreaker yields a stable, determined
    order instead of a fictional one. With a filter, only frames sharkd
    matched survive, keeping their original pcap frame numbers.

    ``link_id`` narrows the frame stream to one capture source **before** any
    engine work (a pure identity filter — only the selected link's pcap gets
    a sharkd pass) and AND-composes with ``filter_expr``. An unknown link
    matches nothing: an empty stream, same shape as a zero-match display
    filter — deliberately not a 404.

    ``sources`` is the stable inventory of the tag: EVERY capture source is
    listed with engine-free total counts, unaffected by ``link_id`` /
    ``filter_expr`` — the inventory must not shrink when the view narrows.
    """

    markers_dir = project.markers_directory
    merged = []
    sources = []
    for entry in entries:
        pcap = os.path.join(
            markers_dir, f"{entry['node_id']}_{entry['link_id']}_{entry['marker']}.pcap"
        )
        frames = scan_pcap_frames(pcap) if os.path.exists(pcap) else []
        # Inventory first: every source, engine-free totals.
        sources.append({**{k: entry[k] for k in ("node_id", "link_id", "marker", "data_link_type")},
                        "count": len(frames)})
        if link_id and entry["link_id"] != link_id:
            continue  # link narrows the stream before any engine work
        if frames:
            columns = await _columns_for(pcap, filter_expr)
        else:
            columns = {}
        source_key = f"{entry['node_id']}_{entry['link_id']}_{entry['marker']}"
        for frame_number, (sec, usec, incl_len) in enumerate(frames, start=1):
            if filter_expr is not None and frame_number not in columns:
                continue
            cols = columns.get(frame_number, {})
            merged.append({
                "ts": _format_ts(sec, usec),
                "ts_us": sec * 1_000_000 + usec,
                "_source": source_key,
                "len": incl_len,
                "node_id": entry["node_id"],
                "link_id": entry["link_id"],
                "marker": entry["marker"],
                "frame_number": frame_number,
                "src": cols.get("src"),
                "dst": cols.get("dst"),
                "proto": cols.get("proto"),
                "info": cols.get("info"),
                "bg": cols.get("bg"),
                "fg": cols.get("fg"),
            })
    merged.sort(key=lambda f: (f["ts_us"], f["_source"], f["frame_number"]))
    for frame in merged:
        del frame["ts_us"]
        del frame["_source"]
    return merged, sources


def _validate_filter(filter_expr):
    if filter_expr is not None and len(filter_expr) > FILTER_MAX_LENGTH:
        raise ControllerBadRequestError(
            f"Display filter too long (max {FILTER_MAX_LENGTH} characters)"
        )


async def build_timeline(project, tag, filter_expr=None, link_id=None):
    """
    The ``range`` response: timeline bounds, per-source stats, and the full
    merged frame list — deliberately uncapped (a flat list is the whole
    contract; rendering a huge list is the client's concern, and the window
    endpoint exists for incremental views). With a ``filter_expr`` and/or a
    ``link_id`` every figure is computed on the matching frames only
    (``sources`` stays the full tag inventory).
    """

    _validate_filter(filter_expr)
    entries = gate_tag(project, tag)
    frames, sources = await _merged_frames(project, entries, filter_expr, link_id=link_id)

    return {
        "tag": tag,
        "start": frames[0]["ts"] if frames else None,
        "end": frames[-1]["ts"] if frames else None,
        "frame_count": len(frames),
        "sources": sources,
        "frames": frames,
    }


async def query_frames(project, tag, ts, window_ms=100, limit=1000, filter_expr=None, link_id=None):
    """
    Frames with ts in ``[T, T+window_ms]`` merged across sources — narrowed
    by ``filter_expr`` / ``link_id`` with the same semantics as the range
    endpoint, so windowed seconds and the histogram always agree. A time
    with no frames is a normal, successful answer — ``{"frames": []}``.
    """

    _validate_filter(filter_expr)
    entries = gate_tag(project, tag)
    frames, _sources = await _merged_frames(project, entries, filter_expr, link_id=link_id)

    start_us = _parse_ts(ts)
    end_us = start_us + max(window_ms, 0) * 1000
    hits = [f for f in frames if start_us <= _parse_ts(f["ts"]) <= end_us]
    return {"frames": hits[:max(limit, 0)]}


# ---------------------------------------------------------------------------
# Frame detail (lazy — one frame per call, via the resident session)
# ---------------------------------------------------------------------------

async def decode_frame(project, tag, ts, node_id, link_id, marker, frame_number=None):
    """
    Decode exactly one frame: locate its pcap by source identity, verify the
    round-tripped ts still matches the file (guards a rebuild between the
    timeline view and this click), read the raw bytes for the hex view
    straight from the pcap, and rename the sharkd protocol tree into the
    REST contract (closed key set, values untouched).

    ``ts`` is not unique within one pcap (same-microsecond frames are kept
    deliberately); an explicit ``frame_number`` from the frame list entry
    disambiguates them and must still land on the exact ts. Without one the
    first ts match decodes — fine unless two frames share a microsecond on
    the same link.
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
    rebuilt_message = (
        f"No frame at ts {ts} in marker '{marker}' (the capture may have been rebuilt)"
    )
    if frame_number is None:
        # The ts must be the exact string the timeline returned; find the frame
        # it identifies rather than trusting any position hint from the client.
        frame_number = next(
            (i for i, (sec, usec, _len) in enumerate(frames, start=1)
             if _format_ts(sec, usec) == ts),
            None,
        )
        if frame_number is None:
            raise ControllerNotFoundError(rebuilt_message)
    else:
        if not 1 <= frame_number <= len(frames):
            raise ControllerNotFoundError(rebuilt_message)
        sec, usec, _len = frames[frame_number - 1]
        if _format_ts(sec, usec) != ts:
            raise ControllerNotFoundError(rebuilt_message)

    raw_hex = read_frame_bytes(pcap, frame_number)
    if raw_hex is None:
        # The header scan listed it but the bytes are gone — mid-write tail.
        raise ControllerNotFoundError(rebuilt_message)

    async with _get_manager().session(pcap) as session:
        try:
            result = await session.rpc("frame", {"frame": frame_number, "proto": True})
        except _SharkdRpcError as e:
            # The frame range was validated against the file above, so an
            # engine error here is a real fault (502), not a client 404.
            raise SharkdError(f"sharkd frame failed: {e.message}")

    tree = _rename_value(result.get("tree", []))
    return {
        "ts": ts,
        "source": {"node_id": node_id, "link_id": link_id, "marker": marker,
                   "frame_number": frame_number},
        "field_count": _count_tree_nodes(tree),
        "hex": raw_hex,
        "tree": tree,
    }
