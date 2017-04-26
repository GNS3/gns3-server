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
from .capabilities import CAPABILITIES_SCHEMA

COMPUTE_CREATE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to register a GNS3 compute instance",
    "type": "object",
    "properties": {
        "compute_id": {
            "description": "Server identifier",
            "type": "string"
        },
        "name": {
            "description": "Server name",
            "type": "string"
        },
        "protocol": {
            "description": "Server protocol",
            "enum": ["http", "https"]
        },
        "host": {
            "description": "Server host",
            "type": "string"
        },
        "port": {
            "description": "Server port",
            "type": "integer"
        },
        "user": {
            "description": "User for authentication",
            "type": ["string", "null"]
        },
        "password": {
            "description": "Password for authentication",
            "type": ["string", "null"]
        }
    },
    "additionalProperties": False,
    "required": ["protocol", "host", "port"]
}

COMPUTE_UPDATE_SCHEMA = copy.deepcopy(COMPUTE_CREATE_SCHEMA)
del COMPUTE_UPDATE_SCHEMA["required"]

COMPUTE_OBJECT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to a GNS3 compute object instance",
    "type": "object",
    "properties": {
        "compute_id": {
            "description": "Server identifier",
            "type": "string"
        },
        "name": {
            "description": "Server name",
            "type": "string"
        },
        "protocol": {
            "description": "Server protocol",
            "enum": ["http", "https"]
        },
        "host": {
            "description": "Server host",
            "type": "string"
        },
        "port": {
            "description": "Server port",
            "type": "integer"
        },
        "user": {
            "description": "User for authentication",
            "type": ["string", "null"]
        },
        "connected": {
            "description": "Whether the controller is connected to the compute server or not",
            "type": "boolean"
        },
        "cpu_usage_percent": {
            "description": "CPU usage of the compute. Read only",
            "type": ["number", "null"],
            "maximum": 100,
            "minimum": 0
        },
        "memory_usage_percent": {
            "description": "RAM usage of the compute. Read only",
            "type": ["number", "null"],
            "maximum": 100,
            "minimum": 0
        },
        "capabilities": CAPABILITIES_SCHEMA
    },
    "additionalProperties": False,
    "required": ["compute_id", "protocol", "host", "port", "name"]
}
