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


IOU_CREATE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to create a new IOU instance",
    "type": "object",
    "properties": {
        "name": {
            "description": "IOU device name",
            "type": "string",
            "minLength": 1,
        },
        "iou_id": {
            "description": "IOU device instance ID",
            "type": "integer"
        },
        "console": {
            "description": "console TCP port",
            "minimum": 1,
            "maximum": 65535,
            "type": "integer"
        },
        "path": {
            "description": "path to the IOU executable",
            "type": "string",
            "minLength": 1,
        },
        "cloud_path": {
            "description": "Path to the image in the cloud object store",
            "type": "string",
        }
    },
    "additionalProperties": False,
    "required": ["name", "path"],
}

IOU_DELETE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to delete an IOU instance",
    "type": "object",
    "properties": {
        "id": {
            "description": "IOU device instance ID",
            "type": "integer"
        },
    },
    "additionalProperties": False,
    "required": ["id"]
}

IOU_UPDATE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to update an IOU instance",
    "type": "object",
    "properties": {
        "id": {
            "description": "IOU device instance ID",
            "type": "integer"
        },
        "name": {
            "description": "IOU device name",
            "type": "string",
            "minLength": 1,
        },
        "path": {
            "description": "path to the IOU executable",
            "type": "string",
            "minLength": 1,
        },
        "initial_config": {
            "description": "path to the IOU initial configuration file",
            "type": "string",
            "minLength": 1,
        },
        "ram": {
            "description": "amount of RAM in MB",
            "type": "integer"
        },
        "nvram": {
            "description": "amount of NVRAM in KB",
            "type": "integer"
        },
        "ethernet_adapters": {
            "description": "number of Ethernet adapters",
            "type": "integer",
            "minimum": 0,
            "maximum": 16,
        },
        "serial_adapters": {
            "description": "number of serial adapters",
            "type": "integer",
            "minimum": 0,
            "maximum": 16,
        },
        "console": {
            "description": "console TCP port",
            "minimum": 1,
            "maximum": 65535,
            "type": "integer"
        },
        "use_default_iou_values": {
            "description": "use the default IOU RAM & NVRAM values",
            "type": "boolean"
        },
        "l1_keepalives": {
            "description": "enable or disable layer 1 keepalive messages",
            "type": "boolean"
        },
        "initial_config_base64": {
            "description": "initial configuration base64 encoded",
            "type": "string"
        },
    },
    "additionalProperties": False,
    "required": ["id"]
}

IOU_START_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to start an IOU instance",
    "type": "object",
    "properties": {
        "id": {
            "description": "IOU device instance ID",
            "type": "integer"
        },
    },
    "additionalProperties": False,
    "required": ["id"]
}

IOU_STOP_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to stop an IOU instance",
    "type": "object",
    "properties": {
        "id": {
            "description": "IOU device instance ID",
            "type": "integer"
        },
    },
    "additionalProperties": False,
    "required": ["id"]
}

IOU_RELOAD_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to reload an IOU instance",
    "type": "object",
    "properties": {
        "id": {
            "description": "IOU device instance ID",
            "type": "integer"
        },
    },
    "additionalProperties": False,
    "required": ["id"]
}

IOU_ALLOCATE_UDP_PORT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to allocate an UDP port for an IOU instance",
    "type": "object",
    "properties": {
        "id": {
            "description": "IOU device instance ID",
            "type": "integer"
        },
        "port_id": {
            "description": "Unique port identifier for the IOU instance",
            "type": "integer"
        },
    },
    "additionalProperties": False,
    "required": ["id", "port_id"]
}

IOU_ADD_NIO_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to add a NIO for an IOU instance",
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
        "id": {
            "description": "IOU device instance ID",
            "type": "integer"
        },
        "port_id": {
            "description": "Unique port identifier for the IOU instance",
            "type": "integer"
        },
        "slot": {
            "description": "Slot number",
            "type": "integer",
            "minimum": 0,
            "maximum": 15
        },
        "port": {
            "description": "Port number",
            "type": "integer",
            "minimum": 0,
            "maximum": 3
        },
        "nio": {
            "type": "object",
            "description": "Network Input/Output",
            "oneOf": [
                {"$ref": "#/definitions/UDP"},
                {"$ref": "#/definitions/Ethernet"},
                {"$ref": "#/definitions/LinuxEthernet"},
                {"$ref": "#/definitions/TAP"},
                {"$ref": "#/definitions/UNIX"},
                {"$ref": "#/definitions/VDE"},
                {"$ref": "#/definitions/NULL"},
            ]
        },
    },
    "additionalProperties": False,
    "required": ["id", "port_id", "slot", "port", "nio"]
}


IOU_DELETE_NIO_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to delete a NIO for an IOU instance",
    "type": "object",
    "properties": {
        "id": {
            "description": "IOU device instance ID",
            "type": "integer"
        },
        "slot": {
            "description": "Slot number",
            "type": "integer",
            "minimum": 0,
            "maximum": 15
        },
        "port": {
            "description": "Port number",
            "type": "integer",
            "minimum": 0,
            "maximum": 3
        },
    },
    "additionalProperties": False,
    "required": ["id", "slot", "port"]
}

IOU_START_CAPTURE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to start a packet capture on an IOU instance port",
    "type": "object",
    "properties": {
        "id": {
            "description": "IOU device instance ID",
            "type": "integer"
        },
        "slot": {
            "description": "Slot number",
            "type": "integer",
            "minimum": 0,
            "maximum": 15
        },
        "port": {
            "description": "Port number",
            "type": "integer",
            "minimum": 0,
            "maximum": 3
        },
        "port_id": {
            "description": "Unique port identifier for the IOU instance",
            "type": "integer"
        },
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
    "required": ["id", "slot", "port", "port_id", "capture_file_name"]
}

IOU_STOP_CAPTURE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to stop a packet capture on an IOU instance port",
    "type": "object",
    "properties": {
        "id": {
            "description": "IOU device instance ID",
            "type": "integer"
        },
        "slot": {
            "description": "Slot number",
            "type": "integer",
            "minimum": 0,
            "maximum": 15
        },
        "port": {
            "description": "Port number",
            "type": "integer",
            "minimum": 0,
            "maximum": 3
        },
        "port_id": {
            "description": "Unique port identifier for the IOU instance",
            "type": "integer"
        },
    },
    "additionalProperties": False,
    "required": ["id", "slot", "port", "port_id"]
}

IOU_EXPORT_CONFIG_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to export an initial-config from an IOU instance",
    "type": "object",
    "properties": {
        "id": {
            "description": "IOU device instance ID",
            "type": "integer"
        },
    },
    "additionalProperties": False,
    "required": ["id"]
}
