"""Console login, privilege changes and supported first-boot dialogs."""

import asyncio
import re

import pytest

from gns3server.schemas.configurations import CONSOLE_DEVICE_TYPES, ConsoleCredentials
from gns3server.services.configurations.console.session_runner import run_console_session
from gns3server.services.configurations.shared.errors import ConfigurationError
from tests.support.configurations import (
    CONFIG,
    MENU,
    PLATFORM_CASES,
    QUESTION,
    assert_interactive_console_available,
)


@pytest.mark.asyncio
async def test_cat9kv_first_boot_can_export_without_saving_setup_configuration(appliance):
    node, transcript = appliance
    transcript.prompt = b"Switch#"
    original_write = transcript.write
    state = {"step": 0, "secret": None}

    def write(data):
        command = data.rstrip(b"\r")
        step = state["step"]
        if step < 5:
            transcript.commands.append(command)
            if step == 0:
                assert command == b""
                response = QUESTION
            elif step == 1:
                assert command == b"no"
                response = "Enter enable secret:"
            elif step == 2:
                assert 10 <= len(command) <= 32
                state["secret"] = command
                response = "Confirm enable secret:"
            elif step == 3:
                assert command == state["secret"]
                response = MENU
            else:
                assert command == b"0"
                response = "Switch>"
            state["step"] += 1
            transcript.reader.feed_data(response.encode())
        elif command == b"enable":
            transcript.commands.append(command)
            transcript.reader.feed_data(b"Switch#")
        else:
            original_write(data)

    transcript.write = write
    result = await run_console_session(node, ConsoleCredentials(), deadline=10)
    assert result == CONFIG
    assert state["step"] == 5
    assert state["secret"] not in result
    assert b"show running-config" in transcript.commands
    assert b"write memory" not in transcript.commands
    assert b"configure terminal" not in transcript.commands


@pytest.mark.asyncio
async def test_missing_enable_secret_leaves_console_available_at_authentication_prompt(appliance):
    node, transcript = appliance
    transcript.login = True
    credentials = ConsoleCredentials(username="admin", password="login-secret")
    with pytest.raises(ConfigurationError, match="console_enable_secret_required"):
        await run_console_session(node, credentials, deadline=5)
    assert transcript.commands[-1] == b"enable"
    assert not node._configuration_console_proxy._console_recovery_required
    await assert_interactive_console_available(node, transcript.prompt, b"enable-secret\r")


@pytest.mark.asyncio
@pytest.mark.parametrize("driver", sorted(CONSOLE_DEVICE_TYPES - {"mikrotik_routeros"}))
async def test_missing_login_password_after_username_leaves_manual_login_available(appliance, driver):
    node, transcript = appliance
    transcript.login = True
    with pytest.raises(ConfigurationError, match="console_authentication_failed"):
        await run_console_session(node, ConsoleCredentials(username="admin"), device_type=driver, deadline=5)
    assert transcript.commands == [b"", b"admin"]
    assert not node._configuration_console_proxy._console_recovery_required
    await assert_interactive_console_available(node, transcript.login_prompt, b"login-secret\r")


@pytest.mark.asyncio
@pytest.mark.parametrize("prompt", [b"R1(config-if)#", b"c8000v(config-cert-chain)#"])
async def test_worker_refuses_unsafe_console_without_exit_or_setup_answers(appliance, prompt):
    node, transcript = appliance
    transcript.prompt = prompt
    with pytest.raises(ConfigurationError, match="console_unsafe_mode"):
        await run_console_session(node, ConsoleCredentials(), deadline=10)
    assert transcript.commands == [b""]
    proxy = node._configuration_console_proxy
    assert not proxy._console_recovery_required
    await assert_interactive_console_available(node, prompt)
    assert node._configuration_console_proxy is proxy


def test_credentials_reject_control_input_and_hide_values_in_repr():
    credentials = ConsoleCredentials(
        username="private-user", password="private-password", enable_secret="private-enable"
    )
    assert "private" not in repr(credentials)
    for key in ("username", "password", "enable_secret"):
        for value in ("line\nbreak", "escape\x1b", "x" * 257):
            with pytest.raises(ValueError):
                ConsoleCredentials(**{key: value})


@pytest.mark.asyncio
async def test_asa_allows_one_empty_enable_password_without_saving_configuration(appliance):
    node, transcript = appliance
    _, _, prompt, header, content, commands = PLATFORM_CASES[1]
    transcript.login = True
    transcript.prompt = prompt
    transcript.capture_header = header
    transcript.content = content
    credentials = ConsoleCredentials(username="admin", password="login-secret")
    assert await run_console_session(node, credentials, device_type="cisco_asa", deadline=5) == content
    assert transcript.commands == [b"", b"admin", b"login-secret", b"enable", b"", *commands]


@pytest.mark.asyncio
@pytest.mark.parametrize("driver", ["cisco_nxos", "cisco_xr"])
async def test_role_based_platforms_never_try_enable(appliance, driver):
    node, transcript = appliance
    transcript.prompt = b"restricted>"
    with pytest.raises(ConfigurationError, match="console_not_ready"):
        await run_console_session(node, ConsoleCredentials(), device_type=driver, deadline=5)
    assert transcript.commands == [b""]


@pytest.mark.asyncio
async def test_nxos_hostname_prefixed_login_uses_guest_credentials_without_enable(appliance):
    node, transcript = appliance
    driver, _, prompt, header, content, commands = PLATFORM_CASES[0]
    transcript.login = True
    transcript.username_prompt = b"N9K login:"
    transcript.login_prompt = prompt
    transcript.prompt = prompt
    transcript.capture_header = header
    transcript.content = content
    credentials = ConsoleCredentials(username="admin", password="login-secret")
    assert await run_console_session(node, credentials, device_type=driver, deadline=5) == content
    assert transcript.commands == [b"", b"admin", b"login-secret", *commands]


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["vmanage", "vbond", "vsmart"])
@pytest.mark.parametrize("suffix", ["#", "@#"])
async def test_viptela_login_and_capture_use_valid_terminal_settings(appliance, role, suffix):
    node, transcript = appliance
    transcript.prompt = f"{role}{suffix}".encode()
    transcript.login = True
    transcript.username_prompt = f"{role} login:".encode()
    transcript.login_prompt = transcript.prompt
    transcript.capture_header = b""
    transcript.content = f"system\n host-name             {role}\n!\n".encode() * 40
    original_write = transcript.write
    paging_disabled = False

    def write(data):
        nonlocal paging_disabled
        if data == b"paginate false\r":
            paging_disabled = True
        if data == b"screen-width 0\r":
            transcript.reader.feed_data(b'syntax error: "0" is out of range\r\n' + transcript.prompt)
            return
        if data == b"show running-config\r" and not paging_disabled:
            transcript.reader.feed_data(b"system\r\n host-name " + role.encode() + b"\r\n--More--")
            return
        original_write(data)

    transcript.write = write
    result = await run_console_session(
        node, ConsoleCredentials(username="admin", password="login-secret"), device_type="cisco_viptela", deadline=5
    )
    assert result == transcript.content
    assert transcript.commands == [
        b"",
        b"admin",
        b"login-secret",
        b"paginate false",
        b"screen-width 256",
        b"show running-config",
    ]
    assert not node._configuration_console_proxy._console_recovery_required


@pytest.mark.parametrize("content", [None, "hostname restored\nend\n"])
@pytest.mark.parametrize("fragmented", [False, True])
def test_cat9kv_setup_is_discarded_before_export_or_restore(scripted_session, content, fragmented):
    chunks = [
        QUESTION,
        "The enable secret is a password used to protect access.\r\nEnter enable secret:",
        "Confirm enable secret:",
        MENU,
        "Press RETURN to get started!",
        "Switch>",
        "Switch#",
    ]
    session = scripted_session(chunks, content=content, fragmented=fragmented)
    assert session.login() == "Switch#"
    commands = [call.args[0].decode().rstrip("\r") for call in session.connection.write.call_args_list]
    secret = commands[2]
    assert 10 <= len(secret) <= 32
    assert re.search("[A-Z]", secret) and re.search("[a-z]", secret) and re.search("[0-9]", secret)
    assert "cisco" not in secret.lower()
    assert commands == ["", "no", secret, secret, "0", "", "enable"]
    assert session.setup_dialog.secret == ""
    assert session.payload["enable_secret"] == ""
    assert secret not in str(session.payload)


@pytest.mark.parametrize("fragmented", [False, True])
def test_ios_autoinstall_question_does_not_block_manual_configuration(scripted_session, fragmented):
    question = "Would you like to terminate autoinstall? [yes]:"
    chunks = [QUESTION + "\r\n", question + "\r\n", "Press RETURN to get started!\r\n", "Router>", "Router#"]
    if fragmented:
        chunks = [part for chunk in chunks for part in chunk]
    session = scripted_session(chunks, content="hostname restored\n")
    assert session.login() == "Router#"
    assert [call.args[0] for call in session.connection.write.call_args_list] == [
        b"\r",
        b"no\r",
        b"yes\r",
        b"\r",
        b"enable\r",
    ]


class PaginatedASA:
    """The console stalls on pager 0; otherwise each page needs one space."""

    def __init__(self, reader):
        self.reader = reader
        self.buffer = b""
        self.commands = []
        self.awaiting_password = False
        self.privileged = False
        self.pages = []
        self.advances = 0
        self.frozen = False
        self.prompt = b"ASAv"
        self.content = b"ASA Version 9.19(1)\nhostname ASAv\nbanner motd <--- More --->\n"
        self.content += b"interface GigabitEthernet0/0\n  description page boundary\n shutdown\n" * 8
        self.content += b"Cryptochecksum: 0123456789abcdef\n: end\n"

    def write(self, data):
        if self.frozen:
            return
        if self.pages:
            assert data == b" ", "Only one space may advance the pager, without a carriage return"
            self.advances += 1
            marker = b"<--- More --->"
            erase = b"\b" * len(marker) + b" " * len(marker) + b"\b" * len(marker)
            self.reader.feed_data(erase)
            self.next_page()
            return
        self.buffer += data
        while b"\r" in self.buffer:
            command, self.buffer = self.buffer.split(b"\r", 1)
            self.commands.append(command)
            if command == b"terminal pager 0":
                self.frozen = True
                return
            if command == b"enable":
                self.awaiting_password = True
                self.reader.feed_data(b"\r\nPassword: ")
                return
            if self.awaiting_password:
                assert command == b"enable-secret"
                self.awaiting_password = False
                self.privileged = True
            elif command == b"show running-config":
                response = command + b"\r\n: Saved\r\n" + self.content.replace(b"\n", b"\r\n")
                lines = response.splitlines(keepends=True)
                self.pages = [b"".join(lines[i : i + 5]) for i in range(0, len(lines), 5)]
                self.pages[-1] += self.prompt + b"#"
                self.next_page()
                return
            self.reader.feed_data(b"\r\n" + self.prompt + (b"#" if self.privileged else b">"))

    def next_page(self):
        self.reader.feed_data(self.pages.pop(0))
        if self.pages:
            self.reader.feed_data(b"<--- More --->")

    async def drain(self):
        await asyncio.sleep(0)


@pytest.mark.parametrize("fragmented", [False, True])
def test_chr_factory_login_exports_without_setting_a_password(scripted_session, fragmented):
    content = "# 2026-11-16 by RouterOS 7.24.6\n/system identity set name=CHR\n"
    session = scripted_session(
        [
            "MikroTik Login:",
            "Password:",
            "Do you want to see the software license? [Y/n]:",
            "Change your password (Ctrl-C to skip)\nnew password>",
            "[admin@CHR] >",
            "/export terse\n" + content + "[admin@CHR] >",
        ],
        driver="mikrotik_routeros",
        fragmented=fragmented,
    )
    session.payload["username"] = "admin"
    assert session.collect() == content.encode()
    commands = [call.args[0] for call in session.connection.write.call_args_list]
    assert b"admin+ct511w4098h\r" in commands
    assert b"n\r" in commands and b"\x03\r" in commands
    assert commands[-1] == b"/export terse\r"
    assert not any(b"/user" in command for command in commands)
