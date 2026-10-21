"""
MCP drawing handler tests: text/rectangle/ellipse creation via the shared
api_handlers layer (SVG building units live in tests/utils/test_drawings.py).
"""

from unittest.mock import MagicMock, patch
from xml.etree import ElementTree as ET

import pytest

from gns3server.agent.gns3_copilot.gns3_client.api_handlers import (
    create_ellipse_drawing_handler,
    create_rectangle_drawing_handler,
    create_text_drawing_handler,
)

AH = "gns3server.agent.gns3_copilot.gns3_client.api_handlers"


def _mock_conn(json_result=None):
    """Create a mocked Gns3Connector with base_url and http_call."""
    conn = MagicMock()
    conn.base_url = "http://192.168.1.3:3080/v3"
    conn.http_call.return_value.json.return_value = json_result or {"status": "ok"}
    return conn


@pytest.fixture
def ctx():
    return {"server_url": "http://192.168.1.3:3080", "jwt_token": "token", "jwt_username": "admin"}


class TestCreateTextDrawingHandler:
    def test_success(self, ctx):
        with patch(f"{AH}._get_connector") as m:
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
        with patch(f"{AH}._get_connector") as m:
            conn = _mock_conn({"drawing_id": "d1"})
            m.return_value = conn
            create_text_drawing_handler({"project_id": "p1", "text": "a\r\nb"}, ctx)
        svg = conn.http_call.call_args.kwargs["json_data"]["svg"]
        assert "\r" not in svg

    @pytest.mark.parametrize("font_size", [0, 201, "13", 13.5, True])
    def test_bad_font_size(self, ctx, font_size):
        result = create_text_drawing_handler({"project_id": "p1", "text": "R1", "font_size": font_size}, ctx)
        assert "error" in result

    @pytest.mark.parametrize("color", ["red", "123456", "#GGGGGG", "#12345", 'black" onload="x'])
    def test_bad_color(self, ctx, color):
        result = create_text_drawing_handler({"project_id": "p1", "text": "R1", "color": color}, ctx)
        assert "error" in result

    @pytest.mark.parametrize("font_family", ['mono" onload="x', "sans<serif>", "a&b", ""])
    def test_bad_font_family(self, ctx, font_family):
        result = create_text_drawing_handler({"project_id": "p1", "text": "R1", "font_family": font_family}, ctx)
        assert "error" in result

    def test_xml_entities_survive_round_trip(self, ctx):
        with patch(f"{AH}._get_connector") as m:
            conn = _mock_conn({"drawing_id": "d1"})
            m.return_value = conn
            create_text_drawing_handler({"project_id": "p1", "text": "R1 & <backup>"}, ctx)
        svg = conn.http_call.call_args.kwargs["json_data"]["svg"]
        assert "R1 &amp; &lt;backup&gt;" in svg
        ET.fromstring(svg)


class TestCreateRectangleDrawingHandler:
    def test_success(self, ctx):
        with patch(f"{AH}._get_connector") as m:
            conn = _mock_conn({"drawing_id": "d2"})
            m.return_value = conn
            result = create_rectangle_drawing_handler(
                {"project_id": "p1", "x": 200, "y": 150, "width": 80, "height": 50, "fill": "#4A90D9"}, ctx
            )
        assert result["drawing"]["drawing_id"] == "d2"
        assert result["width"] == 80
        assert result["height"] == 50
        body = conn.http_call.call_args.kwargs["json_data"]
        # z defaults to 0 (shapes behind text and nodes)
        assert body["z"] == 0
        assert body["svg"] == (
            '<svg height="50" width="80">'
            '<rect fill="#4A90D9" fill-opacity="1.0" height="50" width="80" rx="0" ry="0"/></svg>'
        )

    def test_missing_dimensions(self, ctx):
        assert "error" in create_rectangle_drawing_handler({"project_id": "p1"}, ctx)

    def test_bad_fill_returns_error(self, ctx):
        result = create_rectangle_drawing_handler({"project_id": "p1", "width": 80, "height": 50, "fill": "red"}, ctx)
        assert "error" in result

    def test_qt_remapped_dasharray_rejected(self, ctx):
        result = create_rectangle_drawing_handler(
            {"project_id": "p1", "width": 80, "height": 50, "stroke": "#333333", "dasharray": "25, 25"}, ctx
        )
        assert "error" in result


class TestCreateEllipseDrawingHandler:
    def test_success(self, ctx):
        with patch(f"{AH}._get_connector") as m:
            conn = _mock_conn({"drawing_id": "d3"})
            m.return_value = conn
            result = create_ellipse_drawing_handler(
                {"project_id": "p1", "x": 300, "y": 300, "width": 160, "height": 160, "fill": "#5AA9DD"}, ctx
            )
        assert result["drawing"]["drawing_id"] == "d3"
        body = conn.http_call.call_args.kwargs["json_data"]
        assert body["z"] == 0
        assert body["svg"] == (
            '<svg height="160" width="160">'
            '<ellipse fill="#5AA9DD" fill-opacity="1.0" cx="80" cy="80" rx="80" ry="80"/></svg>'
        )

    def test_odd_dimensions_report_actual_size(self, ctx):
        with patch(f"{AH}._get_connector") as m:
            conn = _mock_conn({"drawing_id": "d3"})
            m.return_value = conn
            result = create_ellipse_drawing_handler({"project_id": "p1", "width": 101, "height": 61}, ctx)
        assert (result["width"], result["height"]) == (100, 60)

    def test_too_small(self, ctx):
        result = create_ellipse_drawing_handler({"project_id": "p1", "width": 1, "height": 60}, ctx)
        assert "error" in result

    def test_missing_dimensions(self, ctx):
        assert "error" in create_ellipse_drawing_handler({"project_id": "p1", "width": 100}, ctx)
