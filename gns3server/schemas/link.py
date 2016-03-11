#!/usr/bin/env python
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


LINK_OBJECT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "A link object",
    "type": "object",
    "properties": {
        "link_id": {
            "description": "Link identifier",
            "type": "string",
            "minLength": 36,
            "maxLength": 36,
            "pattern": "^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$"
        },
        "vms": {
            "description": "List of the VMS",
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "vm_id": {
                        "description": "VM identifier",
                        "type": "string",
                        "minLength": 36,
                        "maxLength": 36,
                        "pattern": "^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$"
                    },
                    "adapter_number": {
                        "description": "Adapter number",
                        "type": "integer"
                    },
                    "port_number": {
                        "description": "Port number",
                        "type": "integer"
                    }
                },
                "required": ["vm_id", "adapter_number", "port_number"],
                "additionalProperties": False
            }
        }
    },
    "required": ["vms"],
    "additionalProperties": False
}
