#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
#
# GNS3-Copilot - AI-powered Network Lab Assistant for GNS3
#
# Unit test script for custom Netmiko LinuxTelnetShell driver
#

"""
Unit test script for LinuxTelnetShell custom device driver.

Covers:
1. Device type registration (CLASS_MAPPER, telnet platform lists)
2. Login expect dance: direct shell, username+password, rejected
   credentials, missing credentials, max-loop exhaustion
3. send_command: marker wrapping, exit-code parsing, output stripping
4. Config mode / paging no-ops

Run with: python -m pytest gns3server/agent/gns3_copilot/utils/custom_netmiko/tests/test_linux_telnet.py
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add project root to path using relative path
test_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(test_dir)))))
sys.path.insert(0, project_root)

from netmiko.exceptions import NetmikoAuthenticationException


def _make_driver(username=None, password=None):
    """Build a driver instance without connecting (skip __init__)."""
    from gns3server.agent.gns3_copilot.utils.custom_netmiko.linux_telnet import LinuxTelnetShell

    instance = LinuxTelnetShell.__new__(LinuxTelnetShell)
    instance.username = username
    instance.password = password
    instance.RETURN = "\r\n"
    instance.last_exit_code = None
    instance.last_timed_out = False
    instance.writes = []
    instance.write_channel = instance.writes.append
    return instance


class TestLinuxTelnetRegistration(unittest.TestCase):
    """Registration of gns3_linux_telnet with Netmiko."""

    @classmethod
    def setUpClass(cls):
        from gns3server.agent.gns3_copilot.utils.custom_netmiko import linux_telnet

        cls.linux_telnet = linux_telnet

    def test_device_type_registered(self):
        from netmiko.ssh_dispatcher import CLASS_MAPPER, CLASS_MAPPER_BASE

        self.assertIn("gns3_linux_telnet", CLASS_MAPPER)
        self.assertIn("gns3_linux_telnet", CLASS_MAPPER_BASE)
        self.assertIs(CLASS_MAPPER["gns3_linux_telnet"], self.linux_telnet.LinuxTelnetShell)

    def test_telnet_transport_dispatch(self):
        """The _telnet name substring is what routes Netmiko to the telnet transport."""
        from netmiko.ssh_dispatcher import telnet_platforms

        self.assertIn("gns3_linux_telnet", telnet_platforms)

    def test_extends_base_connection(self):
        from netmiko.base_connection import BaseConnection

        self.assertTrue(issubclass(self.linux_telnet.LinuxTelnetShell, BaseConnection))


@patch("gns3server.agent.gns3_copilot.utils.custom_netmiko.linux_telnet.time.sleep")
class TestLinuxTelnetLogin(unittest.TestCase):
    """The expect login dance."""

    def _run_login(self, instance, channel_script, probe_outputs):
        """Drive telnet_login with a scripted read_channel / read_until_pattern."""
        reads = iter(channel_script)
        instance.read_channel = lambda: next(reads, "")
        probes = iter(probe_outputs)
        instance.read_until_pattern = MagicMock(side_effect=lambda pattern, read_timeout: next(probes))
        return instance.telnet_login()

    def test_direct_shell_skips_login(self, _sleep):
        """Docker-style console: no login prompt, first sentinel probe wins."""
        instance = _make_driver()
        # read_channel: initial drain, then quiet
        output = self._run_login(instance, ["", ""], ["export TERM=dumb ...\r\n__MCP_PROMPT__ "])
        self.assertIn("__MCP_PROMPT__", output)
        # Only the sentinel probe should have been written
        self.assertEqual(instance.writes, ["export TERM=dumb PAGER=cat PS1='__MCP_PROMPT__ '\r\n"])

    def test_username_password_login(self, _sleep):
        """getty console: login: then Password: then shell."""
        instance = _make_driver(username="admin", password="secret")  # noqa: S106
        script = [
            "Welcome to Ubuntu 22.04\r\nserver login: ",  # initial drain
            "Password: ",  # after username
            "Last login: ...\r\n$ ",  # after password
            "",  # loop 3 read
        ]
        output = self._run_login(instance, script, ["__MCP_PROMPT__ "])
        self.assertIn("__MCP_PROMPT__", output)
        self.assertEqual(instance.writes[:2], ["admin\r\n", "secret\r\n"])

    def test_rejected_credentials(self, _sleep):
        """Password: reappearing after one attempt means rejection."""
        instance = _make_driver(username="admin", password="wrong")  # noqa: S106
        script = [
            "server login: ",
            "Password: ",
            "Password: ",  # rejected → prompt again
        ]
        with self.assertRaises(NetmikoAuthenticationException) as ctx:
            self._run_login(instance, script, [])
        self.assertIn("rejected", str(ctx.exception))

    def test_password_only_console_rejected(self, _sleep):
        """Root consoles skip username; a second Password: is still rejection."""
        instance = _make_driver(password="wrong")  # noqa: S106
        script = [
            "Password: ",
            "Password: ",
        ]
        with self.assertRaises(NetmikoAuthenticationException):
            self._run_login(instance, script, [])

    def test_missing_username(self, _sleep):
        instance = _make_driver()
        with self.assertRaises(NetmikoAuthenticationException) as ctx:
            self._run_login(instance, ["server login: "], [])
        self.assertIn("default_username", str(ctx.exception))

    def test_missing_password(self, _sleep):
        instance = _make_driver(username="admin")
        with self.assertRaises(NetmikoAuthenticationException) as ctx:
            self._run_login(instance, ["server login: ", "Password: "], [])
        self.assertIn("default_password", str(ctx.exception))

    def test_never_reaches_shell(self, _sleep):
        """Quiet console that never responds exhausts the loop and errors."""
        from netmiko.exceptions import ReadTimeout

        instance = _make_driver()
        instance.read_channel = lambda: ""
        instance.read_until_pattern = MagicMock(side_effect=ReadTimeout())
        with self.assertRaises(NetmikoAuthenticationException):
            instance.telnet_login()


class TestLinuxTelnetSendCommand(unittest.TestCase):
    """Marker wrapping, exit-code parsing, timeout and echo stripping."""

    def _make_connected(self, chunks):
        """Driver with a scripted read_channel: first call is the pre-write
        drain, the rest are the loop's reads (then quiet forever)."""
        instance = _make_driver()
        instance.strip_command = lambda cmd, out: out
        remaining = iter(chunks)

        def read_channel():
            return next(remaining, "")

        instance.read_channel = read_channel
        return instance

    def test_marker_wrapping_and_exit_code(self):
        instance = self._make_connected(
            ["", "ls /\r\nbin\r\nboot\r\n__MCP_DONE_0__\r\n__MCP_PROMPT__ "]
        )
        output = instance.send_command("ls /")
        self.assertEqual(instance.last_exit_code, 0)
        self.assertFalse(instance.last_timed_out)
        self.assertNotIn("__MCP_DONE_", output)
        self.assertNotIn("__MCP_PROMPT__", output)
        self.assertIn("bin", output)

    def test_nonzero_exit_code(self):
        instance = self._make_connected(["", "cat nofile\r\ncat: nofile: No such file\r\n__MCP_DONE_1__"])
        output = instance.send_command("cat nofile")
        self.assertEqual(instance.last_exit_code, 1)
        self.assertIn("No such file", output)

    def test_wrapped_command_written(self):
        instance = self._make_connected(["", "__MCP_DONE_0__"])
        instance.send_command("uptime", read_timeout=5)
        self.assertEqual(instance.writes[-1], "uptime; echo __MCP_DONE_$?__\r\n")

    def test_ansi_stripped(self):
        instance = self._make_connected(["", "\x1b[31mFAIL\x1b[0m\r\n__MCP_DONE_2__"])
        output = instance.send_command("false")
        self.assertNotIn("\x1b", output)
        self.assertIn("FAIL", output)
        self.assertEqual(instance.last_exit_code, 2)

    def test_timeout_returns_partial_output_not_an_error(self):
        """A command that outlives read_timeout keeps running: the driver
        reports what arrived so far instead of raising (netmiko's
        read_until_pattern would discard it)."""

        def read_channel():
            return "64 bytes from 10.0.0.1: seq=1\r\n"

        instance = _make_driver()
        instance.strip_command = lambda cmd, out: out
        instance.read_channel = read_channel
        output = instance.send_command("ping 10.0.0.1", read_timeout=0.2)
        self.assertTrue(instance.last_timed_out)
        self.assertIsNone(instance.last_exit_code)
        self.assertIn("64 bytes", output)

    def test_readline_scroll_view_echo_dropped(self):
        """Captured from a live docker PTY: a command longer than the terminal
        width is re-rendered by readline as "<" + command tail, so the echoed
        wrapper is truncated and unmatched. That line is echo debris and must
        be dropped; real output lines must survive."""
        debris = "<pad%.0s' 1 2 3 4 5 6 7 8 9 10; echo __MCP_DONE_$?__"
        instance = self._make_connected(["", f"\n{debris}\nline-one\nline-two\n__MCP_DONE_0__\n__MCP_PROMPT__ "])
        output = instance.send_command("echo line-one && echo line-two")
        self.assertEqual(instance.last_exit_code, 0)
        self.assertNotIn("__MCP_DONE_", output)
        self.assertNotIn("<pad", output)
        self.assertIn("line-one", output)
        self.assertIn("line-two", output)

    def test_wrapped_console_echo_stripped(self):
        """The PTY wraps long echoed lines with CRLF at any column — the
        echoed marker wrapper must still be stripped from the output."""
        cmd = "ip -brief addr show dev eth0"
        wrapped_echo = f"{cmd}; echo __MCP_D" + "\r\n" + "ONE_$?__"
        instance = self._make_connected(
            ["", f"{wrapped_echo}\r\nlo UNKNOWN 127.0.0.1/8\r\n__MCP_DONE_0__\r\n"]
        )
        output = instance.send_command(cmd)
        self.assertEqual(instance.last_exit_code, 0)
        self.assertNotIn("echo __MCP_D", output)
        self.assertNotIn("ONE_$?__", output)
        self.assertIn("127.0.0.1/8", output)


class TestLinuxTelnetNoOps(unittest.TestCase):
    """A shell console has no netmiko config-mode or paging concepts."""

    def test_config_mode_noops(self):
        instance = _make_driver()
        self.assertFalse(instance.check_config_mode())
        self.assertEqual(instance.config_mode(), "")
        self.assertEqual(instance.exit_config_mode(), "")
        self.assertEqual(instance.disable_paging(), "")


if __name__ == "__main__":
    unittest.main()
