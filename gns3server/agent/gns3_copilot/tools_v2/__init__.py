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

"""
GNS3-Copilot Tools Package

Most copilot tools are now adapted from the MCP server registration via
``mcp_bridge.adapted_mcp_tools()`` — the MCP tools are the single source
of truth for names, descriptions and argument schemas (see
``mcp_bridge.MCP_ALLOWED_TOOLS`` for the project-scoped filter).

This package keeps only the copilot-native tools that add behavior the
MCP counterparts lack:

- gns3_create_link: link creation with port-NAME resolution ("link_create";
  shadows the adapted MCP tool of the same name)
- gns3_wait: boot wait timer ("wait_seconds"; pairs with node_start)
- packet_analysis_tool: server-side tshark pcap analysis ("packet_analysis";
  no MCP counterpart by design)

The Nornir/Netmiko device command runners live in the shared layer as
plain classes (gns3_client/device_config_commands.py, device_show_commands.py,
vpcs_commands.py) behind the MCP device_config_send / device_show_run /
vpcs_config_set tools, which the copilot uses through the bridge.

Author: Yue Guobin (岳国宾)
"""

# Import main tool classes
from .gns3_create_link import GNS3LinkTool
from .gns3_wait import GNS3WaitTool
from .mcp_bridge import adapted_mcp_tools
from .packet_analysis_tool import PacketAnalysisTool

# Dynamic version management
try:
    from importlib.metadata import version

    __version__ = version("gns3-copilot")
except Exception:
    __version__ = "unknown"

__author__ = "Yue Guobin (岳国宾)"
__description__ = "AI-powered network automation assistant for GNS3"
__url__ = "https://github.com/yueguobin/gns3-copilot"

# Export main tool classes and the MCP bridge
__all__ = [
    "GNS3LinkTool",
    "GNS3WaitTool",
    "PacketAnalysisTool",
    "adapted_mcp_tools",
]
