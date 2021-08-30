#!/usr/bin/env python
#
# Copyright (C) 2016 GNS3 Technologies Inc.
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

import re
import io
import struct
from xml.etree.ElementTree import ElementTree, ParseError


def get_size(data, default_width=0, default_height=0):
    """
    Get image size
    :param data: A buffer with image content
    :return: Tuple (width, height, filetype)
    """

    height = default_height
    width = default_width
    filetype = None

    # Original version:
    # https://github.com/shibukawa/imagesize_py
    #
    # The MIT License (MIT)
    #
    # Copyright © 2016 Yoshiki Shibukawa
    #
    # Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the “Software”), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
    #
    # The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
    #
    # THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

    size = len(data)
    # handle GIFs
    if size >= 10 and data[:6] in (b'GIF87a', b'GIF89a'):
        # Check to see if content_type is correct
        try:
            width, height = struct.unpack("<hh", data[6:10])
            filetype = "gif"
        except struct.error:
            raise ValueError("Invalid GIF file")
    # see png edition spec bytes are below chunk length then and finally the
    elif size >= 24 and data.startswith(b'\211PNG\r\n\032\n') and data[12:16] == b'IHDR':
        try:
            width, height = struct.unpack(">LL", data[16:24])
            filetype = "png"
        except struct.error:
            raise ValueError("Invalid PNG file")
    # Maybe this is for an older PNG version.
    elif size >= 16 and data.startswith(b'\211PNG\r\n\032\n'):
        # Check to see if we have the right content type
        try:
            width, height = struct.unpack(">LL", data[8:16])
            filetype = "png"
        except struct.error:
            raise ValueError("Invalid PNG file")
    # handle JPEGs
    elif size >= 2 and data.startswith(b'\377\330'):
        try:
            # Not very efficient to copy data to a buffer
            fhandle = io.BytesIO(data)
            size = 2
            ftype = 0
            while not 0xc0 <= ftype <= 0xcf:
                fhandle.seek(size, 1)
                byte = fhandle.read(1)
                while ord(byte) == 0xff:
                    byte = fhandle.read(1)
                ftype = ord(byte)
                size = struct.unpack('>H', fhandle.read(2))[0] - 2
            # We are at a SOFn block
            fhandle.seek(1, 1)  # Skip `precision' byte.
            height, width = struct.unpack('>HH', fhandle.read(4))
            filetype = "jpg"
        except struct.error:
            raise ValueError("Invalid JPEG file")
    # End of https://github.com/shibukawa/imagesize_py

    # handle SVG
    elif size >= 10 and (data.startswith(b'<?xml') or data.startswith(b'<svg')):
        filetype = "svg"
        fhandle = io.BytesIO(data)
        tree = ElementTree()
        try:
            tree.parse(fhandle)
        except ParseError:
            raise ValueError("Invalid SVG file")

        root = tree.getroot()

        try:
            width_attr = root.attrib.get("width", "100%")
            height_attr = root.attrib.get("height", "100%")
            if width_attr.endswith("%") or height_attr.endswith("%"):
                # check to viewBox attribute if width or height value is a percentage
                viewbox = root.attrib.get("viewBox")
                if not viewbox:
                    raise ValueError("Invalid SVG file: missing viewBox attribute")
                _, _, viewbox_width, viewbox_height = re.split(r'[\s,]+', viewbox)
            if width_attr.endswith("%"):
                width = _svg_convert_size(viewbox_width, width_attr)
            else:
                width = _svg_convert_size(width_attr)
            if height_attr.endswith("%"):
                height = _svg_convert_size(viewbox_height, height_attr)
            else:
                height = _svg_convert_size(height_attr)
        except (AttributeError, IndexError) as e:
            raise ValueError("Invalid SVG file: {}".format(e))

    return width, height, filetype


def _svg_convert_size(size, percent=None):
    """
    Convert svg size to the px version

    :param size: String with the size
    :param percent: String with the percentage, None = 100%
    """

    # https://www.w3.org/TR/SVG/coords.html#Units
    conversion_table = {
        "pt": 1.25,
        "pc": 15,
        "mm": 3.543307,
        "cm": 35.43307,
        "in": 90,
        "px": 1
    }
    factor = 1.0
    if len(size) >= 3:
        if size[-2:] in conversion_table:
            factor = conversion_table[size[-2:]]
            size = size[:-2]
    if percent:
        factor *= float(percent.rstrip("%")) / 100.0
    return round(float(size) * factor)
