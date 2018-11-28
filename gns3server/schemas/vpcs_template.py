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


VPCS_TEMPLATE_PROPERTIES = {
    "base_script_file": {
        "description": "Script file",
        "type": "string",
        "minLength": 1,
        "default": "vpcs_base_config.txt"
    },
    "console_type": {
        "description": "Console type",
        "enum": ["telnet", "none"],
        "default": "telnet"
    },
    "console_auto_start": {
        "description": "Automatically start the console when the node has started",
        "type": "boolean",
        "default": False
    },
}

VPCS_TEMPLATE_PROPERTIES.update(copy.deepcopy(BASE_TEMPLATE_PROPERTIES))
VPCS_TEMPLATE_PROPERTIES["category"]["default"] = "guest"
VPCS_TEMPLATE_PROPERTIES["default_name_format"]["default"] = "PC{0}"
VPCS_TEMPLATE_PROPERTIES["symbol"]["default"] = ":/symbols/vpcs_guest.svg"

VPCS_TEMPLATE_OBJECT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "A VPCS template object",
    "type": "object",
    "properties": VPCS_TEMPLATE_PROPERTIES,
    "additionalProperties": False
}
