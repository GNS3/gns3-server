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

# Mypy type checking is disabled for this module due to Netmiko library
# limitations.
#
# Reason: Netmiko does not provide type stubs (py.typed marker), which
# causes mypy to generate errors when importing and using Netmiko classes.
# The main issues are:
#
# 1. Missing library stubs for 'netmiko.huawei.huawei' module
# 2. Dynamic attribute assignments on netmiko.ssh_dispatcher module
#    (platforms, platforms_base, telnet_platforms, etc.) that mypy cannot
#    detect
# 3. Inheritance from HuaweiBase triggers 'import-untyped' errors
#
# Since Netmiko is a third-party library without type annotations, and this
# module is a runtime driver that extends Netmiko's functionality, type
# checking would require maintaining separate type stub files which is
# beyond the scope of this project.
#
# Alternative solutions considered:
# - Adding type stubs for Netmiko (too extensive, requires ongoing
#   maintenance)
# - Using 'type: ignore' on specific lines (too many annotations needed)
# - Disabling only specific mypy errors (still noisy, doesn't address
#   root cause)
#
# Solution: Disable mypy for this entire file. Runtime testing and
# integration tests ensure correctness. Netmiko's own test suite validates
# base functionality.
#
# mypy: ignore-errors

"""
Custom Netmiko device driver for Huawei devices in GNS3 emulation environment.

This module provides a custom device type 'gns3_huawei_telnet_ce' for Huawei
network devices that connect via console without requiring authentication
(username/password).

This is specifically designed for GNS3 emulated Huawei devices
(e.g., CloudEngine series) where the console connection directly enters the
system view without login prompts.

Key Features:
- Inherits from HuaweiBase for proper VRP command handling
- Skips authentication (no username/password required)
- Supports Huawei-specific config mode (system-view)
- Handles Huawei prompt patterns (<>, [], >)
"""

import importlib
import logging
import re
import time

from netmiko.huawei.huawei import HuaweiBase

logger = logging.getLogger(__name__)


class GNS3HuaweiTelnetCE(HuaweiBase):
    """
    Custom Huawei device driver for GNS3 emulation.

    Inherits from HuaweiBase to leverage existing VRP-specific functionality:
    - system-view configuration mode
    - Huawei prompt patterns
    - Config mode detection and exit

    This driver overrides telnet_login to handle GNS3 devices that
    don't require authentication.
    """

    def __init__(
        self,
        *args,
        **kwargs,
    ) -> None:
        """Initialize GNS3HuaweiTelnetCE connection."""
        # Set default device type for proper initialization
        # The '_telnet' suffix in device_type tells Netmiko to use
        # Telnet protocol
        kwargs.setdefault("device_type", "huawei_telnet")

        # Huawei prompt patterns (inherited from HuaweiBase)
        # User view: <HUAWEI>
        # System view: [HUAWEI]
        # Interface view: [HUAWEI-GigabitEthernet0/0/1]

        super().__init__(*args, **kwargs)

    def telnet_login(
        self,
        pri_prompt_terminator: str = r"<\S+>|>\s*$",
        alt_prompt_terminator: str = r"\[\S+\]",
        username_pattern: str = r"(?:user:|username|login|user name)",
        pwd_pattern: str = r"assword",
        delay_factor: float = 1.0,
        max_loops: int = 10,
    ) -> str:
        """
        Telnet login for GNS3 Huawei devices (no authentication).

        Simplified login logic for devices that connect directly to
        command line without username/password prompts.

        Strategy:
        1. Clear any existing buffer data
        2. Send carriage returns to trigger prompt
        3. Wait for Huawei prompt pattern
        4. Return once prompt is detected

        Args:
            pri_prompt_terminator: Primary prompt pattern (e.g., <HUAWEI>)
            alt_prompt_terminator: Alternate prompt pattern (e.g., [HUAWEI])
            username_pattern: Not used (kept for signature compatibility)
            pwd_pattern: Not used (kept for signature compatibility)
            delay_factor: Delay factor for timing
            max_loops: Maximum wait loops

        Returns:
            Output from the connection process
        """
        delay_factor = self.select_delay_factor(delay_factor)
        output = ""
        return_msg = ""

        # Step 1: Clear buffer - read any existing data to avoid interference
        try:
            initial_data = self.read_channel()
            if initial_data:
                return_msg += initial_data
        except Exception:
            # Ignore errors during initial read
            pass

        # Step 2: Send carriage returns and wait for prompt
        for i in range(max_loops):
            try:
                # Send return to trigger prompt
                self.write_channel(self.RETURN)
                time.sleep(0.5 * delay_factor)

                # Read response
                new_output = self.read_channel()
                output = new_output
                return_msg += new_output

                # Check for Huawei prompt patterns
                # User view: <HUAWEI>, System view: [HUAWEI], or just >
                if re.search(pri_prompt_terminator, output, flags=re.M):
                    return return_msg
                if re.search(alt_prompt_terminator, output, flags=re.M):
                    return return_msg

            except EOFError:
                self.remote_conn.close()
                msg = f"Connection failed (EOF): {self.host}"
                raise self.connection_error(msg) from None
            except Exception:
                # Continue trying on other exceptions
                pass

        # Step 3: Final attempt - return what we have
        # Even if we couldn't detect the prompt clearly, the connection
        # might still be usable
        return return_msg

    def session_preparation(self) -> None:
        """
        Prepare the session after connection is established.

        Inherited from HuaweiBase, but ensures proper initialization
        for GNS3 emulation environment.
        """
        # Wait for prompt to stabilize
        time.sleep(0.5 * self.global_delay_factor)

        # Disable paging using Huawei-specific command
        try:
            self.disable_paging(command="screen-length 0 temporary")
        except Exception:
            # If disable_paging fails, try the parent implementation
            super().disable_paging()

        # Ensure we're in a clean state
        try:
            if hasattr(self, 'base_prompt') and self.base_prompt:
                self._test_channel_read(pattern=self.base_prompt)
            else:
                # If base_prompt is not set yet, just read to clear buffer
                self.read_channel()
        except Exception:
            pass

    def disable_paging(
        self,
        command: str = "screen-length 0 temporary",
        **kwargs,
    ) -> str:
        """
        Disable paging for Huawei devices.

        Uses Huawei-specific command 'screen-length 0 temporary'
        which disables paging for the current session only.

        Args:
            command: Command to disable paging

        Returns:
            Output from the disable paging command
        """
        return super().disable_paging(command=command, **kwargs)

    def send_config_set(
        self,
        config_commands: str | list[str],
        **kwargs,
    ) -> str:
        """
        Send configuration commands to Huawei device.

        Overrides the parent method to handle Huawei-specific behavior:
        - Uses Huawei-specific prompts (<...> for user view, [...] for
          system view)
        - Handles the 'return' confirmation prompt
        - Uses read_channel_timing for proper output collection

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

        # Get parameters with Huawei-specific defaults
        exit_config_mode = kwargs.get("exit_config_mode", True)
        # Longer timeout for GNS3 emulation
        read_timeout = kwargs.get("read_timeout", 30)
        delay_factor = self.global_delay_factor
        strip_prompt = kwargs.get("strip_prompt", False)
        strip_command = kwargs.get("strip_command", False)
        config_mode_command = kwargs.get("config_command", "system-view")

        output = ""

        # Enter config mode if needed
        if kwargs.get("enter_config_mode", True):
            output += self.config_mode(config_command=config_mode_command)

        # Send all configuration commands
        # Send all commands, then read all output at once
        for cmd in config_commands:
            self.write_channel(f"{cmd}{self.RETURN}")
            # Small delay between commands
            time.sleep(delay_factor * 0.05)

        # Use read_channel_timing to collect all output
        # This method keeps reading until there is no new data for
        # 'last_read' seconds. This is the proper Netmiko way to handle
        # command output
        output += self.read_channel_timing(
            read_timeout=read_timeout, last_read=2.0
        )

        # Exit config mode if requested
        if exit_config_mode:
            # For Huawei devices, commit configuration before exiting
            # This avoids the "Uncommitted configurations" [Y/N/C] prompt
            try:
                # Send commit command (in system view [HUAWEI])
                self.write_channel(f"commit{self.RETURN}")
                time.sleep(0.5 * self.global_delay_factor)
                commit_output = self.read_channel()
                output += commit_output
            except Exception:
                # If commit fails, continue with exit
                # (might not support commit)
                pass

            # Now exit config mode
            output += self.exit_config_mode()

        if strip_prompt:
            output = self.strip_prompt(output)

        if strip_command:
            output = self.strip_command(config_commands, output)

        return output

    def exit_config_mode(
        self, exit_config: str = "return", pattern: str = r"<\S+>|>\s*$"
    ) -> str:
        r"""
        Exit configuration mode for Huawei devices.

        Huawei devices display a confirmation prompt when using 'return':
          Return to user view? [y/n]:

        This method automatically answers 'y' to the prompt.

        Args:
            exit_config: Command to exit config mode (default: "return")
            pattern: Pattern to detect user view prompt
                     (default: r"<\S+>|>\s*$")

        Returns:
            Output from exiting config mode
        """
        # Check if we're currently in config mode
        if not self.check_config_mode():
            return ""

        output = ""
        # Send the exit command (write_channel returns None, don't concatenate)
        self.write_channel(f"{exit_config}{self.RETURN}")
        time.sleep(0.5 * self.global_delay_factor)

        # Look for the confirmation prompt
        # Huawei prompt: "Return to user view? [y/n]:"
        prompt_pattern = r"\[y/n\]"
        max_loops = 20  # More loops for slower devices

        for _ in range(max_loops):
            new_output = self.read_channel()
            output += new_output

            # If we see the confirmation prompt, send 'y'
            if re.search(prompt_pattern, new_output):
                self.write_channel(f"y{self.RETURN}")  # Returns None
                time.sleep(0.5 * self.global_delay_factor)
                # Clear the confirmation response
                new_output = self.read_channel()
                output += new_output

            # Check if we've exited to user view
            if re.search(pattern, new_output):
                return output

        # Final read to get remaining output
        new_output = self.read_channel()
        output += new_output

        return output


# Register the custom device type with Netmiko
_registered = False  # Flag to prevent duplicate registration

def register_custom_device_type() -> None:
    """
    Register the custom GNS3HuaweiTelnetCE device type with Netmiko.

    This function adds 'gns3_huawei_telnet_ce' to both Netmiko's CLASS_MAPPER
    and CLASS_MAPPER_BASE so it can be used like any other built-in device
    type.

    Additionally, it updates the static 'platforms' and 'telnet_platforms'
    lists which are used by ConnectHandler for device type validation.

    IMPORTANT: This function should be called BEFORE initializing Nornir
    or running any Netmiko tasks. Call it explicitly at the appropriate
    time.

    Note: This function is idempotent - multiple calls will only register once.

    Returns:
        None
    """
    global _registered

    # Prevent duplicate registration
    if _registered:
        logger.debug("Huawei CE device type already registered, skipping")
        return

    # Use importlib to avoid namespace conflicts
    # Import the module using importlib to ensure we get the module,
    # not a function
    sd = importlib.import_module("netmiko.ssh_dispatcher")

    # Register the device type in both mappers
    # CLASS_MAPPER_BASE is used for base class definitions
    sd.CLASS_MAPPER_BASE["gns3_huawei_telnet_ce"] = GNS3HuaweiTelnetCE

    # CLASS_MAPPER is used by ConnectHandler for device type validation
    sd.CLASS_MAPPER["gns3_huawei_telnet_ce"] = GNS3HuaweiTelnetCE

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

    logger.info("Successfully registered Huawei CE device type with Netmiko")


# Auto-register on import
# This ensures the device type is available when the module is imported
# NOTE: For Nornir scenarios, you may need to call this explicitly
# before InitNornir to ensure proper timing
try:
    register_custom_device_type()
except Exception as e:
    # Log but don't fail on import
    logger = logging.getLogger(__name__)
    logger.warning(
        f"Failed to register custom device type: {e}",
        exc_info=True
    )
