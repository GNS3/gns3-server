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


ROUTER_CREATE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to create a new Dynamips router instance",
    "type": "object",
    "properties": {
        "name": {
            "description": "Router name",
            "type": "string",
            "minLength": 1,
        },
        "router_id": {
            "description": "VM/router instance ID",
            "type": "integer"
        },
        "platform": {
            "description": "router platform",
            "type": "string",
            "minLength": 1,
            "pattern": "^c[0-9]{4}$"
        },
        "chassis": {
            "description": "router chassis model",
            "type": "string",
            "minLength": 1,
            "pattern": "^[0-9]{4}(XM)?$"
        },
        "image": {
            "description": "path to the IOS image file",
            "type": "string",
            "minLength": 1
        },
        "ram": {
            "description": "amount of RAM in MB",
            "type": "integer"
        },
        "console": {
            "description": "console TCP port",
            "type": "integer",
            "minimum": 1,
            "maximum": 65535
        },
        "aux": {
            "description": "auxiliary console TCP port",
            "type": "integer",
            "minimum": 1,
            "maximum": 65535
        },
        "mac_addr": {
            "description": "base MAC address",
            "type": "string",
            "minLength": 1,
            "pattern": "^([0-9a-fA-F]{4}\\.){2}[0-9a-fA-F]{4}$"
        },
        "cloud_path": {
            "description": "Path to the image in the cloud object store",
            "type": "string",
        }
    },
    "additionalProperties": False,
    "required": ["name", "platform", "image", "ram"]
}

ROUTER_OBJECT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Dynamips router instance",
    "type": "object",
    "properties": {
        "name": {
            "description": "Dynamips router instance name",
            "type": "string",
            "minLength": 1,
        },
        "vm_id": {
            "description": "Dynamips router instance UUID",
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
    },
    "additionalProperties": False,
    "required": ["name", "vm_id", "project_id"]
}
