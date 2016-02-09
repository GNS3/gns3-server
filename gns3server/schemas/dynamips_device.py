# -*- coding: utf-8 -*-
#
# Copyright (C) 2014 GNS3 Technologies Inc.
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


DEVICE_CREATE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to create a new Dynamips device instance",
    "type": "object",
    "properties": {
        "name": {
            "description": "Dynamips device name",
            "type": "string",
            "minLength": 1,
        },
        "device_id": {
            "description": "Dynamips device instance identifier",
            "oneOf": [
                {"type": "string",
                 "minLength": 36,
                 "maxLength": 36,
                 "pattern": "^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$"},
                {"type": "integer"}  # for legacy projects
            ]
        },
        "device_type": {
            "description": "Dynamips device type",
            "type": "string",
            "minLength": 1,
        },
    },
    "additionalProperties": False,
    "required": ["name", "device_type"]
}

DEVICE_UPDATE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Dynamips device instance",
    "type": "object",
    "definitions": {
        "EthernetSwitchPort": {
            "description": "Ethernet switch port",
            "properties": {
                "port": {
                    "description": "Port number",
                    "type": "integer",
                    "minimum": 1
                },
                "type": {
                    "description": "Port type",
                    "enum": ["access", "dot1q", "qinq"],
                },

                "vlan": {"description": "VLAN number",
                         "type": "integer",
                         "minimum": 1
                         },
                "ethertype": {
                    "description": "QinQ Ethertype",
                    "enum": ["", "0x8100", "0x88A8", "0x9100", "0x9200"],
                },
            },
            "required": ["port", "type", "vlan"],
            "additionalProperties": False
        },
    },
    "properties": {
        "name": {
            "description": "Dynamips device instance name",
            "type": "string",
            "minLength": 1,
        },
        "ports": {
            "type": "array",
            "items": [
                {"type": "object",
                 "oneOf": [
                     {"$ref": "#/definitions/EthernetSwitchPort"}
                 ]},
            ]
        }
    },
    "additionalProperties": False,
}

DEVICE_OBJECT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Dynamips device instance",
    "type": "object",
    "definitions": {
        "EthernetSwitchPort": {
            "description": "Ethernet switch port",
            "properties": {
                "port": {
                    "description": "Port number",
                    "type": "integer",
                    "minimum": 1
                },
                "type": {
                    "description": "Port type",
                    "enum": ["access", "dot1q", "qinq"],
                },
                "vlan": {"description": "VLAN number",
                         "type": "integer",
                         "minimum": 1
                         },
                "ethertype": {
                    "description": "QinQ Ethertype",
                    "enum": ["", "0x8100", "0x88A8", "0x9100", "0x9200"],
                },
            },
            "required": ["port", "type", "vlan"],
            "additionalProperties": False
        },
    },
    "properties": {
        "device_id": {
            "description": "Dynamips router instance UUID",
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
        "name": {
            "description": "Dynamips device instance name",
            "type": "string",
            "minLength": 1,
        },
        "ports": {
            # only Ethernet switches have ports
            "type": "array",
            "items": [
                {"type": "object",
                 "oneOf": [
                     {"$ref": "#/definitions/EthernetSwitchPort"}
                 ]},
            ]
        },
        "mappings": {
            # only Frame-Relay and ATM switches have mappings
            "type": "object",
        }
    },
    "additionalProperties": False,
    "required": ["name", "device_id", "project_id"]
}

DEVICE_NIO_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to add a NIO for a Dynamips device instance",
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
    "properties": {
        "nio": {
            "type": "object",
            "oneOf": [
                {"$ref": "#/definitions/UDP"},
                {"$ref": "#/definitions/Ethernet"},
                {"$ref": "#/definitions/LinuxEthernet"},
                {"$ref": "#/definitions/NAT"},
                {"$ref": "#/definitions/TAP"},
                {"$ref": "#/definitions/UNIX"},
                {"$ref": "#/definitions/VDE"},
                {"$ref": "#/definitions/NULL"},
            ]
        },
        "port_settings": {
            # only Ethernet switches have port settings
            "type": "object",
            "description": "Ethernet switch",
            "properties": {
                "type": {
                    "description": "Port type",
                    "enum": ["access", "dot1q", "qinq"],
                },
                "vlan": {"description": "VLAN number",
                         "type": "integer",
                         "minimum": 1
                         },
                "ethertype": {
                    "description": "QinQ Ethertype",
                    "enum": ["", "0x8100", "0x88A8", "0x9100", "0x9200"],
                },
            },
            "required": ["type", "vlan"],
            "additionalProperties": False
        },
        "mappings": {
            # only Frame-Relay and ATM switches have mappings
            "type": "object",
        }
    },
    "additionalProperties": False,
    "required": ["nio"]
}
