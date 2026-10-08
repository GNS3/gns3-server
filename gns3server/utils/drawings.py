#!/usr/bin/env python
#
# Copyright (C) 2026 GNS3 Technologies Inc.
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
Web UI compatible drawing SVG assembly.

The GNS3 Web UI does not render drawing SVG as-is: it re-parses it into its own
element model with ONE recognized child element per drawing (text, image, rect,
line, ellipse or path) and reads the root width/height for the selection box.
These helpers emit exactly that format, mirroring the attribute sets the Web UI
itself serializes, and validate inputs so callers fail loudly instead of hitting
the controller's silent drop of unparseable SVG strings of 500+ characters.

Shared by the MCP tools (agent/mcp) and the GNS3 copilot tools (tools_v2).
"""

import re
from math import ceil
from typing import Any
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

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
_DASHARRAY_RE = re.compile(r"^[0-9][0-9, ]*$")
# The Web UI remaps these Qt-style dash patterns to different values
# (QtDasharrayFixer); reject them so what you send is what renders.
_QT_REMAPPED_DASHARRAYS = {"25, 25", "5, 25", "5, 25, 25", "25, 25, 5, 25, 5"}
_DEFAULT_DASHARRAY = "10,6"


def _checked_text(text: Any) -> str:
    if text is None:
        raise ValueError("text is required")
    if not isinstance(text, str):
        raise ValueError("text must be a string")
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip("\n")
    if not text:
        raise ValueError("text is required")
    if len(text) > _MAX_TEXT_LENGTH:
        raise ValueError(f"text is too long (max {_MAX_TEXT_LENGTH} characters)")
    if any(ord(ch) < 32 and ch != "\n" for ch in text) or "\x7f" in text:
        raise ValueError("text contains control characters (only newlines are allowed)")
    return text


def _checked_font_size(font_size: Any) -> int:
    if isinstance(font_size, bool) or not isinstance(font_size, int) or not 1 <= font_size <= 200:
        raise ValueError("font_size must be an integer between 1 and 200")
    return font_size


def _checked_font_family(font_family: Any) -> str:
    if not isinstance(font_family, str) or not _FONT_FAMILY_RE.match(font_family):
        raise ValueError("font_family contains invalid characters (allowed: letters, digits, spaces, . ' -)")
    return font_family


def _checked_color(value: Any, name: str) -> str:
    if not isinstance(value, str) or not _COLOR_RE.match(value):
        raise ValueError(f"{name} must be a hex value like #RRGGBB")
    return value


def _checked_dimension(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 2000:
        raise ValueError(f"{name} must be an integer between 1 and 2000")
    return value


def _checked_radius(value: Any, max_radius: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= max_radius:
        raise ValueError(f"rx must be an integer between 0 and {max_radius}")
    return value


def _checked_style(
    fill: Any, fill_opacity: Any, stroke: Any, stroke_width: Any, dashed: Any, dasharray: Any
) -> tuple[str, Any, str | None, int, str | None]:
    """
    Validate the style block shared by rectangle and ellipse drawings.

    :returns: (fill, fill_opacity, stroke, stroke_width, dasharray-or-None)
    """

    if fill != "none" and (not isinstance(fill, str) or not _COLOR_RE.match(fill)):
        raise ValueError('fill must be a hex value like #RRGGBB or "none"')
    if isinstance(fill_opacity, bool) or not isinstance(fill_opacity, (int, float)) or not 0 <= fill_opacity <= 1:
        raise ValueError("fill_opacity must be a number between 0 and 1")

    dash = dasharray if dasharray is not None else (_DEFAULT_DASHARRAY if dashed else None)
    if dash is not None:
        if not isinstance(dash, str) or not _DASHARRAY_RE.match(dash) or dash in _QT_REMAPPED_DASHARRAYS:
            raise ValueError(
                'dasharray must be plain "on,off" number pairs and must not be one of '
                f"the Qt-remapped patterns {sorted(_QT_REMAPPED_DASHARRAYS)}"
            )
        if stroke is None:
            raise ValueError("stroke is required when dasharray is set")

    if stroke is not None:
        stroke = _checked_color(stroke, "stroke")
        if isinstance(stroke_width, bool) or not isinstance(stroke_width, int) or not 1 <= stroke_width <= 20:
            raise ValueError("stroke_width must be an integer between 1 and 20")

    return fill, fill_opacity, stroke, stroke_width, dash


def _style_attrs(fill: str, fill_opacity: Any, stroke: str | None, stroke_width: int, dash: str | None) -> str:
    """Render the validated style block as SVG attributes (Web UI attribute order)."""

    attrs = f'fill="{fill}" fill-opacity="{fill_opacity}"'
    if stroke is not None:
        attrs += f' stroke="{stroke}" stroke-width="{stroke_width}"'
        if dash is not None:
            attrs += f' stroke-dasharray="{dash}"'
    return attrs


def build_text_svg(
    text: Any, font_size: int = 13, color: str = "#000000", bold: bool = False, font_family: str = "monospace"
) -> tuple[str, int, int, int]:
    """
    Build a Web UI compatible single <text> SVG for a canvas label.

    The output mirrors what the Web UI itself serializes for text drawings:
    root <svg height width> with one <text> child and no x/y (the Web UI parser
    ignores them and positions the text itself).

    :returns: (svg, width, height, line_height) with the computed drawing size
    """

    text = _checked_text(text)
    font_size = _checked_font_size(font_size)
    color = _checked_color(color, "color")
    font_family = _checked_font_family(font_family)

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
    ET.fromstring(svg)
    return svg, width, height, line_height


def build_rectangle_svg(
    width: int,
    height: int,
    fill: str = "#FFFFFF",
    fill_opacity: float = 1.0,
    stroke: str | None = None,
    stroke_width: int = 1,
    dashed: bool = False,
    dasharray: str | None = None,
    rx: int = 0,
) -> tuple[str, int, int]:
    """
    Build a Web UI compatible single <rect> SVG.

    The rect sits at the drawing origin (the Web UI ignores rect x/y), so the
    caller positions the drawing itself and the root size equals the rect size.

    :returns: (svg, width, height)
    """

    width = _checked_dimension(width, "width")
    height = _checked_dimension(height, "height")
    rx = _checked_radius(rx, min(width, height) // 2)
    fill, fill_opacity, stroke, stroke_width, dash = _checked_style(
        fill, fill_opacity, stroke, stroke_width, dashed, dasharray
    )

    svg = (
        f'<svg height="{height}" width="{width}">'
        f'<rect {_style_attrs(fill, fill_opacity, stroke, stroke_width, dash)} '
        f'height="{height}" width="{width}" rx="{rx}" ry="{rx}"/></svg>'
    )
    ET.fromstring(svg)
    return svg, width, height


def build_ellipse_svg(
    width: int,
    height: int,
    fill: str = "#FFFFFF",
    fill_opacity: float = 1.0,
    stroke: str | None = None,
    stroke_width: int = 1,
    dashed: bool = False,
    dasharray: str | None = None,
) -> tuple[str, int, int]:
    """
    Build a Web UI compatible single <ellipse> SVG from a bounding box.

    The radii and center are derived (rx = width // 2, cx = rx) because the Web UI
    treats cx/cy as offsets inside the drawing box, not canvas coordinates. For
    odd width/height the drawing is 1 px smaller than requested.

    :returns: (svg, width, height) with the actual (possibly rounded-down) size
    """

    width = _checked_dimension(width, "width")
    height = _checked_dimension(height, "height")
    rx, ry = width // 2, height // 2
    if rx < 1 or ry < 1:
        raise ValueError("width and height must be at least 2")
    fill, fill_opacity, stroke, stroke_width, dash = _checked_style(
        fill, fill_opacity, stroke, stroke_width, dashed, dasharray
    )

    svg = (
        f'<svg height="{2 * ry}" width="{2 * rx}">'
        f'<ellipse {_style_attrs(fill, fill_opacity, stroke, stroke_width, dash)} '
        f'cx="{rx}" cy="{ry}" rx="{rx}" ry="{ry}"/></svg>'
    )
    ET.fromstring(svg)
    return svg, 2 * rx, 2 * ry
