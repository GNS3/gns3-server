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

Drawing utility functions for GNS3 area annotations.

Calculates drawing parameters and generates SVG content for network area annotations.
Supports ellipse and rectangle shapes for two-node annotations.
"""

import math
from typing import Any
from typing import Literal

# Default parameters
DEFAULT_DEVICE_WIDTH = 50
DEFAULT_DEVICE_HEIGHT = 50
DEFAULT_FONT_SIZE = 14
DEFAULT_SHAPE_Z = 0
DEFAULT_TEXT_Z = 1

# Z-order thresholds (pixels)
Z_ORDER_LARGE_AREA_THRESHOLD = 500  # z=1 for large areas
Z_ORDER_MEDIUM_AREA_THRESHOLD = 300  # z=2 for medium areas

# Color schemes (business professional style)
# Text uses 'stroke', shape uses 'fill' with 'fill-opacity'
COLOR_SCHEMES = {
    # Core/Backbone - biz_blue
    "CORE_BACKBONE": {
        "stroke": "#FFFFFF",  # White (for text on dark background)
        "fill": "#2980B9",  # Blue background
        "fill_opacity": 0.8,  # Transparency level
    },
    # Normal Areas - biz_blue_light
    "NORMAL_AREA": {
        "stroke": "#000000",  # Black (for text on light background)
        "fill": "#5AA9DD",  # Light blue background
        "fill_opacity": 0.8,  # Transparency level
    },
    # Logical Isolation - biz_purple
    "ISOLATION": {
        "stroke": "#FFFFFF",  # White (for text on dark background)
        "fill": "#9B59B6",  # Purple background
        "fill_opacity": 0.8,  # Transparency level
    },
    # Management/Infrastructure - biz_orange
    "MANAGEMENT_INFRA": {
        "stroke": "#FFFFFF",  # White (for text on medium-dark background)
        "fill": "#E67E22",  # Orange background
        "fill_opacity": 0.8,  # Transparency level
    },
    # Redundancy/High Availability - biz_orange_bright
    "HIGH_AVAILABILITY": {
        "stroke": "#000000",  # Black (for text on bright background)
        "fill": "#F39C12",  # Bright orange background
        "fill_opacity": 0.8,  # Transparency level
    },
    # External/Boundary - biz_red_bright
    "EXTERNAL": {
        "stroke": "#FFFFFF",  # White (for text on dark background)
        "fill": "#E74C3C",  # Bright red background
        "fill_opacity": 0.8,  # Transparency level
    },
    # Security/Trusted - biz_green_bright
    "SECURITY_TRUSTED": {
        "stroke": "#FFFFFF",  # White (for text on medium-dark background)
        "fill": "#2ECC71",  # Bright green background
        "fill_opacity": 0.8,  # Transparency level
    },
    # Cloud/Tunnel - biz_cyan_dark
    "CLOUD_TUNNEL": {
        "stroke": "#FFFFFF",  # White (for text on dark background)
        "fill": "#00CED1",  # Dark cyan background
        "fill_opacity": 0.8,  # Transparency level
    },
    # Default - biz_gray
    "DEFAULT": {
        "stroke": "#FFFFFF",  # White (for text on medium-dark background)
        "fill": "#A5CC78",  # Gray background
        "fill_opacity": 0.8,  # Transparency level
    },
}


def calculate_two_node_shape(
    node1: dict,
    node2: dict,
    area_name: str,
    shape_type: Literal["ellipse", "rectangle"] = "ellipse",
    text_offset_ratio: float = 0.0,
) -> dict[str, Any]:
    """
    Calculate shape annotation parameters for two nodes.

    Args:
        node1: First node with 'x', 'y', 'height', 'width' (top-left)
        node2: Second node with 'x', 'y', 'height', 'width' (top-left)
        area_name: Name of area (e.g., "Area 0", "AS 100")
        shape_type: "ellipse" or "rectangle" (default: "ellipse")
        text_offset_ratio: Ratio to offset text (0=center, positive=offset)

    Returns:
        Dict with shape, text SVG params, and metadata
    """
    node1_width = node1.get("width", DEFAULT_DEVICE_WIDTH)
    node1_height = node1.get("height", DEFAULT_DEVICE_HEIGHT)
    node2_width = node2.get("width", DEFAULT_DEVICE_WIDTH)
    node2_height = node2.get("height", DEFAULT_DEVICE_HEIGHT)

    node1_center_x = node1["x"] + (node1_width / 2)
    node1_center_y = node1["y"] + (node1_height / 2)
    node2_center_x = node2["x"] + (node2_width / 2)
    node2_center_y = node2["y"] + (node2_height / 2)

    distance = math.sqrt((node2_center_x - node1_center_x) ** 2 + (node2_center_y - node1_center_y) ** 2)

    angle_rad = math.atan2(node2_center_y - node1_center_y, node2_center_x - node1_center_x)
    angle_deg = round(math.degrees(angle_rad))
    angle_rad = math.radians(angle_deg)

    center_x = (node1_center_x + node2_center_x) / 2
    center_y = (node1_center_y + node2_center_y) / 2

    color_scheme = _get_color_scheme(area_name)
    text_svg = generate_text_svg(area_name, color_scheme)

    text_svg_width = len(area_name) * 8 + 20
    text_svg_height = DEFAULT_FONT_SIZE + 16

    if shape_type == "ellipse":
        rx = distance / 2
        ry = math.sqrt((node1_width / 2) ** 2 + (node1_height / 2) ** 2)

        shape_width = rx * 2
        shape_height = ry * 2

        svg_x = center_x - (rx * math.cos(angle_rad) - ry * math.sin(angle_rad))
        svg_y = center_y - (rx * math.sin(angle_rad) + ry * math.cos(angle_rad))

        shape_svg = generate_ellipse_svg(int(rx), int(ry), color_scheme, int(shape_width), int(shape_height))

        offset_distance = ry * text_offset_ratio

        metadata = {
            "center_x": center_x,
            "center_y": center_y,
            "distance": distance,
            "shape_width": shape_width,
            "shape_height": shape_height,
            "angle_deg": angle_deg,
            "rx": rx,
            "ry": ry,
        }

    else:  # rectangle
        shape_width = distance
        shape_height = max(node1_width, node1_height, node2_width, node2_height)

        svg_x = center_x - ((shape_width / 2) * math.cos(angle_rad) - (shape_height / 2) * math.sin(angle_rad))
        svg_y = center_y - ((shape_width / 2) * math.sin(angle_rad) + (shape_height / 2) * math.cos(angle_rad))

        shape_svg = generate_rectangle_svg(int(shape_width), int(shape_height), color_scheme)

        offset_distance = (shape_height / 2) * text_offset_ratio

        metadata = {
            "center_x": center_x,
            "center_y": center_y,
            "distance": distance,
            "shape_width": shape_width,
            "shape_height": shape_height,
            "angle_deg": angle_deg,
            "rx": None,
            "ry": None,
        }

    if text_offset_ratio != 0:
        perpendicular_x = -math.sin(angle_rad)
        perpendicular_y = math.cos(angle_rad)

        text_offset_x = perpendicular_x * offset_distance
        text_offset_y = perpendicular_y * offset_distance

        text_x = int(center_x + text_offset_x - text_svg_width / 2)
        text_y = int(center_y + text_offset_y - text_svg_height / 2)
    else:
        text_x = int(center_x - text_svg_width / 2)
        text_y = int(center_y - text_svg_height / 2)

    return {
        "shape": {
            "svg": shape_svg,
            "x": int(svg_x),
            "y": int(svg_y),
            "z": DEFAULT_SHAPE_Z,
            "rotation": int(angle_deg),
            "type": shape_type,
        },
        "text": {
            "svg": text_svg,
            "x": text_x,
            "y": text_y,
            "z": DEFAULT_TEXT_Z,
            "rotation": 0,
        },
        "metadata": metadata,
    }


def generate_ellipse_svg(
    rx: int,
    ry: int,
    color_scheme: dict[str, Any],
    svg_width: int,
    svg_height: int,
) -> str:
    """Generate SVG for ellipse."""
    return f"""<svg width="{svg_width}" height="{svg_height}"><ellipse cx="{rx}" cy="{ry}" rx="{rx}" ry="{ry}" fill="{color_scheme["fill"]}" fill-opacity="{color_scheme["fill_opacity"]}"/></svg>"""


def generate_rectangle_svg(
    width: int,
    height: int,
    color_scheme: dict[str, Any],
) -> str:
    """Generate SVG for rectangle."""
    return f"""<svg width="{width}" height="{height}"><rect x="0" y="0" width="{width}" height="{height}" fill="{color_scheme["fill"]}" fill-opacity="{color_scheme["fill_opacity"]}"/></svg>"""


def generate_text_svg(text: str, color_scheme: dict[str, Any]) -> str:
    """Generate SVG for text label."""
    text_width = len(text) * 8 + 20
    text_height = DEFAULT_FONT_SIZE + 16

    return f"""<svg width="{text_width}" height="{text_height}"><text font-family="TypeWriter" font-size="{DEFAULT_FONT_SIZE}.0" font-weight="bold" fill="{color_scheme["stroke"]}" text-anchor="middle" x="{text_width / 2}" y="{text_height / 2 + 4}">{text}</text></svg>"""


def _hsv_to_hex(h: int, s: int, v: int) -> str:
    """Convert HSV to HEX color."""
    h_norm = (h % 360) / 360
    s_norm = s / 100
    v_norm = v / 100

    c: float = v_norm * s_norm
    x: float = c * (1 - abs((h_norm / 60) % 2 - 1))
    m: float = v_norm - c

    r: float
    g: float
    b: float

    if 0 <= h_norm < 60:
        r, g, b = c, x, 0.0
    elif 60 <= h_norm < 120:
        r, g, b = x, c, 0.0
    elif 120 <= h_norm < 180:
        r, g, b = 0.0, c, x
    elif 180 <= h_norm < 240:
        r, g, b = 0.0, x, c
    elif 240 <= h_norm < 300:
        r, g, b = x, 0.0, c
    else:
        r, g, b = c, 0.0, x

    r = int((r + m) * 255)
    g = int((g + m) * 255)
    b = int((b + m) * 255)

    return f"#{r:02x}{g:02x}{b:02x}"


def calculate_z_order(area_size: float) -> int:
    """
    Calculate z-order based on area size for proper layering.

    Args:
        area_size: Size of area (width for rectangles, 2*rx for ellipses)

    Returns:
        Z-order: 1=back (large), 2=middle, 3=front (small)
    """
    if area_size >= Z_ORDER_LARGE_AREA_THRESHOLD:
        return 1
    elif area_size >= Z_ORDER_MEDIUM_AREA_THRESHOLD:
        return 2
    else:
        return 3


def _get_color_scheme(area_name: str) -> dict[str, Any]:
    """
    Get color scheme based on area name using keyword inference.

    Maps labels to semantic groups for professional business styling.
    """
    if area_name in COLOR_SCHEMES:
        return COLOR_SCHEMES[area_name]

    label = area_name.upper()

    # 1. Routing Domain Core/Backbone
    if "AREA 0" in label or "BACKBONE" in label or "CORE" in label:
        return COLOR_SCHEMES["CORE_BACKBONE"]

    if "BGP" in label or "AS " in label:
        return COLOR_SCHEMES["CORE_BACKBONE"]

    # 2. Routing Domain Normal Areas
    if "AREA " in label or "LEVEL" in label:
        return COLOR_SCHEMES["NORMAL_AREA"]

    # 3. Logical Isolation
    if "VRF" in label or "VLAN" in label or "MSTP" in label or "VXLAN" in label or "MPLS" in label:
        return COLOR_SCHEMES["ISOLATION"]

    # 4. High Availability
    if "VRRP" in label or "HSRP" in label or "HA" in label or "STACK" in label or "M-LAG" in label:
        return COLOR_SCHEMES["HIGH_AVAILABILITY"]

    # 5. External/Internet
    if "INET" in label or "OUT" in label or "EXTERNAL" in label or "INTERNET" in label or "DMZ" in label:
        return COLOR_SCHEMES["EXTERNAL"]

    # 6. Management
    if "MGMT" in label or "OOB" in label or "MANAGEMENT" in label:
        return COLOR_SCHEMES["MANAGEMENT_INFRA"]

    # 7. Security/Trusted
    if "SECURITY" in label or "TRUSTED" in label or "VPN" in label:
        return COLOR_SCHEMES["SECURITY_TRUSTED"]

    # 8. Cloud/Tunnel
    if "TUNNEL" in label or "CLOUD" in label or "GRE" in label or "IPSEC" in label:
        return COLOR_SCHEMES["CLOUD_TUNNEL"]

    # Legacy keyword matching for backward compatibility
    label_lower = area_name.lower()
    protocol_keywords = [
        ("ospf", "NORMAL_AREA"),
        ("is-is", "NORMAL_AREA"),
        ("rip", "NORMAL_AREA"),
        ("eigrp", "NORMAL_AREA"),
        ("bgp", "CORE_BACKBONE"),
        ("vxlan", "ISOLATION"),
        ("mpls", "ISOLATION"),
        ("vrf", "ISOLATION"),
        ("vlan", "ISOLATION"),
        ("vrrp", "HIGH_AVAILABILITY"),
        ("hsrp", "HIGH_AVAILABILITY"),
        ("gre", "CLOUD_TUNNEL"),
        ("ipsec", "SECURITY_TRUSTED"),
    ]

    for keyword, scheme_key in protocol_keywords:
        if keyword in label_lower:
            return COLOR_SCHEMES[scheme_key]

    return COLOR_SCHEMES["DEFAULT"]


def calculate_two_node_ellipse(
    node1: dict,
    node2: dict,
    area_name: str,
    text_offset_ratio: float = 0.0,
) -> dict[str, Any]:
    """
    Calculate ellipse annotation parameters for two nodes.

    Wrapper around calculate_two_node_shape with shape_type="ellipse".
    """
    result = calculate_two_node_shape(node1, node2, area_name, "ellipse", text_offset_ratio)
    return {
        "ellipse": result["shape"],
        "text": result["text"],
        "metadata": result["metadata"],
    }


def calculate_two_node_rectangle(
    node1: dict,
    node2: dict,
    area_name: str,
    text_offset_ratio: float = 0.0,
) -> dict[str, Any]:
    """
    Calculate rectangle annotation parameters for two nodes.

    Wrapper around calculate_two_node_shape with shape_type="rectangle".
    """
    result = calculate_two_node_shape(node1, node2, area_name, "rectangle", text_offset_ratio)
    metadata = result["metadata"]
    return {
        "rectangle": result["shape"],
        "text": result["text"],
        "metadata": {
            "center_x": metadata["center_x"],
            "center_y": metadata["center_y"],
            "distance": metadata["distance"],
            "rect_width": metadata["shape_width"],
            "rect_height": metadata["shape_height"],
            "angle_deg": metadata["angle_deg"],
        },
    }
