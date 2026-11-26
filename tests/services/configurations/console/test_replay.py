"""Replaying a saved text through the console: login, commands, errors, save and the recovery that follows."""

from types import SimpleNamespace

import pytest

from gns3server.schemas.configurations import ConsoleCredentials
from gns3server.services.configurations.console.replay import apply_line, cli_commands
from gns3server.services.configurations.console.session_runner import run_console_session
from gns3server.services.configurations.shared.errors import CaptureFailure, ConfigurationError
from tests.support.configurations import (
    CONFIG,
    VENDORS,
    serve_console,
)


@pytest.mark.asyncio
async def test_real_worker_applies_configuration_and_returns_to_exec(appliance):
    node, transcript = appliance
    transcript.prompt = b"old#"

    def respond(line):
        if line == b"configure terminal":
            transcript.prompt = b"old(config)#"
        elif line == b"hostname new":
            transcript.prompt = b"new(config)#"
        elif line == b"end":
            transcript.prompt = b"new#"
        return line + b"\r\n" + transcript.prompt

    commands = serve_console(transcript, respond)
    content = "version 15.9\nhostname new\ninterface Gi0/0\n description saved config\nend\n"
    assert await run_console_session(node, ConsoleCredentials(), content=content, deadline=5) == b"applied\n"
    assert commands == [
        b"",
        b"terminal length 0",
        b"terminal width 511",
        b"show version | include operating mode",
        b"configure terminal",
        b"hostname new",
        b"interface Gi0/0",
        b" description saved config",
        b"end",
        b"write memory",
    ]
    assert transcript.prompt == b"new#"
    assert not node._configuration_console_proxy._console_recovery_required


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "driver,prompt,content",
    [
        *(vendor for vendor in VENDORS if vendor[0] != "cisco_viptela"),  # captured, never restored
        ("cisco_nxos", "N9K#", "!Command: show running-config\nversion 9.3(12)\nhostname N9K\n"),
        ("cisco_asa", "asav#", "ASA Version 9.19(1)\nhostname asav\nbanner motd hello\n: end\n"),
        ("cisco_xr", "RP/0/RP0/CPU0:XR#", "!! IOS XR Configuration 7.9.2\nhostname XR\nend\n"),
    ],
)
async def test_real_worker_restores_each_platform_with_save_or_commit(appliance, driver, prompt, content):
    node, transcript = appliance
    transcript.prompt = prompt.encode()

    commands = serve_console(transcript, lambda line: _restore_response(line, transcript))
    result = await run_console_session(node, ConsoleCredentials(), device_type=driver, content=content, deadline=8)
    assert result == b"applied\n"
    expected = {
        "cisco_nxos": b"copy running-config startup-config",
        "cisco_asa": b"write memory",
        "cisco_xr": b"commit",
    }
    if driver in expected:
        assert expected[driver] in commands
    if driver == "mikrotik_routeros":
        assert b"/system identity set name=R1" in commands
    assert not node._configuration_console_proxy._console_recovery_required


IOS_XE_COMMANDS = (
    "service timestamps debug datetime msec",
    "service timestamps log datetime msec",
    "service password-encryption",
    "platform qfp utilization monitor load 80",
    "platform sslvpn use-pd",
    "platform console serial",
    "hostname c8000v-Controller",
)
IOS_XE_CONTENT = "\n".join(("!", "version 17.18", *IOS_XE_COMMANDS[:-1], "!", IOS_XE_COMMANDS[-1], "end", ""))


def ios_xe_exchanges(failed_command=None, failure_reply=None):
    """The controller-managed guest's command echoes, replies and prompts."""
    exec_prompt = "c8000v-Edge#"
    config_prompt = "c8000v-Edge(config)#"
    renamed_prompt = "c8000v-Controller(config)#"
    exchanges = [
        ("", exec_prompt),
        ("terminal length 0", exec_prompt),
        ("terminal width 511", exec_prompt),
        ("show version | include operating mode", f"Router operating mode: Controller-Managed\r\n{exec_prompt}"),
        ("config-transaction", config_prompt),
        *((command, config_prompt) for command in IOS_XE_COMMANDS[:-1]),
        (IOS_XE_COMMANDS[-1], renamed_prompt),
        ("commit", f"Commit complete.\r\n{renamed_prompt}"),
        ("end", "c8000v-Controller#"),
    ]
    if failed_command is not None:
        index = next(index for index, (command, _) in enumerate(exchanges) if command == failed_command)
        exchanges[index:] = [(failed_command, failure_reply)]
    return {command: f"{command}\r\n{reply}" for command, reply in exchanges}


@pytest.mark.parametrize("startup", [False, True], ids=["live", "startup"])
@pytest.mark.parametrize("fragmented", [False, True], ids=["whole", "fragmented"])
@pytest.mark.parametrize(
    "phase,failed_command,reply",
    [
        pytest.param(None, None, None, id="committed"),
        pytest.param(
            "enter", "config-transaction", "% Error: configuration is locked\r\nc8000v-Edge#", id="enter-rejected"
        ),
        pytest.param(
            "enter", "config-transaction", "Configuration mode is unavailable\r\nc8000v-Edge#", id="still-at-exec"
        ),
        pytest.param(
            "replay",
            IOS_XE_COMMANDS[0],
            "% Invalid input detected at '^' marker.\r\nc8000v-Edge(config)#",
            id="command-rejected",
        ),
        pytest.param("save", "commit", "% Error: commit failed\r\nc8000v-Controller(config)#", id="commit-rejected"),
        pytest.param("save", "commit", "No changes were saved\r\nc8000v-Controller(config)#", id="commit-unconfirmed"),
    ],
)
def test_ios_xe_controller_import_uses_transaction_and_confirms_commit(
    scripted_session, startup, fragmented, phase, failed_command, reply
):
    exchanges = ios_xe_exchanges(failed_command, reply)
    session = scripted_session(exchanges.values(), content=IOS_XE_CONTENT, wait_ready=startup, fragmented=fragmented)
    if phase is None:
        assert session.collect() == b"applied\n"
    else:
        with pytest.raises(CaptureFailure, match="configuration_apply_failed") as raised:
            session.collect()
        context = raised.value.context
        assert context["phase"] == phase
        assert context["command"] == failed_command
        if phase == "replay":
            assert context["command_index"] == 1
            assert context["command_total"] == len(IOS_XE_COMMANDS)
    assert [call.args[0] for call in session.connection.write.call_args_list] == [
        (command + "\r").encode() for command in exchanges
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("committed", [True, False], ids=["startup-success", "live-unconfirmed"])
async def test_ios_xe_controller_transaction_through_real_worker(appliance, committed):
    node, transcript = appliance
    transcript.prompt = b"c8000v-Edge#"
    exchanges = (
        ios_xe_exchanges()
        if committed
        else ios_xe_exchanges("commit", "No changes were saved\r\nc8000v-Controller(config)#")
    )
    replies = {command.encode(): reply.encode() for command, reply in exchanges.items()}
    commands = serve_console(transcript, replies.__getitem__)
    options = dict(content=IOS_XE_CONTENT, wait_ready=committed, deadline=8)
    if committed:
        assert await run_console_session(node, ConsoleCredentials(), **options) == b"applied\n"
        assert not node._configuration_console_proxy._console_recovery_required
    else:
        with pytest.raises(ConfigurationError, match="configuration_apply_failed") as raised:
            await run_console_session(node, ConsoleCredentials(), **options)
        assert raised.value.context == {"phase": "save", "command": "commit", "device_error": "No changes were saved"}
    assert commands == list(replies)


@pytest.mark.asyncio
async def test_nexus_replay_failure_reports_command_index_without_configuration_text(appliance):
    node, transcript = appliance
    transcript.prompt = b"switch#"

    def respond(line):
        response = b""
        if line == b"configure terminal":
            transcript.prompt = b"switch(config)#"
        elif line.startswith(b"hostname "):
            transcript.prompt = b"restored(config)#"
        elif line == b"feature unsupported-feature":
            response = b"% Invalid command at '^' marker."
        return line + b"\r\n" + response + b"\r\n" + transcript.prompt

    commands = serve_console(transcript, respond)
    with pytest.raises(ConfigurationError, match="configuration_apply_failed") as caught:
        await run_console_session(
            node,
            ConsoleCredentials(),
            device_type="cisco_nxos",
            content="!Command: show running-config\nversion 9.3\nhostname restored\nfeature unsupported-feature\n",
            deadline=8,
        )
    assert caught.value.context == {
        "phase": "replay",
        "command_index": 2,
        "command_total": 2,
        "command": "feature unsupported-feature",
        "device_error": "% Invalid command at <masked> marker.",
    }
    assert "unsupported-feature" not in str(caught.value)
    assert b"copy running-config startup-config" not in commands


@pytest.mark.asyncio
async def test_save_then_capture_persists_before_capturing(appliance):
    node, transcript = appliance
    assert (
        await run_console_session(node, ConsoleCredentials(), device_type="cisco_ios", save=True, deadline=10) == CONFIG
    )
    assert transcript.commands[-2:] == [b"write memory", b"show running-config"]
    assert not node._configuration_console_proxy._console_recovery_required


@pytest.mark.asyncio
async def test_save_then_capture_refuses_platforms_without_a_declared_save(appliance):
    node, transcript = appliance
    with pytest.raises(ConfigurationError, match="configuration_save_unsupported"):
        await run_console_session(node, ConsoleCredentials(), device_type="cisco_xr", save=True, deadline=5)
    assert transcript.commands == []


def test_restore_keeps_banner_body_and_removes_display_headers():
    content = "! header\nASA Version 9.19(1)\nhostname fw\n: end\n"
    assert list(cli_commands(content, "cisco_asa")) == ["hostname fw"]
    content = "version 15.9\nbanner motd ^C\n! preserved\nR1#\nend\n^C\nhostname R1\nend\n"
    commands = list(cli_commands(content, "cisco_ios_telnet"))
    assert commands[0] == "banner motd %\n! preserved\nR1#\nend\n%"
    assert commands[-1] == "hostname R1"
    with pytest.raises(CaptureFailure, match="configuration_invalid_content"):
        list(cli_commands("banner motd ^C\ntruncated", "cisco_ios_telnet"))


def test_apply_does_not_interpret_echoed_banner_as_error_or_prompt(scripted_session):
    value = "banner motd %\nerror: maintenance\nR1#\n%"
    chunks = iter(["banner motd %\r\nerror: maintenance\r\nR1#", "\r\n%\r\n", "R1(config)#"])
    session = scripted_session(chunks)
    assert session.execute(value).endswith("R1(config)#")


def test_ios_certificate_is_imported_when_the_node_asks_for_the_data(scripted_session):
    session = scripted_session(
        [
            "certificate self-signed 01\r\nEnter the certificate in hexadecimal, type quit when done\r\nR1(config-pki-cert)#",
            "AABB\r\n",
            "quit\r\nR1(config)#",
        ]
    )
    apply_line(session, "certificate self-signed 01\nAABB\nquit")
    assert [call.args[0] for call in session.connection.write.call_args_list] == [
        b"certificate self-signed 01\r",
        b"AABB\r",
        b"quit\r",
    ]


def test_apply_still_rejects_device_errors_after_command_echo(scripted_session):
    chunks = iter(["unknown command\r\n% Invalid input\r\nR1(config)#"])
    session = scripted_session(chunks)
    with pytest.raises(CaptureFailure, match="configuration_apply_failed"):
        session.execute("unknown command")


def _restore_response(line, transcript):
    responses = {b"copy running-config startup-config": b"Copy complete"}
    if line == b"configure terminal":
        transcript.prompt = b"R1(config)#"
    elif line == b"end":
        transcript.prompt = b"R1#"
    return responses.get(line, line) + b"\r\n" + transcript.prompt


@pytest.mark.asyncio
async def test_routeros_save_then_capture_uses_automatic_persistence(appliance):
    node, transcript = appliance
    transcript.prompt = b"[admin@CHR] >"
    transcript.capture_command = b"/export terse"
    transcript.capture_header = b""
    transcript.content = b"# 2026-11-16 by RouterOS 7.24.6\n/system identity set name=CHR\n"
    result = await run_console_session(
        node, ConsoleCredentials(username="admin"), device_type="mikrotik_routeros", save=True, deadline=5
    )
    assert result == transcript.content
    assert b"write memory" not in transcript.commands
    assert transcript.commands[-1] == b"/export terse"


ROUTEROS_TEXT = "# 2026-11-16 by RouterOS 6.46.5\n{}"


def routeros_device(transcript, replies=None, prompt_for=None):
    """A RouterOS console: ``replies`` maps a command to its error line, ``prompt_for`` to a missing-value prompt."""
    transcript.prompt = b"[admin@CHR] >"

    def respond(line):
        if line == prompt_for:
            return line + b"\r\ninterface: "
        reply = (replies or {}).get(line)
        return line + b"\r\n" + (reply + b"\r\n" if reply else b"") + transcript.prompt

    return serve_console(
        transcript,
        respond,
        controls={b"\x03": lambda: b"\r\nScript Error: action cancelled\r\n" + transcript.prompt},
    )


@pytest.mark.asyncio
async def test_routeros_replay_skips_what_the_router_already_has_but_stops_on_other_errors(appliance):
    node, transcript = appliance
    commands = routeros_device(
        transcript,
        {
            b'/lora servers add name="TTN-EU"': b'failure: Server name "TTN-EU" already used',
            b"/ip address add address=10.0.0.1/24 interface=br0": b"failure: already have such address",
            b"/interface bridge set br9 name=x": b"failure: no such item (4)",
        },
    )
    content = ROUTEROS_TEXT.format(
        '/lora servers add name="TTN-EU"\n'
        "/ip address add address=10.0.0.1/24 interface=br0\n"
        "/system identity set name=CHR\n"
    )
    await run_console_session(node, ConsoleCredentials(), device_type="mikrotik_routeros", content=content, deadline=8)
    assert commands[-1] == b"/system identity set name=CHR"

    commands.clear()
    with pytest.raises(ConfigurationError, match="configuration_apply_failed") as caught:
        await run_console_session(
            node,
            ConsoleCredentials(),
            device_type="mikrotik_routeros",
            content=ROUTEROS_TEXT.format("/interface bridge set br9 name=x\n/system identity set name=CHR\n"),
            deadline=8,
        )
    assert caught.value.context["command_index"] == 1
    assert b"/system identity set name=CHR" not in commands


@pytest.mark.asyncio
async def test_routeros_replay_cancels_a_prompt_for_a_missing_value_and_names_the_command(appliance):
    node, transcript = appliance
    commands = routeros_device(transcript, prompt_for=b"/ip dhcp-client add disabled=no")
    with pytest.raises(ConfigurationError, match="configuration_apply_failed") as caught:
        await run_console_session(
            node,
            ConsoleCredentials(),
            device_type="mikrotik_routeros",
            content=ROUTEROS_TEXT.format("/ip dhcp-client add disabled=no\n/system identity set name=CHR\n"),
            deadline=8,
        )
    assert commands.count(b"\x03") == 1
    assert caught.value.context == {
        "phase": "replay",
        "command_index": 1,
        "command_total": 2,
        "command": "/ip dhcp-client add disabled=no",
        "device_error": "interface: a value is required",
    }
    assert b"/system identity set name=CHR" not in commands


@pytest.mark.parametrize(
    "version,command",
    [("6.46.5 (stable)", "/export terse"), ("7.11.2 (stable)", "/export terse show-sensitive")],
)
def test_routeros_backup_export_matches_the_version_flags(version, command):
    from gns3server.services.configurations.console.recipes.config_mikrotik import routeros_backup

    session = SimpleNamespace(execute=lambda *args, **kwargs: f"   uptime: 1m\n  version: {version}\n")
    assert routeros_backup(session, "[admin@CHR] >") == command
    with pytest.raises(CaptureFailure, match="device_version_unsupported"):
        routeros_backup(SimpleNamespace(execute=lambda *args, **kwargs: "no version here"), "[admin@CHR] >")


def routeros_resettable_device(transcript, asks_for_confirmation=True):
    """A RouterOS console that reboots to its login prompt when reset, then logs the user in again."""
    transcript.prompt = b"[admin@CHR] >"
    state = {"login_step": None}

    def respond(line):
        step = state["login_step"]
        if line.startswith(b"/system reset-configuration"):
            if asks_for_confirmation:
                return line + b"\r\nDangerous! Reset anyway? [y/N]: "
            state["login_step"] = 0
            return line + b"\r\nrebooting\r\nMikroTik Login: "
        if line == b"y" and step is None:
            state["login_step"] = 0
            return b"y\r\nrebooting\r\nMikroTik Login: "
        if step == 0 and line == b"":  # the probe before the username
            return b"\r\nMikroTik Login: "
        if step == 0:  # the username
            state["login_step"] = 1
            return line + b"\r\nPassword: "
        if step == 1:
            state["login_step"] = None
            return b"\r\n" + transcript.prompt
        return line + b"\r\n" + transcript.prompt

    return serve_console(transcript, respond)


FULL_EXPORT = "# nov/20/2026 22:28:32 by RouterOS 6.46.5\n# software id = X\n#\n/system identity set name=CHR\n"


@pytest.mark.asyncio
@pytest.mark.parametrize("asks_for_confirmation", [True, False])
async def test_routeros_startup_of_a_full_export_resets_to_an_empty_router_then_logs_in_and_replays(
    appliance, asks_for_confirmation
):
    node, transcript = appliance
    commands = routeros_resettable_device(transcript, asks_for_confirmation)
    await run_console_session(
        node,
        ConsoleCredentials(username="admin"),
        device_type="mikrotik_routeros",
        content=FULL_EXPORT,
        wait_ready=True,
        deadline=10,
    )
    reset = next(i for i, c in enumerate(commands) if c.startswith(b"/system reset-configuration no-defaults=yes"))
    login = next(i for i, c in enumerate(commands) if c.startswith(b"admin+"))
    replay = commands.index(b"/system identity set name=CHR")
    assert reset < login < replay
    assert (b"y" in commands) is asks_for_confirmation


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "content,wait_ready",
    [
        (FULL_EXPORT, False),  # an apply to a running node merges: nothing is reset
        ("/system identity set name=CHR\n", True),  # a short text merges into the defaults
    ],
    ids=["live_apply_of_a_full_export", "startup_of_a_short_text"],
)
async def test_routeros_only_resets_for_a_startup_apply_of_a_full_export(appliance, content, wait_ready):
    node, transcript = appliance
    commands = routeros_resettable_device(transcript)
    await run_console_session(
        node,
        ConsoleCredentials(username="admin"),
        device_type="mikrotik_routeros",
        content=content,
        wait_ready=wait_ready,
        deadline=10,
    )
    assert not any(command.startswith(b"/system reset-configuration") for command in commands)
    assert b"/system identity set name=CHR" in commands
