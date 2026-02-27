#!/usr/bin/env python
#
# Copyright (C) 2025 GNS3 Technologies Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
GNS3 Copilot Tools.

This package provides LangChain tools for the GNS3 Copilot agent to interact
with GNS3 server functionality.
"""

from .topology import GNS3TopologyTool
from .nodes import GNS3CreateNodeTool, GNS3StartNodeTool
from .links import GNS3LinkTool
from .templates import GNS3TemplateTool
from .network_commands import ExecuteDisplayCommandsTool, ExecuteConfigCommandsTool
from .vpcs import VPCSCommandsTool

__all__ = [
    "GNS3TopologyTool",
    "GNS3CreateNodeTool",
    "GNS3StartNodeTool",
    "GNS3LinkTool",
    "GNS3TemplateTool",
    "ExecuteDisplayCommandsTool",
    "ExecuteConfigCommandsTool",
    "VPCSCommandsTool",
]
