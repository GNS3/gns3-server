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


VM_CREATE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to create a new Dynamips VM instance",
    "type": "object",
    "properties": {
        "vm_id": {
            "description": "Dynamips VM instance identifier",
            "oneOf": [
                {"type": "string",
                 "minLength": 36,
                 "maxLength": 36,
                 "pattern": "^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$"},
                {"type": "integer"}  # for legacy projects
            ]
        },
        "dynamips_id": {
            "description": "ID to use with Dynamips",
            "type": "integer"
        },
        "name": {
            "description": "Dynamips VM instance name",
            "type": "string",
            "minLength": 1,
        },
        "platform": {
            "description": "platform",
            "type": "string",
            "minLength": 1,
            "pattern": "^c[0-9]{4}$"
        },
        "chassis": {
            "description": "router chassis model",
            "type": "string",
            "minLength": 1,
            "pattern": "^[0-9]{4}(XM)?$"
        },
        "image": {
            "description": "path to the IOS image",
            "type": "string",
            "minLength": 1,
        },
        "image_md5sum": {
            "description": "checksum of the IOS image",
            "type": ["string", "null"],
            "minLength": 1,
        },
        "startup_config": {
            "description": "path to the IOS startup configuration file",
            "type": "string",
            "minLength": 1,
        },
        "startup_config_content": {
            "description": "Content of IOS startup configuration file",
            "type": "string",
        },
        "private_config": {
            "description": "path to the IOS private configuration file",
            "type": "string",
            "minLength": 1,
        },
        "private_config_content": {
            "description": "Content of IOS private configuration file",
            "type": "string",
        },
        "ram": {
            "description": "amount of RAM in MB",
            "type": "integer"
        },
        "nvram": {
            "description": "amount of NVRAM in KB",
            "type": "integer"
        },
        "mmap": {
            "description": "MMAP feature",
            "type": "boolean"
        },
        "sparsemem": {
            "description": "sparse memory feature",
            "type": "boolean"
        },
        "clock_divisor": {
            "description": "clock divisor",
            "type": "integer"
        },
        "idlepc": {
            "description": "Idle-PC value",
            "type": "string",
            "pattern": "^(0x[0-9a-fA-F]+)?$"
        },
        "idlemax": {
            "description": "idlemax value",
            "type": "integer",
        },
        "idlesleep": {
            "description": "idlesleep value",
            "type": "integer",
        },
        "exec_area": {
            "description": "exec area value",
            "type": "integer",
        },
        "disk0": {
            "description": "disk0 size in MB",
            "type": "integer"
        },
        "disk1": {
            "description": "disk1 size in MB",
            "type": "integer"
        },
        "auto_delete_disks": {
            "description": "automatically delete nvram and disk files",
            "type": "boolean"
        },
        "console": {
            "description": "console TCP port",
            "type": "integer",
            "minimum": 1,
            "maximum": 65535
        },
        "aux": {
            "description": "auxiliary console TCP port",
            "type": "integer",
            "minimum": 1,
            "maximum": 65535
        },
        "mac_addr": {
            "description": "base MAC address",
            "type": "string",
            "minLength": 1,
            "pattern": "^([0-9a-fA-F]{4}\\.){2}[0-9a-fA-F]{4}$"
        },
        "system_id": {
            "description": "system ID",
            "type": "string",
            "minLength": 1,
        },
        "slot0": {
            "description": "Network module slot 0",
            "oneOf": [
                {"type": "string"},
                {"type": "null"}
            ]
        },
        "slot1": {
            "description": "Network module slot 1",
            "oneOf": [
                {"type": "string"},
                {"type": "null"}
            ]
        },
        "slot2": {
            "description": "Network module slot 2",
            "oneOf": [
                {"type": "string"},
                {"type": "null"}
            ]
        },
        "slot3": {
            "description": "Network module slot 3",
            "oneOf": [
                {"type": "string"},
                {"type": "null"}
            ]
        },
        "slot4": {
            "description": "Network module slot 4",
            "oneOf": [
                {"type": "string"},
                {"type": "null"}
            ]
        },
        "slot5": {
            "description": "Network module slot 5",
            "oneOf": [
                {"type": "string"},
                {"type": "null"}
            ]
        },
        "slot6": {
            "description": "Network module slot 6",
            "oneOf": [
                {"type": "string"},
                {"type": "null"}
            ]
        },
        "wic0": {
            "description": "Network module WIC slot 0",
            "oneOf": [
                {"type": "string"},
                {"type": "null"}
            ]
        },
        "wic1": {
            "description": "Network module WIC slot 0",
            "oneOf": [
                {"type": "string"},
                {"type": "null"}
            ]
        },
        "wic2": {
            "description": "Network module WIC slot 0",
            "oneOf": [
                {"type": "string"},
                {"type": "null"}
            ]
        },
        "startup_config_base64": {
            "description": "startup configuration base64 encoded",
            "type": "string"
        },
        "private_config_base64": {
            "description": "private configuration base64 encoded",
            "type": "string"
        },
        # C7200 properties
        "npe": {
            "description": "NPE model",
            "enum": ["npe-100",
                     "npe-150",
                     "npe-175",
                     "npe-200",
                     "npe-225",
                     "npe-300",
                     "npe-400",
                     "npe-g2"]
        },
        "midplane": {
            "description": "Midplane model",
            "enum": ["std", "vxr"]
        },
        "sensors": {
            "description": "Temperature sensors",
            "type": "array"
        },
        "power_supplies": {
            "description": "Power supplies status",
            "type": "array"
        },
        # I/O memory property for all platforms but C7200
        "iomem": {
            "description": "I/O memory percentage",
            "type": "integer",
            "minimum": 0,
            "maximum": 100
        },
    },
    "additionalProperties": False,
    "required": ["name", "platform", "image", "ram"]
}

VM_UPDATE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to update a Dynamips VM instance",
    "type": "object",
    "properties": {
        "name": {
            "description": "Dynamips VM instance name",
            "type": "string",
            "minLength": 1,
        },
        "platform": {
            "description": "platform",
            "type": "string",
            "minLength": 1,
            "pattern": "^c[0-9]{4}$"
        },
        "chassis": {
            "description": "router chassis model",
            "type": "string",
            "minLength": 1,
            "pattern": "^[0-9]{4}(XM)?$"
        },
        "image": {
            "description": "path to the IOS image",
            "type": "string",
            "minLength": 1,
        },
        "image_md5sum": {
            "description": "checksum of the IOS image",
            "type": ["string", "null"],
            "minLength": 1,
        },
        "startup_config_content": {
            "description": "Content of IOS startup configuration file",
            "type": "string",
        },
        "private_config_content": {
            "description": "Content of IOS private configuration file",
            "type": "string",
        },
        "ram": {
            "description": "amount of RAM in MB",
            "type": "integer"
        },
        "nvram": {
            "description": "amount of NVRAM in KB",
            "type": "integer"
        },
        "mmap": {
            "description": "MMAP feature",
            "type": "boolean"
        },
        "sparsemem": {
            "description": "sparse memory feature",
            "type": "boolean"
        },
        "clock_divisor": {
            "description": "clock divisor",
            "type": "integer"
        },
        "idlepc": {
            "description": "Idle-PC value",
            "type": "string",
            "pattern": "^(0x[0-9a-fA-F]+)?$"
        },
        "idlemax": {
            "description": "idlemax value",
            "type": "integer",
        },
        "idlesleep": {
            "description": "idlesleep value",
            "type": "integer",
        },
        "exec_area": {
            "description": "exec area value",
            "type": "integer",
        },
        "disk0": {
            "description": "disk0 size in MB",
            "type": "integer"
        },
        "disk1": {
            "description": "disk1 size in MB",
            "type": "integer"
        },
        "auto_delete_disks": {
            "description": "automatically delete nvram and disk files",
            "type": "boolean"
        },
        "console": {
            "description": "console TCP port",
            "type": "integer",
            "minimum": 1,
            "maximum": 65535
        },
        "aux": {
            "description": "auxiliary console TCP port",
            "type": "integer",
            "minimum": 1,
            "maximum": 65535
        },
        "mac_addr": {
            "description": "base MAC address",
            "type": "string",
            "minLength": 1,
            "pattern": "^([0-9a-fA-F]{4}\\.){2}[0-9a-fA-F]{4}$"
        },
        "system_id": {
            "description": "system ID",
            "type": "string",
            "minLength": 1,
        },
        "slot0": {
            "description": "Network module slot 0",
            "oneOf": [
                {"type": "string"},
                {"type": "null"}
            ]
        },
        "slot1": {
            "description": "Network module slot 1",
            "oneOf": [
                {"type": "string"},
                {"type": "null"}
            ]
        },
        "slot2": {
            "description": "Network module slot 2",
            "oneOf": [
                {"type": "string"},
                {"type": "null"}
            ]
        },
        "slot3": {
            "description": "Network module slot 3",
            "oneOf": [
                {"type": "string"},
                {"type": "null"}
            ]
        },
        "slot4": {
            "description": "Network module slot 4",
            "oneOf": [
                {"type": "string"},
                {"type": "null"}
            ]
        },
        "slot5": {
            "description": "Network module slot 5",
            "oneOf": [
                {"type": "string"},
                {"type": "null"}
            ]
        },
        "slot6": {
            "description": "Network module slot 6",
            "oneOf": [
                {"type": "string"},
                {"type": "null"}
            ]
        },
        "wic0": {
            "description": "Network module WIC slot 0",
            "oneOf": [
                {"type": "string"},
                {"type": "null"}
            ]
        },
        "wic1": {
            "description": "Network module WIC slot 0",
            "oneOf": [
                {"type": "string"},
                {"type": "null"}
            ]
        },
        "wic2": {
            "description": "Network module WIC slot 0",
            "oneOf": [
                {"type": "string"},
                {"type": "null"}
            ]
        },
        "startup_config_base64": {
            "description": "startup configuration base64 encoded",
            "type": "string"
        },
        "private_config_base64": {
            "description": "private configuration base64 encoded",
            "type": "string"
        },
        # C7200 properties
        "npe": {
            "description": "NPE model",
            "enum": ["npe-100",
                     "npe-150",
                     "npe-175",
                     "npe-200",
                     "npe-225",
                     "npe-300",
                     "npe-400",
                     "npe-g2"]
        },
        "midplane": {
            "description": "Midplane model",
            "enum": ["std", "vxr"]
        },
        "sensors": {
            "description": "Temperature sensors",
            "type": "array"
        },
        "power_supplies": {
            "description": "Power supplies status",
            "type": "array"
        },
        # I/O memory property for all platforms but C7200
        "iomem": {
            "description": "I/O memory percentage",
            "type": "integer",
            "minimum": 0,
            "maximum": 100
        },
    },
    "additionalProperties": False,
}


VM_OBJECT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Dynamips VM instance",
    "type": "object",
    "properties": {
        "dynamips_id": {
            "description": "ID to use with Dynamips",
            "type": "integer"
        },
        "vm_id": {
            "description": "Dynamips router instance UUID",
            "type": "string",
            "minLength": 36,
            "maxLength": 36,
            "pattern": "^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$"
        },
        "vm_directory": {
            "decription": "Path to the VM working directory",
            "type": "string"
        },
        "project_id": {
            "description": "Project UUID",
            "type": "string",
            "minLength": 36,
            "maxLength": 36,
            "pattern": "^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$"
        },
        "name": {
            "description": "Dynamips VM instance name",
            "type": "string",
            "minLength": 1,
        },
        "platform": {
            "description": "platform",
            "type": "string",
            "minLength": 1,
            "pattern": "^c[0-9]{4}$"
        },
        "chassis": {
            "description": "router chassis model",
            "type": "string",
            "minLength": 1,
            "pattern": "^[0-9]{4}(XM)?$"
        },
        "image": {
            "description": "path to the IOS image",
            "type": "string",
            "minLength": 1,
        },
        "image_md5sum": {
            "description": "checksum of the IOS image",
            "type": ["string", "null"],
            "minLength": 1,
        },
        "startup_config": {
            "description": "path to the IOS startup configuration file",
            "type": "string",
        },
        "private_config": {
            "description": "path to the IOS private configuration file",
            "type": "string",
        },
        "ram": {
            "description": "amount of RAM in MB",
            "type": "integer"
        },
        "nvram": {
            "description": "amount of NVRAM in KB",
            "type": "integer"
        },
        "mmap": {
            "description": "MMAP feature",
            "type": "boolean"
        },
        "sparsemem": {
            "description": "sparse memory feature",
            "type": "boolean"
        },
        "clock_divisor": {
            "description": "clock divisor",
            "type": "integer"
        },
        "idlepc": {
            "description": "Idle-PC value",
            "type": "string",
            "pattern": "^(0x[0-9a-fA-F]+)?$"
        },
        "idlemax": {
            "description": "idlemax value",
            "type": "integer",
        },
        "idlesleep": {
            "description": "idlesleep value",
            "type": "integer",
        },
        "exec_area": {
            "description": "exec area value",
            "type": "integer",
        },
        "disk0": {
            "description": "disk0 size in MB",
            "type": "integer"
        },
        "disk1": {
            "description": "disk1 size in MB",
            "type": "integer"
        },
        "auto_delete_disks": {
            "description": "automatically delete nvram and disk files",
            "type": "boolean"
        },
        "console": {
            "description": "console TCP port",
            "type": "integer",
            "minimum": 1,
            "maximum": 65535
        },
        "aux": {
            "description": "auxiliary console TCP port",
            "type": ["integer", "null"],
            "minimum": 1,
            "maximum": 65535
        },
        "mac_addr": {
            "description": "base MAC address",
            "type": "string",
            #"minLength": 1,
            #"pattern": "^([0-9a-fA-F]{4}\\.){2}[0-9a-fA-F]{4}$"
        },
        "system_id": {
            "description": "system ID",
            "type": "string",
            "minLength": 1,
        },
        "slot0": {
            "description": "Network module slot 0",
            "oneOf": [
                {"type": "string"},
                {"type": "null"}
            ]
        },
        "slot1": {
            "description": "Network module slot 1",
            "oneOf": [
                {"type": "string"},
                {"type": "null"}
            ]
        },
        "slot2": {
            "description": "Network module slot 2",
            "oneOf": [
                {"type": "string"},
                {"type": "null"}
            ]
        },
        "slot3": {
            "description": "Network module slot 3",
            "oneOf": [
                {"type": "string"},
                {"type": "null"}
            ]
        },
        "slot4": {
            "description": "Network module slot 4",
            "oneOf": [
                {"type": "string"},
                {"type": "null"}
            ]
        },
        "slot5": {
            "description": "Network module slot 5",
            "oneOf": [
                {"type": "string"},
                {"type": "null"}
            ]
        },
        "slot6": {
            "description": "Network module slot 6",
            "oneOf": [
                {"type": "string"},
                {"type": "null"}
            ]
        },
        "wic0": {
            "description": "Network module WIC slot 0",
            "oneOf": [
                {"type": "string"},
                {"type": "null"}
            ]
        },
        "wic1": {
            "description": "Network module WIC slot 0",
            "oneOf": [
                {"type": "string"},
                {"type": "null"}
            ]
        },
        "wic2": {
            "description": "Network module WIC slot 0",
            "oneOf": [
                {"type": "string"},
                {"type": "null"}
            ]
        },
        "startup_config_base64": {
            "description": "startup configuration base64 encoded",
            "type": "string"
        },
        "private_config_base64": {
            "description": "private configuration base64 encoded",
            "type": "string"
        },
        # C7200 properties
        "npe": {
            "description": "NPE model",
            "enum": ["npe-100",
                     "npe-150",
                     "npe-175",
                     "npe-200",
                     "npe-225",
                     "npe-300",
                     "npe-400",
                     "npe-g2"]
        },
        "midplane": {
            "description": "Midplane model",
            "enum": ["std", "vxr"]
        },
        "sensors": {
            "description": "Temperature sensors",
            "type": "array"
        },
        "power_supplies": {
            "description": "Power supplies status",
            "type": "array"
        },
        # I/O memory property for all platforms but C7200
        "iomem": {
            "description": "I/O memory percentage",
            "type": "integer",
            "minimum": 0,
            "maximum": 100
        },
    },
    "additionalProperties": False,
    "required": ["name", "vm_id", "project_id", "dynamips_id"]
}

VM_CONFIGS_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to get the startup and private configuration file",
    "type": "object",
    "properties": {
        "startup_config_content": {
            "description": "Content of the startup configuration file",
            "type": ["string", "null"],
            "minLength": 1,
        },
        "private_config_content": {
            "description": "Content of the private configuration file",
            "type": ["string", "null"],
            "minLength": 1,
        },
    },
    "additionalProperties": False,
}
