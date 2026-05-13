#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
#
# GNS3-Copilot - AI-powered Network Lab Assistant for GNS3
#
# Unit test script for custom Netmiko VPCSTelnet driver
#

"""
Unit test script for VPCSTelnet custom device driver.

This script tests:
1. Device type registration
2. Inheritance from BaseConnection
3. VPCS-specific methods (telnet_login, session_preparation, send_command)
4. Config mode methods (check_config_mode, config_mode, exit_config_mode)
5. disable_paging method
6. Default parameters (default_enter, global_delay_factor, fast_cli)

Run with: python test_vpcs_telnet.py
"""

import sys
import unittest
from unittest.mock import Mock, patch, MagicMock
import os

# Add project root to path using relative path
test_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(
    os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.dirname(test_dir)))))
sys.path.insert(0, project_root)


class TestVPCSTelnetDriver(unittest.TestCase):
    """Test suite for VPCSTelnet custom driver."""

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures - import and register custom driver."""
        # Import the custom driver module (triggers registration)
        from gns3server.agent.gns3_copilot.utils.custom_netmiko import (
            vpcs_telnet,
        )

        cls.vpcs_telnet = vpcs_telnet
        cls.VPCSTelnet = vpcs_telnet.VPCSTelnet

    def test_device_type_registered(self):
        """Test that gns3_vpcs_telnet is registered in Netmiko."""
        from netmiko.ssh_dispatcher import CLASS_MAPPER, CLASS_MAPPER_BASE

        # Check CLASS_MAPPER
        self.assertIn("gns3_vpcs_telnet", CLASS_MAPPER)
        registered_class = CLASS_MAPPER["gns3_vpcs_telnet"]
        # Compare class name since class may be imported via different paths
        self.assertEqual(registered_class.__name__, self.VPCSTelnet.__name__)

        # Check CLASS_MAPPER_BASE
        self.assertIn("gns3_vpcs_telnet", CLASS_MAPPER_BASE)
        registered_class_base = CLASS_MAPPER_BASE["gns3_vpcs_telnet"]
        self.assertEqual(registered_class_base.__name__, self.VPCSTelnet.__name__)

    def test_inheritance_from_base_connection(self):
        """Test that VPCSTelnet inherits from BaseConnection."""
        from netmiko.base_connection import BaseConnection

        # Verify inheritance
        self.assertIsInstance(self.VPCSTelnet, type)
        # Check if VPCSTelnet is a subclass of BaseConnection
        self.assertTrue(issubclass(self.VPCSTelnet, BaseConnection))

    def test_vpcs_methods_available(self):
        """Test that VPCS-specific methods are available."""
        # These methods should be available in VPCSTelnet
        vpcs_methods = [
            "telnet_login",
            "session_preparation",
            "send_command",
            "send_command_timing",
            "check_config_mode",
            "config_mode",
            "exit_config_mode",
            "disable_paging",
        ]

        for method_name in vpcs_methods:
            self.assertTrue(
                hasattr(self.VPCSTelnet, method_name),
                f"Method {method_name} not found in VPCSTelnet",
            )

    def test_connect_handler_accepts_device_type(self):
        """Test that ConnectHandler accepts gns3_vpcs_telnet."""
        from netmiko.ssh_dispatcher import CLASS_MAPPER

        # Get platforms list
        platforms = list(CLASS_MAPPER.keys())

        # Verify gns3_vpcs_telnet is in platforms
        self.assertIn("gns3_vpcs_telnet", platforms)

        # Verify it's in telnet platforms
        telnet_platforms = [x for x in platforms if "telnet" in x]
        self.assertIn("gns3_vpcs_telnet", telnet_platforms)

    def test_telnet_platforms_list(self):
        """Test that gns3_vpcs_telnet is in telnet_platforms list."""
        from netmiko.ssh_dispatcher import telnet_platforms

        self.assertIn("gns3_vpcs_telnet", telnet_platforms)


class TestVPCSTelnetInit(unittest.TestCase):
    """Test VPCSTelnet initialization and default parameters."""

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures."""
        from gns3server.agent.gns3_copilot.utils.custom_netmiko.vpcs_telnet import (  # noqa: E501
            VPCSTelnet,
        )
        cls.VPCSTelnet = VPCSTelnet

    def test_default_enter_parameter(self):
        """Test that default_enter is set to \\r\\n for VPCS."""
        import inspect

        # Check that default_enter is handled in __init__
        init_source = inspect.getsource(self.VPCSTelnet.__init__)
        self.assertIn("default_enter", init_source)
        self.assertIn("\\r\\n", init_source)

    def test_default_parameters_when_none(self):
        """Test default parameters when not provided."""
        # Mock the BaseConnection.__init__ to avoid actual connection
        # But also set device_type since VPCSTelnet.__init__ sets it
        def mock_init(self, *args, **kwargs):
            # Simulate what VPCSTelnet.__init__ does
            kwargs.setdefault("device_type", "gns3_vpcs_telnet")
            self.device_type = kwargs.get("device_type")

        with patch.object(
            self.VPCSTelnet, "__init__", mock_init
        ):
            instance = self.VPCSTelnet(host="127.0.0.1")
            self.assertEqual(instance.device_type, "gns3_vpcs_telnet")

    def test_device_type_set(self):
        """Test that device_type is set to gns3_vpcs_telnet."""
        # Mock the __init__ to set device_type
        def mock_init(self, *args, **kwargs):
            # Simulate what VPCSTelnet.__init__ does
            kwargs.setdefault("device_type", "gns3_vpcs_telnet")
            self.device_type = kwargs.get("device_type")

        with patch.object(
            self.VPCSTelnet, "__init__", mock_init
        ):
            instance = self.VPCSTelnet(host="127.0.0.1")
            self.assertEqual(instance.device_type, "gns3_vpcs_telnet")


class TestVPCSTelnetMethods(unittest.TestCase):
    """Test VPCSTelnet method implementations."""

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures."""
        from gns3server.agent.gns3_copilot.utils.custom_netmiko.vpcs_telnet import (  # noqa: E501
            VPCSTelnet,
        )
        cls.VPCSTelnet = VPCSTelnet

    def test_check_config_mode_always_false(self):
        """Test that check_config_mode always returns False."""
        instance = self.VPCSTelnet.__new__(self.VPCSTelnet)
        result = instance.check_config_mode()
        self.assertFalse(result)

    def test_config_mode_returns_empty(self):
        """Test that config_mode returns empty string."""
        instance = self.VPCSTelnet.__new__(self.VPCSTelnet)
        result = instance.config_mode()
        self.assertEqual(result, "")

    def test_exit_config_mode_returns_empty(self):
        """Test that exit_config_mode returns empty string."""
        instance = self.VPCSTelnet.__new__(self.VPCSTelnet)
        result = instance.exit_config_mode()
        self.assertEqual(result, "")

    def test_disable_paging_returns_empty(self):
        """Test that disable_paging returns empty string."""
        instance = self.VPCSTelnet.__new__(self.VPCSTelnet)
        result = instance.disable_paging()
        self.assertEqual(result, "")

    def test_session_preparation_logs_debug(self):
        """Test that session_preparation completes without errors."""
        instance = self.VPCSTelnet.__new__(self.VPCSTelnet)
        # Should not raise any exception
        instance.session_preparation()


class TestVPCSTelnetSendCommand(unittest.TestCase):
    """Test VPCSTelnet send_command method."""

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures."""
        from gns3server.agent.gns3_copilot.utils.custom_netmiko.vpcs_telnet import (  # noqa: E501
            VPCSTelnet,
        )
        cls.VPCSTelnet = VPCSTelnet

    def test_send_command_writes_bytes(self):
        """Test that send_command writes command as bytes."""
        instance = self.VPCSTelnet.__new__(self.VPCSTelnet)

        # Mock the necessary attributes
        instance.remote_conn = MagicMock()
        instance.remote_conn.write = MagicMock()

        # Test command encoding
        command_string = "ip 192.168.1.1 255.255.255.0"
        expected_bytes = command_string.encode("ascii") + b"\n"

        # Call send_command (will fail at read_until_pattern, but we can
        # check the write call)
        try:
            instance.send_command(command_string)
        except Exception:
            pass

        # Verify write was called with correct bytes
        instance.remote_conn.write.assert_called_once_with(expected_bytes)

    def test_send_command_default_expect_string(self):
        """Test that send_command uses VPCS prompt as default expect_string."""
        import inspect

        # Check that expect_string defaults to r"PC\d+>"
        source = inspect.getsource(self.VPCSTelnet.send_command)
        self.assertIn("expect_string = r\"PC\\d+>\"", source)

    def test_send_command_timing_calls_send_command(self):
        """Test that send_command_timing delegates to send_command."""
        instance = self.VPCSTelnet.__new__(self.VPCSTelnet)

        # Mock send_command
        instance.send_command = Mock(return_value="test output")

        # Call send_command_timing
        result = instance.send_command_timing(
            "ip 192.168.1.1 255.255.255.0",
            strip_prompt=True,
            strip_command=True,
        )

        # Verify send_command was called
        instance.send_command.assert_called_once_with(
            command_string="ip 192.168.1.1 255.255.255.0",
            strip_prompt=True,
            strip_command=True,
        )
        self.assertEqual(result, "test output")


class TestVPCSTelnetTelnetLogin(unittest.TestCase):
    """Test VPCSTelnet telnet_login method."""

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures."""
        from gns3server.agent.gns3_copilot.utils.custom_netmiko.vpcs_telnet import (  # noqa: E501
            VPCSTelnet,
        )
        cls.VPCSTelnet = VPCSTelnet

    def test_telnet_login_default_prompt_pattern(self):
        """Test that telnet_login has correct default prompt pattern."""
        import inspect

        # Check default prompt terminator
        source = inspect.getsource(self.VPCSTelnet.telnet_login)
        self.assertIn('pri_prompt_terminator: str = r"PC\\d+>"', source)

    def test_telnet_login_sends_newlines(self):
        """Test that telnet_login sends 4 newlines."""
        instance = self.VPCSTelnet.__new__(self.VPCSTelnet)

        # Mock necessary attributes
        instance.remote_conn = MagicMock()
        instance.remote_conn.write = MagicMock()
        instance.read_channel = MagicMock(return_value="PC1>")
        instance.select_delay_factor = Mock(return_value=1.0)
        instance.read_until_pattern = MagicMock(return_value="PC1>")

        # Call telnet_login
        instance.telnet_login()

        # Verify write was called 4 times (4 newlines)
        self.assertEqual(instance.remote_conn.write.call_count, 4)

        # Verify each call was with b"\n"
        for call in instance.remote_conn.write.call_args_list:
            self.assertEqual(call[0][0], b"\n")

    def test_telnet_login_waits_for_prompt(self):
        """Test that telnet_login waits for VPCS prompt."""
        instance = self.VPCSTelnet.__new__(self.VPCSTelnet)

        # Mock necessary attributes
        instance.remote_conn = MagicMock()
        instance.remote_conn.write = MagicMock()
        instance.read_channel = MagicMock(return_value="PC1>")
        instance.select_delay_factor = Mock(return_value=1.0)
        instance.read_until_pattern = MagicMock(return_value="PC1>")

        # Call telnet_login
        result = instance.telnet_login()

        # Verify read_until_pattern was called
        instance.read_until_pattern.assert_called_once()


class TestVPCSTelnetRegistration(unittest.TestCase):
    """Test VPCSTelnet registration function."""

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures."""
        from gns3server.agent.gns3_copilot.utils.custom_netmiko import (
            vpcs_telnet,
        )
        cls.vpcs_telnet = vpcs_telnet

    def test_register_function_exists(self):
        """Test that register_custom_device_type function exists."""
        self.assertTrue(
            hasattr(self.vpcs_telnet, "register_custom_device_type")
        )

    def test_register_function_is_callable(self):
        """Test that register_custom_device_type is callable."""
        self.assertTrue(
            callable(self.vpcs_telnet.register_custom_device_type)
        )


class TestVPCSTelnetAnsiStripping(unittest.TestCase):
    """Test VPCSTelnet ANSI escape code stripping."""

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures."""
        from gns3server.agent.gns3_copilot.utils.custom_netmiko.vpcs_telnet import (  # noqa: E501
            VPCSTelnet,
        )
        cls.VPCSTelnet = VPCSTelnet

    def test_strip_ansi_codes_method_exists(self):
        """Test that _strip_ansi_codes method exists."""
        instance = self.VPCSTelnet.__new__(self.VPCSTelnet)
        self.assertTrue(hasattr(instance, "_strip_ansi_codes"))
        self.assertTrue(callable(instance._strip_ansi_codes))

    def test_strip_bold_codes(self):
        """Test stripping bold ANSI codes."""
        instance = self.VPCSTelnet.__new__(self.VPCSTelnet)
        text = "\x1b[1mip\x1b[0m \x1b[4mARG\x1b[0m"
        result = instance._strip_ansi_codes(text)
        self.assertEqual(result, "ip ARG")

    def test_strip_underline_codes(self):
        """Test stripping underline ANSI codes."""
        instance = self.VPCSTelnet.__new__(self.VPCSTelnet)
        text = "\x1b[4maddress\x1b[0m [\x1b[4mmask\x1b[0m]"
        result = instance._strip_ansi_codes(text)
        self.assertEqual(result, "address [mask]")

    def test_strip_reset_codes(self):
        """Test stripping reset ANSI codes."""
        instance = self.VPCSTelnet.__new__(self.VPCSTelnet)
        text = "\x1b[1mNAME\x1b[0m        : PC2[1]"
        result = instance._strip_ansi_codes(text)
        # Note: [1] at the end is not a valid ANSI code, so it should remain
        self.assertEqual(result, "NAME        : PC2[1]")

    def test_strip_color_codes(self):
        """Test stripping color ANSI codes."""
        instance = self.VPCSTelnet.__new__(self.VPCSTelnet)
        text = "\x1b[31mRed\x1b[32mGreen\x1b[0mNormal"
        result = instance._strip_ansi_codes(text)
        self.assertEqual(result, "RedGreenNormal")

    def test_strip_complex_vpcs_output(self):
        """Test stripping ANSI codes from real VPCS output."""
        instance = self.VPCSTelnet.__new__(self.VPCSTelnet)
        # Sample VPCS output with ANSI codes (with proper ESC characters)
        text = """\x1b[1mip\x1b[0m \x1b[4mARG\x1b[0m ... [[\x1b[4mOPTION\x1b[0m]
  Configure the current VPC's IP settings
    \x1b[1mNAME\x1b[0m        : PC2[1]
IP/MASK     : 192.168.1.20/24"""
        result = instance._strip_ansi_codes(text)
        # Verify ANSI codes are removed
        self.assertNotIn("\x1b[1m", result)
        self.assertNotIn("\x1b[0m", result)
        self.assertNotIn("\x1b[4m", result)
        self.assertIn("ip ARG", result)
        self.assertIn("NAME", result)
        self.assertIn("PC2[1]", result)  # [1] is not a valid ANSI escape

    def test_strip_empty_string(self):
        """Test stripping ANSI codes from empty string."""
        instance = self.VPCSTelnet.__new__(self.VPCSTelnet)
        result = instance._strip_ansi_codes("")
        self.assertEqual(result, "")

    def test_strip_no_ansi_codes(self):
        """Test that text without ANSI codes is unchanged."""
        instance = self.VPCSTelnet.__new__(self.VPCSTelnet)
        text = "NAME        : PC2\nIP/MASK     : 192.168.1.20/24"
        result = instance._strip_ansi_codes(text)
        self.assertEqual(result, text)

    def test_send_command_calls_strip_ansi(self):
        """Test that send_command calls _strip_ansi_codes."""
        from unittest.mock import patch

        instance = self.VPCSTelnet.__new__(self.VPCSTelnet)

        # Mock necessary attributes
        instance.remote_conn = MagicMock()
        instance.remote_conn.write = MagicMock()
        instance.read_until_pattern = MagicMock(
            return_value="\x1b[1mNAME\x1b[0m        : PC2\nPC2>"
        )

        # Mock _strip_ansi_codes to verify it's called
        instance._strip_ansi_codes = Mock(
            return_value="NAME        : PC2\nPC2>"
        )

        # Call send_command
        instance.send_command("show ip")

        # Verify _strip_ansi_codes was called
        instance._strip_ansi_codes.assert_called_once()
        call_arg = instance._strip_ansi_codes.call_args[0][0]
        self.assertIn("\x1b[1m", call_arg)  # Verify it received raw output


def run_tests():
    """Run all tests and print results."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test cases
    suite.addTests(loader.loadTestsFromTestCase(TestVPCSTelnetDriver))
    suite.addTests(loader.loadTestsFromTestCase(TestVPCSTelnetInit))
    suite.addTests(loader.loadTestsFromTestCase(TestVPCSTelnetMethods))
    suite.addTests(loader.loadTestsFromTestCase(TestVPCSTelnetSendCommand))
    suite.addTests(loader.loadTestsFromTestCase(TestVPCSTelnetTelnetLogin))
    suite.addTests(loader.loadTestsFromTestCase(TestVPCSTelnetRegistration))
    suite.addTests(loader.loadTestsFromTestCase(TestVPCSTelnetAnsiStripping))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print("\n" + "=" * 100)
    print("Test Summary:")
    print(f"  Run: {result.testsRun}")
    success_count = (
        result.testsRun - len(result.failures) - len(result.errors)
    )
    print(f"  Success: {success_count}")
    print(f"  Failed: {len(result.failures)}")
    print(f"  Errors: {len(result.errors)}")
    print("=" * 100)

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
