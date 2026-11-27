"""Console capture, worker lifecycle, timeout cleanup and transport recovery."""

import asyncio
import logging
from unittest.mock import AsyncMock

import pytest

from gns3server.schemas.configurations import ConsoleCredentials
from gns3server.services.configurations.console import session_runner as console
from gns3server.services.configurations.console.platforms import get_platform
from gns3server.services.configurations.console.session_runner import run_console_session
from gns3server.services.configurations.shared.errors import ConfigurationError
from tests.support.configurations import (
    CONFIG,
    PANOS_CONFIG,
    PLATFORM_CASES,
    VENDORS,
    assert_interactive_console_available,
    serve_console,
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "driver,prompt,setting,error",
    [
        ("cisco_viptela", None, b"screen-width 256\r", b"syntax error: command rejected"),
    ],
)
async def test_a_rejected_terminal_setting_fails_before_capture(appliance, driver, prompt, setting, error):
    node, transcript = appliance
    if prompt:
        transcript.prompt = prompt
    original_write = transcript.write

    def write(data):
        if data == setting:
            transcript.commands.append(setting.rstrip(b"\r"))
            transcript.reader.feed_data(data + b"\n" + error + b"\r\n" + transcript.prompt)
        else:
            original_write(data)

    transcript.write = write
    with pytest.raises(ConfigurationError, match="console_not_ready"):
        await run_console_session(node, ConsoleCredentials(), device_type=driver, deadline=5)
    assert b"show running-config" not in transcript.commands


@pytest.mark.asyncio
async def test_real_worker_reuses_the_console_without_saves_or_secret_logging(appliance, caplog):
    node, transcript = appliance
    transcript.login = True
    proxy = node._configuration_console_proxy
    caplog.set_level(logging.DEBUG)
    credentials = ConsoleCredentials(username="admin", password="login-secret", enable_secret="enable-secret")
    read_commands = [b"terminal length 0", b"terminal width 511", b"show running-config"]

    assert await run_console_session(node, credentials, deadline=10) == CONFIG
    assert transcript.commands[-3:] == read_commands
    assert proxy._exclusive_console is None
    first_capture_end = len(transcript.commands)

    # The guest remains at the command prompt for the next lease.
    assert await run_console_session(node, credentials, deadline=10) == CONFIG
    assert transcript.commands[first_capture_end:] == [b"", *read_commands]
    assert node._configuration_console_proxy is proxy
    assert proxy._exclusive_console is None
    assert not proxy._console_recovery_required
    assert not any(
        command in (b"end", b"exit", b"write memory", b"copy running-config startup-config")
        for command in transcript.commands
    )
    assert all(secret not in caplog.text for secret in ("login-secret", "enable-secret", "private-banner"))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "content,code",
    [
        (b"version 15.9\ninvalid \xff\nend\n", "console_invalid_encoding"),
        (b"x" * (2 * 1024 * 1024 + 1), "console_output_limit"),
    ],
    ids=["invalid-encoding", "output-limit"],
)
async def test_worker_rejects_invalid_encoding_and_oversized_transcripts(appliance, content, code):
    node, transcript = appliance
    transcript.content = content
    with pytest.raises(ConfigurationError, match=code):
        await run_console_session(node, ConsoleCredentials(), deadline=10)
    assert node._configuration_console_proxy._exclusive_console is None
    assert node._configuration_console_proxy._console_recovery_required


@pytest.mark.asyncio
@pytest.mark.parametrize("driver,_parser,prompt,header,content,commands", PLATFORM_CASES)
async def test_platform_real_worker_preserves_config_and_uses_only_read_recipe(
    appliance, caplog, driver, _parser, prompt, header, content, commands
):
    node, transcript = appliance
    transcript.prompt = prompt
    transcript.capture_header = header
    transcript.content = content
    caplog.set_level(logging.DEBUG)
    assert await run_console_session(node, ConsoleCredentials(), device_type=driver, deadline=5) == content
    assert transcript.commands == [b"", *commands]
    assert not node._configuration_console_proxy._console_recovery_required
    assert "private-banner" not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("driver,prompt,content", VENDORS)
async def test_additional_vendor_real_worker_capture(appliance, driver, prompt, content):
    node, transcript = appliance
    transcript.prompt = prompt.encode()
    transcript.content = content.encode()
    transcript.capture_header = b""
    transcript.capture_command = get_platform(driver).capture_command.encode()
    assert await run_console_session(node, ConsoleCredentials(), device_type=driver, deadline=5) == content.encode()
    assert not node._configuration_console_proxy._console_recovery_required


@pytest.mark.asyncio
async def test_asa_startup_backup_uses_unmasked_command_with_paging(appliance):
    node, transcript = appliance
    transcript.content = b"ASA Version 9.19(1)\nhostname asa\ntunnel-group vpn ipsec-attributes\n ikev1 pre-shared-key private-secret\n: end\n"
    transcript.capture_command = b"more system:running-config"
    result = await run_console_session(node, ConsoleCredentials(), device_type="cisco_asa", backup=True, deadline=5)
    assert b"private-secret" in result
    assert b"more system:running-config" in transcript.commands
    assert b"terminal pager 0" not in transcript.commands


@pytest.mark.asyncio
@pytest.mark.parametrize("backup", [False, True])
async def test_viptela_export_and_backup_keep_cli_text(appliance, backup):
    content = (
        "system\n host-name             vsmart\n aaa\n  auth-order local radius tacacs\n !\n!\n"
        "vpn 512\n interface eth0\n  ip address 192.0.2.10/24\n  no shutdown\n !\n!\n"
    )
    node, transcript = appliance
    transcript.prompt = b"vsmart#"
    transcript.capture_header = b""
    transcript.content = content.encode()
    result = await run_console_session(
        node, ConsoleCredentials(), device_type="cisco_viptela", backup=backup, deadline=5
    )
    assert result == content.encode()
    assert b"show running-config" in transcript.commands
    assert all(b"display xml" not in command for command in transcript.commands)
    assert get_platform("cisco_viptela").filename == "running-config.cfg"


@pytest.mark.asyncio
async def test_panos_export_is_the_config_document_without_the_cli_envelope(appliance):
    node, transcript = appliance
    transcript.prompt = b"admin@PA-VM> "
    transcript.capture_command = b"show config running"
    transcript.capture_header = b"\r\nadmin@PA-VM> \r\n"
    transcript.content = f'<response status="success"><result>{PANOS_CONFIG}</result></response>\n'.encode()
    result = await run_console_session(node, ConsoleCredentials(), device_type="paloalto_panos", deadline=5)
    assert result == ('<?xml version="1.0"?>\n' + PANOS_CONFIG + "\n").encode()
    assert transcript.commands[-4:] == [
        b"set cli pager off",
        b"set cli scripting-mode on",
        b"set cli op-command-xml-output on",
        b"show config running",
    ]
    assert get_platform("paloalto_panos_telnet").filename == "running-config.xml"


EOS_CONFIG = (
    "! Command: show running-config\n! device: localhost (vEOS-lab, EOS-4.37.0F)\n!\n"
    "no aaa root\n!\ninterface Ethernet1\n   description to-core\n!\nend\n"
)


@pytest.mark.asyncio
async def test_eos_export_is_the_running_config_with_its_comment_header(appliance):
    node, transcript = appliance
    transcript.prompt = b"localhost#"
    transcript.capture_header = b""
    transcript.content = EOS_CONFIG.encode()
    result = await run_console_session(node, ConsoleCredentials(), device_type="arista_eos_telnet", deadline=5)
    assert result == EOS_CONFIG.encode()
    assert transcript.commands[-3:] == [b"terminal length 0", b"terminal width 511", b"show running-config"]
    assert get_platform("arista_eos").filename == "running-config.cfg"


JUNOS_CONFIG = (
    "## Last commit: 2026-11-24 22:03:21 UTC by root\nversion 23.2R1.13;\nsystem {\n    host-name vsrx;\n}\n"
    "interfaces {\n    fxp0 {\n        unit 0;\n    }\n}\n"
)
JUNOS_SHELL, JUNOS_CLI = b"root@:~ # ", b"root> "


def junos_console(transcript, start, *, cli_works=True):
    """A vSRX NG console that starts in the shell or in the CLI; ``cli`` moves it to the CLI when it works."""
    prompt = {"now": JUNOS_SHELL if start == "shell" else JUNOS_CLI}

    def respond(line):
        text = line.decode()
        if text == "cli" and cli_works:
            prompt["now"] = JUNOS_CLI
        if text == "show configuration | no-more":
            return line + b"\r\n" + JUNOS_CONFIG.replace("\n", "\r\n").encode() + b"\r\n" + prompt["now"]
        return line + b"\r\n" + prompt["now"]

    return serve_console(transcript, respond)


@pytest.mark.asyncio
@pytest.mark.parametrize("start", ["shell", "cli"])
async def test_junos_export_enters_the_cli_from_the_shell_and_keeps_the_config(appliance, start):
    node, transcript = appliance
    commands = junos_console(transcript, start)
    result = await run_console_session(node, ConsoleCredentials(), device_type="juniper_junos_telnet", deadline=5)
    assert result == JUNOS_CONFIG.encode()
    assert (b"cli" in commands) is (start == "shell")
    assert commands[-3:] == [b"set cli screen-length 0", b"set cli screen-width 0", b"show configuration | no-more"]
    assert get_platform("juniper_junos").filename == "running-config.cfg"


@pytest.mark.asyncio
async def test_junos_export_gives_up_when_cli_does_not_leave_the_shell(appliance):
    node, transcript = appliance
    junos_console(transcript, "shell", cli_works=False)
    with pytest.raises(ConfigurationError, match="console_not_ready"):
        await run_console_session(node, ConsoleCredentials(), device_type="juniper_junos", deadline=5)


@pytest.mark.asyncio
@pytest.mark.parametrize("driver", ["cisco_ios_telnet", "cisco_viptela"])
async def test_failed_capture_automatically_recreates_transport_without_reboot(recovering_appliance, driver):
    node, guest, transcripts, connected = recovering_appliance
    if driver == "cisco_viptela":
        guest.prompt = b"vsmart#"
        guest.content = b"system\n host-name             vsmart\n"
    old_proxy, instance, port = node._configuration_console_proxy, node._process, node.console
    connected.clear()
    with pytest.raises(ConfigurationError, match="configuration_capture_timeout"):
        await run_console_session(node, ConsoleCredentials(), device_type=driver, deadline=2)
    await asyncio.wait_for(connected.wait(), timeout=2)
    assert node._configuration_console_proxy is not old_proxy
    assert not node._configuration_console_proxy._console_recovery_required
    assert node._process is instance and node.status == "started" and node.console == port
    assert len(transcripts) == 2
    transcripts[0].reader.feed_data(b"late private configuration\r\n")
    received = await assert_interactive_console_available(node, guest.prompt)
    assert b"private" not in received


@pytest.mark.asyncio
@pytest.mark.parametrize("secret", ["", "wrong-password"])
async def test_asa_missing_or_rejected_enable_password_allows_manual_recovery_without_reset(appliance, secret):
    node, transcript = appliance
    transcript.prompt = b"ASAv>"
    original_write = transcript.write
    awaiting_password = False

    def write(data):
        nonlocal awaiting_password
        if data == b"enable\r":
            awaiting_password = True
            transcript.commands.append(b"enable")
            transcript.reader.feed_data(b"Password: ")
        elif awaiting_password:
            transcript.commands.append(data.rstrip(b"\r"))
            if data == b"correct-enable\r":
                awaiting_password = False
                transcript.prompt = b"ASAv#"
                transcript.reader.feed_data(b"\r\n" + transcript.prompt)
            else:
                transcript.reader.feed_data(b"\r\nInvalid password\r\nPassword: ")
        else:
            original_write(data)

    transcript.write = write
    proxy = node._configuration_console_proxy
    with pytest.raises(ConfigurationError, match="console_authentication_failed"):
        await run_console_session(node, ConsoleCredentials(enable_secret=secret), device_type="cisco_asa", deadline=5)
    assert transcript.commands == [b"", b"enable", secret.encode()]
    assert not proxy._console_recovery_required
    assert b"show running-config" not in transcript.commands
    await assert_interactive_console_available(node, b"ASAv#", b"correct-enable\r")
    assert node._configuration_console_proxy is proxy


@pytest.mark.asyncio
async def test_incomplete_output_times_out_without_partial_export_or_lingering_worker(appliance):
    node, transcript = appliance
    transcript.content = b"version 15.9\nhostname R1\n"
    with pytest.raises(ConfigurationError, match="configuration_capture_timeout"):
        await run_console_session(node, ConsoleCredentials(), deadline=2)
    assert node._configuration_console_proxy._exclusive_console is None
    with pytest.raises(ConfigurationError, match="console_recovery_required") as caught:
        await run_console_session(node, ConsoleCredentials())
    assert caught.value.previous_error == "configuration_capture_timeout"
    proxy = node._configuration_console_proxy
    transcript.reader.feed_data(b"late private configuration")
    port = proxy._server.get_port() if node.console_type == "ssh" else proxy._server.sockets[0].getsockname()[1]
    reader, client = await asyncio.open_connection("127.0.0.1", port)
    try:
        assert b"private" not in await asyncio.wait_for(reader.read(), timeout=2)
    finally:
        client.close()
        await client.wait_closed()


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel", [False, True])
async def test_startup_readiness_timeout_or_cancellation_does_not_take_console_ownership(
    appliance, monkeypatch, cancel
):
    node, transcript = appliance
    proxy = node._configuration_console_proxy
    proxy._console_readiness.clear()
    spawn = AsyncMock(wraps=console._spawn_worker)
    monkeypatch.setattr(console, "_spawn_worker", spawn)
    task = asyncio.create_task(
        run_console_session(
            node,
            ConsoleCredentials(),
            device_type="cisco_nxos",
            content="hostname saved\n",
            wait_ready=True,
            deadline=0.05,
        )
    )
    if cancel:
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    else:
        with pytest.raises(ConfigurationError, match="configuration_apply_timeout"):
            await task
    spawn.assert_not_called()
    assert proxy._exclusive_console is None
    assert not proxy._console_recovery_required
    assert not transcript.commands
    # The ordinary console path remains available; no reset or reboot is required.
    proxy._console_readiness.feed_data(b"R1#")
    await assert_interactive_console_available(node, transcript.prompt)
