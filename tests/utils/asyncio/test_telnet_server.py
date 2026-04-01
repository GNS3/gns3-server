import asyncio
import contextlib

import pytest
import telnetlib3

from gns3server.utils.asyncio.telnet_server import AsyncioTelnetServer


class DummyUpstreamWriter:
    def __init__(self):
        self.buffer = bytearray()
        self.write_event = asyncio.Event()

    def write(self, data):
        self.buffer.extend(data)
        self.write_event.set()

    async def drain(self):
        await asyncio.sleep(0)


def _get_listen_port(server):
    return server.sockets[0].getsockname()[1]


async def _wait_for_connection_count(server, expected_count, timeout=2):
    deadline = asyncio.get_running_loop().time() + timeout
    last_count = 0
    while asyncio.get_running_loop().time() < deadline:
        async with server._connections_lock:
            last_count = len(server._connections)
        if last_count == expected_count:
            return
        await asyncio.sleep(0.05)
    assert last_count == expected_count


@pytest.mark.asyncio
async def test_telnet_server_forwards_client_input_to_upstream_writer():
    upstream_reader = asyncio.StreamReader()
    upstream_writer = DummyUpstreamWriter()
    server = AsyncioTelnetServer(reader=upstream_reader, writer=upstream_writer, binary=True, echo=True)
    listener = await server.start("127.0.0.1", 0)
    port = _get_listen_port(listener)

    client_writer = None
    try:
        _, client_writer = await telnetlib3.open_connection("127.0.0.1", port, encoding=False)
        await _wait_for_connection_count(server, 1)
        client_writer.write(b"ping\r\n")
        await client_writer.drain()

        await asyncio.wait_for(upstream_writer.write_event.wait(), timeout=2)
        assert b"ping\r\n" in bytes(upstream_writer.buffer)
    finally:
        if client_writer is not None:
            client_writer.close()
        listener.close()
        await listener.wait_closed()


@pytest.mark.asyncio
async def test_telnet_server_broadcasts_upstream_output_to_all_clients():
    upstream_reader = asyncio.StreamReader()
    upstream_writer = DummyUpstreamWriter()
    server = AsyncioTelnetServer(reader=upstream_reader, writer=upstream_writer, binary=True, echo=True)
    listener = await server.start("127.0.0.1", 0)
    port = _get_listen_port(listener)

    client1_reader = client1_writer = None
    client2_reader = client2_writer = None

    try:
        client1_reader, client1_writer = await telnetlib3.open_connection("127.0.0.1", port, encoding=False)
        client2_reader, client2_writer = await telnetlib3.open_connection("127.0.0.1", port, encoding=False)
        await _wait_for_connection_count(server, 2)

        upstream_reader.feed_data(b"hello")

        data1 = await asyncio.wait_for(client1_reader.read(5), timeout=2)
        data2 = await asyncio.wait_for(client2_reader.read(5), timeout=2)

        assert data1 == b"hello"
        assert data2 == b"hello"
    finally:
        if client1_writer is not None:
            client1_writer.close()
        if client2_writer is not None:
            client2_writer.close()
        listener.close()
        await listener.wait_closed()


@pytest.mark.asyncio
async def test_telnet_server_naws_callback_uses_negotiated_dimensions():
    callback_event = asyncio.Event()
    callback_result = {}

    async def window_size_changed(columns, rows):
        callback_result["columns"] = columns
        callback_result["rows"] = rows
        callback_event.set()

    server = AsyncioTelnetServer(
        binary=True,
        echo=True,
        naws=True,
        window_size_changed_callback=window_size_changed,
    )
    listener = await server.start("127.0.0.1", 0)
    port = _get_listen_port(listener)

    client_writer = None
    try:
        _, client_writer = await telnetlib3.open_connection(
            "127.0.0.1", port, encoding=False, cols=132, rows=44
        )

        await asyncio.wait_for(callback_event.wait(), timeout=2)
        assert callback_result == {"columns": 132, "rows": 44}
    finally:
        if client_writer is not None:
            client_writer.close()
        listener.close()
        await listener.wait_closed()


@pytest.mark.asyncio
async def test_telnet_server_broadcast_survives_client_disconnect():
    upstream_reader = asyncio.StreamReader()
    upstream_writer = DummyUpstreamWriter()
    server = AsyncioTelnetServer(reader=upstream_reader, writer=upstream_writer, binary=True, echo=True)
    listener = await server.start("127.0.0.1", 0)
    port = _get_listen_port(listener)

    client1_writer = None
    client2_reader = client2_writer = None

    try:
        _, client1_writer = await telnetlib3.open_connection("127.0.0.1", port, encoding=False)
        client2_reader, client2_writer = await telnetlib3.open_connection("127.0.0.1", port, encoding=False)
        await _wait_for_connection_count(server, 2)

        client1_writer.close()
        await _wait_for_connection_count(server, 1)

        upstream_reader.feed_data(b"ok")
        data2 = await asyncio.wait_for(client2_reader.read(2), timeout=2)

        assert data2 == b"ok"
        async with server._connections_lock:
            assert len(server._connections) <= 1
    finally:
        if client1_writer is not None:
            with contextlib.suppress(Exception):
                client1_writer.close()
        if client2_writer is not None:
            with contextlib.suppress(Exception):
                client2_writer.close()
        listener.close()
        await listener.wait_closed()


@pytest.mark.asyncio
async def test_telnet_server_listener_close_cleans_internal_tasks():
    upstream_reader = asyncio.StreamReader()
    upstream_writer = DummyUpstreamWriter()
    server = AsyncioTelnetServer(reader=upstream_reader, writer=upstream_writer, binary=True, echo=True)
    listener = await server.start("127.0.0.1", 0)

    assert server._broadcast_task is not None

    listener.close()
    await listener.wait_closed()

    assert server._broadcast_task is None
