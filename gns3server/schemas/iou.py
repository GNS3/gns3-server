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


IOU_CREATE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to create a new IOU instance",
    "type": "object",
    "properties": {
        "name": {
            "description": "IOU VM name",
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
        "usage": {
            "description": "How to use the IOU VM",
            "type": "string",
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
        "path": {
            "description": "Path of iou binary",
            "type": "string"
        },
        "md5sum": {
            "description": "Checksum of iou binary",
            "type": ["string", "null"]
        },
        "serial_adapters": {
            "description": "How many serial adapters are connected to the IOU",
            "type": "integer"
        },
        "ethernet_adapters": {
            "description": "How many ethernet adapters are connected to the IOU",
            "type": "integer"
        },
        "ram": {
            "description": "Allocated RAM MB",
            "type": ["integer", "null"]
        },
        "nvram": {
            "description": "Allocated NVRAM KB",
            "type": ["integer", "null"]
        },
        "l1_keepalives": {
            "description": "Always up ethernet interface",
            "type": ["boolean", "null"]
        },
        "use_default_iou_values": {
            "description": "Use default IOU values",
            "type": ["boolean", "null"]
        },
        "startup_config_content": {
            "description": "Startup-config of IOU",
            "type": ["string", "null"]
        },
        "private_config_content": {
            "description": "Private-config of IOU",
            "type": ["string", "null"]
        },
        "application_id": {
            "description": "Application ID for running IOU image",
            "type": ["integer", "null"]
        },
    },
    "additionalProperties": False,
    "required": ["application_id", "name", "path"]
}


IOU_START_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to start an IOU instance",
    "type": "object",
    "properties": {
        "iourc_content": {
            "description": "Content of the iourc file. Ignored if Null",
            "type": ["string", "null"]
        },
        "license_check": {
            "description": "Whether the license should be checked",
            "type": "boolean"
        }
    }
}


IOU_OBJECT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "IOU instance",
    "type": "object",
    "properties": {
        "name": {
            "description": "IOU VM name",
            "type": "string",
            "minLength": 1,
        },
        "node_id": {
            "description": "IOU VM UUID",
            "type": "string",
            "minLength": 36,
            "maxLength": 36,
            "pattern": "^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$"
        },
        "usage": {
            "description": "How to use the IOU VM",
            "type": "string",
        },
        "node_directory": {
            "description": "Path to the node working directory",
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
        "path": {
            "description": "Path of iou binary",
            "type": "string"
        },
        "md5sum": {
            "description": "Checksum of iou binary",
            "type": ["string", "null"]
        },
        "serial_adapters": {
            "description": "How many serial adapters are connected to the IOU",
            "type": "integer"
        },
        "ethernet_adapters": {
            "description": "How many ethernet adapters are connected to the IOU",
            "type": "integer"
        },
        "ram": {
            "description": "Allocated RAM MB",
            "type": "integer"
        },
        "nvram": {
            "description": "Allocated NVRAM KB",
            "type": "integer"
        },
        "l1_keepalives": {
            "description": "Always up ethernet interface",
            "type": "boolean"
        },
        "use_default_iou_values": {
            "description": "Use default IOU values",
            "type": ["boolean", "null"]
        },
        "command_line": {
            "description": "Last command line used by GNS3 to start IOU",
            "type": "string"
        },
        "application_id": {
            "description": "Application ID for running IOU image",
            "type": "integer"
        },
    },
    "additionalProperties": False
}
