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
Custom Netmiko device driver for VPCS (Virtual PC Simulator) in GNS3.

VPCS is a lightweight virtual PC simulator used in GNS3 lab environments
for testing network connectivity and basic IP configuration.

Key Features:
- No authentication required (direct console access)
- Simple command-line interface (PC1>, PC2>, etc.)
- Supports basic PC commands (ip, ping, arp, version, etc.)
- Telnet-based connection

Device Type: gns3_vpcs_telnet
"""

import importlib
import logging
import re
import time

from netmiko.base_connection import BaseConnection


logger = logging.getLogger(__name__)

# ANSI escape code pattern for stripping terminal formatting codes
# Matches sequences like: [1m (bold), [0m (reset), [4m (underline), etc.
ANSI_ESCAPE_PATTERN = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")


class VPCSTelnet(BaseConnection):
    """
    Custom VPCS device driver for GNS3 emulation.

    VPCS devices are lightweight virtual PCs that simulate basic network
    functionality for lab testing. This driver handles the unique
    characteristics of VPCS:
    - No authentication (no username/password)
    - Simple prompt pattern (PC1>, PC2>, etc.)
    - No configuration modes
    """

    def __init__(
        self,
        *args,
        **kwargs,
    ) -> None:
        """Initialize VPCS Telnet connection."""
        # Set device type to identify this as a VPCS device
        kwargs.setdefault("device_type", "gns3_vpcs_telnet")

        # VPCS uses carriage return + line feed for command termination
        # This is critical for VPCS devices to respond to commands
        default_enter = kwargs.get("default_enter")
        if default_enter is None:
            kwargs["default_enter"] = "\r\n"

        kwargs.setdefault("global_delay_factor", 1.0)
        kwargs.setdefault("fast_cli", False)

        super().__init__(*args, **kwargs)

    def telnet_login(
        self,
        pri_prompt_terminator: str = r"PC\d+>",
        alt_prompt_terminator: str = r"",
        username_pattern: str = r"(?:user:|username|login|user name)",
        pwd_pattern: str = r"assword",
        delay_factor: float = 1.0,
        max_loops: int = 20,
    ) -> str:
        """
        Telnet login for VPCS devices (no authentication).

        VPCS devices connect directly to command line without username/password.
        This method initializes the connection and waits for the VPCS prompt.

        Strategy (matching telnetlib3 implementation):
        1. Send 4 newlines with 0.5s delay between each
        2. Wait for VPCS prompt pattern (PC1>, PC2>, etc.)
        3. Return once prompt is detected

        Args:
            pri_prompt_terminator: Primary prompt pattern (default: r"PC\\d+>")
            alt_prompt_terminator: Not used for VPCS
            username_pattern: Not used (kept for signature compatibility)
            pwd_pattern: Not used (kept for signature compatibility)
            delay_factor: Delay factor for timing
            max_loops: Maximum wait loops

        Returns:
            Output from the connection process
        """
        delay_factor = self.select_delay_factor(delay_factor)
        return_msg = ""

        # Step 1: Clear buffer - read any existing data
        try:
            initial_data = self.read_channel()
            if initial_data:
                return_msg += initial_data
        except Exception:
            # Ignore errors during initial read
            pass

        # Step 2: Send 4 newlines with delays (matching telnetlib3 exactly)
        # tn.write(b"\n"); sleep(0.5) - repeated 4 times
        for i in range(4):
            try:
                # Send newline directly as bytes
                self.remote_conn.write(b"\n")
                time.sleep(0.5 * delay_factor)

                # Read response
                new_output = self.read_channel()
                if new_output:
                    return_msg += new_output

            except Exception as e:
                logger.debug("Error during VPCS connection initialization: %s", e)

        # Step 3: Wait for VPCS prompt pattern
        try:
            # Read until we see the prompt
            output = self.read_until_pattern(
                pattern=pri_prompt_terminator,
                read_timeout=10
            )
            return_msg += output

            if re.search(pri_prompt_terminator, return_msg, flags=re.M):
                logger.info("VPCS prompt detected")
                return return_msg

        except Exception as e:
            logger.debug("Error waiting for VPCS prompt: %s", e)

        # Step 4: Return what we have (connection might still work)
        logger.debug("VPCS prompt not clearly detected, returning current output")
        return return_msg

    def session_preparation(self) -> None:
        """
        Prepare the session after connection is established.

        VPCS doesn't require special session preparation.
        The telnet_login method already handles initialization with 4 newlines.
        """
        # No additional preparation needed
        logger.debug("VPCS session preparation completed")

    def send_command(
        self,
        command_string: str,
        expect_string: str | None = None,
        read_timeout: float | None = None,
        delay_factor: float | None = None,
        max_loops: int | None = None,
        strip_prompt: bool = False,
        strip_command: bool = False,
        normalize: bool = False,
        use_textfsm: bool = False,
    ) -> str:
        """
        Send a command to VPCS and return the output.

        This method exactly matches the telnetlib3 implementation:
        1. Encode command as ASCII and append newline
        2. Write command+newline as single byte sequence
        3. Sleep for 5 seconds
        4. Wait for prompt pattern and capture output
        5. Return captured output

        Args:
            command_string: The command to send
            expect_string: Pattern to expect (default: VPCS prompt r"PC\\d+>")
            read_timeout: Timeout for reading output
            delay_factor: Not used (kept for signature compatibility)
            max_loops: Not used (kept for signature compatibility)
            strip_prompt: Remove prompt from output (default: False for debugging)
            strip_command: Remove command from output (default: False for debugging)
            normalize: Not used for VPCS
            use_textfsm: Not used for VPCS

        Returns:
            Command output from VPCS
        """
        # Use VPCS prompt as default expect_string
        if expect_string is None:
            expect_string = r"PC\d+>"

        # CRITICAL: Match telnetlib3 behavior exactly
        # tn.write(command.encode(encoding="ascii") + b"\n")
        cmd_bytes = command_string.encode(encoding="ascii") + b"\n"
        self.remote_conn.write(cmd_bytes)

        logger.debug("VPCS: Sent command '%s' (%d bytes)", command_string, len(cmd_bytes))

        # Sleep for 5 seconds (matching telnetlib3: sleep(5))
        time.sleep(5)

        # Wait for prompt pattern and capture output
        # This matches telnetlib3: tn.expect([rb"PC\d+>"]) + tn.read_very_eager()
        # read_until_pattern returns the output including the matched pattern
        try:
            output = self.read_until_pattern(pattern=expect_string, read_timeout=10)
            logger.debug("VPCS: read_until_pattern returned %d chars", len(output))
        except Exception as e:
            # If pattern not found, try to read whatever is available
            logger.debug("VPCS: Pattern not found, reading available output: %s", e)
            output = self.read_channel()
            logger.debug("VPCS: read_channel returned %d chars", len(output) if output else 0)

        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")

        logger.debug("VPCS: Raw output before strip: '%s'", output)

        # Strip ANSI escape codes from VPCS output
        # VPCS uses terminal formatting codes (bold, underline, etc.)
        # that need to be removed for clean output parsing
        output = self._strip_ansi_codes(output)

        # Strip command and prompt if requested (currently disabled for debugging)
        if strip_command:
            output = self.strip_command_packets(command_string, output)
        if strip_prompt:
            output = self.strip_prompt(output)

        logger.debug("VPCS: Final output after strip: '%s'", output)

        return output

    def send_command_timing(
        self,
        command_string: str,
        delay_factor: float | None = None,
        max_loops: int | None = None,
        strip_prompt: bool = True,
        strip_command: bool = True,
        normalize: bool = False,
    ) -> str:
        """
        Send command using timing-based delay.

        For VPCS, timing-based and pattern-based methods are identical,
        both use the telnetlib3 implementation pattern with fixed 5s delay.

        Args:
            command_string: The command to send
            delay_factor: Not used (fixed 5s delay for VPCS)
            max_loops: Not used (kept for signature compatibility)
            strip_prompt: Remove prompt from output
            strip_command: Remove command from output
            normalize: Not used for VPCS

        Returns:
            Command output from VPCS
        """
        # For VPCS, timing and pattern-based methods are identical
        return self.send_command(
            command_string=command_string,
            strip_prompt=strip_prompt,
            strip_command=strip_command,
        )

    def check_config_mode(
        self, check_string: str = "", pattern: str = "", force_regex: bool = False
    ) -> bool:
        """
        VPCS has no configuration mode.

        This method always returns False for VPCS devices.

        Returns:
            False (VPCS has no config mode)
        """
        return False

    def _strip_ansi_codes(self, text: str) -> str:
        """
        Strip ANSI escape codes from VPCS output.

        VPCS uses terminal formatting codes (bold, underline, colors, etc.)
        that need to be removed for clean output parsing. This method removes
        all ANSI escape sequences from the given text.

        Examples of codes removed:
        - [1m - Bold text
        - [0m - Reset formatting
        - [4m - Underline text
        - [30-47m - Color codes

        Args:
            text: Text potentially containing ANSI escape codes

        Returns:
            Text with all ANSI escape codes removed
        """
        return ANSI_ESCAPE_PATTERN.sub("", text)

    def config_mode(
        self, config_command: str = "", pattern: str = "", re_flags: int = 0
    ) -> str:
        """
        VPCS has no configuration mode.

        This method returns an empty string for VPCS devices.

        Returns:
            Empty string (no config mode to enter)
        """
        return ""

    def exit_config_mode(self, exit_config: str = "", pattern: str = "") -> str:
        """
        VPCS has no configuration mode.

        This method returns an empty string for VPCS devices.

        Returns:
            Empty string (no config mode to exit)
        """
        return ""

    def disable_paging(
        self,
        command: str = "",
        delay_factor: float | None = None,
        **kwargs,
    ) -> str:
        """
        VPCS doesn't use paging.

        This method returns an empty string for VPCS devices.

        Returns:
            Empty string (no paging to disable)
        """
        return ""


# Register the custom device type with Netmiko
_registered = False  # Flag to prevent duplicate registration

def register_custom_device_type() -> None:
    """
    Register the custom VPCS Telnet device type with Netmiko.

    This function adds 'gns3_vpcs_telnet' to Netmiko's CLASS_MAPPER
    and updates the platforms lists.

    IMPORTANT: This function should be called BEFORE using the VPCS device
    type with Netmiko.

    Note: This function is idempotent - multiple calls will only register once.
    """
    global _registered

    # Prevent duplicate registration
    if _registered:
        logger.debug("VPCS Telnet device type already registered, skipping")
        return

    # Use importlib to avoid namespace conflicts
    sd = importlib.import_module("netmiko.ssh_dispatcher")

    # Register the device type in both mappers
    # CLASS_MAPPER_BASE is used for base class definitions
    sd.CLASS_MAPPER_BASE["gns3_vpcs_telnet"] = VPCSTelnet

    # CLASS_MAPPER is used by ConnectHandler for device type validation
    sd.CLASS_MAPPER["gns3_vpcs_telnet"] = VPCSTelnet

    # CRITICAL: Update the static platforms lists
    # These lists are computed at module import time and won't
    # automatically update when CLASS_MAPPER is modified.
    # We need to manually rebuild them.

    # Recalculate platforms list
    sd.platforms = list(sd.CLASS_MAPPER.keys())
    sd.platforms.sort()

    # Recalculate platforms_base list
    sd.platforms_base = list(sd.CLASS_MAPPER_BASE.keys())
    sd.platforms_base.sort()

    # Recalculate telnet_platforms list
    sd.telnet_platforms = [x for x in sd.platforms if "telnet" in x]

    # Rebuild the platform strings used in error messages
    sd.platforms_str = "\n" + "\n".join(sd.platforms_base)
    sd.telnet_platforms_str = "\n" + "\n".join(sd.telnet_platforms)

    # Mark as registered
    _registered = True

    logger.info("Successfully registered VPCS Telnet device type with Netmiko")


# Auto-register on import
# This ensures the device type is available when the module is imported
try:
    register_custom_device_type()
except Exception as e:
    # Log but don't fail on import
    logger.warning(
        "Failed to register VPCS device type: %s",
        e,
        exc_info=True
    )
