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


IOU_TEMPLATE_PROPERTIES = {
    "path": {
        "description": "Path of IOU executable",
        "type": "string",
        "minLength": 1
    },
    "usage": {
        "description": "How to use the IOU VM",
        "type": "string",
        "default": ""
    },
    "ethernet_adapters": {
        "description": "Number of ethernet adapters",
        "type": "integer",
        "default": 2
    },
    "serial_adapters": {
        "description": "Number of serial adapters",
        "type": "integer",
        "default": 2
    },
    "ram": {
        "description": "RAM in MB",
        "type": "integer",
        "default": 256
    },
    "nvram": {
        "description": "NVRAM in KB",
        "type": "integer",
        "default": 128
    },
    "use_default_iou_values": {
        "description": "Use default IOU values",
        "type": "boolean",
        "default": True
    },
    "startup_config": {
        "description": "Startup-config of IOU",
        "type": "string",
        "default": "iou_l3_base_startup-config.txt"
    },
    "private_config": {
        "description": "Private-config of IOU",
        "type": "string",
        "default": ""
    },
    "l1_keepalives": {
        "description": "Always keep up Ethernet interface (does not always work)",
        "type": "boolean",
        "default": False
    },
    "console_type": {
        "description": "Console type",
        "enum": ["telnet", "none"],
        "default": "telnet"
    },
    "console_auto_start": {
        "description": "Automatically start the console when the node has started",
        "type": "boolean",
        "default": False
    },
}

IOU_TEMPLATE_PROPERTIES.update(copy.deepcopy(BASE_TEMPLATE_PROPERTIES))
IOU_TEMPLATE_PROPERTIES["category"]["default"] = "router"
IOU_TEMPLATE_PROPERTIES["default_name_format"]["default"] = "IOU{0}"
IOU_TEMPLATE_PROPERTIES["symbol"]["default"] = ":/symbols/multilayer_switch.svg"

IOU_TEMPLATE_OBJECT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "A IOU template object",
    "type": "object",
    "properties": IOU_TEMPLATE_PROPERTIES,
    "required": ["path"],
    "additionalProperties": False
}
