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


ETHERNET_HUB_TEMPLATE_PROPERTIES = {
    "ports_mapping": {
        "type": "array",
        "default": [{"port_number": 0,
                     "name": "Ethernet0"
                     },
                    {"port_number": 1,
                     "name": "Ethernet1"
                     },
                    {"port_number": 2,
                     "name": "Ethernet2"
                     },
                    {"port_number": 3,
                     "name": "Ethernet3"
                     },
                    {"port_number": 4,
                     "name": "Ethernet4"
                     },
                    {"port_number": 5,
                     "name": "Ethernet5"
                     },
                    {"port_number": 6,
                     "name": "Ethernet6"
                     },
                    {"port_number": 7,
                     "name": "Ethernet7"
                     }
        ],
        "items": [
            {"type": "object",
             "oneOf": [{"description": "Ethernet port",
                        "properties": {"name": {"description": "Port name",
                                                "type": "string",
                                                "minLength": 1},
                                       "port_number": {
                                           "description": "Port number",
                                           "type": "integer",
                                           "minimum": 0}
                                       },
                        "required": ["name", "port_number"],
                        "additionalProperties": False}
                       ],
             }
        ]
    }
}

ETHERNET_HUB_TEMPLATE_PROPERTIES.update(copy.deepcopy(BASE_TEMPLATE_PROPERTIES))
ETHERNET_HUB_TEMPLATE_PROPERTIES["category"]["default"] = "switch"
ETHERNET_HUB_TEMPLATE_PROPERTIES["default_name_format"]["default"] = "Hub{0}"
ETHERNET_HUB_TEMPLATE_PROPERTIES["symbol"]["default"] = ":/symbols/hub.svg"

ETHERNET_HUB_TEMPLATE_OBJECT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "An Ethernet hub template object",
    "type": "object",
    "properties": ETHERNET_HUB_TEMPLATE_PROPERTIES,
    "additionalProperties": False
}
