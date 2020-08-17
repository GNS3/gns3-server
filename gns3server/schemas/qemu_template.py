# -*- coding: utf-8 -*-
#
# Copyright (C) 2016 GNS3 Technologies Inc.
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
from .template import BASE_TEMPLATE_PROPERTIES
from .custom_adapters import CUSTOM_ADAPTERS_ARRAY_SCHEMA
from .qemu import QEMU_PLATFORMS


QEMU_TEMPLATE_PROPERTIES = {
    "qemu_path": {
        "description": "Path to QEMU",
        "type": "string",
        "default": ""
    },
    "usage": {
        "description": "How to use the Qemu VM",
        "type": "string",
        "default": ""
    },
    "platform": {
        "description": "Platform to emulate",
        "enum": QEMU_PLATFORMS,
        "default": "i386"
    },
    "linked_clone": {
        "description": "Whether the VM is a linked clone or not",
        "type": "boolean",
        "default": True
    },
    "ram": {
        "description": "Amount of RAM in MB",
        "type": "integer",
        "default": 256
    },
    "cpus": {
        "description": "Number of vCPUs",
        "type": "integer",
        "minimum": 1,
        "maximum": 255,
        "default": 1
    },
    "adapters": {
        "description": "Number of adapters",
        "type": "integer",
        "minimum": 0,
        "maximum": 275,
        "default": 1
    },
    "adapter_type": {
        "description": "QEMU adapter type",
        "type": "string",
        "enum": ["e1000", "e1000-82544gc", "e1000-82545em", "e1000e", "i82550", "i82551", "i82557a", "i82557b", "i82557c", "i82558a",
                 "i82558b", "i82559a", "i82559b", "i82559c", "i82559er", "i82562", "i82801", "ne2k_pci", "pcnet", "rocker", "rtl8139",
                 "virtio", "virtio-net-pci", "vmxnet3"],
        "default": "e1000"
    },
    "mac_address": {
        "description": "QEMU MAC address",
        "type": ["string", "null"],
        "anyOf": [
            {"pattern": "^([0-9a-fA-F]{2}[:]){5}([0-9a-fA-F]{2})$"},
            {"pattern": "^$"}
        ],
        "default": "",
    },
    "first_port_name": {
        "description": "Optional name of the first networking port example: eth0",
        "type": "string",
        "default": ""
    },
    "port_name_format": {
        "description": "Optional formatting of the networking port example: eth{0}",
        "type": "string",
        "default": "Ethernet{0}"
    },
    "port_segment_size": {
        "description": "Optional port segment size. A port segment is a block of port. For example Ethernet0/0 Ethernet0/1 is the module 0 with a port segment size of 2",
        "type": "integer",
        "default": 0
    },
    "console_type": {
        "description": "Console type",
        "enum": ["telnet", "vnc", "spice", "spice+agent", "none"],
        "default": "telnet"
    },
    "console_auto_start": {
        "description": "Automatically start the console when the node has started",
        "type": "boolean",
        "default": False
    },
    "boot_priority": {
        "description": "QEMU boot priority",
        "enum": ["c", "d", "n", "cn", "cd", "dn", "dc", "nc", "nd"],
        "default": "c"
    },
    "hda_disk_image": {
        "description": "QEMU hda disk image path",
        "type": "string",
        "default": ""
    },
    "hda_disk_interface": {
        "description": "QEMU hda interface",
        "enum": ["ide", "sata", "nvme", "scsi", "sd", "mtd", "floppy", "pflash", "virtio", "none"],
        "default": "none"
    },
    "hdb_disk_image": {
        "description": "QEMU hdb disk image path",
        "type": "string",
        "default": ""
    },
    "hdb_disk_interface": {
        "description": "QEMU hdb interface",
        "enum": ["ide", "sata", "nvme", "scsi", "sd", "mtd", "floppy", "pflash", "virtio", "none"],
        "default": "none"
    },
    "hdc_disk_image": {
        "description": "QEMU hdc disk image path",
        "type": "string",
        "default": ""
    },
    "hdc_disk_interface": {
        "description": "QEMU hdc interface",
        "enum": ["ide", "sata", "nvme", "scsi", "sd", "mtd", "floppy", "pflash", "virtio", "none"],
        "default": "none"
    },
    "hdd_disk_image": {
        "description": "QEMU hdd disk image path",
        "type": "string",
        "default": ""
    },
    "hdd_disk_interface": {
        "description": "QEMU hdd interface",
        "enum": ["ide", "sata", "nvme", "scsi", "sd", "mtd", "floppy", "pflash", "virtio", "none"],
        "default": "none"
    },
    "cdrom_image": {
        "description": "QEMU cdrom image path",
        "type": "string",
        "default": ""
    },
    "initrd": {
        "description": "QEMU initrd path",
        "type": "string",
        "default": ""
    },
    "kernel_image": {
        "description": "QEMU kernel image path",
        "type": "string",
        "default": ""
    },
    "bios_image": {
        "description": "QEMU bios image path",
        "type": "string",
        "default": ""
    },
    "kernel_command_line": {
        "description": "QEMU kernel command line",
        "type": "string",
        "default": ""
    },
    "legacy_networking": {
        "description": "Use QEMU legagy networking commands (-net syntax)",
        "type": "boolean",
        "default": False
    },
    "replicate_network_connection_state": {
        "description": "Replicate the network connection state for links in Qemu",
        "type": "boolean",
        "default": True
    },
    "create_config_disk": {
        "description": "Automatically create a config disk on HDD disk interface (secondary slave)",
        "type": "boolean",
        "default": False
    },
    "on_close": {
        "description": "Action to execute on the VM is closed",
        "enum": ["power_off", "shutdown_signal", "save_vm_state"],
        "default": "power_off"
    },
    "cpu_throttling": {
        "description": "Percentage of CPU allowed for QEMU",
        "minimum": 0,
        "maximum": 800,
        "type": "integer",
        "default": 0
    },
    "process_priority": {
        "description": "Process priority for QEMU",
        "enum": ["realtime", "very high", "high", "normal", "low", "very low"],
        "default": "normal"
    },
    "options": {
        "description": "Additional QEMU options",
        "type": "string",
        "default": ""
    },
    "custom_adapters": CUSTOM_ADAPTERS_ARRAY_SCHEMA
}

QEMU_TEMPLATE_PROPERTIES.update(copy.deepcopy(BASE_TEMPLATE_PROPERTIES))
QEMU_TEMPLATE_PROPERTIES["category"]["default"] = "guest"
QEMU_TEMPLATE_PROPERTIES["default_name_format"]["default"] = "{name}-{0}"
QEMU_TEMPLATE_PROPERTIES["symbol"]["default"] = ":/symbols/qemu_guest.svg"

QEMU_TEMPLATE_OBJECT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "A Qemu template object",
    "type": "object",
    "properties": QEMU_TEMPLATE_PROPERTIES,
    "additionalProperties": False
}
