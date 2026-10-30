#
# Copyright (C) 2026 GNS3 Technologies Inc.
# Author: Yue Guobin
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

"""
Unit tests for the console TUI guard (pure functions, no I/O).
"""

from gns3server.agent.mcp.console import (
    ANSI_ESCAPE_PATTERN,
    _device_type_from_node,
    guard_command,
)


class TestShellGuard:
    def test_top_rejected_with_batch_suggestion(self):
        result = guard_command("top", "shell")
        assert result["status"] == "rejected"
        assert result["suggestion"] == "top -b -n 1"

    def test_full_path_head_word(self):
        result = guard_command("/usr/bin/top -d 5", "shell")
        assert result is not None and result["suggestion"] == "top -b -n 1"

    def test_tail_follow_rejected(self):
        result = guard_command("tail -f /var/log/syslog", "shell")
        assert result["status"] == "rejected"
        assert "tail -n" in result["suggestion"]

    def test_tail_bounded_allowed(self):
        assert guard_command("tail -n 50 /var/log/syslog", "shell") is None

    def test_top_batch_form_passes(self):
        # top -b is exactly what the guard suggests — it must not be blocked
        assert guard_command("top -b -n 1", "shell") is None
        assert guard_command("top -b -n 1 | head -3", "shell") is None

    def test_man_suggestion_uses_subject(self):
        result = guard_command("man ls", "shell")
        assert result["suggestion"] == "ls --help"

    def test_plain_commands_allowed(self):
        for cmd in ("uptime", "ip addr show", "cat /etc/os-release", "ps aux", "ping -c 3 10.0.0.1"):
            assert guard_command(cmd, "shell") is None, cmd

    def test_control_keys_bypass_guard(self):
        # Ctrl-C and friends are keystrokes, not commands
        assert guard_command("\x03", "shell") is None
        assert guard_command("q", "shell") is None  # single key to quit a pager — not in the table
        assert guard_command("\r\n", "shell") is None

    def test_empty_allowed(self):
        assert guard_command("", "shell") is None
        assert guard_command("   ", "shell") is None


class TestNetosGuard:
    def test_setup_rejected(self):
        result = guard_command("setup", "netos")
        assert result["status"] == "rejected"

    def test_normal_netos_commands_allowed(self):
        for cmd in ("show version", "show ip interface brief", "ping 10.0.0.1 repeat 5", "conf t"):
            assert guard_command(cmd, "netos") is None, cmd

    def test_shell_table_not_applied_to_netos(self):
        # 'top' on a shell is rejected; unknown families must not over-block
        assert guard_command("top", "netos") is None


class TestAnsiStrip:
    def test_strip(self):
        dirty = "\x1b[31mFAIL\x1b[0m plain \x1b[1mbold\x1b[0m"
        assert ANSI_ESCAPE_PATTERN.sub("", dirty) == "FAIL plain bold"


class TestDeviceTypeResolution:
    def test_field_wins_over_tag(self):
        node = {"netmiko_device_type": "cisco_ios_telnet", "tags": ["device_type:huawei_telnet"]}
        assert _device_type_from_node(node) == "cisco_ios_telnet"

    def test_tag_fallback(self):
        node = {"netmiko_device_type": None, "tags": ["billing", "device_type:gns3_vpcs_telnet"]}
        assert _device_type_from_node(node) == "gns3_vpcs_telnet"

    def test_none_when_missing(self):
        assert (
            _device_type_from_node({"tags": ["billing"], "node_type": "docker"}) is None
        )  # docker is ambiguous (xrd/IOL)
        assert _device_type_from_node({}) is None

    def test_vpcs_node_type_defaults_to_its_only_driver(self):
        # VPCS has exactly one possible driver — not a guess (unlike docker)
        assert _device_type_from_node({"node_type": "vpcs"}) == "gns3_vpcs_telnet"
