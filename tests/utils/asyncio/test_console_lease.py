import asyncio
from types import SimpleNamespace

import asyncssh
import pytest
import telnetlib3

from gns3server.compute.base_node import BaseNode
from gns3server.utils.asyncio.console_lease import ConsoleLeaseError
from gns3server.utils.asyncio.ssh_server import AsyncioSSHServer
from gns3server.utils.asyncio.telnet_server import AsyncioTelnetServer

pytestmark = pytest.mark.asyncio


class DummyUpstreamWriter:
    def __init__(self):
        self.buffer = bytearray()

    def write(self, data):
        self.buffer.extend(data)

    async def drain(self):
        await asyncio.sleep(0)


async def test_lease_refuses_an_existing_client_including_pending_telnet_negotiation():
    server = AsyncioTelnetServer(reader=asyncio.StreamReader(), writer=DummyUpstreamWriter(), keepalive_interval=0)
    listener = await server.start("127.0.0.1", 0)
    reader, writer = await asyncio.open_connection("127.0.0.1", listener.sockets[0].getsockname()[1])
    try:
        await asyncio.wait_for(reader.read(1), timeout=2)
        assert server._protocol_clients
        with pytest.raises(ConsoleLeaseError, match="console_busy"):
            async with server.lease_console():
                pytest.fail("A pending interactive client owns the console")
        assert not writer.is_closing()
    finally:
        writer.close()
        await writer.wait_closed()
        listener.close()
        await listener.wait_closed()


async def test_lease_blocks_external_input_and_output_and_restores_normal_console():
    upstream = asyncio.StreamReader()
    writer = DummyUpstreamWriter()
    server = AsyncioTelnetServer(reader=upstream, writer=writer, keepalive_interval=0)
    connected = asyncio.Event()

    async def client_connected():
        connected.set()

    server.client_connected_hook = client_connected
    listener = await server.start("127.0.0.1", 0)
    port = listener.sockets[0].getsockname()[1]
    try:
        async with server.lease_console() as lease:
            reader, client = await asyncio.open_connection("127.0.0.1", port)
            try:
                data = await asyncio.wait_for(reader.read(), timeout=2)
                assert b"private" not in data
                lease.write(b"read-only-command\r")
                await lease.drain()
                upstream.feed_data(b"private configuration")
                assert await asyncio.wait_for(lease.reader.readexactly(21), timeout=2) == b"private configuration"
                assert bytes(writer.buffer) == b"read-only-command\r"
                with pytest.raises(ConsoleLeaseError, match="console_busy"):
                    async with server.lease_console():
                        pytest.fail("Only one automation owner is permitted")
            finally:
                client.close()
                await client.wait_closed()
        with pytest.raises(ConsoleLeaseError, match="console_lease_closed"):
            lease.write(b"late command")
        reader, client = await telnetlib3.open_connection("127.0.0.1", port, encoding=False)
        try:
            await asyncio.wait_for(connected.wait(), timeout=2)
            assert server._connections
            upstream.feed_data(b"normal")
            assert await asyncio.wait_for(reader.read(6), timeout=2) == b"normal"
        finally:
            client.close()
    finally:
        listener.close()
        await listener.wait_closed()


async def test_lease_output_limit_cancellation_and_shutdown():
    upstream = asyncio.StreamReader()
    server = AsyncioTelnetServer(reader=upstream, writer=DummyUpstreamWriter(), keepalive_interval=0)
    listener = await server.start("127.0.0.1", 0)
    try:
        with pytest.raises(ConsoleLeaseError, match="console_output_limit"):
            async with server.lease_console(max_bytes=4) as lease:
                upstream.feed_data(b"too much")
                await lease.reader.read()
        entered = asyncio.Event()

        async def hold():
            async with server.lease_console():
                entered.set()
                await asyncio.Event().wait()

        task = asyncio.create_task(hold())
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert server._exclusive_console is None
        async with server.lease_console() as lease:
            listener.close()
            await listener.wait_closed()
            assert await lease.reader.read() == b""
    finally:
        listener.close()
        await listener.wait_closed()


async def test_ssh_reservation_covers_handshake_clients_and_is_released_after_disconnect():
    server = AsyncioSSHServer(reader=asyncio.StreamReader(), writer=DummyUpstreamWriter())
    listener = await server.start("127.0.0.1", 0)
    reader, client = await asyncio.open_connection("127.0.0.1", listener.get_port())
    try:
        assert (await asyncio.wait_for(reader.readline(), timeout=2)).startswith(b"SSH-")
        with pytest.raises(ConsoleLeaseError, match="console_busy"):
            async with server.lease_console():
                pytest.fail("A negotiating SSH client owns the console")
        connection = next(iter(server._protocol_clients))
        client.close()
        await client.wait_closed()
        await asyncio.wait_for(connection.wait_closed(), timeout=2)
        async with server.lease_console():
            pass
    finally:
        client.close()
        listener.close()
        await listener.wait_closed()


async def test_ssh_lease_is_exclusive_and_normal_console_resumes_without_private_output():
    upstream = asyncio.StreamReader()
    writer = DummyUpstreamWriter()
    server = AsyncioSSHServer(reader=upstream, writer=writer)
    listener = await server.start("127.0.0.1", 0)
    try:
        async with server.lease_console() as lease:
            with pytest.raises((asyncssh.Error, OSError)):
                async with asyncssh.connect("127.0.0.1", port=listener.get_port(), known_hosts=None):
                    pytest.fail("An interactive client must not enter a reserved console")
            upstream.feed_data(b"private")
            assert await asyncio.wait_for(lease.reader.readexactly(7), timeout=2) == b"private"
            lease.write(b"show running-config\r")
            await lease.drain()
            assert bytes(writer.buffer) == b"show running-config\r"
            with pytest.raises(ConsoleLeaseError, match="console_busy"):
                async with server.lease_console():
                    pytest.fail("Two exports must not share a console")
        async with asyncssh.connect(
            "127.0.0.1", port=listener.get_port(), known_hosts=None, encoding=None
        ) as connection:
            process = await connection.create_process(encoding=None)
            upstream.feed_data(b"normal")
            assert await asyncio.wait_for(process.stdout.readexactly(6), timeout=2) == b"normal"
            with pytest.raises(ConsoleLeaseError, match="console_busy"):
                async with server.lease_console():
                    pytest.fail("A connected SSH client must remain in control")
    finally:
        listener.close()
        await listener.wait_closed()


@pytest.mark.parametrize("console_type", ["telnet", "ssh"])
async def test_cancelled_browser_bridge_releases_console_for_export(console_type):
    upstream = asyncio.StreamReader()
    proxy = (
        AsyncioTelnetServer(reader=upstream, writer=DummyUpstreamWriter(), keepalive_interval=0)
        if console_type == "telnet"
        else AsyncioSSHServer(reader=upstream, writer=DummyUpstreamWriter())
    )
    listener = await proxy.start("127.0.0.1", 0)
    port = listener.sockets[0].getsockname()[1] if console_type == "telnet" else listener.get_port()
    node = SimpleNamespace(
        status="started",
        name="ASAv",
        _console_type=console_type,
        console=port,
        _manager=SimpleNamespace(port_manager=SimpleNamespace(console_host="127.0.0.1")),
    )
    receiving, stopped = asyncio.Event(), asyncio.Event()

    class BrowserConsole:
        client = SimpleNamespace(host="127.0.0.1", port=12345)

        async def receive(self):
            receiving.set()
            try:
                await asyncio.Event().wait()
            finally:
                stopped.set()

        async def send_bytes(self, data):
            pass

    task = asyncio.create_task(BaseNode.start_websocket_console(node, BrowserConsole()))
    try:
        await asyncio.wait_for(receiving.wait(), timeout=3)
        with pytest.raises(ConsoleLeaseError, match="console_busy"):
            async with proxy.lease_console():
                pytest.fail("The active browser must retain its console")
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=3)
        assert stopped.is_set(), "The browser input forwarding task must be reaped"

        async def wait_disconnected():
            while proxy._protocol_clients or (proxy._connections if console_type == "telnet" else proxy._sessions):  # noqa: ASYNC110 - both protocol and shell teardown must finish
                await asyncio.sleep(0.01)

        await asyncio.wait_for(wait_disconnected(), timeout=3)
        async with proxy.lease_console():
            pass  # Export may reserve the console without a proxy reset.
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        listener.close()
        await listener.wait_closed()


async def test_passive_readiness_is_bounded_and_notified_on_close():
    from gns3server.utils.asyncio.console_lease import ConsoleReadiness

    observed = ConsoleReadiness()
    observed.feed_data(b"boot log" * 10000)
    assert len(observed.tail) == 2048
    task = asyncio.create_task(observed.wait_for(lambda text: text.endswith("login:"), 1))
    await asyncio.sleep(0)
    assert not task.done()
    observed.feed_data(b"\nNexus login:")
    await task
    observed.clear()
    task = asyncio.create_task(observed.wait_for(lambda text: text.endswith("login:"), 1))
    await asyncio.sleep(0)
    observed.close()
    with pytest.raises(ConsoleLeaseError, match="console_unavailable"):
        await task
    assert not observed.tail


async def test_passive_readiness_waits_for_a_settled_prompt():
    from gns3server.utils.asyncio.console_lease import ConsoleReadiness

    observed = ConsoleReadiness()
    observed.feed_data(b"Router#")
    task = asyncio.create_task(observed.wait_for(lambda text: text.endswith("#"), 2, settle_seconds=0.05))
    await asyncio.sleep(0.01)
    observed.feed_data(b" continuing boot\r\n")
    await asyncio.sleep(0.1)
    assert not task.done()
    observed.feed_data(b"Router#")
    await asyncio.wait_for(task, 1)


@pytest.mark.parametrize("console_type", ["telnet", "ssh"])
async def test_only_a_finished_lease_hands_its_final_prompt_to_readiness(console_type):
    upstream = asyncio.StreamReader()
    proxy = (
        AsyncioTelnetServer(reader=upstream, writer=DummyUpstreamWriter(), keepalive_interval=0)
        if console_type == "telnet"
        else AsyncioSSHServer(reader=upstream, writer=DummyUpstreamWriter())
    )
    listener = await proxy.start("127.0.0.1", 0)

    async def session(*chunks, fail=False):
        async with proxy.lease_console() as lease:
            for chunk in chunks:
                upstream.feed_data(chunk)
                await asyncio.wait_for(lease.reader.readexactly(len(chunk)), timeout=2)
            if fail:
                raise RuntimeError
        return proxy._console_readiness.tail

    try:
        assert await session(b"private\r\nR", b"1#") == b"R1#"
        with pytest.raises(RuntimeError):
            await session(b"R1(config)#", fail=True)
        assert proxy._console_readiness.tail == b""
    finally:
        listener.close()
        await listener.wait_closed()
