#!/usr/bin/env python
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


NODE_LIST_IMAGES_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "List of binary images",
    "type": "array",
    "items": [
        {
            "type": "object",
            "properties": {
                "filename": {
                    "description": "Image filename",
                    "type": "string",
                    "minLength": 1
                },
                "path": {
                    "description": "Image path",
                    "type": "string",
                    "minLength": 1
                }
            },
            "required": ["filename", "path"],
            "additionalProperties": False
        }
    ],
    "additionalProperties": False,
}


NODE_CAPTURE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to start a packet capture on a port",
    "type": "object",
    "properties": {
        "capture_file_name": {
            "description": "Capture file name",
            "type": "string",
            "minLength": 1,
        },
        "data_link_type": {
            "description": "PCAP data link type (http://www.tcpdump.org/linktypes.html)",
            "enum": ["DLT_ATM_RFC1483", "DLT_EN10MB", "DLT_FRELAY", "DLT_C_HDLC"]
        }
    },
    "additionalProperties": False,
    "required": ["capture_file_name"]
}


NODE_OBJECT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "A node object",
    "type": "object",
    "properties": {
        "compute_id": {
            "description": "Compute identifier",
            "type": "string"
        },
        "project_id": {
            "description": "Project UUID",
            "type": "string",
            "minLength": 36,
            "maxLength": 36,
            "pattern": "^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$"
        },
        "node_id": {
            "description": "Node UUID",
            "type": "string",
            "minLength": 36,
            "maxLength": 36,
            "pattern": "^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$"
        },
        "node_type": {
            "description": "Type of node",
            "enum": ["docker", "dynamips", "vpcs", "virtualbox", "vmware", "iou", "qemu"]
        },
        "node_directory": {
            "description": "Working directory of the node. Read only",
            "type": ["null", "string"]
        },
        "command_line": {
            "description": "Command line use to start the node",
            "type": ["null", "string"]
        },
        "name": {
            "description": "Node name",
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
            "enum": ["serial", "vnc", "telnet"]
        },
        "properties": {
            "description": "Properties specific to an emulator",
            "type": "object"
        },
        "status": {
            "description": "Status of the node",
            "enum": ["stopped", "started"]
        }
    },
    "additionalProperties": False,
    "required": ["name", "node_type", "compute_id"]
}

NODE_UPDATE_SCHEMA = NODE_OBJECT_SCHEMA
del NODE_UPDATE_SCHEMA["required"]
