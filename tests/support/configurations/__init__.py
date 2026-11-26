"""Shared builders, transcripts and fixtures for the startup configuration tests (not tests themselves)."""

import asyncio
import base64
from pathlib import Path
from queue import SimpleQueue
from threading import Barrier, Thread
from time import monotonic
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock
from uuid import UUID, uuid4

import asyncssh
import pytest
import telnetlib3

from gns3server.compute.iou.utils.iou_import import nvram_import
from gns3server.schemas.configurations import ExportFile, ExportResult
from gns3server.services.configurations.console.platforms import get_platform
from gns3server.services.configurations.shared.errors import ConfigurationError


def configuration_project(path, nodes=()):
    return SimpleNamespace(
        id=str(uuid4()),
        path=str(path),
        nodes={node_id: SimpleNamespace(name=name, node_type=node_type) for node_id, name, node_type in nodes},
    )


def startup_state_reply(state="clean", generation=1):
    """A node's ``get`` answering the controller's startup-state request."""
    return AsyncMock(return_value=SimpleNamespace(json={"version": 1, "generation": generation, "state": state}))


def qemu_disk_node(root, **fields):
    """A stopped QEMU node with a linked-clone disk layout under ``root`` (a shared base image beside it)."""
    root.mkdir(parents=True, exist_ok=True)
    base = root.parent / (root.name + "-base.qcow2")
    base.write_bytes(b"shared base image")
    values = {
        "working_dir": str(root),
        "status": "stopped",
        "linked_clone": True,
        "create_config_disk": False,
        "_hda_disk_image": str(base),
        "_hdb_disk_image": "",
        "_hdc_disk_image": "",
        "_hdd_disk_image": "",
    }
    return SimpleNamespace(**(values | fields))


def media_node(root, profile="cisco-c8000v-autonomous", **fields):
    """A ``qemu_disk_node`` that boots the media profile, with free drive slots."""
    values = {
        "id": str(uuid4()),
        "startup_media_profile": profile,
        "_hdc_disk_interface": "none",
        "_hdd_disk_interface": "none",
        "cdrom_image": "",
        "cdrom2_image": "",
        "cdrom_interface": "ide",
        "cdrom2_interface": "ide",
    }
    return qemu_disk_node(root, **(values | fields))


def export_result(node, engine, source, filename, content):
    """The compute's answer to an export of one file."""
    return ExportResult(
        project_id=UUID(node.project.id),
        node_id=UUID(node.id),
        engine=engine,
        source=source,
        files=(ExportFile(filename=filename, content=content),),
    )


def run_concurrent_writes(actions, *, timeout=10):
    """Start writers together and retry only optimistic conflicts within one deadline."""
    gate = Barrier(len(actions), timeout=timeout)
    errors = SimpleQueue()
    deadline = monotonic() + timeout

    def write(action):
        try:
            gate.wait()
            while monotonic() < deadline:
                try:
                    action()
                    return
                except ConfigurationError as error:
                    if error.code != "startup_configurations_changed":
                        raise
            raise TimeoutError("Configuration writer could not finish before the deadline")
        except Exception as error:
            errors.put(error)

    # A deadlock should fail the test rather than keep the test process alive.
    threads = [Thread(target=write, args=(action,), daemon=True) for action in actions]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(max(0, deadline - monotonic()))
    assert not any(thread.is_alive() for thread in threads), "Configuration writers did not finish before the deadline"
    if not errors.empty():
        raise errors.get_nowait()


def native_node(root, engine, identifier=1):
    root.mkdir(parents=True, exist_ok=True)
    node = SimpleNamespace(
        id=str(uuid4()),
        name=f"R{identifier}",
        project=SimpleNamespace(id=str(uuid4())),
        working_dir=str(root),
        status="stopped",
        nvram=64,
        _process=None,
        _iou_process=None,
        _nvram_watcher=None,
        _memory_watcher=None,
        is_running=Mock(return_value=False),
        use_default_iou_values=False,
        update_default_iou_values=AsyncMock(),
    )
    if engine == "iou":
        node.application_id = identifier
    else:
        node.dynamips_id = identifier
        node.platform = "c7200"
        node._hypervisor = object()
        node.startup_config_path = str(root / "configs" / f"i{identifier}_startup-config.cfg")
        node.private_config_path = str(root / "configs" / f"i{identifier}_private-config.cfg")
    return node


@pytest.fixture
def status_queries(monkeypatch):
    calls = []

    async def query(node, operation):
        calls.append((node.id, operation))
        assert operation == "get_status"
        return ["0" if node.status == "stopped" else "2"]

    monkeypatch.setattr("gns3server.compute.configurations.dynamips_query", query)
    return calls


def qemu_runtime_node(project, root, driver, console_type="telnet"):
    """A ``qemu_disk_node`` with a console recipe for the device type and a serial console."""
    return qemu_disk_node(
        root,
        id=str(uuid4()),
        project=project,
        node_type="qemu",
        properties={},
        locked=False,
        netmiko_device_type=driver,
        console_type=console_type,
        default_username="admin",
        default_password="test",
    )


def export_node(tmp_path, **kwargs):
    values = dict(
        id=str(uuid4()),
        name="R1",
        project=SimpleNamespace(id=str(uuid4())),
        working_dir=str(tmp_path),
        status="stopped",
        application_id=42,
        _cid=None,
        _volumes=[],
        extra_volumes=[],
        extra_configs=[],
        is_running=MagicMock(return_value=False),
        _hypervisor=object(),
        get_status=AsyncMock(return_value="inactive"),
        extract_config=AsyncMock(
            return_value=(base64.b64encode(b"hostname R1\r\nend\r\n"), base64.b64encode(b"secret\n"))
        ),
    )
    values.update(kwargs)
    return SimpleNamespace(**values)


def write_nvram(node, *, docker=False, startup=b"hostname R1\r\nend\r\n", private=b"private-secret\n"):
    root = Path(node.working_dir)
    path = root / ("tmp/run" if docker else "") / f"nvram_{node.application_id:05d}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(nvram_import(None, startup, private, 256))
    return path


VENDORS = [
    ("mikrotik_routeros", "[admin@MikroTik] >", "# oct/23/2026 by RouterOS 7.16\n/system identity set name=R1\n"),
    ("cisco_viptela", "vedge#", "system\n host-name             vedge\n!\n"),
]


QUESTION = "Would you like to enter the initial configuration dialog? [yes/no]:"


MENU = (
    "The following configuration command script was created:\r\n"
    "enable secret 9 $9$example\r\n!\r\nend\r\n\r\n"
    "[0] Go to the IOS command prompt without saving this config.\r\n"
    "[1] Return back to the setup without saving this config.\r\n"
    "[2] Save this configuration to nvram and exit.\r\n"
    "Enter your selection [2]:"
)


ios_configuration = get_platform("cisco_ios").parser


nxos_configuration = get_platform("cisco_nxos").parser


asa_configuration = get_platform("cisco_asa").parser


xr_configuration = get_platform("cisco_xr").parser


CONFIG = (
    b"!\nversion 15.9\nhostname R1\nbanner motd ^C\nend\nR1#\nprivate-banner\n^C\ninterface Gi0/0\n shutdown\nend\n"
)


PANOS_CONFIG = (
    '<config version="11.2.0" urldb="paloaltonetworks" detail-version="11.2.12">\n'
    '  <mgt-config>\n    <users>\n      <entry name="admin">\n        <phash>fnRL/G5lXVMug</phash>\n'
    "      </entry>\n    </users>\n  </mgt-config>\n</config>"
)


class ApplianceTranscript:
    def __init__(self, reader):
        self.reader = reader
        self.buffer = b""
        self.commands = []
        self.prompt = b"R1#"
        self.login = False
        self.username_prompt = b"Username:"
        self.login_prompt = b"R1>"
        self.step = 0
        self.content = CONFIG
        self.capture_command = b"show running-config"
        self.capture_header = b"Building configuration...\r\n\r\nCurrent configuration : 100 bytes\r\n\r\n"
        self.sent_capture = asyncio.Event()
        self.on_capture = None

    def write(self, data):
        self.buffer += data
        while b"\r" in self.buffer:
            command, self.buffer = self.buffer.split(b"\r", 1)
            self.commands.append(command)
            if self.login and self.step < 3:
                responses = (self.username_prompt, b"Password:", self.login_prompt)
                self.reader.feed_data(responses[self.step])
                self.step += 1
            elif command == b"enable":
                self.reader.feed_data(b"Password:")
            elif command == b"enable-secret":
                self.reader.feed_data(self.prompt)
            elif command == self.capture_command:
                self.sent_capture.set()
                if self.on_capture is not None:
                    self.on_capture()
                response = command + b"\r\n" + self.capture_header
                response += self.content.replace(b"\n", b"\r\n") + self.prompt
                size = 7 if len(response) < 1024 else len(response)
                for index in range(0, len(response), size):
                    self.reader.feed_data(response[index : index + size])
            else:
                self.reader.feed_data(command + b"\r\n" + self.prompt)

    async def drain(self):
        await asyncio.sleep(0)


def serve_console(transcript, respond, *, controls=None):
    """Replace the appliance's replies: ``respond(line)`` returns the bytes to feed back for each command line.

    ``controls`` maps a raw control byte (Ctrl-C, Ctrl-D), which carries no line ending, to the reply bytes.
    Returns the list of everything received, in order. ``respond`` may change ``transcript.prompt``.
    """
    received, buffer = [], b""

    def write(data):
        nonlocal buffer
        if controls and data in controls:
            received.append(data)
            transcript.reader.feed_data(controls[data]())
            return
        buffer += data
        while b"\r" in buffer:
            line, buffer = buffer.split(b"\r", 1)
            received.append(line)
            transcript.reader.feed_data(respond(line))

    transcript.write = write
    return received


async def assert_interactive_console_available(node, prompt, data=b"\r"):
    proxy = node._configuration_console_proxy
    if node.console_type == "ssh":
        async with asyncssh.connect(
            "127.0.0.1", port=proxy._server.get_port(), known_hosts=None, encoding=None
        ) as connection:
            process = await connection.create_process(encoding=None)
            process.stdin.write(data)
            result = await asyncio.wait_for(process.stdout.readuntil(prompt), timeout=3)
            assert prompt in result
            return result
    else:
        port = proxy._server.sockets[0].getsockname()[1]
        reader, writer = await telnetlib3.open_connection("127.0.0.1", port, encoding=False)
        try:
            writer.write(data)
            result = await asyncio.wait_for(reader.readuntil(prompt), timeout=3)
            assert prompt in result
            return result
        finally:
            writer.close()


PLATFORM_CASES = [
    (
        "cisco_nxos",
        nxos_configuration,
        b"N9K#",
        b"",
        b"!Command: show running-config\n!Time: Thu Oct 22 12:00:00 2026\nversion 9.3(12)\nhostname N9K\nbanner motd ^C\nend\nN9K#\nprivate-banner\n^C\ninterface Ethernet1/1\n  shutdown\n",
        [b"terminal length 0", b"terminal width 511", b"show running-config"],
    ),
    (
        "cisco_asa",
        asa_configuration,
        b"asav/context/act#",
        b": Saved\r\n:\r\n",
        b"ASA Version 9.18(4)\nhostname asav\nbanner motd : end\ninterface GigabitEthernet0/0\n shutdown\nCryptochecksum: 0123456789abcdef\n: end\n",
        [b"terminal pager 24", b"show running-config"],
    ),
    (
        "cisco_xr",
        xr_configuration,
        b"RP/0/RP0/CPU0:XR1#",
        b"Thu Oct 22 12:00:00 UTC\r\nBuilding configuration...\r\n",
        b"!! IOS XR Configuration 7.9.2\nhostname XR1\nbanner motd ^C\nend\nRP/0/RP0/CPU0:XR1#\nprivate-banner\n^C\ninterface GigabitEthernet0/0/0/0\n shutdown\n!\nend\n",
        [b"terminal length 0", b"terminal width 511", b"show running-config"],
    ),
]
