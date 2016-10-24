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

"""
Helper for conversion of Qt stuff
"""


def qt_font_to_style(font, color):
    """
    Convert a Qt font to CSS style
    """
    if font is None:
        font = "TypeWriter,10,-1,5,75,0,0,0,0,0"
    font_info = font.split(",")
    style = "font-family: {};font-size: {};".format(font_info[0], font_info[1])
    if font_info[4] == "75":
        style += "font-weight: bold;"
    if font_info[5] == "1":
        style += "font-style: italic;"

    if color is None:
        color = "000000"
    if len(color) == 9:
        style += "fill: #" + color[-6:] + ";"
        style += "fill-opacity: {};".format(round(1.0 / 255 * int(color[:3][-2:], base=16), 2))
    else:
        style += "fill: #" + color[-6:] + ";"
        style += "fill-opacity: {};".format(1.0)
    return style
