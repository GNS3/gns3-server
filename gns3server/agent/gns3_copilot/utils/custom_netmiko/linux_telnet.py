# SPDX-License-Identifier: GPL-3.0-or-later
#
# GNS3-Copilot - AI-powered Network Lab Assistant for GNS3
#
# This file is part of GNS3-Copilot project.
#
# GNS3-Copilot is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your
# option) any later version.
#
# GNS3-Copilot is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GNS3-Copilot. If not, see <https://www.gnu.org/licenses/>.
#
# Copyright (C) 2026 Yue Guobin (岳国宾)
# Author: Yue Guobin (岳国宾)
#
# Project Home: https://github.com/yueguobin/gns3-copilot
#

# mypy: ignore-errors

"""
Custom Netmiko device driver for Linux shell consoles in GNS3.

Covers nodes whose console is a Linux shell: docker containers exposing an
exec console and QEMU VMs running a Linux image with a getty on the serial
console (netshoot, alpine, generic Linux images...).

The device_type name MUST contain "_telnet": Netmiko dispatches the telnet
transport by that name substring, and GNS3 consoles are telnet TCP ports
(there is no SSH daemon on these consoles).

Completion detection does NOT guess shell prompts. Two sentinels are used
instead, because unlike a network OS the shell is ours to configure:

  - Login:   an expect loop matches the conventional "login:"/"Password:"
             prompts (Linux getty). Docker exec consoles usually land in a
             root shell directly and skip the loop on the first probe.
  - Session: after login the driver sets PS1 to a sentinel prompt and wraps
             every command with `; echo __MCP_DONE_$?__` — the marker carries
             the exit code, giving process-exit-grade completion signalling
             (the same determinism Claude Code gets from waitpid()).

Device Type: gns3_linux_telnet
"""

import logging
import re
import time
from functools import lru_cache

from netmiko.base_connection import BaseConnection
from netmiko.exceptions import ReadTimeout

logger = logging.getLogger(__name__)

# ANSI escape code pattern (shared shape with vpcs_telnet.py; kept local so
# each driver stands alone — see the MCP console layer for the shared copy)
ANSI_ESCAPE_PATTERN = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")

# Conventional Unix login prompts. The username prompt always ends in
# "login:"/"Username:" and the password prompt in "Password:" — decades of
# getty convention make these reliable. The password is never echoed.
USERNAME_PROMPT_RE = re.compile(r"(?i)(?:login|user ?name|username)\s*:")
PASSWORD_PROMPT_RE = re.compile(r"(?i)password\s*:")

# Sentinels. Chosen so they cannot collide with anything a shell would print
# on its own; the marker embeds the command's exit code ($?).
PS1_SENTINEL = "__MCP_PROMPT__"
# Two forms of the marker pattern: the expect form must be fully
# non-capturing — netmiko's read_until_pattern splits on the pattern and
# assumes any capture group wraps the WHOLE match (an inner group makes it
# keep only the group text and drop the marker). The capture form is for
# parsing the exit code out of already-read output.
MARKER_EXPECT = r"__MCP_DONE_(?:\d+)__"
MARKER_RE = re.compile(r"__MCP_DONE_(\d+)__")
MARKER_TEMPLATE = "echo __MCP_DONE_$?__"

# Environment normalization applied once after login: dumb terminal (some
# full-screen TUIs degrade to linear output), no pager, and our sentinel PS1
# so completion detection never depends on the user's shell config.
SESSION_INIT_COMMAND = f"export TERM=dumb PAGER=cat PS1='{PS1_SENTINEL} '"


@lru_cache(maxsize=128)
def _echo_strip_pattern(text: str) -> re.Pattern:
    """Pattern matching `text` as the console echoes it back.

    A PTY wraps long lines by inserting CRLF at any column (not only at
    spaces), so an exact replace misses wrapped echoes and the marker text
    leaks into the output. Allow an optional line break between any two
    characters of the echoed text."""
    return re.compile(r"(?:\r?\n)?".join(re.escape(ch) for ch in text))


class LinuxTelnetShell(BaseConnection):
    """
    Custom Linux shell driver for GNS3 console ports (telnet transport).

    - Login is optional: the expect loop handles getty prompts when present
      (credentials come from the node's default_username/default_password),
      and detects an already-logged-in shell otherwise.
    - send_command wraps each command with an exit-code marker and reads
      until it appears; the parsed exit code is exposed as last_exit_code.
    """

    def __init__(self, *args, **kwargs) -> None:
        kwargs.setdefault("device_type", "gns3_linux_telnet")
        kwargs.setdefault("global_delay_factor", 1.0)
        kwargs.setdefault("fast_cli", False)
        super().__init__(*args, **kwargs)
        # Exit code of the last send_command, parsed from the marker; and
        # whether that command was still running when the read timed out.
        self.last_exit_code: int | None = None
        self.last_timed_out: bool = False

    # ── Login ─────────────────────────────────────────────────────────────

    def telnet_login(
        self,
        pri_prompt_terminator: str = PS1_SENTINEL,
        alt_prompt_terminator: str = "",
        username_pattern: str = "",
        pwd_pattern: str = "",
        delay_factor: float = 1.0,
        max_loops: int = 20,
    ) -> str:
        """
        Expect-style login for Linux console ports.

        Loop with short reads:
          1. "login:"/"Username:"  -> send username
          2. "Password:" (again, after one attempt) -> credentials rejected
          3. neither (quiet or shell-looking) -> probe with the PS1 sentinel;
             if the sentinel echoes back we were already in a shell.

        Raises NetmikoAuthenticationException when a login prompt is present
        but no credentials are configured, or when the password is rejected.
        """
        from netmiko.exceptions import NetmikoAuthenticationException

        output = ""
        username_sent = False
        password_attempts = 0
        # Only scan output this far: prompts already matched must not
        # re-trigger on every loop (the trailing window would keep seeing
        # the historical "login:"/"Password:" strings).
        search_from = 0
        # Give slow VM banners a moment to print before the first probe, so
        # the probe text cannot become accidental username input.
        time.sleep(1.0 * delay_factor)
        output += self.read_channel() or ""

        for _ in range(max_loops):
            fresh = ANSI_ESCAPE_PATTERN.sub("", output[search_from:])

            username_match = USERNAME_PROMPT_RE.search(fresh)
            if username_match:
                if not self.username:
                    raise NetmikoAuthenticationException(
                        "Console asks for a username but the node has no default_username configured"
                    )
                search_from += username_match.end()
                self.write_channel(self.username + self.RETURN)
                username_sent = True
                password_attempts = 0
                time.sleep(0.5 * delay_factor)
                output += self.read_channel() or ""
                continue

            password_match = PASSWORD_PROMPT_RE.search(fresh)
            if password_match:
                if not self.password:
                    raise NetmikoAuthenticationException(
                        "Console asks for a password but the node has no default_password configured"
                    )
                if password_attempts >= 1:
                    # Seeing Password: again after already sending one means
                    # the credentials were rejected (username+password consoles
                    # re-prompt "login:" instead, which resets the counter
                    # above). Stop instead of retrying — repeated failures can
                    # lock the account.
                    raise NetmikoAuthenticationException("Login failed: credentials rejected by the console")
                search_from += password_match.end()
                self.write_channel(self.password + self.RETURN)
                password_attempts += 1
                time.sleep(1.0 * delay_factor)
                output += self.read_channel() or ""
                continue

            # No login prompt in the fresh window: either quiet (nothing
            # prints until we type) or already in a shell. Probe with the
            # sentinel — its echo means we have a shell.
            self.write_channel(SESSION_INIT_COMMAND + self.RETURN)
            try:
                probe_output = self.read_until_pattern(pattern=PS1_SENTINEL, read_timeout=3.0)
                output += probe_output
                logger.info("Linux shell console detected (sentinel prompt set)")
                return output
            except ReadTimeout:
                # Not in a shell yet; poke the console and loop.
                self.write_channel(self.RETURN)
                time.sleep(0.5 * delay_factor)
                output += self.read_channel() or ""
                # The probe text and poke may not have been prompts; do not
                # advance search_from — a delayed login prompt must still
                # be findable in what we have read.

        raise NetmikoAuthenticationException(
            f"Could not reach a shell prompt on the Linux console within {max_loops} attempts"
        )

    def session_preparation(self) -> None:
        """Re-assert the sentinel prompt and environment after login."""
        self.write_channel(SESSION_INIT_COMMAND + self.RETURN)
        try:
            self.read_until_pattern(pattern=PS1_SENTINEL, read_timeout=5.0)
        except ReadTimeout:
            logger.debug("session_preparation: sentinel prompt not confirmed (continuing)")

    # ── Command execution ─────────────────────────────────────────────────

    def send_command(
        self,
        command_string: str,
        expect_string: str | None = None,
        read_timeout: float | None = None,
        delay_factor: float | None = None,
        max_loops: int | None = None,
        strip_prompt: bool = True,
        strip_command: bool = True,
        normalize: bool = False,
        use_textfsm: bool = False,
    ) -> str:
        """
        Send a command and read until its completion marker.

        The command is wrapped as `cmd; echo __MCP_DONE_$?__` so completion
        is signalled by the marker (with the exit code embedded) rather than
        by guessing a prompt pattern. The exit code is parsed into
        self.last_exit_code; the echoed wrapped command and the marker line
        are stripped from the returned output.

        The read loop is owned here rather than delegated to netmiko's
        read_until_pattern: on timeout that helper RAISES and discards the
        output it has already read, while an interactive caller needs the
        partial output plus a "still running" signal. On timeout the partial
        output is returned, self.last_timed_out is set and last_exit_code
        stays None — the command itself keeps running on the console.
        """
        if read_timeout is None:
            read_timeout = 30.0
        if expect_string is None:
            expect_string = MARKER_EXPECT

        self.last_exit_code = None
        self.last_timed_out = False
        wrapped = f"{command_string}; {MARKER_TEMPLATE}"
        # Drain stale output from a previous command on this cached session
        # before writing, so it cannot bleed into this command's result.
        try:
            self.read_channel()
        except Exception:
            pass
        self.write_channel(wrapped + self.RETURN)

        # read_timeout 0 means "no timeout" (netmiko convention).
        deadline = time.monotonic() + read_timeout if read_timeout else None
        output = ""
        while True:
            output += self.read_channel() or ""
            if re.search(expect_string, output):
                break
            if deadline is not None and time.monotonic() >= deadline:
                self.last_timed_out = True
                logger.debug("Command %r not complete after %.1fs (still running)", command_string, read_timeout)
                break
            time.sleep(0.05)

        output = ANSI_ESCAPE_PATTERN.sub("", output)

        marker_match = MARKER_RE.search(output)
        if marker_match:
            self.last_exit_code = int(marker_match.group(1))

        if strip_prompt:
            # Drop the marker line, the echoed wrapped command, any sentinel
            # prompt fragments (the shell glues the prompt in front of the
            # echo, so line-based strip helpers cannot find it) and the
            # session-init echo that the first command's read may pick up.
            # Echoed text is matched wrap-tolerantly: a PTY inserts CRLF at
            # any column when a long line wraps.
            output = MARKER_RE.sub("", output)
            output = _echo_strip_pattern(wrapped).sub("", output)
            output = _echo_strip_pattern(SESSION_INIT_COMMAND).sub("", output)
            output = output.replace(PS1_SENTINEL, "")
            # Readline renders a long pasted line as a horizontal-scroll view
            # ("<" + command tail ...; echo __MCP_DONE_$?__") instead of a
            # wrapped echo, so the echoed wrapper can appear mangled beyond
            # what the fuzzy strip can match. Any line still carrying marker
            # text at this point is echo debris — real output never contains
            # the marker unexpanded. Drop the whole line (it is echo, not
            # device data).
            output = "\n".join(line for line in output.splitlines() if "__MCP_DONE_" not in line)
        return output.strip("\n")

    def send_command_timing(self, command_string: str, **kwargs) -> str:
        """Timing variant — identical to the marker-based send_command."""
        return self.send_command(command_string=command_string)

    # ── Shell consoles have no netmiko config-mode/paging concepts ────────

    def check_config_mode(self, check_string: str = "", pattern: str = "", force_regex: bool = False) -> bool:
        return False

    def config_mode(self, config_command: str = "", pattern: str = "", re_flags: int = 0) -> str:
        return ""

    def exit_config_mode(self, exit_config: str = "", pattern: str = "") -> str:
        return ""

    def disable_paging(self, command: str = "", delay_factor: float | None = None, **kwargs) -> str:
        return ""


# Register the custom device type with Netmiko
_registered = False  # Flag to prevent duplicate registration


def register_custom_device_type() -> None:
    """
    Register the custom Linux shell Telnet device type with Netmiko.

    Adds 'gns3_linux_telnet' to Netmiko's CLASS_MAPPER and rebuilds the
    static platform lists (they are computed at import time). Idempotent.
    """
    global _registered

    if _registered:
        logger.debug("Linux shell Telnet device type already registered, skipping")
        return

    import importlib

    sd = importlib.import_module("netmiko.ssh_dispatcher")

    sd.CLASS_MAPPER_BASE["gns3_linux_telnet"] = LinuxTelnetShell
    sd.CLASS_MAPPER["gns3_linux_telnet"] = LinuxTelnetShell

    # Rebuild the static lists (same procedure as vpcs_telnet.py)
    sd.platforms = sorted(sd.CLASS_MAPPER.keys())
    sd.platforms_base = sorted(sd.CLASS_MAPPER_BASE.keys())
    sd.telnet_platforms = [x for x in sd.platforms if "telnet" in x]
    sd.platforms_str = "\n" + "\n".join(sd.platforms_base)
    sd.telnet_platforms_str = "\n" + "\n".join(sd.telnet_platforms)

    _registered = True
    logger.info("Successfully registered Linux shell Telnet device type with Netmiko")


# Auto-register on import
try:
    register_custom_device_type()
except Exception as e:
    logger.warning("Failed to register Linux shell device type: %s", e, exc_info=True)
