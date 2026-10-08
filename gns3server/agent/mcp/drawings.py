#
# Copyright (C) 2026 GNS3 Technologies Inc.
# Author: Yue Guobin
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
MCP tool handlers for GNS3 drawing management.
"""

import logging
import re
from math import ceil
from typing import Any
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

log = logging.getLogger(__name__)


# ── Helper ─────────────────────────────────────────────────────────────────


def _get_connector(gns3_ctx: dict[str, Any]):
    from gns3server.agent.gns3_copilot.gns3_client.connector import Gns3Connector

    return Gns3Connector(
        url=gns3_ctx["server_url"],
        jwt_token=gns3_ctx["jwt_token"],
        api_version=3,
        verify=False,
    )


# ── Tool handlers ──────────────────────────────────────────────────────────


def get_drawings_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    project_id = params.get("project_id")
    if not project_id:
        return {"error": "project_id is required"}
    conn = _get_connector(gns3_ctx)
    drawings = conn.http_call("get", f"{conn.base_url}/projects/{project_id}/drawings").json()
    return {"drawings": drawings, "count": len(drawings)}


def create_drawing_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    project_id = params.get("project_id")
    svg = params.get("svg")
    if not project_id or not svg:
        return {"error": "project_id and svg are required"}
    conn = _get_connector(gns3_ctx)
    data = {
        "svg": svg,
        "x": params.get("x", 0),
        "y": params.get("y", 0),
        "z": params.get("z", 0),
        "locked": params.get("locked", False),
        "rotation": params.get("rotation", 0),
    }
    result = conn.http_call("post", f"{conn.base_url}/projects/{project_id}/drawings", json_data=data).json()
    return {"message": "Drawing created", "drawing": result}


# ── Text drawing ───────────────────────────────────────────────────────────

# The Web UI renders font-size as pt (1pt = 4/3 px) and monospace glyphs advance
# ~0.6em, so one character is ~0.8 x font_size in canvas pixels. Proportional
# fonts get a wider worst-case factor so the selection box does not clip the text.
_MONOSPACE_CHAR_FACTOR = 0.8
_PROPORTIONAL_CHAR_FACTOR = 1.0
# The Web UI stacks lines at dy=1.4em, i.e. 1.4 x 4/3 ~ 1.87 px per pt of font size.
_LINE_HEIGHT_FACTOR = 1.9
_MAX_TEXT_LENGTH = 500

_COLOR_RE = re.compile(r"^#(?:[0-9A-Fa-f]{3,4}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})$")
_FONT_FAMILY_RE = re.compile(r"^[A-Za-z0-9 ,.'-]+$")


def build_text_svg(
    text: str, font_size: int = 13, color: str = "#000000", bold: bool = False, font_family: str = "monospace"
) -> tuple[str, int, int, int]:
    """
    Build a Web UI compatible single <text> SVG for a canvas label.

    The output mirrors what the Web UI itself serializes for text drawings:
    root <svg height width> with one <text> child and no x/y (the Web UI parser
    ignores them and positions the text itself).

    :returns: (svg, width, height, line_height) with the computed drawing size
    """

    lines = text.split("\n")
    factor = _MONOSPACE_CHAR_FACTOR if "monospace" in font_family.lower() else _PROPORTIONAL_CHAR_FACTOR
    width = max(1, ceil(max(len(line) for line in lines) * font_size * factor))
    line_height = ceil(font_size * _LINE_HEIGHT_FACTOR)
    height = len(lines) * line_height
    weight = "bold" if bold else "normal"
    svg = (
        f'<svg height="{height}" width="{width}">'
        f'<text fill="{color}" fill-opacity="1.0" '
        f'font-family="{font_family}" font-size="{font_size}" '
        f'font-weight="{weight}">{escape(text)}</text></svg>'
    )
    # Fail loudly here: the controller silently keeps the previous (empty) SVG
    # when handed an unparseable string of 500+ characters.
    ET.fromstring(svg)
    return svg, width, height, line_height


def create_text_drawing_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    project_id = params.get("project_id")
    text = params.get("text")
    if not project_id:
        return {"error": "project_id is required"}
    if not text:
        return {"error": "text is required"}
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip("\n")
    if not text:
        return {"error": "text is required"}
    if len(text) > _MAX_TEXT_LENGTH:
        return {"error": f"text is too long (max {_MAX_TEXT_LENGTH} characters)"}
    if any(ord(ch) < 32 and ch != "\n" for ch in text) or "\x7f" in text:
        return {"error": "text contains control characters (only newlines are allowed)"}

    font_size = params.get("font_size", 13)
    if isinstance(font_size, bool) or not isinstance(font_size, int) or not 1 <= font_size <= 200:
        return {"error": "font_size must be an integer between 1 and 200"}
    color = params.get("color", "#000000")
    if not _COLOR_RE.match(color):
        return {"error": "color must be a hex value like #RRGGBB"}
    font_family = params.get("font_family", "monospace")
    if not _FONT_FAMILY_RE.match(font_family):
        return {"error": "font_family contains invalid characters (allowed: letters, digits, spaces, . ' -)"}

    try:
        svg, width, height, line_height = build_text_svg(
            text, font_size=font_size, color=color, bold=params.get("bold", False), font_family=font_family
        )
    except ET.ParseError as e:
        return {"error": f"generated SVG is not valid XML: {e}"}

    conn = _get_connector(gns3_ctx)
    data = {
        "svg": svg,
        "x": params.get("x", 0),
        "y": params.get("y", 0),
        "z": params.get("z", 1),
    }
    result = conn.http_call("post", f"{conn.base_url}/projects/{project_id}/drawings", json_data=data).json()
    return {
        "message": "Text drawing created",
        "drawing": result,
        "width": width,
        "height": height,
        "line_height": line_height,
    }


def get_drawing_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    project_id = params.get("project_id")
    drawing_id = params.get("drawing_id")
    if not project_id or not drawing_id:
        return {"error": "project_id and drawing_id are required"}
    conn = _get_connector(gns3_ctx)
    return conn.http_call("get", f"{conn.base_url}/projects/{project_id}/drawings/{drawing_id}").json()


def update_drawing_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    project_id = params.get("project_id")
    drawing_id = params.get("drawing_id")
    if not project_id or not drawing_id:
        return {"error": "project_id and drawing_id are required"}
    conn = _get_connector(gns3_ctx)
    data = {k: v for k, v in params.items() if k not in ("project_id", "drawing_id") and v is not None}
    return conn.http_call("put", f"{conn.base_url}/projects/{project_id}/drawings/{drawing_id}", json_data=data).json()


def delete_drawing_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    project_id = params.get("project_id")
    drawing_id = params.get("drawing_id")
    if not project_id or not drawing_id:
        return {"error": "project_id and drawing_id are required"}
    conn = _get_connector(gns3_ctx)
    conn.http_call("delete", f"{conn.base_url}/projects/{project_id}/drawings/{drawing_id}")
    return {"message": f"Drawing {drawing_id} deleted", "drawing_id": drawing_id}
