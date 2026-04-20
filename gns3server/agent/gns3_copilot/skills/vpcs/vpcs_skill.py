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
# Copyright (C) 2025 Yue Guobin
# Author: Yue Guobin
#
# Project Home: https://github.com/yueguobin/gns3-copilot
#

"""
VPCS Skill Definition

GNS3 VPCS (Virtual PC Simulator) is a lightweight virtual PC simulator
used in GNS3 labs for testing network connectivity and basic IP configuration.

Key Characteristics:
- NOT a network device (router/switch), it's a simple PC simulator
- No authentication required (direct console access)
- No configuration mode (commands entered directly)
- Simple command set focused on IP configuration and connectivity testing

Device Type Tag: device_type:gns3_vpcs_telnet
"""

# VPCS Skill Definition
VPCS_SKILL = {
    "device_type": "gns3_vpcs_telnet",
    "category": "device",  # device, protocol, or feature
    "name": "VPCS Virtual PC Simulator",
    "description": "GNS3 VPCS lightweight virtual PC simulator for testing network connectivity and basic IP configuration",

    # Configuration Commands (no config mode needed)
    "config_commands": {
        "ip_config": {
            "syntax": "ip <address>/<mask> <gateway>",
            "example": "ip 10.10.0.12/24 10.10.0.254",
            "description": "Configure PC IP address and default gateway",
            "parameters": {
                "address": "IP address, e.g., 10.10.0.12",
                "mask": "Subnet mask in CIDR notation, e.g., 24 means 255.255.255.0",
                "gateway": "Default gateway, e.g., 10.10.0.254"
            }
        },
        "ip_dhcp": {
            "syntax": "ip dhcp",
            "description": "Obtain IP configuration from DHCP server"
        },
        "save": {
            "syntax": "save",
            "description": "Save current configuration to NVRAM (persists after reboot)"
        },
        "reset": {
            "syntax": "reset",
            "description": "Reset VPCS configuration (clears all settings)"
        },
    },

    # Display/Diagnostic Commands
    "display_commands": {
        "show_ip": {
            "syntax": "show ip",
            "description": "Show current IP configuration (IP address, subnet mask, gateway)"
        },
        "ping": {
            "syntax": "ping <destination>",
            "example": "ping 10.10.0.254",
            "description": "Test connectivity to destination (sends 4 ICMP echo requests)"
        },
        "ping_count": {
            "syntax": "ping <destination> <count>",
            "example": "ping 10.10.0.254 10",
            "description": "Send specified number of ICMP packets"
        },
        "arp": {
            "syntax": "arp",
            "description": "Display ARP cache table"
        },
        "version": {
            "syntax": "version",
            "description": "Show VPCS version information"
        },
        "show": {
            "syntax": "show",
            "description": "Display current running configuration"
        },
        "pc_info": {
            "syntax": "pcinfo",
            "description": "Display PC hardware information"
        },
        "route": {
            "syntax": "route",
            "description": "Display routing table (static routes)"
        },
    },

    # Important Notes
    "notes": [
        "WARNING: VPCS is NOT a network device (router/switch), it is a lightweight PC simulator!",
        "WARNING: Do NOT use router/switch config commands on VPCS (e.g., configure terminal, interface)",
        "VPCS has no config mode, commands are entered directly",
        "VPCS does not require username/password authentication, direct console access",
        "Prompt format: PC1>, PC2>, VPCS>",
        "Default sends 4 ICMP packets, use ping <ip> <count> to specify number",
        "Must execute save to persist configuration, otherwise lost after reboot",
    ],

    # Troubleshooting Guide
    "troubleshooting": {
        "ping failed": [
            "1. Use show ip to verify IP configuration is correct",
            "2. Verify target gateway is reachable (ping gateway IP)",
            "3. Ensure source and target are in same subnet or gateway is correct",
            "4. Check if link is UP (verify GNS3 topology connections)"
        ],
        "configuration lost": [
            "1. VPCS configuration is lost after reboot",
            "2. Must execute save command after any configuration change",
            "3. Use show command to verify current configuration"
        ],
        "cannot connect to console": [
            "1. Check if node is started in GNS3",
            "2. Verify console port mapping is correct",
            "3. Confirm telnet connection parameters are correct (IP:port)"
        ],
    },

    # Command aliases (for LLM understanding)
    "command_aliases": {
        "show ip": "show ip",
        "display ip": "show ip",
        "config ip": "ip <address>/<mask> <gateway>",
        "set ip": "ip <address>/<mask> <gateway>",
        "test connectivity": "ping <destination>",
        "ping test": "ping <destination>",
        "save config": "save",
        "save": "save",
        "reset": "reset",
        "show route": "route",
        "show arp": "arp",
        "show version": "version",
    },
}
