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

from .label import LABEL_OBJECT_SCHEMA


LINK_OBJECT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "A link object",
    "type": "object",
    "properties": {
        "link_id": {
            "description": "Link UUID",
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
        "nodes": {
            "description": "List of the VMS",
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "node_id": {
                        "description": "Node UUID",
                        "type": "string",
                        "minLength": 36,
                        "maxLength": 36,
                        "pattern": "^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$"
                    },
                    "adapter_number": {
                        "description": "Adapter number",
                        "type": "integer"
                    },
                    "port_number": {
                        "description": "Port number",
                        "type": "integer"
                    },
                    "label": LABEL_OBJECT_SCHEMA
                },
                "required": ["node_id", "adapter_number", "port_number"],
                "additionalProperties": False
            }
        },
        "capturing": {
            "description": "Read only property. True if a capture running on the link",
            "type": "boolean"
        },
        "capture_file_name": {
            "description": "Read only property. The name of the capture file if capture is running",
            "type": ["string", "null"]
        },
        "capture_file_path": {
            "description": "Read only property. The full path of the capture file if capture is running",
            "type": ["string", "null"]
        },
        "link_type": {
            "description": "Type of link",
            "enum": ["ethernet", "serial"]
        }
    },
    "required": ["nodes"],
    "additionalProperties": False
}


LINK_CAPTURE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to start a packet capture on a link",
    "type": "object",
    "properties": {
        "data_link_type": {
            "description": "PCAP data link type (http://www.tcpdump.org/linktypes.html)",
            "enum": ["DLT_ATM_RFC1483", "DLT_EN10MB", "DLT_FRELAY", "DLT_C_HDLC", "DLT_PPP_SERIAL"]
        },
        "capture_file_name": {
            "description": "Read only property. The name of the capture file if capture is running",
            "type": "string"
        }
    },
    "additionalProperties": False
}
