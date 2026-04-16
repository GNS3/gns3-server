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
Topology Planner Skill for GNS3 Lab Automation

This skill helps users plan and create network lab topologies automatically.

Key Constraints:
- Default image: IOU (L3 device)
- Default IP range: 10.0.0.0/8 (use 10.x.x.x subnets)
- Max 10 nodes recommended
- Node naming: Router=R, Switch=S, PC=PC
"""

# Standard lab IP subnet allocation (10.0.0.0/8)
# Subnets are allocated sequentially, each /24 by default
IP_SUBNET_POOL = [
    "10.0.0.0/24",   # Management/console
    "10.0.1.0/24",   # LAN segment 1
    "10.0.2.0/24",   # LAN segment 2
    "10.0.3.0/24",   # WAN segment 1 (P2P links)
    "10.0.4.0/24",   # WAN segment 2
    "10.0.5.0/24",   # WAN segment 3
    "10.0.10.0/24",  # Loopback pools
    "10.0.20.0/24",
    "10.0.30.0/24",
    "10.0.40.0/24",
]

# Default node naming convention
NODE_NAMING = {
    "router": "R",      # e.g., R1, R2, R3
    "switch": "S",      # e.g., S1, S2
    "pc": "PC",         # e.g., PC1, PC2
}

# Default IOU template name
DEFAULT_IOU_TEMPLATE = "IOU"


# Topology Planner Skill Definition
TOPOLOGY_PLANNER_SKILL = {
    "device_type": "topology_planner",
    "category": "feature",
    "name": "GNS3 Topology Planner",
    "description": "Automatically plan and create GNS3 network lab topologies",

    # Default settings
    "defaults": {
        "image": "IOU",
        "ip_range": "10.0.0.0/8",
        "subnet_size": "/24",
        "max_nodes": 10,
        "naming": NODE_NAMING,
    },

    # IP planning rules
    "ip_planning": {
        "default_subnet_pool": IP_SUBNET_POOL,
        "subnet_allocation": "Sequential from pool, /24 for LANs, /30 for P2P links",
        "gateway_convention": ".254 for LAN subnets, .1/.2 for P2P links",
    },

    # Node naming conventions
    "naming_rules": {
        "router": "R{number}, e.g., R1, R2, R3",
        "switch": "S{number}, e.g., S1, S2",
        "pc": "PC{number}, e.g., PC1, PC2",
        "firewall": "FW{number}",
        "loopback": "Lo{number}, e.g., Lo0, Lo1",
    },

    # Node positioning rules
    "positioning_rules": {
        "min_distance_px": 250,
        "grid_cols": 4,
        "grid_start": {"x": -400, "y": -200},
        "grid_spacing": {"x": 300, "y": 250},
        "formula": "x = -400 + col * 300, y = -200 + row * 250",
        "example": {
            "node_0": {"x": -400, "y": -200},
            "node_1": {"x": -100, "y": -200},
            "node_2": {"x": 200, "y": -200},
            "node_3": {"x": 500, "y": -200},
            "node_4": {"x": -400, "y": 50},
        }
    },

    # Tool call workflow
    "workflow": {
        "step_1_read_templates": {
            "tool": "gns3_template_reader",
            "purpose": "Find available IOU template name",
            "example": "List templates to identify IOU template"
        },
        "step_2_create_nodes": {
            "tool": "gns3_create_node",
            "purpose": "Create all router/switch/PC nodes",
            "params_required": ["project_id", "nodes: [{template_id, x, y, name?}]"],
            "positioning": "Use grid layout: x = -400 + col * 300, y = -200 + row * 250, min 250px between nodes",
            "note": "Use 'name' field to set node names directly (e.g., R1, R2). No separate rename step needed."
        },
        "step_3_create_links": {
            "tool": "gns3_link_tool",
            "purpose": "Connect nodes according to topology design",
            "params_required": ["node1_id", "node1_port", "node2_id", "node2_port"]
        },
        "step_4_start_nodes": {
            "tool": "gns3_start_node_tool",
            "purpose": "Power on all nodes",
            "params_required": ["node_ids"],
            "note": "Start nodes before configuration"
        },
        "step_5_verify": {
            "tool": "execute_multiple_device_commands",
            "purpose": "Verify connectivity before config",
            "example_commands": ["ping <neighbor_ip>"]
        },
        "step_6_config": {
            "tool": "execute_multiple_device_config_commands",
            "purpose": "Apply network configuration",
            "note": "Only after verifying physical connectivity"
        },
    },

    # Troubleshooting
    "troubleshooting": {
        "node_creation_failed": [
            "1. Check if template name is correct (use gns3_template_reader)",
            "2. Verify GNS3 server is running",
            "3. Check compute resource availability"
        ],
        "link_creation_failed": [
            "1. Verify both nodes exist and have available ports",
            "2. Check if link already exists between nodes",
            "3. Confirm nodes are stopped before linking (some setups)"
        ],
        "node_start_failed": [
            "1. Check if node is already running",
            "2. Verify compute resource has enough memory",
            "3. Check console port availability"
        ],
        "connectivity_failed": [
            "1. Use show ip interface brief to verify IPs are configured",
            "2. Check if interfaces are administratively up (no shutdown)",
            "3. Verify cable/port mapping in GNS3 topology"
        ],
    },

    # Planning output format
    "output_template": """
## Topology Plan

### Devices
| Node | Type | Image | Description |
|------|------|-------|-------------|
| R1 | Router | IOU | Core router |
| ... | ... | ... | ... |

### Connections
| Node1 | Port | Node2 | Port |
|-------|------|-------|------|
| R1 | Gi0/0 | R2 | Gi0/0 |
| ... | ... | ... | ... |

### IP Addressing
| Device | Interface | IP Address | Subnet |
|--------|-----------|------------|--------|
| R1 | Gi0/0 | 10.0.1.1 | /30 |
| ... | ... | ... | ... |

### Configuration Steps
1. Create nodes: gns3_create_node(...)
2. Create links: gns3_link_tool(...)
3. Start nodes: gns3_start_node_tool(...)
4. Verify connectivity: ping ...
5. Apply config: execute_multiple_device_config_commands(...)

Note: Use "name" field in gns3_create_node to set node names directly. No separate rename step needed.
""",
}
