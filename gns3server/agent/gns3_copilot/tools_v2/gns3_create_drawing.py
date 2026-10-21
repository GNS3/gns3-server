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
GNS3 canvas drawing tools for text, rectangle and ellipse annotations.

Thin LangChain wrappers over the shared REST handlers in
``gns3_client.api_handlers``; the Web UI compatible SVG is assembled and
validated by ``gns3server.utils.drawings`` (single implementation shared
with the MCP drawing tools).
"""

import json
import logging
from typing import Any

from langchain.tools import BaseTool
from langchain_core.callbacks import CallbackManagerForToolRun

from gns3server.agent.gns3_copilot.gns3_client.api_handlers import (
    build_gns3_ctx,
    create_ellipse_drawing_handler,
    create_rectangle_drawing_handler,
    create_text_drawing_handler,
)

# Configure logging
logger = logging.getLogger(__name__)


class _GNS3CreateDrawingToolBase(BaseTool):
    """Shared plumbing: parse JSON input, build ctx, dispatch to a handler."""

    def _dispatch(self, input_data: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def _run(
        self,
        tool_input: str,
        run_manager: CallbackManagerForToolRun | None = None,
    ) -> dict[str, Any]:
        try:
            input_data = json.loads(tool_input)

            gns3_ctx = build_gns3_ctx()
            if gns3_ctx is None:
                logger.error("Failed to create GNS3 connector")
                return {"error": "Failed to connect to GNS3 server. Please check your configuration."}

            return self._dispatch(input_data, gns3_ctx)
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON input: %s", e)
            return {"error": f"Invalid JSON input: {e}"}
        except Exception as e:
            logger.exception("Drawing creation failed")
            return {"error": str(e)}


class GNS3CreateTextDrawingTool(_GNS3CreateDrawingToolBase):
    """
    A LangChain tool to add a text label to the GNS3 project canvas.

    **Input**:
    A JSON object with project_id, x, y (top-left corner on the canvas)
    and text; optional font_size (1-200, default 13), color (#RRGGBB,
    default #000000), bold (default false), font_family (default
    monospace) and z (default 1, keeps text above links).
    Newlines in text start additional lines; XML characters are escaped
    automatically; the computed width/height are returned.

    **Output**:
    A dictionary with the created drawing, its drawing_id and the
    computed width/height/line_height, or an "error" key on failure.
    """

    name: str = "create_gns3_text_drawing"
    description: str = """
    Adds a text label to the GNS3 project canvas.
    Input: JSON with project_id, x, y (top-left corner), text and optional
    font_size, color, bold, font_family, z.
    Returns: the created drawing with its computed width and height.
    """

    def _dispatch(self, input_data: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
        return create_text_drawing_handler(input_data, gns3_ctx)


class GNS3CreateRectangleDrawingTool(_GNS3CreateDrawingToolBase):
    """
    A LangChain tool to add a rectangle to the GNS3 project canvas.

    **Input**:
    A JSON object with project_id, x, y (top-left corner), width and
    height (1-2000); optional fill (#RRGGBB or "none", default #FFFFFF),
    fill_opacity (0-1, default 1.0), stroke (#RRGGBB, no border by
    default), stroke_width (1-20), dashed (bool), dasharray (like "4,2",
    requires stroke) and rx (corner radius, default 0). z defaults to 0
    so shapes stay behind nodes and text.

    **Output**:
    A dictionary with the created drawing, or an "error" key on failure.
    """

    name: str = "create_gns3_rectangle_drawing"
    description: str = """
    Adds a rectangle to the GNS3 project canvas.
    Input: JSON with project_id, x, y, width, height and optional fill,
    fill_opacity, stroke, stroke_width, dashed, dasharray, rx, z.
    Returns: the created drawing with its width and height.
    """

    def _dispatch(self, input_data: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
        return create_rectangle_drawing_handler(input_data, gns3_ctx)


class GNS3CreateEllipseDrawingTool(_GNS3CreateDrawingToolBase):
    """
    A LangChain tool to add an ellipse (or circle) to the GNS3 canvas.

    **Input**:
    A JSON object with project_id, x, y (bounding box top-left corner),
    width and height (2-2000, equal values give a circle); the same
    optional style fields as the rectangle tool. cx/cy are derived from
    the bounding box; for odd width/height the drawing is 1 px smaller
    than requested and the actual size is returned.

    **Output**:
    A dictionary with the created drawing, or an "error" key on failure.
    """

    name: str = "create_gns3_ellipse_drawing"
    description: str = """
    Adds an ellipse or circle to the GNS3 project canvas.
    Input: JSON with project_id, x, y, width, height (bounding box) and
    optional fill, fill_opacity, stroke, stroke_width, dashed, dasharray, z.
    Returns: the created drawing with its actual width and height.
    """

    def _dispatch(self, input_data: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
        return create_ellipse_drawing_handler(input_data, gns3_ctx)
