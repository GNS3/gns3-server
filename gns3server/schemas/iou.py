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
        "vm_id": {
            "description": "IOU VM identifier",
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
        "path": {
            "description": "Path of iou binary",
            "type": "string"
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
        "initial_config": {
            "description": "Path to the initial configuration of IOU",
            "type": ["string", "null"]
        },
        "initial_config_content": {
            "description": "Initial configuration of IOU",
            "type": ["string", "null"]
        },
        "iourc_content": {
            "description": "Content of the iourc file, if a file exist on servers this variable is ignored. It's mostly for compatibility with < 1.3 releases",
            "type": ["string", "null"]
        }
    },
    "additionalProperties": False,
    "required": ["name", "path"]
}

IOU_UPDATE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to update a IOU instance",
    "type": "object",
    "properties": {
        "name": {
            "description": "IOU VM name",
            "type": ["string", "null"],
            "minLength": 1,
        },
        "console": {
            "description": "console TCP port",
            "minimum": 1,
            "maximum": 65535,
            "type": ["integer", "null"]
        },
        "path": {
            "description": "Path of iou binary",
            "type": ["string", "null"]
        },
        "serial_adapters": {
            "description": "How many serial adapters are connected to the IOU",
            "type": ["integer", "null"]
        },
        "ethernet_adapters": {
            "description": "How many ethernet adapters are connected to the IOU",
            "type": ["integer", "null"]
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
        "initial_config_content": {
            "description": "Initial configuration of IOU",
            "type": ["string", "null"]
        },
        "use_default_iou_values": {
            "description": "Use default IOU values",
            "type": ["boolean", "null"]
        },
        "iourc_content": {
            "description": "Content of the iourc file, if a file exist on servers this variable is ignored. It's mostly for compatibility with < 1.3 releases",
            "type": ["string", "null"]
        }
    },
    "additionalProperties": False,
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
        "vm_id": {
            "description": "IOU VM UUID",
            "type": "string",
            "minLength": 36,
            "maxLength": 36,
            "pattern": "^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$"
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
        "path": {
            "description": "Path of iou binary",
            "type": "string"
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
        "initial_config": {
            "description": "Path of the initial config content relative to project directory",
            "type": ["string", "null"]
        },
        "use_default_iou_values": {
            "description": "Use default IOU values",
            "type": ["boolean", "null"]
        },
        "iourc_path": {
            "description": "Path of the iourc file used by remote servers",
            "type": ["string", "null"]
        }
    },
    "additionalProperties": False,
    "required": ["name", "vm_id", "console", "project_id", "path", "serial_adapters", "ethernet_adapters", "ram", "nvram", "l1_keepalives", "initial_config", "use_default_iou_values"]
}

IOU_CAPTURE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to start a packet capture on a IOU instance",
    "type": "object",
    "properties": {
        "capture_file_name": {
            "description": "Capture file name",
            "type": "string",
            "minLength": 1,
        },
        "data_link_type": {
            "description": "PCAP data link type",
            "type": "string",
            "minLength": 1,
        },
    },
    "additionalProperties": False,
    "required": ["capture_file_name", "data_link_type"]
}

IOU_INITIAL_CONFIG_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to get the initial configuration file",
    "type": "object",
    "properties": {
        "content": {
            "description": "Content of the initial configuration file",
            "type": ["string", "null"]
        },
    },
    "additionalProperties": False,
    "required": ["content"]
}
