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


ETHERNET_SWITCH_TEMPLATE_PROPERTIES = {
    "ports_mapping": {
        "type": "array",
        "default": [{"ethertype": "",
                     "name": "Ethernet0",
                     "vlan": 1,
                     "type": "access",
                     "port_number": 0
                     },
                    {"ethertype": "",
                     "name": "Ethernet1",
                     "vlan": 1,
                     "type": "access",
                     "port_number": 1
                     },
                    {"ethertype": "",
                     "name": "Ethernet2",
                     "vlan": 1,
                     "type": "access",
                     "port_number": 2
                     },
                    {"ethertype": "",
                     "name": "Ethernet3",
                     "vlan": 1,
                     "type": "access",
                     "port_number": 3
                     },
                    {"ethertype": "",
                     "name": "Ethernet4",
                     "vlan": 1,
                     "type": "access",
                     "port_number": 4
                     },
                    {"ethertype": "",
                     "name": "Ethernet5",
                     "vlan": 1,
                     "type": "access",
                     "port_number": 5
                     },
                    {"ethertype": "",
                     "name": "Ethernet6",
                     "vlan": 1,
                     "type": "access",
                     "port_number": 6
                     },
                    {"ethertype": "",
                     "name": "Ethernet7",
                     "vlan": 1,
                     "type": "access",
                     "port_number": 7
                     }
                    ],
        "items": [
            {"type": "object",
             "oneOf": [
                 {
                     "description": "Ethernet port",
                     "properties": {
                         "name": {
                             "description": "Port name",
                             "type": "string",
                             "minLength": 1
                         },
                         "port_number": {
                             "description": "Port number",
                             "type": "integer",
                             "minimum": 0
                         },
                         "type": {
                             "description": "Port type",
                             "enum": ["access", "dot1q", "qinq"],
                         },
                         "vlan": {"description": "VLAN number",
                                  "type": "integer",
                                  "minimum": 1
                                  },
                         "ethertype": {
                             "description": "QinQ Ethertype",
                             "enum": ["", "0x8100", "0x88A8", "0x9100", "0x9200"],
                         },
                     },
                     "required": ["name", "port_number", "type"],
                     "additionalProperties": False
                 },
             ]},
        ]
    },
    "console_type": {
        "description": "Console type",
        "enum": ["telnet", "none"],
        "default": "none"
    },
}

ETHERNET_SWITCH_TEMPLATE_PROPERTIES.update(copy.deepcopy(BASE_TEMPLATE_PROPERTIES))
ETHERNET_SWITCH_TEMPLATE_PROPERTIES["category"]["default"] = "switch"
ETHERNET_SWITCH_TEMPLATE_PROPERTIES["default_name_format"]["default"] = "Switch{0}"
ETHERNET_SWITCH_TEMPLATE_PROPERTIES["symbol"]["default"] = ":/symbols/ethernet_switch.svg"

ETHERNET_SWITCH_TEMPLATE_OBJECT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "An Ethernet switch template object",
    "type": "object",
    "properties": ETHERNET_SWITCH_TEMPLATE_PROPERTIES,
    "additionalProperties": False
}
