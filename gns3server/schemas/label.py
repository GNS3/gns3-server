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
            "description": "SVG style attribute",
            "type": "string"
        },
        "x": {
            "description": "Relative X position of the label. If null center it",
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
        "text",
        "x",
        "y"
    ],
    "additionalProperties": False
}
