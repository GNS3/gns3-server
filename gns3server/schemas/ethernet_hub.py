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

ETHERNET_HUB_PORT_SCHEMA = {
    "description": "Ethernet port",
    "properties": {
        "name": {
            "description": "Port name",
            "type": "string",
            "minLength": 1,
        },
        "port_number": {
            "description": "Port number",
            "type": "integer",
            "minimum": 0
        },
    },
    "required": ["name", "port_number"],
    "additionalProperties": False
}

ETHERNET_HUB_CREATE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to create a new Ethernet hub instance",
    "type": "object",
    "definitions": {
        "EthernetHubPort": ETHERNET_HUB_PORT_SCHEMA
    },
    "properties": {
        "name": {
            "description": "Ethernet hub name",
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
        "ports_mapping": {
            "type": "array",
            "items": {
                "$ref": "#/definitions/EthernetHubPort"
            }
        },
    },
    "additionalProperties": False,
    "required": ["name"]
}

ETHERNET_HUB_OBJECT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Ethernet hub instance",
    "type": "object",
    "definitions": {
        "EthernetHubPort": ETHERNET_HUB_PORT_SCHEMA
    },
    "properties": {
        "name": {
            "description": "Ethernet hub name",
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
        "ports_mapping": {
            "type": "array",
            "items": {
                "$ref": "#/definitions/EthernetHubPort"
            }
        },
        "status": {
            "description": "Node status",
            "enum": ["started", "stopped", "suspended"]
        },
    },
    "additionalProperties": False,
    "required": ["name", "node_id", "project_id", "ports_mapping"]
}

ETHERNET_HUB_UPDATE_SCHEMA = copy.deepcopy(ETHERNET_HUB_OBJECT_SCHEMA)
del ETHERNET_HUB_UPDATE_SCHEMA["required"]
