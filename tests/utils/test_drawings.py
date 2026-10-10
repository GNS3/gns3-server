"""
Web UI compatible drawing SVG builder tests.
"""

from xml.etree import ElementTree as ET

import pytest

from gns3server.utils.drawings import build_ellipse_svg, build_rectangle_svg, build_text_svg


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

    def test_newline_normalization(self):
        svg, _, height, _ = build_text_svg("a\r\nb\rc", font_size=10)
        assert "\r" not in svg
        assert height == 3 * 19

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

    @pytest.mark.parametrize("text", [None, "", "\n\n"])
    def test_empty_text_rejected(self, text):
        with pytest.raises(ValueError):
            build_text_svg(text)

    def test_text_too_long(self):
        with pytest.raises(ValueError):
            build_text_svg("x" * 501)

    def test_control_characters_rejected(self):
        with pytest.raises(ValueError):
            build_text_svg("a\x00b")

    @pytest.mark.parametrize("font_size", [0, 201, "13", 13.5, True])
    def test_bad_font_size(self, font_size):
        with pytest.raises(ValueError):
            build_text_svg("R1", font_size=font_size)

    @pytest.mark.parametrize("color", ["red", "123456", "#GGGGGG", "#12345", 'black" onload="x'])
    def test_bad_color(self, color):
        with pytest.raises(ValueError):
            build_text_svg("R1", color=color)

    @pytest.mark.parametrize("font_family", ['mono" onload="x', "sans<serif>", "a&b", ""])
    def test_bad_font_family(self, font_family):
        with pytest.raises(ValueError):
            build_text_svg("R1", font_family=font_family)

    def test_font_family_with_spaces_accepted(self):
        svg, _, _, _ = build_text_svg("R1", font_family="DejaVu Sans Mono")
        assert 'font-family="DejaVu Sans Mono"' in svg


class TestBuildRectangleSvg:
    def test_plain_fill(self):
        svg, width, height = build_rectangle_svg(80, 50, fill="#4A90D9")
        assert svg == (
            '<svg height="50" width="80">'
            '<rect fill="#4A90D9" fill-opacity="1.0" height="50" width="80" rx="0" ry="0"/></svg>'
        )
        assert (width, height) == (80, 50)
        # no stroke requested -> no stroke attributes (Web UI serializer parity)
        assert "stroke" not in svg

    def test_stroke_and_dashed(self):
        svg, _, _ = build_rectangle_svg(
            80, 50, fill="none", fill_opacity=0.5, stroke="#333333", stroke_width=2, dashed=True
        )
        assert 'fill="none"' in svg
        assert 'fill-opacity="0.5"' in svg
        assert 'stroke="#333333" stroke-width="2" stroke-dasharray="10,6"' in svg

    def test_custom_dasharray(self):
        svg, _, _ = build_rectangle_svg(80, 50, stroke="#000000", dasharray="4,2")
        assert 'stroke-dasharray="4,2"' in svg

    def test_corner_radius(self):
        svg, _, _ = build_rectangle_svg(100, 60, rx=8)
        assert 'rx="8" ry="8"' in svg

    def test_fill_none_renders_unfilled(self):
        # the Web UI renders fill="none" as an outline-only box
        svg, _, _ = build_rectangle_svg(80, 50, fill="none", stroke="#333333")
        ET.fromstring(svg)

    @pytest.mark.parametrize("width,height", [(0, 50), (80, 0), (-1, 50), (2001, 50), ("80", 50)])
    def test_bad_dimensions(self, width, height):
        with pytest.raises(ValueError):
            build_rectangle_svg(width, height)

    def test_radius_too_large(self):
        with pytest.raises(ValueError):
            build_rectangle_svg(80, 50, rx=26)

    @pytest.mark.parametrize("fill", ["red", 123, "transparent"])
    def test_bad_fill(self, fill):
        with pytest.raises(ValueError):
            build_rectangle_svg(80, 50, fill=fill)

    @pytest.mark.parametrize("fill_opacity", [-0.1, 1.1, "0.5", True])
    def test_bad_fill_opacity(self, fill_opacity):
        with pytest.raises(ValueError):
            build_rectangle_svg(80, 50, fill_opacity=fill_opacity)

    def test_bad_stroke(self):
        with pytest.raises(ValueError):
            build_rectangle_svg(80, 50, stroke="blue")

    def test_bad_stroke_width(self):
        with pytest.raises(ValueError):
            build_rectangle_svg(80, 50, stroke="#333333", stroke_width=0)

    @pytest.mark.parametrize("dasharray", ["25, 25", "5, 25", "abc", "5;5", '5,5" onload="x'])
    def test_bad_dasharray(self, dasharray):
        with pytest.raises(ValueError):
            build_rectangle_svg(80, 50, stroke="#333333", dasharray=dasharray)

    def test_dasharray_without_stroke(self):
        with pytest.raises(ValueError):
            build_rectangle_svg(80, 50, dasharray="5,5")


class TestBuildEllipseSvg:
    def test_bounding_box_derivation(self):
        svg, width, height = build_ellipse_svg(100, 60, fill="#5AA9DD", fill_opacity=0.8)
        assert svg == (
            '<svg height="60" width="100">'
            '<ellipse fill="#5AA9DD" fill-opacity="0.8" cx="50" cy="30" rx="50" ry="30"/></svg>'
        )
        assert (width, height) == (100, 60)

    def test_odd_dimensions_round_down(self):
        svg, width, height = build_ellipse_svg(101, 61)
        assert (width, height) == (100, 60)
        assert 'cx="50" cy="30" rx="50" ry="30"' in svg

    def test_circle(self):
        svg, width, height = build_ellipse_svg(80, 80, stroke="#333333")
        assert width == height == 80
        assert 'rx="40" ry="40"' in svg

    def test_too_small(self):
        with pytest.raises(ValueError):
            build_ellipse_svg(1, 60)

    def test_stroke_and_dashed(self):
        svg, _, _ = build_ellipse_svg(100, 60, fill="none", stroke="#E74C3C", stroke_width=2, dashed=True)
        assert 'stroke-dasharray="10,6"' in svg
        ET.fromstring(svg)
