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

BASE_TEMPLATE_PROPERTIES = {
    "template_id": {
        "description": "Template UUID",
        "type": "string",
        "minLength": 36,
        "maxLength": 36,
        "pattern": "^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$"
    },
    "template_type": {
        "description": "Type of node",
        "enum": ["cloud", "ethernet_hub", "ethernet_switch", "docker", "dynamips", "vpcs", "traceng",
                 "virtualbox", "vmware", "iou", "qemu"]
    },
    "name": {
        "description": "Template name",
        "type": "string",
        "minLength": 1,
    },
    "compute_id": {
        "description": "Compute identifier",
        "type": ["null", "string"]
    },
    "default_name_format": {
        "description": "Default name format",
        "type": "string",
        "minLength": 1
    },
    "symbol": {
        "description": "Symbol of the template",
        "type": "string",
        "minLength": 1
    },
    "category": {
        "description": "Template category",
        "anyOf": [
            {"type": "integer"},  # old category support
            {"enum": ["router", "switch", "guest", "firewall"]}
        ]
    },
    "builtin": {
        "description": "Template is builtin",
        "type": "boolean"
    },
}

TEMPLATE_OBJECT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "A template object",
    "type": "object",
    "properties": BASE_TEMPLATE_PROPERTIES,
    "required": ["name", "template_type", "template_id", "category", "compute_id", "default_name_format", "symbol", "builtin"]
}

TEMPLATE_CREATE_SCHEMA = copy.deepcopy(TEMPLATE_OBJECT_SCHEMA)

# create schema
# these properties are not required to create a template
TEMPLATE_CREATE_SCHEMA["required"].remove("template_id")
TEMPLATE_CREATE_SCHEMA["required"].remove("category")
TEMPLATE_CREATE_SCHEMA["required"].remove("default_name_format")
TEMPLATE_CREATE_SCHEMA["required"].remove("symbol")
TEMPLATE_CREATE_SCHEMA["required"].remove("builtin")

# update schema
TEMPLATE_UPDATE_SCHEMA = copy.deepcopy(TEMPLATE_OBJECT_SCHEMA)
del TEMPLATE_UPDATE_SCHEMA["required"]

TEMPLATE_USAGE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to use a Template instance",
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
        "name": {
            "description": "Use this name to create a new node",
            "type": ["null", "string"]
        },
        "compute_id": {
            "description": "If the template don't have a default compute use this compute",
            "type": ["null", "string"]
        }
    },
    "additionalProperties": False,
    "required": ["x", "y"]
}
