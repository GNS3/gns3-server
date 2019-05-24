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

ETHERNET_SWITCH_CREATE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to create a new Ethernet switch instance",
    "type": "object",
    "definitions": {
        "EthernetSwitchPort": {
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
                "type": {
                    "description": "Port type",
                    "enum": ["access", "dot1q", "qinq"],
                },
                "vlan": {"description": "VLAN number",
                         "type": "integer",
                         "minimum": 1
                         },
                "ethertype": {
                    "description": "QinQ Ethertype",
                    "enum": ["", "0x8100", "0x88A8", "0x9100", "0x9200"],
                },
            },
            "required": ["name", "port_number", "type"],
            "additionalProperties": False
        },
    },
    "properties": {
        "name": {
            "description": "Ethernet switch name",
            "type": "string",
            "minLength": 1,
        },
        "console": {
            "description": "Console TCP port",
            "minimum": 1,
            "maximum": 65535,
            "type": ["integer", "null"]
        },
        "console_type": {
            "description": "Console type",
            "enum": ["telnet", "none"]
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
            "items": [
                {"type": "object",
                 "oneOf": [
                     {"$ref": "#/definitions/EthernetSwitchPort"}
                 ]},
            ]
        },
    },
    "additionalProperties": False,
    "required": ["name"]
}

ETHERNET_SWITCH_OBJECT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Ethernet switch instance",
    "type": "object",
    "definitions": {
        "EthernetSwitchPort": {
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
                "type": {
                    "description": "Port type",
                    "enum": ["access", "dot1q", "qinq"],
                },
                "vlan": {"description": "VLAN number",
                         "type": "integer",
                         "minimum": 1
                         },
                "ethertype": {
                    "description": "QinQ Ethertype",
                    "enum": ["", "0x8100", "0x88A8", "0x9100", "0x9200"],
                },
            },
            "required": ["name", "port_number", "type"],
            "additionalProperties": False
        },
    },
    "properties": {
        "name": {
            "description": "Ethernet switch name",
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
            "items": [
                {"type": "object",
                 "oneOf": [
                     {"$ref": "#/definitions/EthernetSwitchPort"}
                 ]},
            ]
        },
        "status": {
            "description": "Node status",
            "enum": ["started", "stopped", "suspended"]
        },
        "console": {
            "description": "Console TCP port",
            "minimum": 1,
            "maximum": 65535,
            "type": ["integer", "null"]
        },
        "console_type": {
            "description": "Console type",
            "enum": ["telnet", "none"]
        },
    },
    "additionalProperties": False,
    "required": ["name", "node_id", "project_id"]
}

ETHERNET_SWITCH_UPDATE_SCHEMA = copy.deepcopy(ETHERNET_SWITCH_OBJECT_SCHEMA)
del ETHERNET_SWITCH_UPDATE_SCHEMA["required"]
