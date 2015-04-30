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


QEMU_CREATE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to create a new QEMU VM instance",
    "type": "object",
    "properties": {
        "vm_id": {
            "description": "QEMU VM identifier",
            "oneOf": [
                {"type": "string",
                 "minLength": 36,
                 "maxLength": 36,
                 "pattern": "^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$"},
                {"type": "integer"}  # for legacy projects
            ]
        },
        "name": {
            "description": "QEMU VM instance name",
            "type": "string",
            "minLength": 1,
        },
        "qemu_path": {
            "description": "Path to QEMU",
            "type": "string",
            "minLength": 1,
        },
        "console": {
            "description": "console TCP port",
            "minimum": 1,
            "maximum": 65535,
            "type": ["integer", "null"]
        },
        "hda_disk_image": {
            "description": "QEMU hda disk image path",
            "type": ["string", "null"],
        },
        "hdb_disk_image": {
            "description": "QEMU hdb disk image path",
            "type": ["string", "null"],
        },
        "hdc_disk_image": {
            "description": "QEMU hdc disk image path",
            "type": ["string", "null"],
        },
        "hdd_disk_image": {
            "description": "QEMU hdd disk image path",
            "type": ["string", "null"],
        },
        "ram": {
            "description": "amount of RAM in MB",
            "type": ["integer", "null"]
        },
        "adapters": {
            "description": "number of adapters",
            "type": ["integer", "null"],
            "minimum": 0,
            "maximum": 32,
        },
        "adapter_type": {
            "description": "QEMU adapter type",
            "type": ["string", "null"],
            "minLength": 1,
        },
        "initrd": {
            "description": "QEMU initrd path",
            "type": ["string", "null"],
        },
        "kernel_image": {
            "description": "QEMU kernel image path",
            "type": ["string", "null"],
        },
        "kernel_command_line": {
            "description": "QEMU kernel command line",
            "type": ["string", "null"],
        },
        "legacy_networking": {
            "description": "Use QEMU legagy networking commands (-net syntax)",
            "type": ["boolean", "null"],
        },
        "cpu_throttling": {
            "description": "Percentage of CPU allowed for QEMU",
            "minimum": 0,
            "maximum": 800,
            "type": ["integer", "null"],
        },
        "process_priority": {
            "description": "Process priority for QEMU",
            "enum": ["realtime",
                     "very high",
                     "high",
                     "normal",
                     "low",
                     "very low",
                     "null"]
        },
        "options": {
            "description": "Additional QEMU options",
            "type": ["string", "null"],
        },
    },
    "additionalProperties": False,
    "required": ["name", "qemu_path"],
}

QEMU_UPDATE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to update a QEMU VM instance",
    "type": "object",
    "properties": {
        "name": {
            "description": "QEMU VM instance name",
            "type": ["string", "null"],
            "minLength": 1,
        },
        "qemu_path": {
            "description": "Path to QEMU",
            "type": ["string", "null"],
            "minLength": 1,
        },
        "console": {
            "description": "console TCP port",
            "minimum": 1,
            "maximum": 65535,
            "type": ["integer", "null"]
        },
        "hda_disk_image": {
            "description": "QEMU hda disk image path",
            "type": ["string", "null"],
        },
        "hdb_disk_image": {
            "description": "QEMU hdb disk image path",
            "type": ["string", "null"],
        },
        "hdc_disk_image": {
            "description": "QEMU hdc disk image path",
            "type": ["string", "null"],
        },
        "hdd_disk_image": {
            "description": "QEMU hdd disk image path",
            "type": ["string", "null"],
        },
        "ram": {
            "description": "amount of RAM in MB",
            "type": ["integer", "null"]
        },
        "adapters": {
            "description": "number of adapters",
            "type": ["integer", "null"],
            "minimum": 0,
            "maximum": 32,
        },
        "adapter_type": {
            "description": "QEMU adapter type",
            "type": ["string", "null"],
            "minLength": 1,
        },
        "initrd": {
            "description": "QEMU initrd path",
            "type": ["string", "null"],
        },
        "kernel_image": {
            "description": "QEMU kernel image path",
            "type": ["string", "null"],
        },
        "kernel_command_line": {
            "description": "QEMU kernel command line",
            "type": ["string", "null"],
        },
        "legacy_networking": {
            "description": "Use QEMU legagy networking commands (-net syntax)",
            "type": ["boolean", "null"],
        },
        "cpu_throttling": {
            "description": "Percentage of CPU allowed for QEMU",
            "minimum": 0,
            "maximum": 800,
            "type": ["integer", "null"],
        },
        "process_priority": {
            "description": "Process priority for QEMU",
            "enum": ["realtime",
                     "very high",
                     "high",
                     "normal",
                     "low",
                     "very low",
                     "null"]
        },
        "options": {
            "description": "Additional QEMU options",
            "type": ["string", "null"],
        },
    },
    "additionalProperties": False,
}

QEMU_OBJECT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation for a QEMU VM instance",
    "type": "object",
    "properties": {
        "vm_id": {
            "description": "QEMU VM uuid",
            "type": "string",
            "minLength": 1,
        },
        "project_id": {
            "description": "Project uuid",
            "type": "string",
            "minLength": 1,
        },
        "name": {
            "description": "QEMU VM instance name",
            "type": "string",
            "minLength": 1,
        },
        "qemu_path": {
            "description": "path to QEMU",
            "type": "string",
            "minLength": 1,
        },
        "hda_disk_image": {
            "description": "QEMU hda disk image path",
            "type": "string",
        },
        "hdb_disk_image": {
            "description": "QEMU hdb disk image path",
            "type": "string",
        },
        "hdc_disk_image": {
            "description": "QEMU hdc disk image path",
            "type": "string",
        },
        "hdd_disk_image": {
            "description": "QEMU hdd disk image path",
            "type": "string",
        },
        "ram": {
            "description": "amount of RAM in MB",
            "type": "integer"
        },
        "adapters": {
            "description": "number of adapters",
            "type": "integer",
            "minimum": 0,
            "maximum": 32,
        },
        "adapter_type": {
            "description": "QEMU adapter type",
            "type": "string",
            "minLength": 1,
        },
        "console": {
            "description": "console TCP port",
            "minimum": 1,
            "maximum": 65535,
            "type": "integer"
        },
        "initrd": {
            "description": "QEMU initrd path",
            "type": "string",
        },
        "kernel_image": {
            "description": "QEMU kernel image path",
            "type": "string",
        },
        "kernel_command_line": {
            "description": "QEMU kernel command line",
            "type": "string",
        },
        "legacy_networking": {
            "description": "Use QEMU legagy networking commands (-net syntax)",
            "type": "boolean",
        },
        "cpu_throttling": {
            "description": "Percentage of CPU allowed for QEMU",
            "minimum": 0,
            "maximum": 800,
            "type": "integer",
        },
        "process_priority": {
            "description": "Process priority for QEMU",
            "enum": ["realtime",
                     "very high",
                     "high",
                     "normal",
                     "low",
                     "very low"]
        },
        "options": {
            "description": "Additional QEMU options",
            "type": "string",
        },
    },
    "additionalProperties": False,
    "required": ["vm_id", "project_id", "name", "qemu_path", "hda_disk_image", "hdb_disk_image",
                 "hdc_disk_image", "hdd_disk_image", "ram", "adapters", "adapter_type", "console",
                 "initrd", "kernel_image", "kernel_command_line",
                 "legacy_networking", "cpu_throttling", "process_priority", "options"
                 ]
}

QEMU_BINARY_LIST_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation for a list of qemu binaries",
    "type": "array",
    "items": {
        "$ref": "#/definitions/QemuPath"
    },
    "definitions": {
        "QemuPath": {
            "description": "Qemu path object",
            "properties": {
                "path": {
                    "description": "Qemu path",
                    "type": "string",
                },
                "version": {
                    "description": "Qemu version",
                    "type": "string",
                },
            },
        }
    },
    "additionalProperties": False,
}
