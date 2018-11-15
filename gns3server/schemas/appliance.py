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

import copy
from .dynamips_vm import DYNAMIPS_ADAPTERS, DYNAMIPS_WICS
from .qemu import QEMU_PLATFORMS
from .port import PORT_OBJECT_SCHEMA
from .custom_adapters import CUSTOM_ADAPTERS_ARRAY_SCHEMA


BASE_APPLIANCE_PROPERTIES = {
    "appliance_id": {
        "description": "Appliance UUID from which the node has been created. Read only",
        "type": ["null", "string"],
        "minLength": 36,
        "maxLength": 36,
        "pattern": "^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$"
    },
    "compute_id": {
        "description": "Compute identifier",
        "type": "string"
    },
    "category": {
        "description": "Appliance category",
        "anyOf": [
            {"type": "integer"},  # old category support
            {"enum": ["router", "switch", "guest", "firewall"]}
        ]
    },
    "name": {
        "description": "Appliance name",
        "type": "string",
        "minLength": 1,
    },
    "default_name_format": {
        "description": "Default name format",
        "type": "string",
        "minLength": 1,
    },
    "symbol": {
        "description": "Symbol of the appliance",
        "type": "string",
        "minLength": 1
    },
    "builtin": {
        "description": "Appliance is builtin",
        "type": "boolean"
    },
}

#TODO: improve schema for Dynamips (match platform specific options, e.g. NPE allowd only for c7200)
DYNAMIPS_APPLIANCE_PROPERTIES = {
    "appliance_type": {
        "enum": ["dynamips"]
    },
    "image": {
        "description": "Path to the IOS image",
        "type": "string",
        "minLength": 1
    },
    "chassis": {
        "description": "Chassis type",
        "enum": ["1720","1721", "1750", "1751", "1760", "2610", "2620", "2610XM", "2620XM", "2650XM", "2621", "2611XM",
                 "2621XM", "2651XM", "3620", "3640", "3660", ""]
    },
    "platform": {
        "description": "Platform type",
        "enum": ["c1700", "c2600", "c2691", "c3725", "c3745", "c3600", "c7200"]
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
    "mac_addr": {
        "description": "Base MAC address",
        "type": "string",
        "anyOf": [
            {"pattern": "^([0-9a-fA-F]{4}\\.){2}[0-9a-fA-F]{4}$"},
            {"pattern": "^$"}
        ]
    },
    "system_id": {
        "description": "System ID",
        "type": "string",
        "minLength": 1,
    },
    "startup_config": {
        "description": "IOS startup configuration file",
        "type": "string"
    },
    "private_config": {
        "description": "IOS private configuration file",
        "type": "string"
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
    "iomem": {
        "description": "I/O memory percentage",
        "type": "integer",
        "minimum": 0,
        "maximum": 100
    },
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
    "auto_delete_disks": {
        "description": "Automatically delete nvram and disk files",
        "type": "boolean"
    },
    "wic0": DYNAMIPS_WICS,
    "wic1": DYNAMIPS_WICS,
    "wic2": DYNAMIPS_WICS,
    "slot0": DYNAMIPS_ADAPTERS,
    "slot1": DYNAMIPS_ADAPTERS,
    "slot2": DYNAMIPS_ADAPTERS,
    "slot3": DYNAMIPS_ADAPTERS,
    "slot4": DYNAMIPS_ADAPTERS,
    "slot5": DYNAMIPS_ADAPTERS,
    "slot6": DYNAMIPS_ADAPTERS,
    "console_type": {
        "description": "Console type",
        "enum": ["telnet", "none"]
    },
    "console_auto_start": {
        "description": "Automatically start the console when the node has started",
        "type": "boolean"
    }
}

DYNAMIPS_APPLIANCE_PROPERTIES.update(BASE_APPLIANCE_PROPERTIES)

IOU_APPLIANCE_PROPERTIES = {
    "appliance_type": {
        "enum": ["iou"]
    },
    "path": {
        "description": "Path of IOU executable",
        "type": "string",
        "minLength": 1
    },
    "ethernet_adapters": {
        "description": "Number of ethernet adapters",
        "type": "integer",
    },
    "serial_adapters": {
        "description": "Number of serial adapters",
        "type": "integer"
    },
    "ram": {
        "description": "RAM in MB",
        "type": "integer"
    },
    "nvram": {
        "description": "NVRAM in KB",
        "type": "integer"
    },
    "use_default_iou_values": {
        "description": "Use default IOU values",
        "type": "boolean"
    },
    "startup_config": {
        "description": "Startup-config of IOU",
        "type": "string"
    },
    "private_config": {
        "description": "Private-config of IOU",
        "type": "string"
    },
    "console_type": {
        "description": "Console type",
        "enum": ["telnet", "none"]
    },
    "console_auto_start": {
        "description": "Automatically start the console when the node has started",
        "type": "boolean"
    },
}

IOU_APPLIANCE_PROPERTIES.update(BASE_APPLIANCE_PROPERTIES)

DOCKER_APPLIANCE_PROPERTIES = {
    "appliance_type": {
        "enum": ["docker"]
    },
    "image": {
        "description": "Docker image name",
        "type": "string",
        "minLength": 1
    },
    "adapters": {
        "description": "Number of adapters",
        "type": "integer",
        "minimum": 0,
        "maximum": 99
    },
    "start_command": {
        "description": "Docker CMD entry",
        "type": "string",
        "minLength": 1
    },
    "environment": {
        "description": "Docker environment variables",
        "type": "string",
        "minLength": 1
    },
    "console_type": {
        "description": "Console type",
        "enum": ["telnet", "vnc", "http", "https", "none"]
    },
    "console_auto_start": {
        "description": "Automatically start the console when the node has started",
        "type": "boolean"
    },
    "console_http_port": {
        "description": "Internal port in the container for the HTTP server",
        "type": "integer",
        "minimum": 1,
        "maximum": 65535
    },
    "console_http_path": {
        "description": "Path of the web interface",
        "type": "string",
        "minLength": 1
    },
    "console_resolution": {
        "description": "Console resolution for VNC",
        "type": "string",
        "pattern": "^[0-9]+x[0-9]+$"
    },
    "extra_hosts": {
        "description": "Docker extra hosts (added to /etc/hosts)",
        "type": "string",
        "minLength": 1
    },
    "custom_adapters": CUSTOM_ADAPTERS_ARRAY_SCHEMA
}

DOCKER_APPLIANCE_PROPERTIES.update(BASE_APPLIANCE_PROPERTIES)

QEMU_APPLIANCE_PROPERTIES = {
    "appliance_type": {
        "enum": ["qemu"]
    },
    "usage": {
        "description": "How to use the Qemu VM",
        "type": "string",
        "minLength": 1
    },
    "qemu_path": {
        "description": "Path to QEMU",
        "type": ["string", "null"],
        "minLength": 1,
    },
    "platform": {
        "description": "Platform to emulate",
        "enum": QEMU_PLATFORMS
    },
    "linked_clone": {
        "description": "Whether the VM is a linked clone or not",
        "type": "boolean"
    },
    "ram": {
        "description": "Amount of RAM in MB",
        "type": "integer"
    },
    "cpus": {
        "description": "Number of vCPUs",
        "type": "integer",
        "minimum": 1,
        "maximum": 255
    },
    "adapters": {
        "description": "Number of adapters",
        "type": "integer",
        "minimum": 0,
        "maximum": 275
    },
    "adapter_type": {
        "description": "QEMU adapter type",
        "type": "string",
        "minLength": 1
    },
    "mac_address": {
        "description": "QEMU MAC address",
        "type": "string",
        "minLength": 1,
        "pattern": "^([0-9a-fA-F]{2}[:]){5}([0-9a-fA-F]{2})$"
    },
    "first_port_name": {
        "description": "Optional name of the first networking port example: eth0",
        "type": "string",
        "minLength": 1
    },
    "port_name_format": {
        "description": "Optional formatting of the networking port example: eth{0}",
        "type": "string",
        "minLength": 1
    },
    "port_segment_size": {
        "description": "Optional port segment size. A port segment is a block of port. For example Ethernet0/0 Ethernet0/1 is the module 0 with a port segment size of 2",
        "type": "integer"
    },
    "console_type": {
        "description": "Console type",
        "enum": ["telnet", "vnc", "spice", "spice+agent", "none"]
    },
    "console_auto_start": {
        "description": "Automatically start the console when the node has started",
        "type": "boolean"
    },
    "boot_priority": {
        "description": "QEMU boot priority",
        "enum": ["c", "d", "n", "cn", "cd", "dn", "dc", "nc", "nd"]
    },
    "hda_disk_image": {
        "description": "QEMU hda disk image path",
        "type": "string",
        "minLength": 1
    },
    "hda_disk_interface": {
        "description": "QEMU hda interface",
        "type": "string",
        "minLength": 1
    },
    "hdb_disk_image": {
        "description": "QEMU hdb disk image path",
        "type": "string",
        "minLength": 1
    },
    "hdb_disk_interface": {
        "description": "QEMU hdb interface",
        "type": "string",
        "minLength": 1
    },
    "hdc_disk_image": {
        "description": "QEMU hdc disk image path",
        "type": "string",
        "minLength": 1
    },
    "hdc_disk_interface": {
        "description": "QEMU hdc interface",
        "type": "string",
        "minLength": 1
    },
    "hdd_disk_image": {
        "description": "QEMU hdd disk image path",
        "type": "string",
        "minLength": 1
    },
    "hdd_disk_interface": {
        "description": "QEMU hdd interface",
        "type": "string",
        "minLength": 1
    },
    "cdrom_image": {
        "description": "QEMU cdrom image path",
        "type": "string",
        "minLength": 1
    },
    "initrd": {
        "description": "QEMU initrd path",
        "type": "string",
        "minLength": 1
    },
    "kernel_image": {
        "description": "QEMU kernel image path",
        "type": "string",
        "minLength": 1
    },
    "bios_image": {
        "description": "QEMU bios image path",
        "type": "string",
        "minLength": 1
    },
    "kernel_command_line": {
        "description": "QEMU kernel command line",
        "type": "string",
        "minLength": 1
    },
    "legacy_networking": {
        "description": "Use QEMU legagy networking commands (-net syntax)",
        "type": "boolean"
    },
    "on_close": {
        "description": "Action to execute on the VM is closed",
        "enum": ["power_off", "shutdown_signal", "save_vm_state"],
    },
    "cpu_throttling": {
        "description": "Percentage of CPU allowed for QEMU",
        "minimum": 0,
        "maximum": 800,
        "type": "integer"
    },
    "process_priority": {
        "description": "Process priority for QEMU",
        "enum": ["realtime", "very high", "high", "normal", "low", "very low"]
    },
    "options": {
        "description": "Additional QEMU options",
        "type": "string",
        "minLength": 1
    },
    "custom_adapters": CUSTOM_ADAPTERS_ARRAY_SCHEMA
}

QEMU_APPLIANCE_PROPERTIES.update(BASE_APPLIANCE_PROPERTIES)

VMWARE_APPLIANCE_PROPERTIES = {
    "appliance_type": {
        "enum": ["vmware"]
    },
    "vmx_path": {
        "description": "Path to the vmx file",
        "type": "string",
        "minLength": 1,
    },
    "linked_clone": {
        "description": "Whether the VM is a linked clone or not",
        "type": "boolean"
    },
    "first_port_name": {
        "description": "Optional name of the first networking port example: eth0",
        "type": "string",
        "minLength": 1
    },
    "port_name_format": {
        "description": "Optional formatting of the networking port example: eth{0}",
        "type": "string",
        "minLength": 1
    },
    "port_segment_size": {
        "description": "Optional port segment size. A port segment is a block of port. For example Ethernet0/0 Ethernet0/1 is the module 0 with a port segment size of 2",
        "type": "integer"
    },
    "adapters": {
        "description": "Number of adapters",
        "type": "integer",
        "minimum": 0,
        "maximum": 10,  # maximum adapters support by VMware VMs
    },
    "adapter_type": {
        "description": "VMware adapter type",
        "type": "string",
        "minLength": 1,
    },
    "use_any_adapter": {
        "description": "Allow GNS3 to use any VMware adapter",
        "type": "boolean",
    },
    "headless": {
        "description": "Headless mode",
        "type": "boolean"
    },
    "on_close": {
        "description": "Action to execute on the VM is closed",
        "enum": ["power_off", "shutdown_signal", "save_vm_state"],
    },
    "console_type": {
        "description": "Console type",
        "enum": ["telnet", "none"]
    },
    "console_auto_start": {
        "description": "Automatically start the console when the node has started",
        "type": "boolean"
    },
    "custom_adapters": CUSTOM_ADAPTERS_ARRAY_SCHEMA
}

VMWARE_APPLIANCE_PROPERTIES.update(BASE_APPLIANCE_PROPERTIES)

VIRTUALBOX_APPLIANCE_PROPERTIES = {
    "appliance_type": {
        "enum": ["virtualbox"]
    },
    "vmname": {
        "description": "VirtualBox VM name (in VirtualBox itself)",
        "type": "string",
        "minLength": 1,
    },
    "ram": {
        "description": "Amount of RAM",
        "minimum": 0,
        "maximum": 65535,
        "type": "integer"
    },
    "linked_clone": {
        "description": "Whether the VM is a linked clone or not",
        "type": "boolean"
    },
    "adapters": {
        "description": "Number of adapters",
        "type": "integer",
        "minimum": 0,
        "maximum": 36,  # maximum given by the ICH9 chipset in VirtualBox
    },
    "use_any_adapter": {
        "description": "Allow GNS3 to use any VirtualBox adapter",
        "type": "boolean",
    },
    "adapter_type": {
        "description": "VirtualBox adapter type",
        "type": "string",
        "minLength": 1,
    },
    "first_port_name": {
        "description": "Optional name of the first networking port example: eth0",
        "type": "string",
        "minLength": 1
    },
    "port_name_format": {
        "description": "Optional formatting of the networking port example: eth{0}",
        "type": "string",
        "minLength": 1
    },
    "port_segment_size": {
        "description": "Optional port segment size. A port segment is a block of port. For example Ethernet0/0 Ethernet0/1 is the module 0 with a port segment size of 2",
        "type": "integer"
    },
    "headless": {
        "description": "Headless mode",
        "type": "boolean"
    },
    "on_close": {
        "description": "Action to execute on the VM is closed",
        "enum": ["power_off", "shutdown_signal", "save_vm_state"],
    },
    "console_type": {
        "description": "Console type",
        "enum": ["telnet", "none"]
    },
    "console_auto_start": {
        "description": "Automatically start the console when the node has started",
        "type": "boolean"
    },
    "custom_adapters": CUSTOM_ADAPTERS_ARRAY_SCHEMA
}

VIRTUALBOX_APPLIANCE_PROPERTIES.update(BASE_APPLIANCE_PROPERTIES)

TRACENG_APPLIANCE_PROPERTIES = {
    "appliance_type": {
        "enum": ["traceng"]
    },
    "ip_address": {
        "description": "Source IP address for tracing",
        "type": ["string"],
        "minLength": 1
    },
    "default_destination": {
        "description": "Default destination IP address or hostname for tracing",
        "type": ["string"],
        "minLength": 1
    },
    "console_type": {
        "description": "Console type",
        "enum": ["none"]
    },
}

TRACENG_APPLIANCE_PROPERTIES.update(BASE_APPLIANCE_PROPERTIES)

VPCS_APPLIANCE_PROPERTIES = {
    "appliance_type": {
        "enum": ["vpcs"]
    },
    "base_script_file": {
        "description": "Script file",
        "type": "string",
        "minLength": 1,
    },
    "console_type": {
        "description": "Console type",
        "enum": ["telnet", "none"]
    },
    "console_auto_start": {
        "description": "Automatically start the console when the node has started",
        "type": "boolean"
    },
}

VPCS_APPLIANCE_PROPERTIES.update(BASE_APPLIANCE_PROPERTIES)

ETHERNET_SWITCH_APPLIANCE_PROPERTIES = {
    "appliance_type": {
        "enum": ["ethernet_switch"]
    },
    "ports_mapping": {
        "type": "array",
        "items": [
            {"type": "object",
             "oneOf": [
                 {
                     "description": "Ethernet port",
                     "properties": {
                         "name": {
                             "description": "Port name",
                             "type": "string",
                             "minLength": 1
                         },
                         "port_number": {
                             "description": "Port number",
                             "type": "integer",
                             "minimum": 0
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
                     "required": ["name", "port_number", "type"],
                     "additionalProperties": False
                 },
             ]},
        ]
    },
    "console_type": {
        "description": "Console type",
        "enum": ["telnet", "none"]
    },
}

ETHERNET_SWITCH_APPLIANCE_PROPERTIES.update(BASE_APPLIANCE_PROPERTIES)

ETHERNET_HUB_APPLIANCE_PROPERTIES = {
    "appliance_type": {
        "enum": ["ethernet_hub"]
    },
    "ports_mapping": {
        "type": "array",
        "items": [
            {"type": "object",
             "oneOf": [
                 {
                     "description": "Ethernet port",
                     "properties": {
                         "name": {
                             "description": "Port name",
                             "type": "string",
                             "minLength": 1
                         },
                         "port_number": {
                             "description": "Port number",
                             "type": "integer",
                             "minimum": 0
                         },
                     },
                     "required": ["name", "port_number"],
                     "additionalProperties": False
                 },
             ]},
        ]
    }
}

ETHERNET_HUB_APPLIANCE_PROPERTIES.update(BASE_APPLIANCE_PROPERTIES)

CLOUD_APPLIANCE_PROPERTIES = {
    "appliance_type": {
        "enum": ["cloud"]
    },
    "ports_mapping": {
        "type": "array",
        "items": [
            PORT_OBJECT_SCHEMA
        ]
    },
    "remote_console_host": {
        "description": "Remote console host or IP",
        "type": ["string"],
        "minLength": 1
    },
    "remote_console_port": {
        "description": "Console TCP port",
        "minimum": 1,
        "maximum": 65535,
        "type": "integer"
    },
    "remote_console_type": {
        "description": "Console type",
        "enum": ["telnet", "vnc", "spice", "http", "https", "none"]
    },
    "remote_console_http_path": {
        "description": "Path of the remote web interface",
        "type": "string",
        "minLength": 1
    },
}

CLOUD_APPLIANCE_PROPERTIES.update(BASE_APPLIANCE_PROPERTIES)

APPLIANCE_OBJECT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "A template object",
    "type": "object",
    "definitions": {
        "Dynamips": {
            "description": "Dynamips appliance",
            "properties": DYNAMIPS_APPLIANCE_PROPERTIES,
            #"additionalProperties": False,
            "required": ["platform", "image", "ram"]
        },
        "IOU": {
            "description": "IOU appliance",
            "properties": IOU_APPLIANCE_PROPERTIES,
            "additionalProperties": False,
            "required": ["path"]
        },
        "Docker": {
            "description": "Docker appliance",
            "properties": DOCKER_APPLIANCE_PROPERTIES,
            "additionalProperties": False,
            "required": ["image"]
        },
        "Qemu": {
            "description": "Qemu appliance",
            "properties": QEMU_APPLIANCE_PROPERTIES,
            "additionalProperties": False,
        },
        "VMware": {
            "description": "VMware appliance",
            "properties": VMWARE_APPLIANCE_PROPERTIES,
            "additionalProperties": False,
            "required": ["vmx_path", "linked_clone"]
        },
        "VirtualBox": {
            "description": "VirtualBox appliance",
            "properties": VIRTUALBOX_APPLIANCE_PROPERTIES,
            "additionalProperties": False,
            "required": ["vmname"]
        },
        "TraceNG": {
            "description": "TraceNG appliance",
            "properties": TRACENG_APPLIANCE_PROPERTIES,
            "additionalProperties": False,
        },
        "VPCS": {
            "description": "VPCS appliance",
            "properties": VPCS_APPLIANCE_PROPERTIES,
            "additionalProperties": False,
        },
        "EthernetSwitch": {
            "description": "Ethernet switch appliance",
            "properties": ETHERNET_SWITCH_APPLIANCE_PROPERTIES,
            "additionalProperties": False,
        },
        "EthernetHub": {
            "description": "Ethernet hub appliance",
            "properties": ETHERNET_HUB_APPLIANCE_PROPERTIES,
            "additionalProperties": False,
        },
        "Cloud": {
            "description": "Cloud appliance",
            "properties": CLOUD_APPLIANCE_PROPERTIES,
            "additionalProperties": False,
        },
    },
    "oneOf": [
        {"$ref": "#/definitions/Dynamips"},
        {"$ref": "#/definitions/IOU"},
        {"$ref": "#/definitions/Docker"},
        {"$ref": "#/definitions/Qemu"},
        {"$ref": "#/definitions/VMware"},
        {"$ref": "#/definitions/VirtualBox"},
        {"$ref": "#/definitions/TraceNG"},
        {"$ref": "#/definitions/VPCS"},
        {"$ref": "#/definitions/EthernetSwitch"},
        {"$ref": "#/definitions/EthernetHub"},
        {"$ref": "#/definitions/Cloud"},
    ],
    "required": ["name", "appliance_id", "appliance_type", "category", "compute_id", "default_name_format", "symbol"]
}

APPLIANCE_CREATE_SCHEMA = copy.deepcopy(APPLIANCE_OBJECT_SCHEMA)

# create schema
# these properties are not required to create an appliance
APPLIANCE_CREATE_SCHEMA["required"].remove("appliance_id")
APPLIANCE_CREATE_SCHEMA["required"].remove("compute_id")
APPLIANCE_CREATE_SCHEMA["required"].remove("default_name_format")
APPLIANCE_CREATE_SCHEMA["required"].remove("symbol")

# update schema
APPLIANCE_UPDATE_SCHEMA = copy.deepcopy(APPLIANCE_OBJECT_SCHEMA)
del APPLIANCE_UPDATE_SCHEMA["required"]

APPLIANCE_USAGE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to use an Appliance instance",
    "type": "object",
    "properties": {
        "x": {
            "description": "X position",
            "type": "integer"
        },
        "y": {
            "description": "Y position",
            "type": "integer"
        },
        "compute_id": {
            "description": "If the appliance don't have a default compute use this compute",
            "type": ["null", "string"]
        }
    },
    "additionalProperties": False,
    "required": ["x", "y"]
}
