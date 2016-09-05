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


PORT_OBJECT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "A port use in the cloud",
    "type": "object",
    "oneOf": [
        {
            "description": "Ethernet interface port",
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
                    "enum": ["ethernet"]
                },
                "interface": {
                    "description": "Ethernet interface name e.g. eth0",
                    "type": "string",
                    "minLength": 1
                },
            },
            "required": ["name", "port_number", "type", "interface"],
            "additionalProperties": False
        },
        {
            "description": "TAP interface port",
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
                    "enum": ["tap"]
                },
                "interface": {
                    "description": "TAP interface name e.g. tap0",
                    "type": "string",
                    "minLength": 1
                },
            },
            "required": ["name", "port_number", "type", "interface"],
            "additionalProperties": False
        },
        {
            "description": "UDP tunnel port",
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
                    "enum": ["udp"]
                },
                "lport": {
                    "description": "Local UDP tunnel port",
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 65535
                },
                "rhost": {
                    "description": "Remote UDP tunnel host",
                    "type": "string",
                    "minLength": 1
                },
                "rport": {
                    "description": "Remote UDP tunnel port",
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 65535
                }
            },
            "required": ["name", "port_number", "type", "lport", "rhost", "rport"],
            "additionalProperties": False
        }
    ]
}
