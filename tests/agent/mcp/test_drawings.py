"""
MCP text drawing tests: SVG builder units and handler behavior.
"""

from unittest.mock import MagicMock, patch
from xml.etree import ElementTree as ET

import pytest

from gns3server.agent.mcp.drawings import build_text_svg, create_text_drawing_handler

BASE = "gns3server.agent.mcp"


def _mock_conn(json_result=None):
    """Create a mocked Gns3Connector with base_url and http_call."""
    conn = MagicMock()
    conn.base_url = "http://192.168.1.3:3080/v3"
    conn.http_call.return_value.json.return_value = json_result or {"status": "ok"}
    return conn


@pytest.fixture
def ctx():
    return {"server_url": "http://192.168.1.3:3080", "jwt_token": "token", "jwt_username": "admin"}


class TestBuildTextSvg:
    def test_single_line(self):
        svg, width, height, line_height = build_text_svg("R1", font_size=13)
        assert svg == (
            '<svg height="25" width="21">'
            '<text fill="#000000" fill-opacity="1.0" font-family="monospace" '
            'font-size="13" font-weight="normal">R1</text></svg>'
        )
        # 2 chars x 13 x 0.8 = 20.8 -> 21; one line of 13 x 1.9 = 24.7 -> 25
        assert width == 21
        assert height == 25
        assert line_height == 25

    def test_bold_and_color(self):
        svg, _, _, _ = build_text_svg("R1", font_size=13, color="#CC0000", bold=True)
        assert 'fill="#CC0000"' in svg
        assert 'font-weight="bold"' in svg

    def test_escapes_xml_characters(self):
        svg, _, _, _ = build_text_svg("a<b&c", font_size=10)
        root = ET.fromstring(svg)
        # round-trips through the parser back to the original text
        assert root.find("text").text == "a<b&c"
        assert "a&lt;b&amp;c" in svg

    def test_multi_line(self):
        svg, width, height, line_height = build_text_svg("hello\nworld!", font_size=10)
        # longest line is 6 chars x 10 x 0.8 = 48; two lines of ceil(19)
        assert width == 48
        assert height == 38
        assert line_height == 19
        assert "\n" in ET.fromstring(svg).find("text").text

    def test_proportional_font_wider(self):
        mono_w, _, _, _ = build_text_svg("same", font_size=10, font_family="monospace")
        prop_w, _, _, _ = build_text_svg("same", font_size=10, font_family="Noto Sans")
        assert prop_w > mono_w

    def test_empty_line_kept(self):
        # a blank line still occupies a line box
        _, _, height, line_height = build_text_svg("a\n\nb", font_size=10)
        assert height == 3 * line_height

    def test_matches_web_ui_serializer_shape(self):
        # byte-for-byte structural parity with the Web UI's own text output
        svg, width, height, _ = build_text_svg("demo", font_size=11)
        assert svg.startswith(f'<svg height="{height}" width="{width}"><text fill=')
        assert svg.endswith("</text></svg>")


class TestCreateTextDrawingHandler:
    def test_success(self, ctx):
        with patch(f"{BASE}.drawings._get_connector") as m:
            conn = _mock_conn({"drawing_id": "d1", "x": 100, "y": 80})
            m.return_value = conn
            result = create_text_drawing_handler(
                {"project_id": "p1", "text": "R1", "x": 100, "y": 80, "bold": True}, ctx
            )
        assert result["drawing"]["drawing_id"] == "d1"
        assert result["width"] == 21
        assert result["height"] == 25
        # z defaults to 1 (above links)
        body = conn.http_call.call_args.kwargs["json_data"]
        assert body["z"] == 1
        assert body["x"] == 100
        assert 'font-weight="bold"' in body["svg"]

    def test_missing_project_id(self, ctx):
        assert "error" in create_text_drawing_handler({"text": "R1"}, ctx)

    def test_missing_text(self, ctx):
        assert "error" in create_text_drawing_handler({"project_id": "p1"}, ctx)

    def test_blank_text(self, ctx):
        assert "error" in create_text_drawing_handler({"project_id": "p1", "text": "\n\n"}, ctx)

    def test_newline_normalization(self, ctx):
        with patch(f"{BASE}.drawings._get_connector") as m:
            conn = _mock_conn({"drawing_id": "d1"})
            m.return_value = conn
            create_text_drawing_handler({"project_id": "p1", "text": "a\r\nb"}, ctx)
        svg = conn.http_call.call_args.kwargs["json_data"]["svg"]
        assert "\r" not in svg

    def test_text_too_long(self, ctx):
        assert "error" in create_text_drawing_handler({"project_id": "p1", "text": "x" * 501}, ctx)

    def test_control_characters_rejected(self, ctx):
        assert "error" in create_text_drawing_handler({"project_id": "p1", "text": "a\x00b"}, ctx)

    @pytest.mark.parametrize("font_size", [0, 201, "13", 13.5, True])
    def test_bad_font_size(self, ctx, font_size):
        result = create_text_drawing_handler({"project_id": "p1", "text": "R1", "font_size": font_size}, ctx)
        assert "error" in result

    @pytest.mark.parametrize("color", ["red", "123456", "#GGGGGG", "#12345", "black\" onload=\"x"])
    def test_bad_color(self, ctx, color):
        result = create_text_drawing_handler({"project_id": "p1", "text": "R1", "color": color}, ctx)
        assert "error" in result

    @pytest.mark.parametrize("font_family", ['mono" onload="x', "sans<serif>", "a&b", ""])
    def test_bad_font_family(self, ctx, font_family):
        result = create_text_drawing_handler({"project_id": "p1", "text": "R1", "font_family": font_family}, ctx)
        assert "error" in result

    def test_font_family_with_spaces_accepted(self, ctx):
        with patch(f"{BASE}.drawings._get_connector") as m:
            conn = _mock_conn({"drawing_id": "d1"})
            m.return_value = conn
            result = create_text_drawing_handler(
                {"project_id": "p1", "text": "R1", "font_family": "DejaVu Sans Mono"}, ctx
            )
        assert "error" not in result

    def test_xml_entities_survive_round_trip(self, ctx):
        with patch(f"{BASE}.drawings._get_connector") as m:
            conn = _mock_conn({"drawing_id": "d1"})
            m.return_value = conn
            create_text_drawing_handler({"project_id": "p1", "text": "R1 & <backup>"}, ctx)
        svg = conn.http_call.call_args.kwargs["json_data"]["svg"]
        assert "R1 &amp; &lt;backup&gt;" in svg
        ET.fromstring(svg)
