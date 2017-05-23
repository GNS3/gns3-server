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
        "dynamips_id": {
            "description": "Dynamips ID",
            "type": ["integer", "null"]
        },
        "name": {
            "description": "Dynamips VM instance name",
            "type": "string",
            "minLength": 1,
        },
        "platform": {
            "description": "Cisco router platform",
            "type": "string",
            "minLength": 1,
            "pattern": "^c[0-9]{4}$"
        },
        "chassis": {
            "description": "Cisco router chassis model",
            "type": "string",
            "minLength": 1,
            "pattern": "^[0-9]{4}(XM)?$"
        },
        "image": {
            "description": "Path to the IOS image",
            "type": "string",
            "minLength": 1,
        },
        "image_md5sum": {
            "description": "Checksum of the IOS image",
            "type": ["string", "null"],
            "minLength": 1,
        },
        "startup_config": {
            "description": "Path to the IOS startup configuration file",
            "type": "string",
        },
        "startup_config_content": {
            "description": "Content of IOS startup configuration file",
            "type": "string",
        },
        "private_config": {
            "description": "Path to the IOS private configuration file",
            "type": "string",
        },
        "private_config_content": {
            "description": "Content of IOS private configuration file",
            "type": "string",
        },
        "ram": {
            "description": "Amount of RAM in MB",
            "type": "integer"
        },
        "nvram": {
            "description": "Amount of NVRAM in KB",
            "type": "integer"
        },
        "mmap": {
            "description": "MMAP feature",
            "type": "boolean"
        },
        "sparsemem": {
            "description": "Sparse memory feature",
            "type": "boolean"
        },
        "clock_divisor": {
            "description": "Clock divisor",
            "type": "integer"
        },
        "idlepc": {
            "description": "Idle-PC value",
            "type": "string",
            "pattern": "^(0x[0-9a-fA-F]+)?$"
        },
        "idlemax": {
            "description": "Idlemax value",
            "type": "integer",
        },
        "idlesleep": {
            "description": "Idlesleep value",
            "type": "integer",
        },
        "exec_area": {
            "description": "Exec area value",
            "type": "integer",
        },
        "disk0": {
            "description": "Disk0 size in MB",
            "type": "integer"
        },
        "disk1": {
            "description": "Disk1 size in MB",
            "type": "integer"
        },
        "auto_delete_disks": {
            "description": "Automatically delete nvram and disk files",
            "type": "boolean"
        },
        "console": {
            "description": "Console TCP port",
            "type": "integer",
            "minimum": 1,
            "maximum": 65535
        },
        "console_type": {
            "description": "Console type",
            "enum": ["telnet"]
        },
        "aux": {
            "description": "Auxiliary console TCP port",
            "type": ["null", "integer"],
            "minimum": 1,
            "maximum": 65535
        },
        "mac_addr": {
            "description": "Base MAC address",
            "type": "string",
            "minLength": 1,
            "pattern": "^([0-9a-fA-F]{4}\\.){2}[0-9a-fA-F]{4}$"
        },
        "system_id": {
            "description": "System ID",
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
            "description": "Cisco router platform",
            "type": "string",
            "minLength": 1,
            "pattern": "^c[0-9]{4}$"
        },
        "chassis": {
            "description": "Cisco router chassis model",
            "type": "string",
            "minLength": 1,
            "pattern": "^[0-9]{4}(XM)?$"
        },
        "image": {
            "description": "Path to the IOS image",
            "type": "string",
            "minLength": 1,
        },
        "image_md5sum": {
            "description": "Checksum of the IOS image",
            "type": ["string", "null"],
            "minLength": 1,
        },
        "dynamips_id": {
            "description": "Dynamips ID",
            "type": "integer"
        },
        "startup_config": {
            "description": "Path to the IOS startup configuration file.",
            "type": "string",
        },
        "private_config": {
            "description": "Path to the IOS private configuration file.",
            "type": "string",
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
            "description": "Amount of RAM in MB",
            "type": "integer"
        },
        "nvram": {
            "description": "Amount of NVRAM in KB",
            "type": "integer"
        },
        "mmap": {
            "description": "MMAP feature",
            "type": "boolean"
        },
        "sparsemem": {
            "description": "Sparse memory feature",
            "type": "boolean"
        },
        "clock_divisor": {
            "description": "Clock divisor",
            "type": "integer"
        },
        "idlepc": {
            "description": "Idle-PC value",
            "type": "string",
            "pattern": "^(0x[0-9a-fA-F]+)?$"
        },
        "idlemax": {
            "description": "Idlemax value",
            "type": "integer",
        },
        "idlesleep": {
            "description": "Idlesleep value",
            "type": "integer",
        },
        "exec_area": {
            "description": "Exec area value",
            "type": "integer",
        },
        "disk0": {
            "description": "Disk0 size in MB",
            "type": "integer"
        },
        "disk1": {
            "description": "Disk1 size in MB",
            "type": "integer"
        },
        "auto_delete_disks": {
            "description": "Automatically delete nvram and disk files",
            "type": "boolean"
        },
        "console": {
            "description": "Console TCP port",
            "type": "integer",
            "minimum": 1,
            "maximum": 65535
        },
        "console_type": {
            "description": "Console type",
            "enum": ["telnet"]
        },
        "aux": {
            "description": "Auxiliary console TCP port",
            "type": "integer",
            "minimum": 1,
            "maximum": 65535
        },
        "mac_addr": {
            "description": "Base MAC address",
            "type": "string",
            "minLength": 1,
            "pattern": "^([0-9a-fA-F]{4}\\.){2}[0-9a-fA-F]{4}$"
        },
        "system_id": {
            "description": "System ID",
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
        "node_id": {
            "description": "Node UUID",
            "type": "string",
            "minLength": 36,
            "maxLength": 36,
            "pattern": "^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$"
        },
        "node_directory": {
            "description": "Path to the vm working directory",
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
        "status": {
            "description": "VM status",
            "enum": ["started", "stopped", "suspended"]
        },
        "platform": {
            "description": "Cisco router platform",
            "type": "string",
            "minLength": 1,
            "pattern": "^c[0-9]{4}$"
        },
        "chassis": {
            "description": "Cisco router chassis model",
            "type": "string",
            "minLength": 1,
            "pattern": "^[0-9]{4}(XM)?$"
        },
        "image": {
            "description": "Path to the IOS image",
            "type": "string",
            "minLength": 1,
        },
        "image_md5sum": {
            "description": "Checksum of the IOS image",
            "type": ["string", "null"],
            "minLength": 1,
        },
        "startup_config": {
            "description": "Path to the IOS startup configuration file",
            "type": "string",
        },
        "private_config": {
            "description": "Path to the IOS private configuration file",
            "type": "string",
        },
        "ram": {
            "description": "Amount of RAM in MB",
            "type": "integer"
        },
        "nvram": {
            "description": "Amount of NVRAM in KB",
            "type": "integer"
        },
        "mmap": {
            "description": "MMAP feature",
            "type": "boolean"
        },
        "sparsemem": {
            "description": "Sparse memory feature",
            "type": "boolean"
        },
        "clock_divisor": {
            "description": "Clock divisor",
            "type": "integer"
        },
        "idlepc": {
            "description": "Idle-PC value",
            "type": "string",
            "pattern": "^(0x[0-9a-fA-F]+)?$"
        },
        "idlemax": {
            "description": "Idlemax value",
            "type": "integer",
        },
        "idlesleep": {
            "description": "Idlesleep value",
            "type": "integer",
        },
        "exec_area": {
            "description": "Exec area value",
            "type": "integer",
        },
        "disk0": {
            "description": "Disk0 size in MB",
            "type": "integer"
        },
        "disk1": {
            "description": "Disk1 size in MB",
            "type": "integer"
        },
        "auto_delete_disks": {
            "description": "Automatically delete nvram and disk files",
            "type": "boolean"
        },
        "console": {
            "description": "Console TCP port",
            "type": "integer",
            "minimum": 1,
            "maximum": 65535
        },
        "console_type": {
            "description": "Console type",
            "enum": ["telnet"]
        },
        "aux": {
            "description": "Auxiliary console TCP port",
            "type": ["integer", "null"],
            "minimum": 1,
            "maximum": 65535
        },
        "mac_addr": {
            "description": "Base MAC address",
            "type": "string",
            #"minLength": 1,
            #"pattern": "^([0-9a-fA-F]{4}\\.){2}[0-9a-fA-F]{4}$"
        },
        "system_id": {
            "description": "System ID",
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
        "startup_config_content": {
            "description": "Content of IOS startup configuration file",
            "type": "string",
        },
        "private_config_content": {
            "description": "Content of IOS private configuration file",
            "type": "string",
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
    "required": ["name", "node_id", "project_id", "dynamips_id", "console", "console_type"]
}
