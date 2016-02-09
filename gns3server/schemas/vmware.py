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


VMWARE_CREATE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to create a new VMware VM instance",
    "type": "object",
    "properties": {
        "vm_id": {
            "description": "VMware VM instance identifier",
            "type": "string",
            "minLength": 36,
            "maxLength": 36,
            "pattern": "^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$"
        },
        "linked_clone": {
            "description": "either the VM is a linked clone or not",
            "type": "boolean"
        },
        "name": {
            "description": "VMware VM instance name",
            "type": "string",
            "minLength": 1,
        },
        "vmx_path": {
            "description": "path to the vmx file",
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
            "maximum": 10,  # maximum adapters support by VMware VMs
        },
        "adapter_type": {
            "description": "VMware adapter type",
            "type": "string",
            "minLength": 1,
        },
        "use_ubridge": {
            "description": "use uBridge for network connections",
            "type": "boolean",
        },
        "use_any_adapter": {
            "description": "allow GNS3 to use any VMware adapter",
            "type": "boolean",
        },
    },
    "additionalProperties": False,
    "required": ["name", "vmx_path", "linked_clone"],
}

VMWARE_UPDATE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to update a VMware VM instance",
    "type": "object",
    "properties": {
        "name": {
            "description": "VMware VM instance name",
            "type": "string",
            "minLength": 1,
        },
        "vmx_path": {
            "description": "path to the vmx file",
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
            "maximum": 10,  # maximum adapters support by VMware VMs
        },
        "adapter_type": {
            "description": "VMware adapter type",
            "type": "string",
            "minLength": 1,
        },
        "use_ubridge": {
            "description": "use uBridge for network connections",
            "type": "boolean",
        },
        "use_any_adapter": {
            "description": "allow GNS3 to use any VMware adapter",
            "type": "boolean",
        },
    },
    "additionalProperties": False,
}


VMWARE_OBJECT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "VMware VM instance",
    "type": "object",
    "properties": {
        "name": {
            "description": "VMware VM instance name",
            "type": "string",
            "minLength": 1,
        },
        "vm_id": {
            "description": "VMware VM instance UUID",
            "type": "string",
            "minLength": 36,
            "maxLength": 36,
            "pattern": "^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$"
        },
        "vm_directory": {
            "decription": "Path to the VM working directory",
            "type": ["string", "null"]
        },
        "project_id": {
            "description": "Project UUID",
            "type": "string",
            "minLength": 36,
            "maxLength": 36,
            "pattern": "^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$"
        },
        "vmx_path": {
            "description": "path to the vmx file",
            "type": "string",
            "minLength": 1,
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
            "maximum": 10,  # maximum adapters support by VMware VMs
        },
        "adapter_type": {
            "description": "VMware adapter type",
            "type": "string",
            "minLength": 1,
        },
        "use_ubridge": {
            "description": "use uBridge for network connections",
            "type": "boolean",
        },
        "use_any_adapter": {
            "description": "allow GNS3 to use any VMware adapter",
            "type": "boolean",
        },
        "console": {
            "description": "console TCP port",
            "minimum": 1,
            "maximum": 65535,
            "type": "integer"
        },
    },
    "additionalProperties": False,
    "required": ["name", "vm_id", "project_id"]
}
