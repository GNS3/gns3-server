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


IOU_CREATE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to create a new IOU instance",
    "type": "object",
    "properties": {
        "name": {
            "description": "IOU VM name",
            "type": "string",
            "minLength": 1,
        },
        "vm_id": {
            "description": "IOU VM identifier",
            "oneOf": [
                {"type": "string",
                 "minLength": 36,
                 "maxLength": 36,
                 "pattern": "^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$"},
                {"type": "integer"}  # for legacy projects
            ]
        },
        "console": {
            "description": "console TCP port",
            "minimum": 1,
            "maximum": 65535,
            "type": ["integer", "null"]
        },
        "path": {
            "description": "Path of iou binary",
            "type": "string"
        },
        "iourc_path": {
            "description": "Path of iourc",
            "type": "string"
        },
    },
    "additionalProperties": False,
    "required": ["name", "path", "iourc_path"]
}

IOU_UPDATE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to update a IOU instance",
    "type": "object",
    "properties": {
        "name": {
            "description": "IOU VM name",
            "type": ["string", "null"],
            "minLength": 1,
        },
        "console": {
            "description": "console TCP port",
            "minimum": 1,
            "maximum": 65535,
            "type": ["integer", "null"]
        },
        "path": {
            "description": "Path of iou binary",
            "type": "string"
        },
        "iourc_path": {
            "description": "Path of iourc",
            "type": "string"
        },
    },
    "additionalProperties": False,
}

IOU_OBJECT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "IOU instance",
    "type": "object",
    "properties": {
        "name": {
            "description": "IOU VM name",
            "type": "string",
            "minLength": 1,
        },
        "vm_id": {
            "description": "IOU VM UUID",
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
        "project_id": {
            "description": "Project UUID",
            "type": "string",
            "minLength": 36,
            "maxLength": 36,
            "pattern": "^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$"
        },
        "path": {
            "description": "Path of iou binary",
            "type": "string"
        },
        "iourc_path": {
            "description": "Path of iourc",
            "type": "string"
        },
    },
    "additionalProperties": False,
    "required": ["name", "vm_id", "console", "project_id", "path", "iourc_path"]
}
