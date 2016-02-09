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


VBOX_CREATE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to create a new VirtualBox VM instance",
    "type": "object",
    "properties": {
        "vm_id": {
            "description": "VirtualBox VM instance identifier",
            "oneOf": [
                {"type": "string",
                 "minLength": 36,
                 "maxLength": 36,
                 "pattern": "^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$"},
                {"type": "integer"}  # for legacy projects
            ]
        },
        "linked_clone": {
            "description": "either the VM is a linked clone or not",
            "type": "boolean"
        },
        "name": {
            "description": "VirtualBox VM instance name",
            "type": "string",
            "minLength": 1,
        },
        "vmname": {
            "description": "VirtualBox VM name (in VirtualBox itself)",
            "type": "string",
            "minLength": 1,
        },
        "adapters": {
            "description": "number of adapters",
            "type": "integer",
            "minimum": 0,
            "maximum": 36,  # maximum given by the ICH9 chipset in VirtualBox
        },
        "use_any_adapter": {
            "description": "allow GNS3 to use any VirtualBox adapter",
            "type": "boolean",
        },
        "adapter_type": {
            "description": "VirtualBox adapter type",
            "type": "string",
            "minLength": 1,
        },
        "console": {
            "description": "console TCP port",
            "minimum": 1,
            "maximum": 65535,
            "type": "integer"
        },
        "enable_remote_console": {
            "description": "enable the remote console",
            "type": "boolean"
        },
        "ram": {
            "description": "Amount of RAM",
            "minimum": 0,
            "maximum": 65535,
            "type": "integer"
        },
        "headless": {
            "description": "headless mode",
            "type": "boolean"
        },
        "acpi_shutdown": {
            "description": "ACPI shutdown",
            "type": "boolean"
        },
    },
    "additionalProperties": False,
    "required": ["name", "vmname", "linked_clone"],
}

VBOX_UPDATE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to update a VirtualBox VM instance",
    "type": "object",
    "properties": {
        "name": {
            "description": "VirtualBox VM instance name",
            "type": "string",
            "minLength": 1,
        },
        "vmname": {
            "description": "VirtualBox VM name (in VirtualBox itself)",
            "type": "string",
            "minLength": 1,
        },
        "adapters": {
            "description": "number of adapters",
            "type": "integer",
            "minimum": 0,
            "maximum": 36,  # maximum given by the ICH9 chipset in VirtualBox
        },
        "use_any_adapter": {
            "description": "allow GNS3 to use any VirtualBox adapter",
            "type": "boolean",
        },
        "adapter_type": {
            "description": "VirtualBox adapter type",
            "type": "string",
            "minLength": 1,
        },
        "console": {
            "description": "console TCP port",
            "minimum": 1,
            "maximum": 65535,
            "type": "integer"
        },
        "enable_remote_console": {
            "description": "enable the remote console",
            "type": "boolean"
        },
        "ram": {
            "description": "Amount of RAM",
            "minimum": 0,
            "maximum": 65535,
            "type": "integer"
        },
        "headless": {
            "description": "headless mode",
            "type": "boolean"
        },
        "acpi_shutdown": {
            "description": "ACPI shutdown",
            "type": "boolean"
        },
    },
    "additionalProperties": False,
}


VBOX_OBJECT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "VirtualBox VM instance",
    "type": "object",
    "properties": {
        "name": {
            "description": "VirtualBox VM instance name",
            "type": "string",
            "minLength": 1,
        },
        "vm_id": {
            "description": "VirtualBox VM instance UUID",
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
        "vmname": {
            "description": "VirtualBox VM name (in VirtualBox itself)",
            "type": "string",
            "minLength": 1,
        },
        "vm_directory": {
            "decription": "Path to the VM working directory",
            "type": ["string", "null"]
        },
        "enable_remote_console": {
            "description": "enable the remote console",
            "type": "boolean"
        },
        "headless": {
            "description": "headless mode",
            "type": "boolean"
        },
        "acpi_shutdown": {
            "description": "ACPI shutdown",
            "type": "boolean"
        },
        "adapters": {
            "description": "number of adapters",
            "type": "integer",
            "minimum": 0,
            "maximum": 36,  # maximum given by the ICH9 chipset in VirtualBox
        },
        "use_any_adapter": {
            "description": "allow GNS3 to use any VirtualBox adapter",
            "type": "boolean",
        },
        "adapter_type": {
            "description": "VirtualBox adapter type",
            "type": "string",
            "minLength": 1,
        },
        "console": {
            "description": "console TCP port",
            "minimum": 1,
            "maximum": 65535,
            "type": "integer"
        },
        "ram": {
            "description": "Amount of RAM",
            "minimum": 0,
            "maximum": 65535,
            "type": "integer"
        },
    },
    "additionalProperties": False,
    "required": ["name", "vm_id", "project_id", "vm_directory"]
}
