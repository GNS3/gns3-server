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


VBOX_CREATE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to create a new VirtualBox VM instance",
    "type": "object",
    "properties": {
        "name": {
            "description": "VirtualBox VM instance name",
            "type": "string",
            "minLength": 1,
        },
        "vmname": {
            "description": "VirtualBox VM name (in VirtualBox itself)",
            "type": "string",
            "minLength": 1,
        },
        "linked_clone": {
            "description": "either the VM is a linked clone or not",
            "type": "boolean"
        },
        "vbox_id": {
            "description": "VirtualBox VM instance ID (for project created before GNS3 1.3)",
            "type": "integer"
        },
        "uuid": {
            "description": "VirtualBox VM instance UUID",
            "type": "string",
            "minLength": 36,
            "maxLength": 36,
            "pattern": "^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$"
        },
        "project_uuid": {
            "description": "Project UUID",
            "type": "string",
            "minLength": 36,
            "maxLength": 36,
            "pattern": "^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$"
        },
    },
    "additionalProperties": False,
    "required": ["name", "vmname"],
}

VBOX_OBJECT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "VirtualBox VM instance",
    "type": "object",
    "properties": {
        "name": {
            "description": "VirtualBox VM instance name",
            "type": "string",
            "minLength": 1,
        },
        "uuid": {
            "description": "VirtualBox VM instance UUID",
            "type": "string",
            "minLength": 36,
            "maxLength": 36,
            "pattern": "^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$"
        },
        "project_uuid": {
            "description": "Project UUID",
            "type": "string",
            "minLength": 36,
            "maxLength": 36,
            "pattern": "^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$"
        },
        "console": {
            "description": "console TCP port",
            "minimum": 1,
            "maximum": 65535,
            "type": "integer"
        },
    },
    "additionalProperties": False,
    "required": ["name", "uuid"]
}
