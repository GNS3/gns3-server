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
from .port import PORT_OBJECT_SCHEMA


CLOUD_TEMPLATE_PROPERTIES = {
    "ports_mapping": {
        "type": "array",
        "items": [PORT_OBJECT_SCHEMA],
        "default": []
    },
    "remote_console_host": {
        "description": "Remote console host or IP",
        "type": ["string"],
        "minLength": 1,
        "default": "127.0.0.1"
    },
    "remote_console_port": {
        "description": "Console TCP port",
        "minimum": 1,
        "maximum": 65535,
        "type": "integer",
        "default": 23
    },
    "remote_console_type": {
        "description": "Console type",
        "enum": ["telnet", "vnc", "spice", "http", "https", "none"],
        "default": "none"
    },
    "remote_console_http_path": {
        "description": "Path of the remote web interface",
        "type": "string",
        "minLength": 1,
        "default": "/"
    },
}

CLOUD_TEMPLATE_PROPERTIES.update(copy.deepcopy(BASE_TEMPLATE_PROPERTIES))
CLOUD_TEMPLATE_PROPERTIES["category"]["default"] = "guest"
CLOUD_TEMPLATE_PROPERTIES["default_name_format"]["default"] = "Cloud{0}"
CLOUD_TEMPLATE_PROPERTIES["symbol"]["default"] = ":/symbols/cloud.svg"

CLOUD_TEMPLATE_OBJECT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "A cloud template object",
    "type": "object",
    "properties": CLOUD_TEMPLATE_PROPERTIES,
    "additionalProperties": False
}
