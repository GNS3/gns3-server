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
from .node import NODE_TYPE_SCHEMA

APPLIANCE_TYPE_SCHEMA = NODE_TYPE_SCHEMA

APPLIANCE_OBJECT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "A template object",
    "type": "object",
    "properties": {
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
        "appliance_type": APPLIANCE_TYPE_SCHEMA,
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
    },
    "additionalProperties": True,  #TODO: validate all properties
    "required": ["appliance_id", "compute_id", "appliance_type", "name", "default_name_format", "symbol"]
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
