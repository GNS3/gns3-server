# -*- coding: utf-8 -*-
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

import copy

FRAME_RELAY_SWITCH_CREATE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to create a new Frame Relay switch instance",
    "type": "object",
    "properties": {
        "name": {
            "description": "Frame Relay switch name",
            "type": "string",
            "minLength": 1,
        },
        "node_id": {
            "description": "Node UUID",
            "oneOf": [
                {"type": "string",
                 "minLength": 36,
                 "maxLength": 36,
                 "pattern": "^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$"}
            ]
        },
        "mappings": {
            "description": "Frame Relay mappings",
            "type": "object",
        },
    },
    "additionalProperties": False,
    "required": ["name"]
}

FRAME_RELAY_SWITCH_OBJECT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Frame Relay switch instance",
    "type": "object",
    "properties": {
        "name": {
            "description": "Frame Relay switch name",
            "type": "string",
            "minLength": 1,
        },
        "node_id": {
            "description": "Node UUID",
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
        "mappings": {
            "description": "Frame Relay mappings",
            "type": "object",
        },
        "status": {
            "description": "Node status",
            "enum": ["started", "stopped", "suspended"]
        },
    },
    "additionalProperties": False,
    "required": ["name", "node_id", "project_id"]
}

FRAME_RELAY_SWITCH_UPDATE_SCHEMA = copy.deepcopy(FRAME_RELAY_SWITCH_OBJECT_SCHEMA)
del FRAME_RELAY_SWITCH_UPDATE_SCHEMA["required"]
