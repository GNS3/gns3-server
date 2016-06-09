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
        "color": {
            "type": "string",
            "pattern": "^#[0-9a-f]{6,8}$"
        },
        "font": {
            "type": "string",
            "minLength": 1
        },
        "text": {"type": "string"},
        "x": {"type": "number"},
        "y": {"type": "number"},
        "z": {"type": "number"},
        "rotation": {"type": "number"}
    },
    "required": [
        "text",
        "x",
        "y"
    ],
    "additionalProperties": False
}
