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


SERVER_CREATE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to register a GNS3 server instance",
    "type": "object",
    "properties": {
        "server_id": {
            "description": "Server identifier",
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
            "description": "User for auth",
            "type": "string"
        },
        "password": {
            "description": "Password for auth",
            "type": "string"
        }
    },
    "additionalProperties": False,
    "required": ["server_id", "protocol", "host", "port"]
}

SERVER_OBJECT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to a GNS3 server object instance",
    "type": "object",
    "properties": {
        "server_id": {
            "description": "Server identifier",
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
            "description": "User for auth",
            "type": "string"
        },
        "connected": {
            "description": "True if controller is connected to the server",
            "type": "boolean"
        },
        "version": {
            "description": "Version of the GNS3 remote server",
            "type": ["string", "null"]
        }
    },
    "additionalProperties": False,
    "required": ["server_id", "protocol", "host", "port"]
}
