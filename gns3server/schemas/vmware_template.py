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


VMWARE_TEMPLATE_PROPERTIES = {
    "vmx_path": {
        "description": "Path to the vmx file",
        "type": "string",
        "minLength": 1,
    },
    "usage": {
        "description": "How to use the VMware VM",
        "type": "string",
        "default": ""
    },
    "linked_clone": {
        "description": "Whether the VM is a linked clone or not",
        "type": "boolean",
        "default": False
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
    "adapters": {
        "description": "Number of adapters",
        "type": "integer",
        "minimum": 0,
        "maximum": 10,  # maximum adapters support by VMware VMs,
        "default": 1
    },
    "adapter_type": {
        "description": "VMware adapter type",
        "enum": ["default", "e1000", "e1000e", "flexible", "vlance", "vmxnet", "vmxnet2", "vmxnet3"],
        "default": "e1000"
    },
    "use_any_adapter": {
        "description": "Allow GNS3 to use any VMware adapter",
        "type": "boolean",
        "default": False
    },
    "headless": {
        "description": "Headless mode",
        "type": "boolean",
        "default": False
    },
    "on_close": {
        "description": "Action to execute on the VM is closed",
        "enum": ["power_off", "shutdown_signal", "save_vm_state"],
        "default": "power_off"
    },
    "console_type": {
        "description": "Console type",
        "enum": ["telnet", "none"],
        "default": "none"
    },
    "console_auto_start": {
        "description": "Automatically start the console when the node has started",
        "type": "boolean",
        "default": False
    },
    "custom_adapters": CUSTOM_ADAPTERS_ARRAY_SCHEMA
}

VMWARE_TEMPLATE_PROPERTIES.update(copy.deepcopy(BASE_TEMPLATE_PROPERTIES))
VMWARE_TEMPLATE_PROPERTIES["category"]["default"] = "guest"
VMWARE_TEMPLATE_PROPERTIES["default_name_format"]["default"] = "{name}-{0}"
VMWARE_TEMPLATE_PROPERTIES["symbol"]["default"] = ":/symbols/vmware_guest.svg"

VMWARE_TEMPLATE_OBJECT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "A VMware template object",
    "type": "object",
    "properties": VMWARE_TEMPLATE_PROPERTIES,
    "required": ["vmx_path"],
    "additionalProperties": False
}
