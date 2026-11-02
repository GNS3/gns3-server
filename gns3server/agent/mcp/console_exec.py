#
# Copyright (C) 2026 GNS3 Technologies Inc.
# Author: Yue Guobin
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
node_console_exec: one-shot node console executor.

Server-side equivalent of the client-side chain this workflow used to need:

    node_console (mint URL+ticket) -> bash: { sleep ..; printf 'cmd\r\n'; .. }
                                      | timeout N websocat -t --no-close '<url>'

One tool call is one complete console session: the server spawns
``timeout N websocat -t --no-close <url>``, feeds the command lines through
stdin, keeps reading stdout until the timeout kills websocat, and returns the
collected output as plain text. No session state survives the call; node-side
state (config mode, running pings) persists across calls by nature of the
console itself.

The transport is deliberately the host's websocat binary instead of a
self-built WebSocket client — the same wire behavior as the field-proven
bash template, including its quirks (raw byte stream, no early return).

Output funnel: up to DIRECT_LINES lines are returned as-is. Beyond that a
SAMPLE_LINES excerpt comes back with retrieval hints — re-filter the cached
capture (regrep), dump its tail (full), or download the whole capture written
to the node's files. The raw capture is cached per node so a second look at a
command's output never re-runs it (and never repeats its side effects).
"""

import asyncio
import contextlib
import logging
import math
import os
import re
import signal
from typing import Any

from gns3server.services import access_ticket_service

log = logging.getLogger(__name__)

# Wall clock of the whole session (connect + send + receive), matching
# `timeout N websocat`. Field-tested sizing: 2-3 verification commands fit
# in 15 s; 46-50 config lines (~15 s of paced input) need 30 s or more.
DEFAULT_TIMEOUT_S = 15.0
MAX_TIMEOUT_S = 300.0
# Pacing between command lines. Consoles ingest lines much slower than a
# local shell (IOL polls its console ~50 ms per key; remote pty echo lags),
# and dumping 50 lines at once can drop input.
LINE_INTERVAL_S = 0.3
# Output funnel thresholds.
DIRECT_LINES = 50
SAMPLE_LINES = 10
FULL_LINES = 400
MAX_OUTPUT_BYTES = 64 * 1024
# Flood guard for one session: stop collecting after this much raw output.
MAX_CAPTURE_BYTES = 8 * 1024 * 1024
CAPTURE_FILE = "console-capture.txt"

# Newest raw output per node (resolved UUIDs) — the regrep/full target.
_OUTPUT_CACHE: dict[tuple[str, str], str] = {}


def prepare_payloads(command: str) -> list[str]:
    """Split a command string into console-ready stdin payloads.

    Each line becomes one write:

    - a plain line gets ``\\r\\n`` appended (consoles need the carriage
      return; a bare ``\\n`` does not execute on most NOS),
    - a line already ending in ``\\r`` only gets the ``\\n``,
    - a line containing control characters (``\\x03`` and friends) is sent
      verbatim with no line ending — it is a keypress, not a command.
    """

    payloads = []
    for line in command.split("\n"):
        if line.endswith("\r"):
            payloads.append(line + "\n")
        elif any(ord(ch) < 0x20 and ch != "\t" for ch in line):
            payloads.append(line)
        else:
            payloads.append(line + "\r\n")
    return payloads


def _ws_url(server_url: str, project_id: str, node_id: str, token: str) -> str:
    """Console WS URL on the controller (it proxies to the node's compute)."""

    url = f"{server_url}/v3/projects/{project_id}/nodes/{node_id}/console/ws"
    url = url.replace("https://", "wss://").replace("http://", "ws://")
    # JWTs are base64url + dots, safe in a query string as-is.
    return f"{url}?token={token}"


async def _resolve_console_node(
    project_id: str,
    node_id: str,
    gns3_ctx: dict[str, Any],
    validate_console: bool = True,
) -> tuple[dict[str, Any] | None, str | None]:
    """Fetch the node (resolving names to UUIDs) and validate its console.

    Returns (node dict, None) or (None, plain error text). Name resolution
    goes through the same ``resolve_locators`` choke point as every other
    tool (known-names fast failure included). With ``validate_console`` off,
    only existence is required (the regrep path reads a capture from a node
    that may since have been stopped).
    """

    from gns3server.agent.gns3_copilot.gns3_client.api_handlers import _get_connector
    from gns3server.agent.mcp.locators import resolve_locators

    def resolve_and_fetch() -> dict[str, Any]:
        resolved, resolution_error = resolve_locators(
            {"project_id": project_id, "node_id": node_id},
            lambda handler, params: handler(params, gns3_ctx),
        )
        if resolved is None:
            assert resolution_error is not None  # resolve_locators' None-error contract
            return resolution_error
        conn = _get_connector(gns3_ctx)
        url = f"{conn.base_url}/projects/{resolved['project_id']}/nodes/{resolved['node_id']}"
        return conn.http_call("get", url).json()

    try:
        node = await asyncio.to_thread(resolve_and_fetch)
    except Exception as e:
        return None, f"could not resolve project '{project_id}' / node '{node_id}': {e}"

    if "error" in node:  # resolution failure dict from resolve_locators
        return None, str(node["error"])

    if not validate_console:
        return node, None

    name = node.get("name", node_id)
    if (node.get("console_type") or "telnet") == "vnc":
        return None, f"node '{name}' has a VNC console (pixel stream) — there is no text command channel"
    if not node.get("console"):
        return None, f"node '{name}' has no console"
    if node.get("status") != "started":
        return None, f"node '{name}' is {node.get('status')} — start it before using the console"
    return node, None


async def _spawn(url: str, seconds: int) -> asyncio.subprocess.Process:
    """Start ``timeout <seconds> websocat -t --no-close <url>``.

    The subprocess gets its own process group: websocat is a child of
    ``timeout``, and a cancelled call must take down the whole tree (an
    externally killed ``timeout`` alone could orphan websocat).
    """

    return await asyncio.create_subprocess_exec(
        "timeout",
        str(seconds),
        "websocat",
        "-t",
        "--no-close",
        url,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
    )


async def _feed_lines(stdin: asyncio.StreamWriter, payloads: list[str]) -> None:
    """Write one payload per turn with pacing, then half-close stdin."""

    try:
        for payload in payloads:
            stdin.write(payload.encode("utf-8", errors="replace"))
            await stdin.drain()
            await asyncio.sleep(LINE_INTERVAL_S)
    finally:
        stdin.close()


async def _drain_stream(stream: asyncio.StreamReader | None, cap: int) -> bytes:
    """Read a subprocess stream to EOF, stopping at ``cap`` bytes."""

    if stream is None:
        return b""
    chunks: list[bytes] = []
    total = 0
    while total < cap:
        block = await stream.read(65536)
        if not block:
            break
        chunks.append(block)
        total += len(block)
    return b"".join(chunks)


async def _run_session(url: str, payloads: list[str], seconds: int) -> tuple[bytes, bytes, int | None]:
    """Run one websocat session: feed the payloads, collect stdout until EOF.

    Returns (stdout, stderr, returncode). Exit code 124 (the ``timeout``
    kill) is the normal end of a session; websocat exiting on its own means
    the console side dropped the connection.
    """

    try:
        proc = await _spawn(url, seconds)
    except FileNotFoundError:
        return b"", b"timeout binary not found", -1

    # stdin/stdout/stderr were requested as PIPE, so the Optional is static only
    assert proc.stdin is not None and proc.stdout is not None and proc.stderr is not None
    feed_task = asyncio.create_task(_feed_lines(proc.stdin, payloads))
    stderr_task = asyncio.create_task(_drain_stream(proc.stderr, 64 * 1024))
    try:
        stdout = await _drain_stream(proc.stdout, MAX_CAPTURE_BYTES)
        returncode = await proc.wait()
        return stdout, await stderr_task, returncode
    except asyncio.CancelledError:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(proc.pid, signal.SIGTERM)
        raise
    finally:
        feed_task.cancel()
        stderr_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, BrokenPipeError, ConnectionResetError):
            await feed_task
        with contextlib.suppress(asyncio.CancelledError):
            await stderr_task
        if proc.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                proc.kill()
        with contextlib.suppress(asyncio.CancelledError):
            await proc.wait()


def _session_error(stderr: bytes, returncode: int | None, seconds: int) -> str:
    """Classify an output-less session into plain error text."""

    err = stderr.decode("utf-8", errors="replace").strip()
    # coreutils timeout exits 125 when it cannot run the command; the
    # message text is the reliable marker for a missing websocat.
    if "failed to run command" in err or returncode in (125, 127):
        return (
            "websocat is not installed on the server host — install it "
            "(https://github.com/vi/websocat/releases or `cargo install websocat`) and retry"
        )
    if returncode == 124:
        return (
            f"no console output within {seconds}s — the console may still be booting or silent; "
            "retry with a larger timeout"
        )
    detail = f": {err[-400:]}" if err else ""
    return f"websocat exited with code {returncode}{detail}"


def _tail_bytes(text: str, cap: int) -> tuple[str, bool]:
    """Byte-cap a string from the end; returns (text, was_capped)."""

    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= cap:
        return text, False
    return encoded[-cap:].decode("utf-8", errors="replace"), True


def shape_view(text: str, grep: str | None, full: bool) -> tuple[str, dict[str, Any] | None]:
    """Filter and size the captured text for return.

    Returns (reply_body, None) for a final reply — including the plain-error
    cases (invalid pattern, grep miss) — or (header, metadata) when the
    output exceeded DIRECT_LINES: the caller appends retrieval hints to the
    metadata-carrying header (it knows the download URL).
    """

    shown = text.splitlines()
    if grep is not None:
        try:
            pattern = re.compile(grep)
        except re.error as e:
            return f"invalid grep pattern {grep!r}: {e}", None
        shown = [line for line in shown if pattern.search(line)]
        if not shown:
            return (
                f"grep {grep!r} matched nothing — {len(text.splitlines())} lines captured. "
                "Retry with a wider pattern and regrep=true (re-filters the capture, no re-run), "
                f"or regrep=true + full=true to dump its last {FULL_LINES} lines.",
                None,
            )

    if full:
        tail = shown[-FULL_LINES:]
        body, capped = _tail_bytes("\n".join(tail), MAX_OUTPUT_BYTES)
        header = f"output: last {len(tail)} of {len(shown)} lines"
        if len(shown) > FULL_LINES:
            header += f" (line cap {FULL_LINES})"
        if capped:
            header += f" (byte cap {MAX_OUTPUT_BYTES // 1024} KiB)"
        return f"{header}\n{body}", None

    if len(shown) > DIRECT_LINES:
        sample = "\n".join(shown[:SAMPLE_LINES])
        header = f"output: {len(shown)} lines total — first {SAMPLE_LINES} shown:\n{sample}\n---"
        return header, {"lines": len(shown), "grep": grep}

    body = "\n".join(shown) if grep is not None else text
    return f"output:\n{body}", None


def _write_capture_and_url(text: str, project_id: str, node_id: str, gns3_ctx: dict[str, Any]) -> str | None:
    """Persist the raw capture into the node's files; return a ticketed download URL.

    The file route and the path-bound access ticket are the same mechanism
    the capture-download tool uses. Any failure here only costs the hint,
    not the reply — return None and let the caller fall back.
    """

    from gns3server.agent.gns3_copilot.gns3_client.api_handlers import _get_connector

    username = gns3_ctx.get("jwt_username")
    if not username:
        return None
    try:
        conn = _get_connector(gns3_ctx)
        conn.http_call(
            "post",
            f"{conn.base_url}/projects/{project_id}/nodes/{node_id}/files/{CAPTURE_FILE}",
            data=text,
            headers={"Content-Type": "text/plain"},
        )
    except Exception as e:
        log.warning("Could not write the console capture file for node %s: %s", node_id, e)
        return None
    path = f"/v3/projects/{project_id}/nodes/{node_id}/files/{CAPTURE_FILE}"
    ticket = access_ticket_service.mint(username, token_version=gns3_ctx.get("jwt_token_version", 0), path=path)
    return f"{gns3_ctx['server_url']}{path}?token={ticket}"


async def console_exec(
    project_id: str,
    node_id: str,
    command: str,
    timeout: float,  # noqa: ASYNC109 - operation-specific timeout is intentional
    grep: str | None = None,
    regrep: bool = False,
    full: bool = False,
    gns3_ctx: dict[str, Any] | None = None,
) -> str:
    """Run one one-shot console session (or re-view its capture) as plain text."""

    assert gns3_ctx is not None
    node, error = await _resolve_console_node(project_id, node_id, gns3_ctx, validate_console=not regrep)
    if error is not None:
        return error
    assert node is not None
    key = (str(node["project_id"]), str(node["node_id"]))

    if regrep:
        text = _OUTPUT_CACHE.get(key)
        if text is None:
            return (
                f"no captured output for node '{node.get('name', node_id)}' yet — "
                "run a command first, then re-filter it with regrep=true"
            )
    else:
        url = _ws_url(gns3_ctx["server_url"], key[0], key[1], gns3_ctx.get("jwt_token") or "")
        payloads = prepare_payloads(command) or ["\r\n"]
        seconds = max(1, math.ceil(min(max(float(timeout), 1.0), MAX_TIMEOUT_S)))
        stdout, stderr, returncode = await _run_session(url, payloads, seconds)
        if not stdout:
            return _session_error(stderr, returncode, seconds)
        # Raw console bytes decoded with replacement only — telnet/ANSI noise
        # is left in on purpose (no stripping layer between AI and console).
        text = stdout.decode("utf-8", errors="replace")
        _OUTPUT_CACHE[key] = text

    body, too_long = shape_view(text, grep, full)
    if too_long is None:
        return body

    download_url = await asyncio.to_thread(_write_capture_and_url, text, key[0], key[1], gns3_ctx)
    hints = [
        f"{too_long['lines']} lines is too long to return whole. Without re-running the command:",
        "- regrep=true + grep=<pattern> re-filters the captured output",
        f"- regrep=true + full=true returns its last {FULL_LINES} lines",
    ]
    if too_long["grep"] is None:
        hints.append("- grep=<pattern> re-runs the command with the filter applied")
    if download_url:
        hints.append(f"- download the full capture: curl -o {CAPTURE_FILE} '{download_url}'")
    return "\n".join([body, *hints])
