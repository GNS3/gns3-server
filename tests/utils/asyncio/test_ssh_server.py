import asyncio
import contextlib

import asyncssh
import pytest

from gns3server.utils.asyncio.ssh_server import AsyncioSSHServer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class DummyUpstreamWriter:
    def __init__(self):
        self.buffer = bytearray()
        self.write_event = asyncio.Event()

    def write(self, data):
        self.buffer.extend(data)
        self.write_event.set()

    async def drain(self):
        await asyncio.sleep(0)


def _get_listen_port(listener):
    """Return the TCP port the asyncssh listener is bound to."""
    return listener.get_port()


async def _connect(port):
    """Open a bare asyncssh client connection (no auth required)."""
    return await asyncssh.connect(
        "127.0.0.1",
        port=port,
        username="gns3",
        known_hosts=None,
        encoding=None,
    )


async def _wait_for_session_count(server, expected_count, timeout=2):
    deadline = asyncio.get_running_loop().time() + timeout
    last_count = 0
    while asyncio.get_running_loop().time() < deadline:
        async with server._sessions_lock:
            last_count = len(server._sessions)
        if last_count == expected_count:
            return
        await asyncio.sleep(0.05)
    assert last_count == expected_count, (
        f"Expected {expected_count} sessions, got {last_count} after {timeout}s"
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ssh_server_forwards_client_input_to_upstream_writer():
    """Data typed by a connected SSH client must reach the upstream writer."""
    upstream_reader = asyncio.StreamReader()
    upstream_writer = DummyUpstreamWriter()
    server = AsyncioSSHServer(reader=upstream_reader, writer=upstream_writer)
    listener = await server.start("127.0.0.1", 0)
    port = _get_listen_port(listener)

    conn = None
    try:
        conn = await _connect(port)
        process = await conn.create_process(encoding=None, term_type="xterm")
        await _wait_for_session_count(server, 1)

        process.stdin.write(b"ping\n")
        await process.stdin.drain()

        await asyncio.wait_for(upstream_writer.write_event.wait(), timeout=2)
        assert b"ping\n" in bytes(upstream_writer.buffer)
    finally:
        if conn is not None:
            conn.close()
            with contextlib.suppress(Exception):
                await conn.wait_closed()
        listener.close()
        await listener.wait_closed()


@pytest.mark.asyncio
async def test_ssh_server_broadcasts_upstream_output_to_all_clients():
    """Data fed into the upstream reader must reach every connected client."""
    upstream_reader = asyncio.StreamReader()
    upstream_writer = DummyUpstreamWriter()
    server = AsyncioSSHServer(reader=upstream_reader, writer=upstream_writer)
    listener = await server.start("127.0.0.1", 0)
    port = _get_listen_port(listener)

    conn1 = conn2 = None
    proc1 = proc2 = None
    try:
        conn1 = await _connect(port)
        proc1 = await conn1.create_process(encoding=None, term_type="xterm")

        conn2 = await _connect(port)
        proc2 = await conn2.create_process(encoding=None, term_type="xterm")

        await _wait_for_session_count(server, 2)

        upstream_reader.feed_data(b"hello")

        data1 = await asyncio.wait_for(proc1.stdout.read(5), timeout=2)
        data2 = await asyncio.wait_for(proc2.stdout.read(5), timeout=2)

        assert data1 == b"hello"
        assert data2 == b"hello"
    finally:
        for conn in (conn1, conn2):
            if conn is not None:
                conn.close()
                with contextlib.suppress(Exception):
                    await conn.wait_closed()
        listener.close()
        await listener.wait_closed()


@pytest.mark.asyncio
async def test_ssh_server_broadcast_survives_client_disconnect():
    """
    When one client disconnects mid-session the broadcast to the remaining
    client must continue without raising an exception.
    """
    upstream_reader = asyncio.StreamReader()
    upstream_writer = DummyUpstreamWriter()
    server = AsyncioSSHServer(reader=upstream_reader, writer=upstream_writer)
    listener = await server.start("127.0.0.1", 0)
    port = _get_listen_port(listener)

    conn1 = conn2 = None
    proc2 = None
    try:
        conn1 = await _connect(port)
        await conn1.create_process(encoding=None, term_type="xterm")

        conn2 = await _connect(port)
        proc2 = await conn2.create_process(encoding=None, term_type="xterm")

        await _wait_for_session_count(server, 2)

        # Disconnect the first client.
        conn1.close()
        with contextlib.suppress(Exception):
            await conn1.wait_closed()
        conn1 = None

        await _wait_for_session_count(server, 1)

        # The second client should still receive data.
        upstream_reader.feed_data(b"ok")
        data2 = await asyncio.wait_for(proc2.stdout.read(2), timeout=2)

        assert data2 == b"ok"
        async with server._sessions_lock:
            assert len(server._sessions) <= 1
    finally:
        if conn1 is not None:
            conn1.close()
            with contextlib.suppress(Exception):
                await conn1.wait_closed()
        if conn2 is not None:
            conn2.close()
            with contextlib.suppress(Exception):
                await conn2.wait_closed()
        listener.close()
        await listener.wait_closed()


@pytest.mark.asyncio
async def test_ssh_server_listener_close_cleans_internal_tasks():
    """
    Calling close()/wait_closed() on the _ManagedSSHListener must cancel the
    broadcast task and shut down the underlying asyncssh server.
    """
    upstream_reader = asyncio.StreamReader()
    upstream_writer = DummyUpstreamWriter()
    server = AsyncioSSHServer(reader=upstream_reader, writer=upstream_writer)
    listener = await server.start("127.0.0.1", 0)

    assert server._broadcast_task is not None
    assert not server._broadcast_task.done()

    listener.close()
    await listener.wait_closed()

    assert server._broadcast_task is None
    assert server._server is None


@pytest.mark.asyncio
async def test_ssh_server_multiple_clients_input_all_reach_upstream():
    """
    Input from several concurrent clients must all be forwarded to the single
    upstream writer (order may vary, but nothing should be lost under low
    concurrency).
    """
    upstream_reader = asyncio.StreamReader()
    upstream_writer = DummyUpstreamWriter()
    server = AsyncioSSHServer(reader=upstream_reader, writer=upstream_writer)
    listener = await server.start("127.0.0.1", 0)
    port = _get_listen_port(listener)

    conns = []
    try:
        for _ in range(3):
            conn = await _connect(port)
            proc = await conn.create_process(encoding=None, term_type="xterm")
            conns.append((conn, proc))

        await _wait_for_session_count(server, 3)

        for i, (_, proc) in enumerate(conns):
            proc.stdin.write(f"msg{i}\n".encode())
            await proc.stdin.drain()

        # Allow all writes to propagate.
        await asyncio.sleep(0.3)

        received = bytes(upstream_writer.buffer)
        for i in range(3):
            assert f"msg{i}\n".encode() in received
    finally:
        for conn, _ in conns:
            conn.close()
            with contextlib.suppress(Exception):
                await conn.wait_closed()
        listener.close()
        await listener.wait_closed()


@pytest.mark.asyncio
async def test_ssh_server_no_upstream_reader_no_broadcast_task():
    """
    When constructed with reader=None the broadcast task must not be created,
    but client connections should still be accepted and their input discarded
    without error.
    """
    upstream_writer = DummyUpstreamWriter()
    server = AsyncioSSHServer(reader=None, writer=upstream_writer)
    listener = await server.start("127.0.0.1", 0)
    port = _get_listen_port(listener)

    assert server._broadcast_task is None

    conn = None
    try:
        conn = await _connect(port)
        proc = await conn.create_process(encoding=None, term_type="xterm")
        await _wait_for_session_count(server, 1)

        # Input should be forwarded to the writer even without a reader.
        proc.stdin.write(b"data\n")
        await proc.stdin.drain()

        await asyncio.wait_for(upstream_writer.write_event.wait(), timeout=2)
        assert b"data\n" in bytes(upstream_writer.buffer)
    finally:
        if conn is not None:
            conn.close()
            with contextlib.suppress(Exception):
                await conn.wait_closed()
        listener.close()
        await listener.wait_closed()
