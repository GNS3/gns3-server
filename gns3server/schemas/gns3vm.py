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


GNS3VM_SETTINGS_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Settings of the GNS3VM",
    "type": "object",
    "properties": {
        "enable": {
            "type": "boolean",
            "description": "Enable the VM"
        },
        "vmname": {
            "type": "string",
            "description": "The name of the VM"
        },
        "when_exit": {
            "description": "What to do with the VM when GNS3 exit",
            "enum": ["stop", "suspend", "keep"]
        },
        "headless": {
            "type": "boolean",
            "description": "Start the VM GUI or not",
        },
        "engine": {
            "description": "The engine to use for the VM. Null to disable",
            "enum": ["vmware", "virtualbox", None]
        },
        "allocate_vcpus_ram": {
            "description": "Allocate vCPUS and RAM settings",
            "type": "boolean"
        },
        "vcpus": {
            "description": "Number of vCPUS affected to the VM",
            "type": "integer"
        },
        "ram": {
            "description": "Amount of ram affected to the VM",
            "type": "integer"
        },
        "port": {
            "description": "Server port",
            "type": "integer",
            "minimum": 1,
            "maximum": 65535
        }
    },
    "additionalProperties": False
}
