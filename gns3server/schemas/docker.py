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


DOCKER_CREATE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to create a new Docker container",
    "type": "object",
    "properties": {
        "node_id": {
            "description": "Node UUID",
            "type": "string",
            "minLength": 36,
            "maxLength": 36,
            "pattern": "^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$"
        },
        "name": {
            "description": "Docker container name",
            "type": "string",
            "minLength": 1,
        },
        "console": {
            "description": "Console TCP port",
            "minimum": 1,
            "maximum": 65535,
            "type": ["integer", "null"]
        },
        "console_type": {
            "description": "Console type",
            "enum": ["telnet", "vnc", "http", "https"]
        },
        "console_resolution": {
            "description": "Console resolution for VNC",
            "type": ["string", "null"],
            "pattern": "^[0-9]+x[0-9]+$"
        },
        "console_http_port": {
            "description": "Internal port in the container for the HTTP server",
            "type": "integer",
        },
        "console_http_path": {
            "description": "Path of the web interface",
            "type": "string",
        },
        "aux": {
            "description": "Auxiliary TCP port",
            "minimum": 1,
            "maximum": 65535,
            "type": ["integer", "null"]
        },
        "start_command": {
            "description": "Docker CMD entry",
            "type": ["string", "null"],
            "minLength": 0,
        },
        "image": {
            "description": "Docker image name",
            "type": "string",
            "minLength": 1,
        },
        "adapters": {
            "description": "Number of adapters",
            "type": ["integer", "null"],
            "minimum": 0,
            "maximum": 99,
        },
        "environment": {
            "description": "Docker environment variables",
            "type": ["string", "null"],
            "minLength": 0,
        },
        "container_id": {
            "description": "Docker container ID Read only",
            "type": "string",
            "minLength": 12,
            "maxLength": 64,
            "pattern": "^[a-f0-9]+$"
        }
    },
    "additionalProperties": False,
    "required": ["name", "image"]
}

DOCKER_OBJECT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Docker container instance",
    "type": "object",
    "properties": {
        "name": {
            "description": "Docker container name",
            "type": "string",
            "minLength": 1,
        },
        "node_id": {
            "description": "Node UUID",
            "type": "string",
            "minLength": 36,
            "maxLength": 36,
            "pattern": "^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$"
        },
        "aux": {
            "description": "Auxiliary TCP port",
            "minimum": 1,
            "maximum": 65535,
            "type": "integer"
        },
        "console": {
            "description": "Console TCP port",
            "minimum": 1,
            "maximum": 65535,
            "type": "integer"
        },
        "console_resolution": {
            "description": "Console resolution for VNC",
            "type": "string",
            "pattern": "^[0-9]+x[0-9]+$"
        },
        "console_type": {
            "description": "Console type",
            "enum": ["telnet", "vnc", "http", "https"]
        },
        "console_http_port": {
            "description": "Internal port in the container for the HTTP server",
            "type": "integer",
        },
        "console_http_path": {
            "description": "Path of the web interface",
            "type": "string",
        },
        "container_id": {
            "description": "Docker container ID Read only",
            "type": "string",
            "minLength": 12,
            "maxLength": 64,
            "pattern": "^[a-f0-9]+$"
        },
        "project_id": {
            "description": "Project UUID Read only",
            "type": "string",
            "minLength": 36,
            "maxLength": 36,
            "pattern": "^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$"
        },
        "image": {
            "description": "Docker image name  Read only",
            "type": "string",
            "minLength": 1,
        },
        "adapters": {
            "description": "number of adapters",
            "type": ["integer", "null"],
            "minimum": 0,
            "maximum": 99,
        },
        "start_command": {
            "description": "Docker CMD entry",
            "type": ["string", "null"],
            "minLength": 0,
        },
        "environment": {
            "description": "Docker environment",
            "type": ["string", "null"],
            "minLength": 0,
        },
        "node_directory": {
            "description": "Path to the node working directory  Read only",
            "type": "string"
        },
        "status": {
            "description": "VM status Read only",
            "enum": ["started", "stopped", "suspended"]
        },
    },
    "additionalProperties": False,
}


DOCKER_LIST_IMAGES_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Docker list of images",
    "type": "array",
    "items": [
        {
            "type": "object",
            "properties": {
                "image": {
                    "description": "Docker image name",
                    "type": "string",
                    "minLength": 1
                }
            }
        }
    ]
}
