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
        "vm_id": {
            "description": "VPCS VM identifier",
            "oneOf": [
                {"type": "string",
                 "minLength": 36,
                 "maxLength": 36,
                 "pattern": "^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$"},
                {"type": "integer"}  # for legacy projects
            ]
        },
        "console": {
            "description": "console TCP port",
            "minimum": 1,
            "maximum": 65535,
            "type": ["integer", "null"]
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
            "description": "console TCP port",
            "minimum": 1,
            "maximum": 65535,
            "type": ["integer", "null"]
        },
        "startup_script": {
            "description": "Content of the VPCS startup script",
            "type": ["string", "null"]
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
        "vm_id": {
            "description": "VPCS VM UUID",
            "type": "string",
            "minLength": 36,
            "maxLength": 36,
            "pattern": "^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$"
        },
        "vm_directory": {
            "decription": "Path to the VM working directory",
            "type": "string"
        },
        "status": {
            "description": "VM status",
            "enum": ["started", "stopped"]
        },
        "console": {
            "description": "console TCP port",
            "minimum": 1,
            "maximum": 65535,
            "type": "integer"
        },
        "project_id": {
            "description": "Project UUID",
            "type": "string",
            "minLength": 36,
            "maxLength": 36,
            "pattern": "^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$"
        },
        "startup_script": {
            "description": "Content of the VPCS startup script",
            "type": ["string", "null"]
        },
        "startup_script_path": {
            "description": "Path of the VPCS startup script relative to project directory",
            "type": ["string", "null"]
        },
        "command_line": {
            "description": "Last command line used by GNS3 to start QEMU",
            "type": "string"
        }
    },
    "additionalProperties": False,
    "required": ["name", "vm_id", "status", "console", "project_id", "startup_script_path", "command_line"]
}
