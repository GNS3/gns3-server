#!/usr/bin/env python
#
# Copyright (C) 2015 GNS3 Technologies Inc.
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


DRAWING_OBJECT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "An drawing object",
    "type": "object",
    "properties": {
        "drawing_id": {
            "description": "Drawing UUID",
            "type": "string",
            "minLength": 36,
            "maxLength": 36,
            "pattern": "^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$"
        },
        "project_id": {
            "description": "Project UUID",
            "type": "string",
            "minLength": 36,
            "maxLength": 36,
            "pattern": "^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$"
        },
        "x": {
            "description": "X property",
            "type": "integer"
        },
        "y": {
            "description": "Y property",
            "type": "integer"
        },
        "z": {
            "description": "Z property",
            "type": "integer"
        },
        "rotation": {
            "description": "Rotation of the element",
            "type": "integer",
            "minimum": -359,
            "maximum": 360
        },
        "svg": {
            "description": "SVG content of the drawing",
            "type": "string"
        }
    },
    "additionalProperties": False
}
