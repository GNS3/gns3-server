# -*- coding: utf-8 -*-
#
# Copyright (C) 2014 GNS3 Technologies Inc.
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


ETHERNET_HUB_CREATE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to create a new Ethernet hub instance",
    "type": "object",
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
        }
    },
    "additionalProperties": False,
    "required": ["name"]
}

ETHERNET_HUB_OBJECT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Ethernet hub instance",
    "type": "object",
    "definitions": {
        "EthernetPort": {
            "description": "Ethernet port",
            "properties": {
                "port": {
                    "description": "Port number",
                    "type": "integer",
                    "minimum": 1
                },
            },
            "required": ["port"],
            "additionalProperties": False
        },
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
        "ports": {
            "type": "array",
            "items": [
                {"type": "object",
                 "oneOf": [
                     {"$ref": "#/definitions/EthernetPort"}
                 ]},
            ]
        }
    },
    "additionalProperties": False,
    "required": ["name", "node_id", "project_id"]
}

ETHERNET_HUB_UPDATE_SCHEMA = ETHERNET_HUB_OBJECT_SCHEMA
del ETHERNET_HUB_UPDATE_SCHEMA["required"]
