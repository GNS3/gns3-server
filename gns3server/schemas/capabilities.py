# -*- coding: utf-8 -*-
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

from .node import NODE_TYPE_SCHEMA


CAPABILITIES_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Get what a server support",
    "type": "object",
    "required": ["version", "node_types"],
    "properties": {
        "version": {
            "description": "Version number",
            "type": ["string", "null"],
        },
        "node_types": {
            "type": "array",
            "items": NODE_TYPE_SCHEMA,
            "description": "Node type supported by the compute"
        },
        "platform": {
            "type": "string",
            "description": "Platform where the compute is running"
        }
    },
    "additionalProperties": False
}
