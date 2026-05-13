#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
#
# GNS3-Copilot - AI-powered Network Lab Assistant for GNS3
#
# Script to list all Netmiko supported devices (SSH and Telnet)
#
# This script queries the Netmiko library to extract all device types
# that support SSH and Telnet connections, grouped by vendor/brand.
# Includes custom device drivers from the GNS3-Copilot project.
# Outputs a Markdown document with the complete device list.
#
# Usage: python list_netmiko_devices.py
# Output: netmiko_devices.md (in current directory)
#

"""
Netmiko Device List Generator

This script extracts and displays all SSH and Telnet-supported device
types from the Netmiko library, organized by vendor/brand.

Features:
- Automatically detects Netmiko version
- Loads custom GNS3-Copilot device drivers
- Extracts all SSH and Telnet device types from CLASS_MAPPER
- Groups devices by vendor/brand
- Generates Markdown documentation
- Provides statistics and summary
"""

import os
import sys
from typing import Dict, List, Tuple
from datetime import datetime


def get_netmiko_version() -> str:
    """Get Netmiko library version."""
    try:
        import netmiko
        return netmiko.__version__
    except Exception:
        return "Unknown"


def register_custom_drivers() -> set:
    """
    Register custom GNS3-Copilot device drivers.

    This function imports and executes the registration functions for
    custom device drivers, adding them to Netmiko's CLASS_MAPPER.

    Returns:
        Set of custom device type names that were registered
    """
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Find the custom drivers directory
    custom_drivers_dir = os.path.dirname(script_dir)

    # Add to sys.path if not already there
    if custom_drivers_dir not in sys.path:
        sys.path.insert(0, custom_drivers_dir)

    custom_devices = set()

    try:
        # Import and register Huawei CE driver
        from gns3server.agent.gns3_copilot.utils.custom_netmiko \
            import huawei_ce

        # Store custom device types before registration
        custom_devices.add("gns3_huawei_telnet_ce")

        # The driver auto-registers on import, but we can call it
        # explicitly
        if hasattr(huawei_ce, 'register_custom_device_type'):
            huawei_ce.register_custom_device_type()
    except ImportError:
        # Silently skip if custom drivers are not available
        pass
    except Exception as e:
        # Log but don't fail
        print(
            f"Warning: Failed to register Huawei CE driver: {e}",
            file=sys.stderr
        )

    try:
        # Import and register Ruijie Telnet driver
        from gns3server.agent.gns3_copilot.utils.custom_netmiko \
            import ruijie_telnet

        # Store custom device types before registration
        custom_devices.add("gns3_ruijie_telnet")

        # The driver auto-registers on import, but we can call it
        # explicitly
        if hasattr(ruijie_telnet, 'register_custom_device_type'):
            ruijie_telnet.register_custom_device_type()
    except ImportError:
        # Silently skip if custom drivers are not available
        pass
    except Exception as e:
        # Log but don't fail
        print(
            f"Warning: Failed to register Ruijie driver: {e}",
            file=sys.stderr
        )

    return custom_devices


def extract_brand_name(device_type: str) -> str:
    """
    Extract brand name from device type.

    Args:
        device_type: Device type string (e.g., 'cisco_ios_telnet')

    Returns:
        Brand name in a standardized format
    """
    # Remove common suffixes
    name = device_type.replace('_telnet', '').replace('_ssh', '')
    name = name.replace('_serial', '')

    # Map to standard brand names
    brand_mapping = {
        'cisco': 'Cisco',
        'huawei': 'Huawei',
        'juniper': 'Juniper',
        'arista': 'Arista',
        'hp': 'HP',
        'aruba': 'Aruba',
        'dell': 'Dell',
        'brocade': 'Brocade',
        'extreme': 'Extreme',
        'ruckus': 'Ruckus',
        'ruijie': 'Ruijie (锐捷)',
        'zte': 'ZTE (中兴)',
        'maipu': 'Maipu (迈普)',
        'h3c': 'H3C (华三)',
        'nokia': 'Nokia',
        'paloalto': 'Palo Alto',
        'f5': 'F5',
        'checkpoint': 'Check Point',
        'generic': 'Generic',
        'huaweiyt': 'HuaweiYT',
        'vsz': 'Ruckus',
    }

    # Check for exact matches first
    for key, value in brand_mapping.items():
        if name == key:
            return value

    # Check for partial matches
    for key, value in brand_mapping.items():
        if key in name:
            return value

    # Return capitalized version of the first part
    return name.split('_')[0].capitalize()


def group_devices_by_brand(device_types: List[str]) -> Dict[str, List[str]]:
    """
    Group device types by brand.

    Args:
        device_types: List of device type strings

    Returns:
        Dictionary mapping brand names to device type lists
    """
    brands = {}

    for device_type in device_types:
        brand = extract_brand_name(device_type)

        if brand not in brands:
            brands[brand] = []

        brands[brand].append(device_type)

    return brands


def get_devices_by_protocol() -> Tuple[List[str], List[str]]:
    """
    Get all SSH and Telnet device types from Netmiko.

    Returns:
        Tuple of (ssh_devices, telnet_devices) as sorted lists
    """
    try:
        from netmiko.ssh_dispatcher import CLASS_MAPPER

        ssh_devices = []
        telnet_devices = []
        both_protocols = []

        for device_type in CLASS_MAPPER.keys():
            device_lower = device_type.lower()
            has_telnet = 'telnet' in device_lower
            has_ssh = 'ssh' in device_lower

            if has_telnet and has_ssh:
                both_protocols.append(device_type)
            elif has_telnet:
                telnet_devices.append(device_type)
            elif has_ssh:
                ssh_devices.append(device_type)

        # Devices with both protocols go to both lists
        ssh_devices.extend(both_protocols)
        telnet_devices.extend(both_protocols)

        return sorted(ssh_devices), sorted(telnet_devices)

    except ImportError as e:
        print(f"Error: Failed to import Netmiko: {e}", file=sys.stderr)
        sys.exit(1)


def get_total_device_count() -> int:
    """Get total number of device types in Netmiko."""
    try:
        from netmiko.ssh_dispatcher import CLASS_MAPPER
        return len(CLASS_MAPPER)
    except ImportError:
        return 0


def generate_markdown(
    version: str,
    ssh_devices: List[str],
    telnet_devices: List[str],
    total_count: int,
    custom_devices: set
) -> str:
    """
    Generate Markdown documentation with table format.

    Args:
        version: Netmiko version string
        ssh_devices: List of SSH device types
        telnet_devices: List of Telnet device types
        total_count: Total number of device types
        custom_devices: Set of custom device type names

    Returns:
        Markdown formatted string
    """
    md_lines = []

    # Header
    md_lines.append("# Netmiko Supported Devices")
    md_lines.append("")
    md_lines.append(f"**Netmiko Version:** {version}")
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    md_lines.append(f"**Generated:** {timestamp}")
    md_lines.append("")
    md_lines.append("---")
    md_lines.append("")

    # Summary
    md_lines.append("## Summary")
    md_lines.append("")
    md_lines.append(f"- **Total Device Types:** {total_count}")
    md_lines.append(f"- **SSH Devices:** {len(ssh_devices)}")
    md_lines.append(f"- **Telnet Devices:** {len(telnet_devices)}")
    md_lines.append(f"- **Custom Devices:** {len(custom_devices)}")
    md_lines.append("")

    # SSH Devices Section
    md_lines.append("## SSH Supported Devices")
    md_lines.append("")
    md_lines.append("| Platform | Device Type | Source |")
    md_lines.append("|----------|-------------|--------|")

    ssh_brands = group_devices_by_brand(ssh_devices)
    for brand in sorted(ssh_brands.keys()):
        devices = sorted(ssh_brands[brand])
        for device in devices:
            if device in custom_devices:
                source = "Custom ✨"
            else:
                source = "Netmiko"
            md_lines.append(f"| {brand} | `{device}` | {source} |")
    md_lines.append("")

    # Telnet Devices Section
    md_lines.append("## Telnet Supported Devices")
    md_lines.append("")
    md_lines.append("| Platform | Device Type | Source |")
    md_lines.append("|----------|-------------|--------|")

    telnet_brands = group_devices_by_brand(telnet_devices)
    for brand in sorted(telnet_brands.keys()):
        devices = sorted(telnet_brands[brand])
        for device in devices:
            if device in custom_devices:
                source = "Custom ✨"
            else:
                source = "Netmiko"
            md_lines.append(f"| {brand} | `{device}` | {source} |")
    md_lines.append("")

    # Footer
    md_lines.append("---")
    md_lines.append("")
    md_lines.append("*This document was generated automatically by the "
                    "Netmiko device list script.*")

    return "\n".join(md_lines)


def save_markdown(content: str, filename: str = "netmiko_devices.md") -> None:
    """
    Save Markdown content to file in docs/gns3-copilot directory.

    Args:
        content: Markdown content to save
        filename: Output filename (default: netmiko_devices.md)
    """
    # Get the project root directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Go up from: .../gns3server/agent/gns3_copilot/utils/
    #            custom_netmiko/scripts to project root
    # That's 6 levels up
    project_root = os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.dirname(script_dir))))
        )
    )

    # Target directory: docs/gns3-copilot
    target_dir = os.path.join(project_root, "docs", "gns3-copilot")

    # Create directory if it doesn't exist
    os.makedirs(target_dir, exist_ok=True)

    # Full file path
    output_path = os.path.join(target_dir, filename)

    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Markdown document saved to: {output_path}")
    except IOError as e:
        print(f"Error: Failed to save Markdown file: {e}",
              file=sys.stderr)
        sys.exit(1)


def print_summary(version: str, ssh_count: int, telnet_count: int,
                  total_count: int, output_file: str) -> None:
    """Print summary to console."""
    print("=" * 80)
    print("Netmiko Device List Generator")
    print(f"Netmiko Version: {version}")
    print("=" * 80)
    print()
    print(f"Total SSH devices: {ssh_count}")
    print(f"Total Telnet devices: {telnet_count}")
    print(f"Total device types: {total_count}")
    print()
    print(f"Output file: {output_file}")
    print("=" * 80)


def main() -> int:
    """
    Main function to execute the script.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    # Register custom GNS3-Copilot drivers
    custom_devices = register_custom_drivers()

    # Get Netmiko version
    version = get_netmiko_version()

    # Get SSH and Telnet devices
    ssh_devices, telnet_devices = get_devices_by_protocol()

    if not ssh_devices and not telnet_devices:
        print("Error: No devices found!", file=sys.stderr)
        return 1

    # Get total device count
    total_count = get_total_device_count()

    # Generate Markdown
    markdown_content = generate_markdown(
        version=version,
        ssh_devices=ssh_devices,
        telnet_devices=telnet_devices,
        total_count=total_count,
        custom_devices=custom_devices
    )

    # Save to file
    output_file = "netmiko_devices.md"
    save_markdown(markdown_content, output_file)

    # Print summary
    print_summary(
        version=version,
        ssh_count=len(ssh_devices),
        telnet_count=len(telnet_devices),
        total_count=total_count,
        output_file=output_file
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
