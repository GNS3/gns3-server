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
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
# for more details.
#
# You should have received a copy of the GNU General Public License
# along with GNS3-Copilot. If not, see <https://www.gnu.org/licenses/>.
#
# Copyright (C) 2025 Yue Guobin (岳国宾)
# Author: Yue Guobin (岳国宾)
#
# Project Home: https://github.com/yueguobin/gns3-copilot
#

# mypy: ignore-errors

"""
Custom Netmiko device driver for Ruijie (锐捷) devices in GNS3 emulation.

This module provides enhanced handling for Ruijie network devices,
specifically addressing interactive prompts during configuration.

Key Features:
- Inherits from RuijieOSBase (Netmiko's native Ruijie support)
- Handles interactive prompts (e.g., OSPF router-id [yes/no] confirmation)
- Maintains compatibility with Netmiko's Ruijie implementation

Device Type: gns3_ruijie_telnet
"""

import importlib
import logging
import re
import time

from netmiko.ruijie.ruijie_os import RuijieOSBase

logger = logging.getLogger(__name__)


class RuijieTelnetEnhanced(RuijieOSBase):
    """
    Enhanced Ruijie device driver with interactive prompt handling.

    Inherits from RuijieOSBase to maintain native Netmiko compatibility,
    and adds automatic handling for interactive configuration prompts.
    """

    # Interactive command patterns that trigger [yes/no] prompts
    # These are commands that commonly require confirmation
    INTERACTIVE_PATTERNS = [
        re.compile(r'^router-id\s+', re.IGNORECASE),  # OSPF router-id
        re.compile(r'^erase\s+', re.IGNORECASE),  # erase startup-config
        re.compile(r'^delete\s+', re.IGNORECASE),  # delete files
        re.compile(r'^format\s+', re.IGNORECASE),  # format filesystem
        re.compile(r'^reload\b', re.IGNORECASE),  # reload/reboot
        re.compile(r'^boot\s+system\s+', re.IGNORECASE),  # change boot image
    ]

    def __init__(
        self,
        *args,
        **kwargs,
    ) -> None:
        """Initialize RuijieTelnetEnhanced connection."""
        # Set default_enter for telnet (like Netmiko's RuijieOSTelnet)
        default_enter = kwargs.get("default_enter")
        if default_enter is None:
            kwargs["default_enter"] = "\r\n"
        super().__init__(*args, **kwargs)

    def _preprocess_interactive_commands(
        self, config_commands: list[str]
    ) -> list[str]:
        """
        Preprocess commands to insert 'yes' after interactive commands.

        Detects commands that trigger [yes/no] prompts and automatically
        inserts 'yes' response after them.

        Args:
            config_commands: List of configuration commands

        Returns:
            List of commands with 'yes' inserted after interactive commands
        """
        processed = []

        for cmd in config_commands:
            # Add the original command
            processed.append(cmd)

            # Check if this command matches any interactive pattern
            for pattern in self.INTERACTIVE_PATTERNS:
                if pattern.match(cmd.strip()):
                    logging.info(
                        "Ruijie device: Detected interactive command '%s', "
                        "inserting 'yes'",
                        cmd.strip(),
                    )
                    # Insert 'yes' after this command
                    processed.append("yes")
                    break

        return processed

    def send_config_set(
        self,
        config_commands: str | list[str],
        **kwargs,
    ) -> str:
        """
        Send configuration commands with interactive prompt handling.

        Hybrid Strategy:
        1. Preprocess commands to insert 'yes' after known interactive commands
        2. Try batch send (fast)
        3. If batch fails, fallback to one-by-one send with real-time detection

        Args:
            config_commands: Configuration commands to send
            **kwargs: Additional arguments (exit_config_mode, read_timeout,
                      etc.)

        Returns:
            Output from configuration commands
        """
        # Convert string to list
        if isinstance(config_commands, str):
            config_commands = [config_commands]

        # Get parameters with defaults
        exit_config_mode = kwargs.get("exit_config_mode", True)
        enter_config_mode = kwargs.get("enter_config_mode", True)
        read_timeout = kwargs.get("read_timeout", 60)
        delay_factor = self.global_delay_factor

        output = ""

        # Enter config mode if needed
        if enter_config_mode:
            output += self.config_mode()

        # Preprocess: Insert 'yes' after known interactive commands
        processed_commands = self._preprocess_interactive_commands(
            config_commands
        )

        # Try batch send first (fast path)
        try:
            output += self._send_config_batch(
                processed_commands, read_timeout, delay_factor
            )
        except Exception as batch_error:
            logging.warning(
                "Ruijie device: Batch send failed, "
                "falling back to one-by-one: %s",
                batch_error,
            )
            # Fallback to one-by-one send with real-time detection
            output += self._send_config_one_by_one(
                config_commands, read_timeout, delay_factor
            )

        # Exit config mode if requested
        if exit_config_mode:
            output += self.exit_config_mode()

        return output

    def _send_config_batch(
        self, commands: list[str], read_timeout: int, delay_factor: float
    ) -> str:
        """
        Send configuration commands in batch (fast).

        This works when all interactive prompts have been pre-processed
        with 'yes' responses inserted.
        """
        output = ""

        # Batch send: Write all commands rapidly
        for cmd in commands:
            self.write_channel(f"{cmd}{self.RETURN}")
            time.sleep(0.01)

        # Read all output at once
        # Use same default as Netmiko (2.0 seconds) to ensure complete output
        output += self.read_channel_timing(
            read_timeout=read_timeout, last_read=2.0
        )

        return output

    def _send_config_one_by_one(
        self, commands: list[str], read_timeout: int, delay_factor: float
    ) -> str:
        """
        Send commands one-by-one with real-time prompt detection.

        This is the fallback method when batch send fails.
        """
        output = ""
        interactive_patterns = [
            r"\[yes/no\]",
            r"\[y/n\]",
            r"\[Y/N\]",
        ]

        # Send commands ONE BY ONE to detect prompts after each command
        for cmd in commands:
            # Write the command
            self.write_channel(f"{cmd}{self.RETURN}")
            time.sleep(0.05)

            # Read output after this command
            new_output = self.read_channel_timing(
                read_timeout=10, last_read=0.5
            )
            output += new_output

            # Check if interactive prompt appeared after this command
            for pattern in interactive_patterns:
                if re.search(pattern, new_output, re.IGNORECASE):
                    logging.info(
                        "Ruijie device: Detected interactive prompt "
                        "after '%s', sending 'yes'",
                        cmd,
                    )
                    # Send 'yes' to confirm
                    self.write_channel(f"yes{self.RETURN}")
                    time.sleep(0.3)
                    # Read the confirmation response
                    output += self.read_channel_timing(
                        read_timeout=30, last_read=0.5
                    )
                    break

        return output


# Register the custom device type with Netmiko
_registered = False  # Flag to prevent duplicate registration

def register_custom_device_type() -> None:
    """
    Register the custom RuijieTelnetEnhanced device type with Netmiko.

    This function adds 'gns3_ruijie_telnet' to Netmiko's CLASS_MAPPER
    and updates the platforms lists.

    Note: This function is idempotent - multiple calls will only register once.
    """
    global _registered

    # Prevent duplicate registration
    if _registered:
        logger.debug("Ruijie Telnet device type already registered, skipping")
        return

    sd = importlib.import_module("netmiko.ssh_dispatcher")

    # Register in both mappers
    sd.CLASS_MAPPER_BASE["gns3_ruijie_telnet"] = RuijieTelnetEnhanced
    sd.CLASS_MAPPER["gns3_ruijie_telnet"] = RuijieTelnetEnhanced

    # Update platforms lists
    sd.platforms = list(sd.CLASS_MAPPER.keys())
    sd.platforms.sort()
    sd.platforms_base = list(sd.CLASS_MAPPER_BASE.keys())
    sd.platforms_base.sort()
    sd.telnet_platforms = [x for x in sd.platforms if "telnet" in x]
    sd.platforms_str = "\n" + "\n".join(sd.platforms_base)
    sd.telnet_platforms_str = "\n" + "\n".join(sd.telnet_platforms)

    # Mark as registered
    _registered = True

    logger.info("Successfully registered Ruijie Telnet device type with Netmiko")


# Auto-register on import
try:
    register_custom_device_type()
except Exception as e:
    logger = logging.getLogger(__name__)
    logger.warning(
        f"Failed to register Ruijie device type: {e}",
        exc_info=True
    )
