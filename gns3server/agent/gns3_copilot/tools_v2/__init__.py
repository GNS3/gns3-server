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

This package provides various tools for interacting with GNS3 network simulator:
- Device configuration command execution
- Display command execution
- Multiple device command execution using Nornir
- VPCS device configuration using Netmiko
- Node and link management

Main modules:
- config_tools_nornir: Multiple device configuration command execution tool using Nornir
- display_tools_nornir: Multiple device command execution tool using Nornir
- vpcs_tools_netmiko: VPCS device configuration tool using Netmiko
- gns3_create_node: GNS3 node creation tool
- gns3_create_link: GNS3 link creation tool
- gns3_start_node: GNS3 node startup tool
- gns3_get_node_temp: GNS3 template retrieval tool
- gns3_update_node_name: GNS3 node name update tool

Note: GNS3TopologyTool is now available from gns3_client package

Author: Yue Guobin (岳国宾)
"""

# Import main tool classes
from .config_tools_nornir import ExecuteMultipleDeviceConfigCommands
from .display_tools_nornir import ExecuteMultipleDeviceCommands
from .gns3_create_link import GNS3LinkTool
from .gns3_create_node import GNS3CreateNodeTool
from .gns3_get_node_temp import GNS3TemplateTool
from .gns3_start_node import GNS3StartNodeQuickTool
from .gns3_start_node import GNS3StartNodeTool
from .gns3_stop_node import GNS3StopNodeTool
from .gns3_suspend_node import GNS3SuspendNodeTool
from .gns3_update_node_name import GNS3UpdateNodeNameTool
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

# Export main tool classes
__all__ = [
    "ExecuteMultipleDeviceConfigCommands",
    "ExecuteMultipleDeviceCommands",
    "GNS3CreateNodeTool",
    "GNS3LinkTool",
    "GNS3StartNodeTool",
    "GNS3StartNodeQuickTool",
    "GNS3StopNodeTool",
    "GNS3SuspendNodeTool",
    "GNS3UpdateNodeNameTool",
    "GNS3TemplateTool",
    "PacketAnalysisTool",
]

# Package initialization message
# print(f"GNS3-Copilot Tools package loaded (version {__version__})")
