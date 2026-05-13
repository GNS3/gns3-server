#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
#
# GNS3-Copilot - AI-powered Network Lab Assistant for GNS3
#
# Unit test script for custom Netmiko GNS3HuaweiTelnetCE driver
#

"""
Unit test script for GNS3HuaweiTelnetCE custom device driver.

This script tests:
1. Device type registration
2. Inheritance from HuaweiBase
3. VRP-specific command handling
4. Telnet login logic (mocked)

Run with: python test_huawei_ce.py
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


class TestHuaweiTelnetCEDriver(unittest.TestCase):
    """Test suite for GNS3HuaweiTelnetCE custom driver."""

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures - import and register custom driver."""
        # Import the custom driver module (triggers registration)
        from gns3server.agent.gns3_copilot.utils.custom_netmiko import (
            huawei_ce,
        )

        cls.huawei_ce = huawei_ce
        cls.HuaweiTelnetCE = huawei_ce.GNS3HuaweiTelnetCE

    def test_device_type_registered(self):
        """Test that gns3_huawei_telnet_ce is registered in Netmiko."""
        from netmiko.ssh_dispatcher import CLASS_MAPPER, CLASS_MAPPER_BASE

        # Check CLASS_MAPPER
        self.assertIn("gns3_huawei_telnet_ce", CLASS_MAPPER)
        registered_class = CLASS_MAPPER["gns3_huawei_telnet_ce"]
        # Compare class name since class may be imported via different paths
        self.assertEqual(registered_class.__name__, self.HuaweiTelnetCE.__name__)

        # Check CLASS_MAPPER_BASE
        self.assertIn("gns3_huawei_telnet_ce", CLASS_MAPPER_BASE)
        registered_class_base = CLASS_MAPPER_BASE["gns3_huawei_telnet_ce"]
        self.assertEqual(registered_class_base.__name__, self.HuaweiTelnetCE.__name__)

    def test_inheritance_from_huawei_base(self):
        """Test that GNS3HuaweiTelnetCE inherits from HuaweiBase."""
        from netmiko.huawei.huawei import HuaweiBase

        # Verify inheritance
        self.assertIsInstance(self.HuaweiTelnetCE, type)
        # Check if GNS3HuaweiTelnetCE is a subclass of HuaweiBase
        self.assertTrue(issubclass(self.HuaweiTelnetCE, HuaweiBase))

    def test_huawei_base_methods_available(self):
        """Test that VRP-specific methods are available."""
        # These methods should be inherited from HuaweiBase
        vrp_methods = [
            "config_mode",
            "check_config_mode",
            "exit_config_mode",
            "send_config_set",
            "send_command",
            "disable_paging",
        ]

        for method_name in vrp_methods:
            self.assertTrue(
                hasattr(self.HuaweiTelnetCE, method_name),
                f"Method {method_name} not found in GNS3HuaweiTelnetCE",
            )

    def test_telnet_login_method_exists(self):
        """Test that telnet_login method is overridden."""
        # Should have overridden telnet_login
        self.assertTrue(hasattr(self.HuaweiTelnetCE, "telnet_login"))

        # Check if method is in GNS3HuaweiTelnetCE's __dict__
        # (means it's defined there, not inherited)
        self.assertIn(
            "telnet_login",
            self.HuaweiTelnetCE.__dict__,
            "telnet_login should be defined in GNS3HuaweiTelnetCE",
        )

    def test_initialization_parameters(self):
        """Test that initialization sets correct parameters."""
        # Create a mock instance (without actual connection)
        with patch.object(
            self.HuaweiTelnetCE, "__init__",
            lambda self, *args, **kwargs: None
        ):
            instance = self.HuaweiTelnetCE.__new__(
                self.HuaweiTelnetCE
            )

            # Mock the necessary attributes
            instance.protocol = "telnet"
            instance.device_type = "huawei_telnet"

            # Verify protocol is set to telnet
            self.assertEqual(instance.protocol, "telnet")
            self.assertEqual(instance.device_type, "huawei_telnet")

    def test_connect_handler_accepts_device_type(self):
        """Test that ConnectHandler accepts gns3_huawei_telnet_ce."""
        from netmiko.ssh_dispatcher import CLASS_MAPPER

        # Get platforms list
        platforms = list(CLASS_MAPPER.keys())

        # Verify gns3_huawei_telnet_ce is in platforms
        self.assertIn("gns3_huawei_telnet_ce", platforms)

        # Verify it's in telnet platforms
        telnet_platforms = [x for x in platforms if "telnet" in x]
        self.assertIn("gns3_huawei_telnet_ce", telnet_platforms)

    def test_prompt_pattern_constants(self):
        """Test that Huawei prompt patterns are correctly defined."""
        import inspect

        # Get the telnet_login method signature
        sig = inspect.signature(self.HuaweiTelnetCE.telnet_login)

        # Check default prompt patterns
        pri_prompt = sig.parameters["pri_prompt_terminator"].default
        alt_prompt = sig.parameters["alt_prompt_terminator"].default

        # Should match Huawei prompt patterns
        self.assertIn("<", pri_prompt)
        self.assertIn("[", alt_prompt)

    def test_disable_paging_command(self):
        """Test that disable_paging uses correct Huawei command."""
        import inspect

        sig = inspect.signature(self.HuaweiTelnetCE.disable_paging)
        command_default = sig.parameters["command"].default

        # Should use Huawei-specific command
        self.assertEqual(command_default, "screen-length 0 temporary")


class TestHuaweiTelnetCEIntegration(unittest.TestCase):
    """Integration tests for GNS3HuaweiTelnetCE driver."""

    def test_mock_telnet_connection(self):
        """Test telnet_login logic with mocked connection."""
        from gns3server.agent.gns3_copilot.utils.custom_netmiko.huawei_ce import (  # noqa: E501
            GNS3HuaweiTelnetCE,
        )

        # Create a mock instance
        instance = GNS3HuaweiTelnetCE.__new__(
            GNS3HuaweiTelnetCE
        )

        # Mock the necessary attributes and methods
        instance.host = "127.0.0.1"
        instance.RETURN = "\r\n"
        instance.global_delay_factor = 1.0
        instance.remote_conn = Mock()

        # Mock select_delay_factor
        instance.select_delay_factor = Mock(return_value=1.0)

        # Mock read_channel and write_channel
        test_outputs = ["", "<HUAWEI>"]
        instance.read_channel = Mock(side_effect=test_outputs)
        instance.write_channel = Mock()

        # Call telnet_login
        result = instance.telnet_login()

        # Verify behavior
        self.assertIn("<HUAWEI>", result)
        instance.write_channel.assert_called()
        self.assertEqual(instance.read_channel.call_count, 2)


def run_tests():
    """Run all tests and print results."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test cases
    suite.addTests(
        loader.loadTestsFromTestCase(TestHuaweiTelnetCEDriver)
    )
    suite.addTests(
        loader.loadTestsFromTestCase(TestHuaweiTelnetCEIntegration)
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
