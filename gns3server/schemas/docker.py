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
        "vm_id": {
            "description": "Docker VM instance identifier",
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
            "description": "console TCP port",
            "minimum": 1,
            "maximum": 65535,
            "type": ["integer", "null"]
        },
        "console_type": {
            "description": "console type",
            "enum": ["telnet", "vnc", "http", "https"]
        },
        "console_resolution": {
            "description": "console resolution for VNC",
            "type": ["string", "null"],
            "pattern": "^[0-9]+x[0-9]+$"
        },
        "console_http_port": {
            "description": "Internal port in the container of the HTTP server",
            "type": "integer",
        },
        "console_http_path": {
            "description": "Path of the web interface",
            "type": "string",
        },
        "aux": {
            "description": "auxilary TCP port",
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
            "description": "number of adapters",
            "type": ["integer", "null"],
            "minimum": 0,
            "maximum": 99,
        },
        "environment": {
            "description": "Docker environment",
            "type": ["string", "null"],
            "minLength": 0,
        }

    },
    "additionalProperties": False,
}


DOCKER_UPDATE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to create a new Docker container",
    "type": "object",
    "properties": {
        "name": {
            "description": "Docker container name",
            "type": "string",
            "minLength": 1,
        },
        "console": {
            "description": "console TCP port",
            "minimum": 1,
            "maximum": 65535,
            "type": ["integer", "null"]
        },
        "console_resolution": {
            "description": "console resolution for VNC",
            "type": ["string", "null"],
            "pattern": "^[0-9]+x[0-9]+$"
        },
        "console_type": {
            "description": "console type",
            "enum": ["telnet", "vnc", "http", "https"]
        },
        "console_http_port": {
            "description": "Internal port in the container of the HTTP server",
            "type": "integer",
        },
        "console_http_path": {
            "description": "Path of the web interface",
            "type": "string",
        },
        "aux": {
            "description": "auxilary TCP port",
            "minimum": 1,
            "maximum": 65535,
            "type": ["integer", "null"]
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
        "adapters": {
            "description": "number of adapters",
            "type": ["integer", "null"],
            "minimum": 0,
            "maximum": 99,
        }
    },
    "additionalProperties": False,
}

DOCKER_OBJECT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Docker instance",
    "type": "object",
    "properties": {
        "name": {
            "description": "Docker container name",
            "type": "string",
            "minLength": 1,
        },
        "vm_id": {
            "description": "Docker container instance UUID",
            "type": "string",
            "minLength": 36,
            "maxLength": 36,
            "pattern": "^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$"
        },
        "aux": {
            "description": "auxilary TCP port",
            "minimum": 1,
            "maximum": 65535,
            "type": "integer"
        },
        "console": {
            "description": "console TCP port",
            "minimum": 1,
            "maximum": 65535,
            "type": "integer"
        },
        "console_resolution": {
            "description": "console resolution for VNC",
            "type": "string",
            "pattern": "^[0-9]+x[0-9]+$"
        },
        "console_type": {
            "description": "console type",
            "enum": ["telnet", "vnc", "http", "https"]
        },
        "console_http_port": {
            "description": "Internal port in the container of the HTTP server",
            "type": "integer",
        },
        "console_http_path": {
            "description": "Path of the web interface",
            "type": "string",
        },
        "container_id": {
            "description": "Docker container ID",
            "type": "string",
            "minLength": 12,
            "maxLength": 64,
            "pattern": "^[a-f0-9]+$"
        },
        "project_id": {
            "description": "Project UUID",
            "type": "string",
            "minLength": 36,
            "maxLength": 36,
            "pattern": "^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$"
        },
        "image": {
            "description": "Docker image name",
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
        "vm_directory": {
            "decription": "Path to the VM working directory",
            "type": "string"
        }
    },
    "additionalProperties": False,
    "required": ["vm_id", "project_id", "image", "container_id", "adapters", "aux", "console", "console_type", "console_resolution", "start_command", "environment", "vm_directory"]
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
