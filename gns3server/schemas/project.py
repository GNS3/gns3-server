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


PROJECT_CREATE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to create a new Project instance",
    "type": "object",
    "properties": {
        "name": {
            "description": "Project name",
            "type": ["string", "null"],
            "minLength": 1
        },
        "path": {
            "description": "Project directory",
            "type": ["string", "null"],
            "minLength": 1
        },
        "project_id": {
            "description": "Project UUID",
            "type": ["string", "null"],
            "minLength": 36,
            "maxLength": 36,
            "pattern": "^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$"
        },
        "temporary": {
            "description": "If project is a temporary project",
            "type": "boolean"
        },
    },
    "additionalProperties": False,
}

PROJECT_UPDATE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to update a Project instance",
    "type": "object",
    "properties": {
        "name": {
            "description": "Project name",
            "type": ["string", "null"],
            "minLength": 1
        },
        "temporary": {
            "description": "If project is a temporary project",
            "type": "boolean"
        },
        "path": {
            "description": "Path of the project on the server (work only with --local)",
            "type": ["string", "null"]
        },
    },
    "additionalProperties": False,
}

PROJECT_OBJECT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Project instance",
    "type": "object",
    "properties": {
        "name": {
            "description": "Project name",
            "type": ["string", "null"],
            "minLength": 1
        },
        "location": {
            "description": "Base directory where the project should be created on remote server",
            "type": "string",
            "minLength": 1
        },
        "path": {
            "description": "Directory of the project on the server",
            "type": "string",
            "minLength": 1
        },
        "project_id": {
            "description": "Project UUID",
            "type": "string",
            "minLength": 36,
            "maxLength": 36,
            "pattern": "^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$"
        },
        "temporary": {
            "description": "If project is a temporary project",
            "type": "boolean"
        },
    },
    "additionalProperties": False,
    "required": ["location", "project_id", "temporary"]
}

PROJECT_LIST_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "List of projects",
    "type": "array",
    "items": PROJECT_OBJECT_SCHEMA
}

PROJECT_FILE_LIST_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "List files in the project",
    "type": "array",
    "items": [
        {
            "type": "object",
            "properties": {
                "path": {
                    "description": "File path",
                    "type": ["string"]
                },
                "md5sum": {
                    "description": "MD5 hash of the file",
                    "type": ["string"]
                },

            },
        }
    ],
    "additionalProperties": False,
}
