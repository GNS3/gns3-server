"""Console fixtures for managed Telnet/SSH proxies and recovery."""

import asyncio
from types import MethodType, SimpleNamespace

import pytest
import pytest_asyncio

from gns3server.compute.base_node import BaseNode
from gns3server.utils.asyncio.ssh_server import AsyncioSSHServer
from gns3server.utils.asyncio.telnet_server import AsyncioTelnetServer
from tests.support.configurations import ApplianceTranscript
from tests.support.configurations.fixtures import scripted_session as scripted_session


@pytest.fixture(params=["telnet", "ssh"])
def console_type(request):
    return request.param


@pytest_asyncio.fixture
async def appliance(console_type):
    upstream = asyncio.StreamReader()
    transcript = ApplianceTranscript(upstream)
    proxy = (
        AsyncioTelnetServer(reader=upstream, writer=transcript, keepalive_interval=0)
        if console_type == "telnet"
        else AsyncioSSHServer(reader=upstream, writer=transcript)
    )
    listener = await proxy.start("127.0.0.1", 0)
    node = SimpleNamespace(
        status="started", console_type=console_type, _configuration_console_proxy=proxy, _process=object()
    )
    proxy._console_readiness.feed_data(b"R1#")
    try:
        yield node, transcript
    finally:
        listener.close()
        await listener.wait_closed()


@pytest_asyncio.fixture
async def recovering_appliance(console_type):
    """Real BaseNode transport reset around a persistent simulated guest."""
    guest = SimpleNamespace(prompt=b"R1#", content=b"version 15.9\nhostname R1\n", header=b"", respond=True)
    transcripts = []
    connections = set()
    connected = asyncio.Event()

    async def accept(reader, writer):
        task = asyncio.current_task()
        connections.add(task)
        output = asyncio.StreamReader()
        transcript = ApplianceTranscript(output)
        transcripts.append(transcript)
        connected.set()

        async def send_output():
            while data := await output.read(65536):
                writer.write(data)
                await writer.drain()

        sending = asyncio.create_task(send_output())
        try:
            if console_type == "telnet":
                assert await reader.readexactly(3) == b"\xff\xfb\x01"
            while data := await reader.read(1024):
                transcript.prompt = guest.prompt
                transcript.content = guest.content
                transcript.capture_header = guest.header
                if guest.respond and data:
                    transcript.write(data)
        finally:
            sending.cancel()
            await asyncio.gather(sending, return_exceptions=True)
            writer.close()
            await writer.wait_closed()
            connections.discard(task)

    upstream = await asyncio.start_server(accept, "127.0.0.1", 0)
    node = SimpleNamespace(
        status="started",
        console=0,
        console_type=console_type,
        _console_type=console_type,
        _manager=SimpleNamespace(port_manager=SimpleNamespace(console_host="127.0.0.1")),
        _internal_console_port=upstream.sockets[0].getsockname()[1],
        _wrap_console=True,
        _wrap_aux=False,
        _wrapper_telnet_servers=[],
        _wrap_console_writers=[],
        _configuration_console_proxy=None,
        _process=object(),
    )
    methods = (
        "_wrap_console_proxy",
        "_internal_console_host",
        "start_wrap_console",
        "stop_wrap_console",
        "reset_wrap_console",
    )
    for name in methods:
        setattr(node, name, MethodType(getattr(BaseNode, name), node))
    node.reset_console = node.reset_wrap_console
    await node.start_wrap_console()
    await connected.wait()
    proxy = node._configuration_console_proxy
    node.console = proxy._server.get_port() if console_type == "ssh" else proxy._server.sockets[0].getsockname()[1]
    try:
        yield node, guest, transcripts, connected
    finally:
        await node.stop_wrap_console()
        upstream.close()
        await upstream.wait_closed()
        for task in tuple(connections):
            task.cancel()
        await asyncio.gather(*connections, return_exceptions=True)
