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
GNS3 Client Package

This package provides the shared GNS3 REST client layer:

- Gns3Connector (connector.py): authenticated HTTP session for the
  controller API — v2 basic / v3 JWT auth, token refresh, error extraction
- api_handlers.py: endpoint handlers taking ``(params, gns3_ctx)`` dicts,
  shared by the copilot tools and the MCP service
- project_inventory.py: nodes/links aggregation for the topology context
- GNS3TopologyTool / GNS3ProjectInfoTool: LangChain reader tools

Main functions:
- get_gns3_connector: Factory function to create Gns3Connector
- get_gns3_connector_with_llm_config: Create connector AND retrieve LLM config
- get_gns3_server_host: Get GNS3 server hostname from Controller or Config
- get_llm_config: Get user's default LLM config with API key

The connector is adapted from the upstream gns3fy project
(https://github.com/davidban77/gns3fy).
"""

from .api_handlers import build_gns3_ctx
from .connector import Gns3Connector
from .connector_factory import get_gns3_connector
from .connector_factory import get_gns3_connector_with_llm_config
from .connector_factory import get_gns3_server_host
from .connector_factory import get_llm_config
from .context_helpers import get_current_jwt_token
from .context_helpers import get_current_llm_config
from .context_helpers import set_current_jwt_token
from .context_helpers import set_current_llm_config
from .gns3_project_info import GNS3ProjectInfoTool
from .gns3_topology_reader import GNS3TopologyTool

# Dynamic version management
try:
    from importlib.metadata import version

    __version__ = version("gns3-copilot")
except Exception:
    __version__ = "unknown"

__author__ = "Yue Guobin (岳国宾)"
__description__ = "AI-powered network automation assistant for GNS3"
__url__ = "https://github.com/yueguobin/gns3-copilot"

__all__ = [
    "Gns3Connector",
    "build_gns3_ctx",
    "GNS3TopologyTool",
    "GNS3ProjectInfoTool",
    "get_gns3_connector",
    "get_gns3_connector_with_llm_config",
    "get_gns3_server_host",
    "get_llm_config",
    "set_current_jwt_token",
    "get_current_jwt_token",
    "set_current_llm_config",
    "get_current_llm_config",
]
