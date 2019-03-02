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

import copy
from .label import LABEL_OBJECT_SCHEMA
from .custom_adapters import CUSTOM_ADAPTERS_ARRAY_SCHEMA

NODE_TYPE_SCHEMA = {
    "description": "Type of node",
    "enum": [
        "cloud",
        "nat",
        "ethernet_hub",
        "ethernet_switch",
        "frame_relay_switch",
        "atm_switch",
        "docker",
        "dynamips",
        "vpcs",
        "traceng",
        "virtualbox",
        "vmware",
        "iou",
        "qemu"
    ]
}

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
                },
                "md5sum": {
                    "description": "md5sum of the image if available",
                    "type": ["string", "null"],
                    "minLength": 1
                },
                "filesize": {
                    "description": "size of the image if available",
                    "type": ["integer", "null"],
                    "minimum": 0
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
            "enum": ["DLT_ATM_RFC1483", "DLT_EN10MB", "DLT_FRELAY", "DLT_C_HDLC", "DLT_PPP_SERIAL"]
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
        "template_id": {
            "description": "Template UUID from which the node has been created. Read only",
            "type": ["null", "string"],
            "minLength": 36,
            "maxLength": 36,
            "pattern": "^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$"
        },
        "node_type": NODE_TYPE_SCHEMA,
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
        "console_host": {
            "description": "Console host. Warning if the host is 0.0.0.0 or :: (listen on all interfaces) you need to use the same address you use to connect to the controller.",
            "type": "string",
            "minLength": 1,
        },
        "console_type": {
            "description": "Console type",
            "enum": ["vnc", "telnet", "http", "https", "spice", "spice+agent", "none", None]
        },
        "console_auto_start": {
            "description": "Automatically start the console when the node has started",
            "type": "boolean"
        },
        "properties": {
            "description": "Properties specific to an emulator",
            "type": "object"
        },
        "status": {
            "description": "Status of the node",
            "enum": ["stopped", "started", "suspended"]
        },
        "label": LABEL_OBJECT_SCHEMA,
        "symbol": {
            "description": "Symbol of the node",
            "type": ["string", "null"],
            "minLength": 1
        },
        "width": {
            "description": "Width of the node (Read only)",
            "type": "integer"
        },
        "height": {
            "description": "Height of the node (Read only)",
            "type": "integer"
        },
        "x": {
            "description": "X position of the node",
            "type": "integer"
        },
        "y": {
            "description": "Y position of the node",
            "type": "integer"
        },
        "z": {
            "description": "Z position of the node",
            "type": "integer"
        },
        "locked": {
            "description": "Whether the element locked or not",
            "type": "boolean"
        },
        "port_name_format": {
            "description": "Formating for port name {0} will be replace by port number",
            "type": "string"
        },
        "port_segment_size": {
            "description": "Size of the port segment",
            "type": "integer",
            "minimum": 0
        },
        "first_port_name": {
            "description": "Name of the first port",
            "type": ["string", "null"],
        },
        "custom_adapters": CUSTOM_ADAPTERS_ARRAY_SCHEMA,
        "ports": {
            "description": "List of node ports READ only",
            "type": "array",
            "items": {
                "type": "object",
                "description": "A node port",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Port name",
                    },
                    "short_name": {
                        "type": "string",
                        "description": "Short version of port name",
                    },
                    "adapter_number": {
                        "type": "integer",
                        "description": "Adapter slot"
                    },
                    "adapter_type": {
                        "description": "Adapter type",
                        "type": ["string", "null"],
                        "minLength": 1,
                    },
                    "port_number": {
                        "type": "integer",
                        "description": "Port slot"
                    },
                    "link_type": {
                        "description": "Type of link",
                        "enum": ["ethernet", "serial"]
                    },
                    "data_link_types": {
                        "type": "object",
                        "description": "Available PCAP types for capture",
                        "properties": {}
                    },
                    "mac_address": {
                        "description": "MAC address (if available)",
                        "type": ["string", "null"],
                        "minLength": 1,
                        "pattern": "^([0-9a-fA-F]{2}[:]){5}([0-9a-fA-F]{2})$"
                    },
                },
                "additionalProperties": False
            }
        }
    },
    "additionalProperties": False,
    "required": ["name", "node_type", "compute_id"]
}

NODE_CREATE_SCHEMA = NODE_OBJECT_SCHEMA
NODE_UPDATE_SCHEMA = copy.deepcopy(NODE_OBJECT_SCHEMA)
del NODE_UPDATE_SCHEMA["required"]


NODE_DUPLICATE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Duplicate a node",
    "type": "object",
    "properties": {
        "x": {
            "description": "X position of the node",
            "type": "integer"
        },
        "y": {
            "description": "Y position of the node",
            "type": "integer"
        },
        "z": {
            "description": "Z position of the node",
            "type": "integer"
        }
    },
    "additionalProperties": False,
    "required": ["x", "y"]
}
