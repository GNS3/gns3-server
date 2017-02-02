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
        "console": {
            "description": "Console TCP port",
            "minimum": 1,
            "maximum": 65535,
            "type": ["integer", "null"]
        },
        "console_type": {
            "description": "Console type",
            "enum": ["telnet", None]
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
        "startup_config": {
            "description": "Path to the startup-config of IOU",
            "type": ["string", "null"]
        },
        "private_config": {
            "description": "Path to the private-config of IOU",
            "type": ["string", "null"]
        },
        "startup_config_content": {
            "description": "Startup-config of IOU",
            "type": ["string", "null"]
        },
        "private_config_content": {
            "description": "Private-config of IOU",
            "type": ["string", "null"]
        },
        "iourc_content": {
            "description": "Content of the iourc file. Ignored if Null",
            "type": ["string", "null"]
        }
    },
    "additionalProperties": False,
    "required": ["name", "path"]
}


IOU_START_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to start an IOU instance",
    "type": "object",
    "properties": {
        "iourc_content": {
            "description": "Content of the iourc file. Ignored if Null",
            "type": ["string", "null"]
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
            "type": "integer"
        },
        "console_type": {
            "description": "Console type",
            "enum": ["telnet"]
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
        "startup_config": {
            "description": "Path of the startup-config content relative to project directory",
            "type": ["string", "null"]
        },
        "private_config": {
            "description": "Path of the private-config content relative to project directory",
            "type": ["string", "null"]
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
        "iourc_content": {
            "description": "Content of the iourc file. Ignored if Null",
            "type": ["string", "null"]
        },
        "command_line": {
            "description": "Last command line used by GNS3 to start QEMU",
            "type": "string"
        }
    },
    "additionalProperties": False
}
