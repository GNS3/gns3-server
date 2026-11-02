"""
node_console_exec tests.

The transport is the host's websocat binary behind `timeout`, so the session
tests run against a fake subprocess (a recorder with the asyncio Process
shape) — no binary, no network. One integration test exercises the real
websocat against a local WebSocket server and is skipped when websocat is
not installed. Node resolution is mocked at the connector layer, matching
the other handler tests.
"""

import contextlib
import importlib
import shutil
import time
from unittest.mock import patch

import pytest

from gns3server.agent.mcp.console_exec import (
    _ws_url,
    console_exec,
    prepare_payloads,
    shape_view,
)

# the package __init__ rebinds the name "console_exec" to the tool function,
# so import paths hand back the function — the module (monkeypatch target for
# module-level constants) must come from sys.modules
ce_module = importlib.import_module("gns3server.agent.mcp.console_exec")

AH = "gns3server.agent.gns3_copilot.gns3_client.api_handlers"
# list_projects_handler lives in the MCP projects module with its own
# _get_connector binding — both must be patched for locator-chain tests
PROJECTS = "gns3server.agent.mcp.projects"
CE = "gns3server.agent.mcp.console_exec"


def _node_payload(**overrides):
    node = {
        "node_id": "n-uuid-1",
        "project_id": "p-uuid-1",
        "name": "R1",
        "status": "started",
        "console": 5000,
        "console_type": "telnet",
    }
    node.update(overrides)
    return node


class _MockResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class _MockConnector:
    def __init__(self, payload):
        self.base_url = "http://127.0.0.1:3080/v3"
        self._payload = payload
        self.calls = []

    def http_call(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return _MockResponse(self._payload)


class _RoutingConnector:
    """Serves the calls the locator chain makes: project list (name lookup),
    node list (name lookup) and node detail — in URL-shape order."""

    def __init__(self, projects, nodes, node):
        self.base_url = "http://127.0.0.1:3080/v3"
        self._projects = projects
        self._nodes = nodes
        self._node = node
        self.calls = []

    def http_call(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if url.endswith("/nodes"):
            return _MockResponse(self._nodes)
        if url.endswith("/projects"):
            return _MockResponse(self._projects)
        return _MockResponse(self._node)


class _FakeReader:
    """StreamReader shape: hands out the given chunks, then EOF forever."""

    def __init__(self, chunks):
        self._chunks = list(chunks)

    async def read(self, n=-1):
        if not self._chunks:
            return b""
        return self._chunks.pop(0)


class _FakeWriter:
    """StreamWriter shape: records writes, never blocks."""

    def __init__(self):
        self.received = []
        self.closed = False

    def write(self, data):
        self.received.append(data)

    async def drain(self):
        return None

    def close(self):
        self.closed = True


class _FakeProc:
    """asyncio Process shape for a websocat-under-timeout session."""

    def __init__(self, stdout_chunks, stderr_chunks=(), returncode=124):
        self.stdin = _FakeWriter()
        self.stdout = _FakeReader(stdout_chunks)
        self.stderr = _FakeReader(stderr_chunks)
        self.returncode = returncode
        self.pid = 4242

    async def wait(self):
        return self.returncode

    def kill(self):
        pass


class _SpawnRecorder:
    """Stands in for console_exec._spawn, handing out prepared processes."""

    def __init__(self, *procs):
        self.procs = list(procs)
        self.calls = []

    async def __call__(self, url, seconds):
        self.calls.append((url, seconds))
        return self.procs.pop(0)


def _ctx(server_url="http://127.0.0.1:3080"):
    return {"server_url": server_url, "jwt_token": "jwt-abc", "jwt_username": "admin", "jwt_token_version": 1}


@pytest.fixture(autouse=True)
def _fast_pacing_and_clean_cache(monkeypatch):
    monkeypatch.setattr(ce_module, "LINE_INTERVAL_S", 0.01)
    monkeypatch.setattr(ce_module, "_OUTPUT_CACHE", {})


# ── pure helpers ────────────────────────────────────────────────────────


def test_plain_lines_get_crlf():
    assert prepare_payloads("show version\nshow ip route") == ["show version\r\n", "show ip route\r\n"]


def test_line_already_ending_with_cr_gets_bare_lf():
    assert prepare_payloads("vtysh\r") == ["vtysh\r\n"]


def test_control_character_line_sent_verbatim():
    # Ctrl-C is a keypress, not a command: no line ending is appended
    assert prepare_payloads("\x03") == ["\x03"]
    assert prepare_payloads("conf t\n\x03") == ["conf t\r\n", "\x03"]


def test_no_control_spelling_translation():
    # the 4-character spelling "\x03" is text and must arrive as text
    assert prepare_payloads("\\x03") == ["\\x03\r\n"]


def test_ws_url_scheme_and_token():
    assert _ws_url("https://h:3080", "p", "n", "t") == "wss://h:3080/v3/projects/p/nodes/n/console/ws?token=t"
    assert _ws_url("http://h:3080", "p", "n", "t") == "ws://h:3080/v3/projects/p/nodes/n/console/ws?token=t"


def test_short_output_returns_raw_text():
    text = "Welcome to the console\r\nPC1> \r\n"
    body, too_long = shape_view(text, grep=None, full=False)
    assert too_long is None
    assert body == "output:\n" + text  # byte-faithful, \r\n untouched


def test_grep_filters_matching_lines():
    body, too_long = shape_view("R1# a\nR1# b\nX c\n", grep="^R1#", full=False)
    assert too_long is None
    assert body == "output:\nR1# a\nR1# b"


def test_grep_python_syntax_works():
    # \d is valid Python re (a grep -E would treat it as literal 'd')
    body, _ = shape_view("ip 10.0.0.1\nip foo\n", grep=r"ip 10\.\d+", full=False)
    assert "10.0.0.1" in body and "foo" not in body


def test_grep_miss_points_at_regrep():
    body, too_long = shape_view("aaa\nbbb\n", grep="zzz", full=False)
    assert too_long is None
    assert "matched nothing" in body and "2 lines captured" in body
    assert "regrep=true" in body


def test_invalid_grep_is_a_plain_error():
    body, too_long = shape_view("aaa\n", grep="([unclosed", full=False)
    assert too_long is None
    assert body.startswith("invalid grep pattern")


def test_long_output_trips_the_funnel():
    text = "\n".join(f"line {i}" for i in range(60))
    body, too_long = shape_view(text, grep=None, full=False)
    assert too_long == {"lines": 60, "grep": None}
    assert body.startswith("output: 60 lines total — first 10 shown:\nline 0\n")
    assert body.endswith("line 9\n---")


def test_full_returns_the_tail_with_header():
    text = "\n".join(f"line {i}" for i in range(500))
    body, too_long = shape_view(text, grep=None, full=True)
    assert too_long is None
    assert body.startswith("output: last 400 of 500 lines (line cap 400)\nline 100\n")


# ── sessions against a fake subprocess ──────────────────────────────────


@pytest.mark.asyncio
async def test_one_shot_session_collects_output_and_feeds_lines():
    proc = _FakeProc([b"Welcome\r\n", b"R1# show version\r\n", b"uptime 5m\r\n"])
    recorder = _SpawnRecorder(proc)
    with (
        patch(f"{AH}._get_connector", return_value=_MockConnector(_node_payload())),
        patch(f"{CE}._spawn", recorder),
    ):
        result = await console_exec(
            "11111111-1111-1111-1111-111111111111",
            "22222222-2222-2222-2222-222222222222",
            "show version",
            5,
            gns3_ctx=_ctx(),
        )

    assert result.startswith("output:\n")
    assert "uptime 5m" in result
    assert proc.stdin.received == [b"show version\r\n"]
    assert proc.stdin.closed  # stdin half-closed after feeding (--no-close keeps the session)
    url, seconds = recorder.calls[0]
    assert url == "ws://127.0.0.1:3080/v3/projects/p-uuid-1/nodes/n-uuid-1/console/ws?token=jwt-abc"
    assert seconds == 5


@pytest.mark.asyncio
async def test_empty_command_sends_a_single_enter():
    proc = _FakeProc([b"PC1> \r\n"])
    with (
        patch(f"{AH}._get_connector", return_value=_MockConnector(_node_payload())),
        patch(f"{CE}._spawn", _SpawnRecorder(proc)),
    ):
        result = await console_exec(
            "11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222", "", 3, gns3_ctx=_ctx()
        )
    assert proc.stdin.received == [b"\r\n"]
    assert "PC1>" in result


@pytest.mark.asyncio
async def test_timeout_is_clamped_to_the_allowed_range():
    proc = _FakeProc([b"PC1> \r\n"])
    recorder = _SpawnRecorder(proc)
    with (
        patch(f"{AH}._get_connector", return_value=_MockConnector(_node_payload())),
        patch(f"{CE}._spawn", recorder),
    ):
        await console_exec(
            "11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222", "", 9999, gns3_ctx=_ctx()
        )
    assert recorder.calls[0][1] == 300


@pytest.mark.asyncio
async def test_missing_websocat_is_a_plain_install_hint():
    proc = _FakeProc([], stderr_chunks=[b"timeout: failed to run command 'websocat': No such file"], returncode=125)
    with (
        patch(f"{AH}._get_connector", return_value=_MockConnector(_node_payload())),
        patch(f"{CE}._spawn", _SpawnRecorder(proc)),
    ):
        result = await console_exec(
            "11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222", "x", 3, gns3_ctx=_ctx()
        )
    assert "websocat is not installed" in result
    assert "install" in result


@pytest.mark.asyncio
async def test_silent_console_reports_the_window():
    proc = _FakeProc([], returncode=124)
    with (
        patch(f"{AH}._get_connector", return_value=_MockConnector(_node_payload())),
        patch(f"{CE}._spawn", _SpawnRecorder(proc)),
    ):
        result = await console_exec(
            "11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222", "x", 8, gns3_ctx=_ctx()
        )
    assert "no console output within 8s" in result
    assert "larger timeout" in result


@pytest.mark.asyncio
async def test_node_not_started_is_rejected_before_spawning():
    recorder = _SpawnRecorder()
    with (
        patch(f"{AH}._get_connector", return_value=_MockConnector(_node_payload(status="stopped"))),
        patch(f"{CE}._spawn", recorder),
    ):
        result = await console_exec(
            "11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222", "x", 3, gns3_ctx=_ctx()
        )
    assert "stopped" in result
    assert recorder.calls == []


@pytest.mark.asyncio
async def test_vnc_console_has_no_text_channel():
    with (
        patch(f"{AH}._get_connector", return_value=_MockConnector(_node_payload(console_type="vnc"))),
        patch(f"{CE}._spawn", _SpawnRecorder()),
    ):
        result = await console_exec(
            "11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222", "x", 3, gns3_ctx=_ctx()
        )
    assert "VNC" in result


@pytest.mark.asyncio
async def test_project_and_node_names_resolve_to_uuids():
    projects = [{"project_id": "p-uuid-1", "name": "ospf-lab"}]
    nodes = [{"node_id": "n-uuid-1", "name": "R1"}]
    connector = _RoutingConnector(projects, nodes, _node_payload())
    proc = _FakeProc([b"R1# \r\n"])
    with (
        patch(f"{AH}._get_connector", return_value=connector),
        patch(f"{PROJECTS}._get_connector", return_value=connector),
        patch(f"{CE}._spawn", _SpawnRecorder(proc)),
    ):
        result = await console_exec("ospf-lab", "R1", "show version", 3, gns3_ctx=_ctx())
    assert "R1#" in result


@pytest.mark.asyncio
async def test_unknown_node_name_lists_known_names():
    projects = [{"project_id": "p-uuid-1", "name": "ospf-lab"}]
    nodes = [{"node_id": "n-uuid-1", "name": "R1"}]
    connector = _RoutingConnector(projects, nodes, _node_payload())
    with (
        patch(f"{AH}._get_connector", return_value=connector),
        patch(f"{PROJECTS}._get_connector", return_value=connector),
        patch(f"{CE}._spawn", _SpawnRecorder()),
    ):
        result = await console_exec("ospf-lab", "ghost", "x", 3, gns3_ctx=_ctx())
    assert "Node 'ghost' not found" in result
    assert "R1" in result  # known names come back with the failure


@pytest.mark.asyncio
async def test_regrep_filters_the_cache_without_a_new_session():
    lines = [f"R1# line {i}" for i in range(6)]
    proc = _FakeProc(["\n".join(lines).encode()])
    recorder = _SpawnRecorder(proc)
    with (
        patch(f"{AH}._get_connector", return_value=_MockConnector(_node_payload())),
        patch(f"{CE}._spawn", recorder),
    ):
        first = await console_exec(
            "11111111-1111-1111-1111-111111111111",
            "22222222-2222-2222-2222-222222222222",
            "show thing",
            3,
            gns3_ctx=_ctx(),
        )
        assert "line 3" in first
        # second look: no re-run, no second spawn
        second = await console_exec(
            "11111111-1111-1111-1111-111111111111",
            "22222222-2222-2222-2222-222222222222",
            "",
            3,
            grep="line [3-4]$",
            regrep=True,
            gns3_ctx=_ctx(),
        )
    assert "line 3" in second and "line 4" in second
    assert "line 0" not in second
    assert len(recorder.calls) == 1


@pytest.mark.asyncio
async def test_regrep_without_cache_says_so():
    with (
        patch(f"{AH}._get_connector", return_value=_MockConnector(_node_payload())),
        patch(f"{CE}._spawn", _SpawnRecorder()),
    ):
        result = await console_exec(
            "11111111-1111-1111-1111-111111111111",
            "22222222-2222-2222-2222-222222222222",
            "",
            3,
            grep="x",
            regrep=True,
            gns3_ctx=_ctx(),
        )
    assert "no captured output" in result


@pytest.mark.asyncio
async def test_long_output_writes_capture_file_and_mints_path_ticket():
    text = "\n".join(f"line {i}" for i in range(60)) + "\n"
    proc = _FakeProc([text.encode()])
    connector = _MockConnector(_node_payload())
    with (
        patch(f"{AH}._get_connector", return_value=connector),
        patch(f"{CE}._spawn", _SpawnRecorder(proc)),
    ):
        result = await console_exec(
            "11111111-1111-1111-1111-111111111111",
            "22222222-2222-2222-2222-222222222222",
            "show tech",
            5,
            gns3_ctx=_ctx(),
        )

    assert "60 lines total" in result
    assert "regrep=true" in result and "full=true" in result
    assert (
        "curl -o console-capture.txt "
        "'http://127.0.0.1:3080/v3/projects/p-uuid-1/nodes/n-uuid-1/files/console-capture.txt?token=gns3t_" in result
    )
    # the full raw capture was pushed through the node files API
    posts = [(m, u) for m, u, _ in connector.calls if m == "post"]
    assert posts == [("post", "http://127.0.0.1:3080/v3/projects/p-uuid-1/nodes/n-uuid-1/files/console-capture.txt")]
    # the embedded ticket redeems for exactly that path
    from gns3server.services import access_ticket_service

    url = result.split("curl -o console-capture.txt '")[1].split("'")[0]
    ticket = url.split("token=")[1]
    redeemed = access_ticket_service.redeem_for_path(
        ticket, "/v3/projects/p-uuid-1/nodes/n-uuid-1/files/console-capture.txt"
    )
    assert redeemed is not None and redeemed.username == "admin"
    # the ticket is path-bound: it must not open anything else
    assert (
        access_ticket_service.redeem_for_path(ticket, "/v3/projects/p-uuid-1/nodes/other/files/console-capture.txt")
        is None
    )


@pytest.mark.asyncio
async def test_short_output_does_not_write_a_capture_file():
    proc = _FakeProc([b"R1# ok\r\n"])
    connector = _MockConnector(_node_payload())
    with (
        patch(f"{AH}._get_connector", return_value=connector),
        patch(f"{CE}._spawn", _SpawnRecorder(proc)),
    ):
        await console_exec(
            "11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222", "x", 3, gns3_ctx=_ctx()
        )
    assert [m for m, _, _ in connector.calls if m == "post"] == []


@pytest.mark.asyncio
async def test_grep_hit_on_long_output_returns_only_matches():
    # filtered view fits the direct budget: no funnel, no capture file write
    text = "\n".join(f"row {i} keep" if i % 10 == 0 else f"row {i}" for i in range(200)) + "\n"
    proc = _FakeProc([text.encode()])
    connector = _MockConnector(_node_payload())
    with (
        patch(f"{AH}._get_connector", return_value=connector),
        patch(f"{CE}._spawn", _SpawnRecorder(proc)),
    ):
        result = await console_exec(
            "11111111-1111-1111-1111-111111111111",
            "22222222-2222-2222-2222-222222222222",
            "show big",
            5,
            grep=" keep$",
            gns3_ctx=_ctx(),
        )
    assert result.count("keep") == 20  # exactly the matching lines, none of the noise
    assert [m for m, _, _ in connector.calls if m == "post"] == []


# ── integration: the real websocat binary ───────────────────────────────


@contextlib.asynccontextmanager
async def _serve_console(received, replies):
    """aiohttp WS server behaving like a console: banner on connect (BINARY,
    the way the compute side ships it), reply per received line."""

    from aiohttp import WSMsgType, web

    async def handler(request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        await ws.send_bytes(b"Welcome to the console\r\n")
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                received.append(msg.data)
                await ws.send_bytes(replies.encode())
        return ws

    app = web.Application()
    app.router.add_get("/v3/projects/{project_id}/nodes/{node_id}/console/ws", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        await runner.cleanup()


@pytest.mark.asyncio
@pytest.mark.skipif(shutil.which("websocat") is None, reason="websocat is not installed")
async def test_real_websocat_session_end_to_end():
    received = []
    async with _serve_console(received, replies="R1# show version\r\nuptime 5m\r\n") as base:
        with patch(f"{AH}._get_connector", return_value=_MockConnector(_node_payload())):
            result = await console_exec(
                "11111111-1111-1111-1111-111111111111",
                "22222222-2222-2222-2222-222222222222",
                "show version",
                2,
                gns3_ctx=_ctx(base),
            )

    assert "uptime 5m" in result
    assert received == ["show version\r\n"]


@pytest.mark.asyncio
@pytest.mark.skipif(shutil.which("websocat") is None, reason="websocat is not installed")
async def test_real_websocat_stays_open_the_full_window():
    # --no-close: after stdin EOF the session keeps receiving until timeout
    received = []
    async with _serve_console(received, replies="ok\r\n") as base:
        with patch(f"{AH}._get_connector", return_value=_MockConnector(_node_payload())):
            started = time.monotonic()
            await console_exec(
                "11111111-1111-1111-1111-111111111111",
                "22222222-2222-2222-2222-222222222222",
                "x",
                2,
                gns3_ctx=_ctx(base),
            )
            elapsed = time.monotonic() - started

    assert elapsed >= 1.8  # it did not bail out after the echo ack
