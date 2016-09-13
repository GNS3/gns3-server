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

from .port import PORT_OBJECT_SCHEMA


NAT_OBJECT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Nat instance",
    "type": "object",
    "properties": {
        "name": {
            "description": "Nat name",
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
        "status": {
            "description": "Node status",
            "enum": ["started", "stopped", "suspended"]
        },
        "ports_mapping": {
            "type": "array",
            "items": [
                PORT_OBJECT_SCHEMA
            ]
        },
    },
    "additionalProperties": False,
    "required": ["name", "node_id", "project_id"]
}


NAT_CREATE_SCHEMA = NAT_OBJECT_SCHEMA
NAT_CREATE_SCHEMA["required"] = ["name"]

NAT_UPDATE_SCHEMA = NAT_OBJECT_SCHEMA
del NAT_UPDATE_SCHEMA["required"]
