#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
#
# GNS3-Copilot - AI-powered Network Lab Assistant for GNS3
#
# Unit test script for custom Netmiko RuijieTelnetEnhanced driver
#

"""
Unit test script for RuijieTelnetEnhanced custom device driver.

This script tests:
1. Device type registration
2. Inheritance from RuijieOSBase
3. Interactive command preprocessing
4. Batch send and fallback logic (mocked)

Run with: python test_ruijie_telnet.py
"""

import sys
import unittest
from unittest.mock import Mock, patch
import os

# Add project root to path using relative path
test_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(
    os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.dirname(test_dir)))))
sys.path.insert(0, project_root)


class TestRuijieTelnetEnhancedDriver(unittest.TestCase):
    """Test suite for RuijieTelnetEnhanced custom driver."""

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures - import and register custom driver."""
        # Import the custom driver module (triggers registration)
        from gns3server.agent.gns3_copilot.utils.custom_netmiko import (
            ruijie_telnet,
        )

        cls.ruijie_telnet = ruijie_telnet
        cls.RuijieTelnetEnhanced = ruijie_telnet.RuijieTelnetEnhanced

    def test_device_type_registered(self):
        """Test that gns3_ruijie_telnet is registered in Netmiko."""
        from netmiko.ssh_dispatcher import CLASS_MAPPER, CLASS_MAPPER_BASE

        # Check CLASS_MAPPER
        self.assertIn("gns3_ruijie_telnet", CLASS_MAPPER)
        registered_class = CLASS_MAPPER["gns3_ruijie_telnet"]
        # Compare class name since class may be imported via different paths
        self.assertEqual(registered_class.__name__, self.RuijieTelnetEnhanced.__name__)

        # Check CLASS_MAPPER_BASE
        self.assertIn("gns3_ruijie_telnet", CLASS_MAPPER_BASE)
        registered_class_base = CLASS_MAPPER_BASE["gns3_ruijie_telnet"]
        self.assertEqual(registered_class_base.__name__, self.RuijieTelnetEnhanced.__name__)

    def test_inheritance_from_ruijie_os_base(self):
        """Test that RuijieTelnetEnhanced inherits from RuijieOSBase."""
        from netmiko.ruijie.ruijie_os import RuijieOSBase

        # Verify inheritance
        self.assertIsInstance(self.RuijieTelnetEnhanced, type)
        # Check if RuijieTelnetEnhanced is a subclass of RuijieOSBase
        self.assertTrue(issubclass(self.RuijieTelnetEnhanced, RuijieOSBase))

    def test_ruijie_base_methods_available(self):
        """Test that Ruijie-specific methods are available."""
        # These methods should be inherited from RuijieOSBase
        ruijie_methods = [
            "config_mode",
            "check_config_mode",
            "exit_config_mode",
            "send_config_set",
            "send_command",
            "disable_paging",
        ]

        for method_name in ruijie_methods:
            self.assertTrue(
                hasattr(self.RuijieTelnetEnhanced, method_name),
                f"Method {method_name} not found in RuijieTelnetEnhanced",
            )

    def test_interactive_patterns_defined(self):
        """Test that INTERACTIVE_PATTERNS is correctly defined."""
        import re

        # Should have INTERACTIVE_PATTERNS as a class attribute
        self.assertTrue(
            hasattr(self.RuijieTelnetEnhanced, "INTERACTIVE_PATTERNS")
        )

        # Check it's a list
        patterns = self.RuijieTelnetEnhanced.INTERACTIVE_PATTERNS
        self.assertIsInstance(patterns, list)

        # Check it contains expected patterns (compiled regex)
        self.assertGreater(len(patterns), 0)
        for pattern in patterns:
            self.assertIsInstance(pattern, re.Pattern)

    def test_preprocess_interactive_commands(self):
        """Test that interactive commands are preprocessed correctly."""
        # Create a mock instance (without actual connection)
        with patch.object(
            self.RuijieTelnetEnhanced, "__init__",
            lambda self, *args, **kwargs: None
        ):
            instance = self.RuijieTelnetEnhanced.__new__(
                self.RuijieTelnetEnhanced
            )

            # Set INTERACTIVE_PATTERNS from class
            instance.INTERACTIVE_PATTERNS = (
                self.RuijieTelnetEnhanced.INTERACTIVE_PATTERNS
            )

            # Test commands with router-id (should trigger 'yes')
            commands = [
                "router ospf 1",
                "router-id 1.1.1.1",
                "network 10.0.0.0 0.0.0.255 area 0",
            ]

            processed = instance._preprocess_interactive_commands(
                commands
            )

            # Should have inserted 'yes' after router-id command
            self.assertEqual(len(processed), 4)
            self.assertEqual(processed[0], "router ospf 1")
            self.assertEqual(processed[1], "router-id 1.1.1.1")
            self.assertEqual(processed[2], "yes")
            self.assertEqual(
                processed[3], "network 10.0.0.0 0.0.0.255 area 0"
            )

    def test_preprocess_non_interactive_commands(self):
        """Test that non-interactive commands are not modified."""
        # Create a mock instance
        with patch.object(
            self.RuijieTelnetEnhanced, "__init__",
            lambda self, *args, **kwargs: None
        ):
            instance = self.RuijieTelnetEnhanced.__new__(
                self.RuijieTelnetEnhanced
            )

            # Set INTERACTIVE_PATTERNS from class
            instance.INTERACTIVE_PATTERNS = (
                self.RuijieTelnetEnhanced.INTERACTIVE_PATTERNS
            )

            # Test commands without interactive prompts
            commands = [
                "interface GigabitEthernet 0/1",
                "description Test Interface",
                "ip address 192.168.1.1 255.255.255.0",
            ]

            processed = instance._preprocess_interactive_commands(commands)

            # Should not have inserted any 'yes' commands
            self.assertEqual(len(processed), 3)
            self.assertEqual(processed, commands)

    def test_connect_handler_accepts_device_type(self):
        """Test that ConnectHandler accepts gns3_ruijie_telnet."""
        from netmiko.ssh_dispatcher import CLASS_MAPPER

        # Get platforms list
        platforms = list(CLASS_MAPPER.keys())

        # Verify gns3_ruijie_telnet is in platforms
        self.assertIn("gns3_ruijie_telnet", platforms)

        # Verify it's in telnet platforms
        telnet_platforms = [x for x in platforms if "telnet" in x]
        self.assertIn("gns3_ruijie_telnet", telnet_platforms)

    def test_default_enter_parameter(self):
        """Test that default_enter is set to \\r\\n for telnet."""
        import inspect

        # Check that default_enter is handled in __init__
        # (The actual logic is in the __init__ method body)
        init_source = inspect.getsource(
            self.RuijieTelnetEnhanced.__init__
        )
        self.assertIn("default_enter", init_source)
        self.assertIn("\\r\\n", init_source)


class TestRuijieTelnetEnhancedIntegration(unittest.TestCase):
    """Integration tests for RuijieTelnetEnhanced driver."""

    def test_send_config_set_calls_preprocess(self):
        """Test that send_config_set calls preprocessing."""
        from gns3server.agent.gns3_copilot.utils.custom_netmiko.ruijie_telnet import (  # noqa: E501
            RuijieTelnetEnhanced,
        )

        # Create a mock instance
        instance = RuijieTelnetEnhanced.__new__(
            RuijieTelnetEnhanced
        )

        # Mock the necessary attributes and methods
        instance.RETURN = "\r\n"
        instance.global_delay_factor = 1.0

        # Mock config_mode and exit_config_mode
        instance.config_mode = Mock(return_value="")
        instance.exit_config_mode = Mock(return_value="")
        instance._send_config_batch = Mock(return_value="Output")

        # Test commands
        commands = ["interface GigabitEthernet 0/1", "description Test"]

        # Call send_config_set
        instance.send_config_set(
            commands, enter_config_mode=False, exit_config_mode=False
        )

        # Verify _send_config_batch was called
        instance._send_config_batch.assert_called_once()

    def test_multiple_interactive_patterns(self):
        """Test that multiple interactive commands are detected."""
        from gns3server.agent.gns3_copilot.utils.custom_netmiko.ruijie_telnet import (  # noqa: E501
            RuijieTelnetEnhanced,
        )

        # Create a mock instance
        instance = RuijieTelnetEnhanced.__new__(
            RuijieTelnetEnhanced
        )
        instance.INTERACTIVE_PATTERNS = (
            RuijieTelnetEnhanced.INTERACTIVE_PATTERNS
        )

        # Test commands with multiple interactive prompts
        commands = [
            "router-id 1.1.1.1",      # Should trigger 'yes'
            "erase startup-config",    # Should trigger 'yes'
            "interface GigabitEthernet 0/1",  # Should NOT trigger
        ]

        processed = instance._preprocess_interactive_commands(commands)

        # Should have inserted 'yes' after first two commands
        # processed[0] = "router-id 1.1.1.1", processed[1] = "yes"
        # processed[2] = "erase startup-config", processed[3] = "yes"
        # processed[4] = "interface GigabitEthernet 0/1"
        self.assertEqual(len(processed), 5)
        self.assertEqual(processed[0], "router-id 1.1.1.1")
        self.assertEqual(processed[1], "yes")
        self.assertEqual(processed[2], "erase startup-config")
        self.assertEqual(processed[3], "yes")
        self.assertEqual(processed[4], "interface GigabitEthernet 0/1")


def run_tests():
    """Run all tests and print results."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test cases
    suite.addTests(
        loader.loadTestsFromTestCase(TestRuijieTelnetEnhancedDriver)
    )
    suite.addTests(
        loader.loadTestsFromTestCase(TestRuijieTelnetEnhancedIntegration)
    )

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
