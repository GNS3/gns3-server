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

LABEL_OBJECT_SCHEMA = {
    "type": "object",
    "properties": {
        "text": {"type": "string"},
        "style": {
            "description": "SVG style attribute. Apply default style if null",
            "type": ["string", "null"]
        },
        "x": {
            "description": "Relative X position of the label. Center it if null",
            "type": ["integer", "null"]
        },
        "y": {
            "description": "Relative Y position of the label",
            "type": "integer"
        },
        "rotation": {
            "description": "Rotation of the label",
            "type": "integer",
            "minimum": -359,
            "maximum": 360
        },
    },
    "required": [
        "text"
    ],
    "additionalProperties": False
}
