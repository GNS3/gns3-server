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
from .port import PORT_OBJECT_SCHEMA

HOST_INTERFACE_SCHEMA = {
    "description": "Interfaces on this host",
    "properties": {
        "name": {
            "description": "Interface name",
            "type": "string",
            "minLength": 1,
        },
        "type": {
            "description": "Interface type",
            "enum": ["ethernet", "tap"]
        },
        "special": {
            "description": "If true the interface is non standard (firewire for example)",
            "type": "boolean"
        }
    },
    "required": ["name", "type", "special"],
    "additionalProperties": False
}


CLOUD_CREATE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to create a new cloud instance",
    "type": "object",
    "definitions": {
        "HostInterfaces": HOST_INTERFACE_SCHEMA
    },
    "properties": {
        "name": {
            "description": "Cloud name",
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
        "remote_console_host": {
            "description": "Remote console host or IP",
            "type": ["string"]
        },
        "remote_console_port": {
            "description": "Console TCP port",
            "minimum": 1,
            "maximum": 65535,
            "type": ["integer", "null"]
        },
        "remote_console_type": {
            "description": "Console type",
            "enum": ["telnet", "vnc", "spice", "http", "https", "none"]
        },
        "remote_console_http_path": {
            "description": "Path of the remote web interface",
            "type": "string",
        },
        "ports_mapping": {
            "type": "array",
            "items": [
                PORT_OBJECT_SCHEMA
            ]
        },
        "interfaces": {
            "type": "array",
            "items": [
                {"type": "object",
                 "oneOf": [
                     {"$ref": "#/definitions/HostInterfaces"}
                 ]},
            ]
        }
    },
    "additionalProperties": False,
    "required": ["name"]
}

CLOUD_OBJECT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Cloud instance",
    "type": "object",
    "definitions": {
        "HostInterfaces": HOST_INTERFACE_SCHEMA
    },
    "properties": {
        "name": {
            "description": "Cloud name",
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
        "remote_console_host": {
            "description": "Remote console host or IP",
            "type": ["string"]
        },
        "remote_console_port": {
            "description": "Console TCP port",
            "minimum": 1,
            "maximum": 65535,
            "type": ["integer", "null"]
        },
        "remote_console_type": {
            "description": "Console type",
            "enum": ["telnet", "vnc", "spice", "http", "https", "none"]
        },
        "remote_console_http_path": {
            "description": "Path of the remote web interface",
            "type": "string",
        },
        "ports_mapping": {
            "type": "array",
            "items": [
                PORT_OBJECT_SCHEMA
            ]
        },
        "interfaces": {
            "type": "array",
            "items": [
                {"type": "object",
                 "oneOf": [
                     {"$ref": "#/definitions/HostInterfaces"}
                 ]},
            ]
        },
        "node_directory": {
            "description": "Path to the VM working directory",
            "type": "string"
        },
        "status": {
            "description": "Node status",
            "enum": ["started", "stopped", "suspended"]
        },
    },
    "additionalProperties": False,
    "required": ["name", "node_id", "project_id", "ports_mapping"]
}

CLOUD_UPDATE_SCHEMA = copy.deepcopy(CLOUD_OBJECT_SCHEMA)
del CLOUD_UPDATE_SCHEMA["required"]
