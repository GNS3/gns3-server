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


VPCS_CREATE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to create a new VPCS instance",
    "type": "object",
    "properties": {
        "name": {
            "description": "VPCS VM name",
            "type": "string",
            "minLength": 1,
        },
        "node_id": {
            "description": "Node UUID",
            "oneOf": [
                {"type": "string",
                 "minLength": 36,
                 "maxLength": 36,
                 "pattern": "^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$"},
                {"type": "integer"}  # for legacy projects
            ]
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
        "startup_script": {
            "description": "Content of the VPCS startup script",
            "type": ["string", "null"]
        },
    },
    "additionalProperties": False,
    "required": ["name"]
}

VPCS_UPDATE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to update a VPCS instance",
    "type": "object",
    "properties": {
        "name": {
            "description": "VPCS VM name",
            "type": ["string", "null"],
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
    },
    "additionalProperties": False,
}

VPCS_OBJECT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "VPCS instance",
    "type": "object",
    "properties": {
        "name": {
            "description": "VPCS VM name",
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
        "node_directory": {
            "description": "Path to the VM working directory",
            "type": "string"
        },
        "status": {
            "description": "VM status",
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
        "project_id": {
            "description": "Project UUID",
            "type": "string",
            "minLength": 36,
            "maxLength": 36,
            "pattern": "^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$"
        },
        "command_line": {
            "description": "Last command line used by GNS3 to start VPCS",
            "type": "string"
        }
    },
    "additionalProperties": False,
    "required": ["name", "node_id", "status", "console", "console_type", "project_id", "command_line"]
}
