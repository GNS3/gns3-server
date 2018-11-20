#!/usr/bin/env python
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

CUSTOM_ADAPTERS_ARRAY_SCHEMA = {
    "type": "array",
    "default": [],
    "items": {
        "type": "object",
        "description": "Custom properties",
        "properties": {
            "adapter_number": {
                "type": "integer",
                "description": "Adapter number"
            },
            "port_name": {
                "type": "string",
                "description": "Custom port name",
                "minLength": 1,
            },
            "adapter_type": {
                "type": "string",
                "description": "Custom adapter type",
                "minLength": 1,
            },
            "mac_address": {
                "description": "Custom MAC address",
                "type": "string",
                "minLength": 1,
                "pattern": "^([0-9a-fA-F]{2}[:]){5}([0-9a-fA-F]{2})$"
            },
        },
        "additionalProperties": False,
        "required": ["adapter_number"]
    },
}
