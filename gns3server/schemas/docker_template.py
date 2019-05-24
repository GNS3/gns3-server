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
from .custom_adapters import CUSTOM_ADAPTERS_ARRAY_SCHEMA


DOCKER_TEMPLATE_PROPERTIES = {
    "image": {
        "description": "Docker image name",
        "type": "string",
        "minLength": 1
    },
    "usage": {
        "description": "How to use the Docker container",
        "type": "string",
        "default": ""
    },
    "adapters": {
        "description": "Number of adapters",
        "type": "integer",
        "minimum": 0,
        "maximum": 99,
        "default": 1
    },
    "start_command": {
        "description": "Docker CMD entry",
        "type": "string",
        "default": ""
    },
    "environment": {
        "description": "Docker environment variables",
        "type": "string",
        "default": ""
    },
    "console_type": {
        "description": "Console type",
        "enum": ["telnet", "vnc", "http", "https", "none"],
        "default": "telnet"
    },
    "console_auto_start": {
        "description": "Automatically start the console when the node has started",
        "type": "boolean",
        "default": False,
    },
    "console_http_port": {
        "description": "Internal port in the container for the HTTP server",
        "type": "integer",
        "minimum": 1,
        "maximum": 65535,
        "default": 80
    },
    "console_http_path": {
        "description": "Path of the web interface",
        "type": "string",
        "minLength": 1,
        "default": "/"
    },
    "console_resolution": {
        "description": "Console resolution for VNC",
        "type": "string",
        "pattern": "^[0-9]+x[0-9]+$",
        "default": "1024x768"
    },
    "extra_hosts": {
        "description": "Docker extra hosts (added to /etc/hosts)",
        "type": "string",
        "default": ""
    },
    "extra_volumes": {
        "description": "Additional directories to make persistent",
        "type": "array",
        "default": []
    },
    "custom_adapters": CUSTOM_ADAPTERS_ARRAY_SCHEMA
}

DOCKER_TEMPLATE_PROPERTIES.update(copy.deepcopy(BASE_TEMPLATE_PROPERTIES))
DOCKER_TEMPLATE_PROPERTIES["category"]["default"] = "guest"
DOCKER_TEMPLATE_PROPERTIES["default_name_format"]["default"] = "{name}-{0}"
DOCKER_TEMPLATE_PROPERTIES["symbol"]["default"] = ":/symbols/docker_guest.svg"

DOCKER_TEMPLATE_OBJECT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "A Docker template object",
    "type": "object",
    "properties": DOCKER_TEMPLATE_PROPERTIES,
    "required": ["image"],
    "additionalProperties": False
}
