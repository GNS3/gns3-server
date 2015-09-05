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


NIO_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to add a NIO for a VM instance",
    "type": "object",
    "definitions": {
        "UDP": {
            "description": "UDP Network Input/Output",
            "properties": {
                "type": {
                    "enum": ["nio_udp"]
                },
                "lport": {
                    "description": "Local port",
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 65535
                },
                "rhost": {
                    "description": "Remote host",
                    "type": "string",
                    "minLength": 1
                },
                "rport": {
                    "description": "Remote port",
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 65535
                }
            },
            "required": ["type", "lport", "rhost", "rport"],
            "additionalProperties": False
        },
        "Ethernet": {
            "description": "Generic Ethernet Network Input/Output",
            "properties": {
                "type": {
                    "enum": ["nio_generic_ethernet"]
                },
                "ethernet_device": {
                    "description": "Ethernet device name e.g. eth0",
                    "type": "string",
                    "minLength": 1
                },
            },
            "required": ["type", "ethernet_device"],
            "additionalProperties": False
        },
        "LinuxEthernet": {
            "description": "Linux Ethernet Network Input/Output",
            "properties": {
                "type": {
                    "enum": ["nio_linux_ethernet"]
                },
                "ethernet_device": {
                    "description": "Ethernet device name e.g. eth0",
                    "type": "string",
                    "minLength": 1
                },
            },
            "required": ["type", "ethernet_device"],
            "additionalProperties": False
        },
        "NAT": {
            "description": "NAT Network Input/Output",
            "properties": {
                "type": {
                    "enum": ["nio_nat"]
                },
            },
            "required": ["type"],
            "additionalProperties": False
        },
        "TAP": {
            "description": "TAP Network Input/Output",
            "properties": {
                "type": {
                    "enum": ["nio_tap"]
                },
                "tap_device": {
                    "description": "TAP device name e.g. tap0",
                    "type": "string",
                    "minLength": 1
                },
            },
            "required": ["type", "tap_device"],
            "additionalProperties": False
        },
        "UNIX": {
            "description": "UNIX Network Input/Output",
            "properties": {
                "type": {
                    "enum": ["nio_unix"]
                },
                "local_file": {
                    "description": "path to the UNIX socket file (local)",
                    "type": "string",
                    "minLength": 1
                },
                "remote_file": {
                    "description": "path to the UNIX socket file (remote)",
                    "type": "string",
                    "minLength": 1
                },
            },
            "required": ["type", "local_file", "remote_file"],
            "additionalProperties": False
        },
        "VDE": {
            "description": "VDE Network Input/Output",
            "properties": {
                "type": {
                    "enum": ["nio_vde"]
                },
                "control_file": {
                    "description": "path to the VDE control file",
                    "type": "string",
                    "minLength": 1
                },
                "local_file": {
                    "description": "path to the VDE control file",
                    "type": "string",
                    "minLength": 1
                },
            },
            "required": ["type", "control_file", "local_file"],
            "additionalProperties": False
        },
        "VMNET": {
            "description": "VMNET Network Input/Output",
            "properties": {
                "type": {
                    "enum": ["nio_vmnet"]
                },
                "vmnet": {
                    "description": "VMnet interface name e.g. vmnet12",
                    "type": "string",
                    "minLength": 1
                },
            },
            "required": ["type", "vmnet"],
            "additionalProperties": False
        },
        "NULL": {
            "description": "NULL Network Input/Output",
            "properties": {
                "type": {
                    "enum": ["nio_null"]
                },
            },
            "required": ["type"],
            "additionalProperties": False
        },
    },
    "oneOf": [
        {"$ref": "#/definitions/UDP"},
        {"$ref": "#/definitions/Ethernet"},
        {"$ref": "#/definitions/LinuxEthernet"},
        {"$ref": "#/definitions/NAT"},
        {"$ref": "#/definitions/TAP"},
        {"$ref": "#/definitions/UNIX"},
        {"$ref": "#/definitions/VDE"},
        {"$ref": "#/definitions/VMNET"},
        {"$ref": "#/definitions/NULL"},
    ],
    "additionalProperties": True,
    "required": ["type"]
}
