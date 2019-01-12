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
from .dynamips_vm import DYNAMIPS_ADAPTERS, DYNAMIPS_WICS


DYNAMIPS_TEMPLATE_PROPERTIES = {
    "platform": {
        "description": "Platform type",
        "enum": ["c7200", "c3745", "c3725", "c3600", "c2691", "c2600", "c1700"]
    },
    "image": {
        "description": "Path to the IOS image",
        "type": "string",
        "minLength": 1
    },
    "usage": {
        "description": "How to use the Dynamips VM",
        "type": "string",
        "default": ""
    },
    "mmap": {
        "description": "MMAP feature",
        "type": "boolean",
        "default": True
    },
    "exec_area": {
        "description": "Exec area value",
        "type": "integer",
        "default": 64
    },
    "mac_addr": {
        "description": "Base MAC address",
        "type": "string",
        "anyOf": [
            {"pattern": "^([0-9a-fA-F]{4}\\.){2}[0-9a-fA-F]{4}$"},
            {"pattern": "^$"}
        ],
        "default": ""
    },
    "system_id": {
        "description": "System ID",
        "type": "string",
        "minLength": 1,
        "default": "FTX0945W0MY"
    },
    "startup_config": {
        "description": "IOS startup configuration file",
        "type": "string",
        "default": "ios_base_startup-config.txt"
    },
    "private_config": {
        "description": "IOS private configuration file",
        "type": "string",
        "default": ""
    },
    "idlepc": {
        "description": "Idle-PC value",
        "type": "string",
        "pattern": "^(0x[0-9a-fA-F]+)?$",
        "default": ""
    },
    "idlemax": {
        "description": "Idlemax value",
        "type": "integer",
        "default": 500
    },
    "idlesleep": {
        "description": "Idlesleep value",
        "type": "integer",
        "default": 30
    },
    "disk0": {
        "description": "Disk0 size in MB",
        "type": "integer",
        "default": 0
    },
    "disk1": {
        "description": "Disk1 size in MB",
        "type": "integer",
        "default": 0
    },
    "auto_delete_disks": {
        "description": "Automatically delete nvram and disk files",
        "type": "boolean",
        "default": False
    },
    "wic0": DYNAMIPS_WICS,
    "wic1": DYNAMIPS_WICS,
    "wic2": DYNAMIPS_WICS,
    "slot0": DYNAMIPS_ADAPTERS,
    "slot1": DYNAMIPS_ADAPTERS,
    "slot2": DYNAMIPS_ADAPTERS,
    "slot3": DYNAMIPS_ADAPTERS,
    "slot4": DYNAMIPS_ADAPTERS,
    "slot5": DYNAMIPS_ADAPTERS,
    "slot6": DYNAMIPS_ADAPTERS,
    "console_type": {
        "description": "Console type",
        "enum": ["telnet", "none"],
        "default": "telnet"
    },
    "console_auto_start": {
        "description": "Automatically start the console when the node has started",
        "type": "boolean",
        "default": False
    }
}

DYNAMIPS_TEMPLATE_PROPERTIES.update(copy.deepcopy(BASE_TEMPLATE_PROPERTIES))
DYNAMIPS_TEMPLATE_PROPERTIES["category"]["default"] = "router"
DYNAMIPS_TEMPLATE_PROPERTIES["default_name_format"]["default"] = "R{0}"
DYNAMIPS_TEMPLATE_PROPERTIES["symbol"]["default"] = ":/symbols/router.svg"

DYNAMIPS_TEMPLATE_OBJECT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "A Dynamips template object",
    "type": "object",
    "properties": DYNAMIPS_TEMPLATE_PROPERTIES,
    "required": ["platform", "image"],
}

C7200_DYNAMIPS_TEMPLATE_PROPERTIES = {
    "ram": {
        "description": "Amount of RAM in MB",
        "type": "integer",
        "default": 512
    },
    "nvram": {
        "description": "Amount of NVRAM in KB",
        "type": "integer",
        "default": 512
    },
    "npe": {
        "description": "NPE model",
        "enum": ["npe-100", "npe-150", "npe-175", "npe-200", "npe-225", "npe-300", "npe-400", "npe-g2"],
        "default": "npe-400"
    },
    "midplane": {
        "description": "Midplane model",
        "enum": ["std", "vxr"],
        "default": "vxr"
    },
    "sparsemem": {
        "description": "Sparse memory feature",
        "type": "boolean",
        "default": True
    }
}

C7200_DYNAMIPS_TEMPLATE_PROPERTIES.update(DYNAMIPS_TEMPLATE_PROPERTIES)

C7200_DYNAMIPS_TEMPLATE_OBJECT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "A c7200 Dynamips template object",
    "type": "object",
    "properties": C7200_DYNAMIPS_TEMPLATE_PROPERTIES,
    "additionalProperties": False
}

C3745_DYNAMIPS_TEMPLATE_PROPERTIES = {
    "ram": {
        "description": "Amount of RAM in MB",
        "type": "integer",
        "default": 256
    },
    "nvram": {
        "description": "Amount of NVRAM in KB",
        "type": "integer",
        "default": 256
    },
    "iomem": {
        "description": "I/O memory percentage",
        "type": "integer",
        "minimum": 0,
        "maximum": 100,
        "default": 5
    },
    "sparsemem": {
        "description": "Sparse memory feature",
        "type": "boolean",
        "default": True
    }
}

C3745_DYNAMIPS_TEMPLATE_PROPERTIES.update(DYNAMIPS_TEMPLATE_PROPERTIES)

C3745_DYNAMIPS_TEMPLATE_OBJECT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "A c3745 Dynamips template object",
    "type": "object",
    "properties": C3745_DYNAMIPS_TEMPLATE_PROPERTIES,
    "additionalProperties": False
}

C3725_DYNAMIPS_TEMPLATE_PROPERTIES = {
    "ram": {
        "description": "Amount of RAM in MB",
        "type": "integer",
        "default": 128
    },
    "nvram": {
        "description": "Amount of NVRAM in KB",
        "type": "integer",
        "default": 256
    },
    "iomem": {
        "description": "I/O memory percentage",
        "type": "integer",
        "minimum": 0,
        "maximum": 100,
        "default": 5
    },
    "sparsemem": {
        "description": "Sparse memory feature",
        "type": "boolean",
        "default": True
    }
}

C3725_DYNAMIPS_TEMPLATE_PROPERTIES.update(DYNAMIPS_TEMPLATE_PROPERTIES)

C3725_DYNAMIPS_TEMPLATE_OBJECT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "A c3725 Dynamips template object",
    "type": "object",
    "properties": C3725_DYNAMIPS_TEMPLATE_PROPERTIES,
    "additionalProperties": False
}

C3600_DYNAMIPS_TEMPLATE_PROPERTIES = {
    "chassis": {
        "description": "Chassis type",
        "enum": ["3620", "3640", "3660"],
        "default": "3660"
    },
    "ram": {
        "description": "Amount of RAM in MB",
        "type": "integer",
        "default": 192
    },
    "nvram": {
        "description": "Amount of NVRAM in KB",
        "type": "integer",
        "default": 128
    },

    "iomem": {
        "description": "I/O memory percentage",
        "type": "integer",
        "minimum": 0,
        "maximum": 100,
        "default": 5
    },
    "sparsemem": {
        "description": "Sparse memory feature",
        "type": "boolean",
        "default": True
    }
}

C3600_DYNAMIPS_TEMPLATE_PROPERTIES.update(DYNAMIPS_TEMPLATE_PROPERTIES)

C3600_DYNAMIPS_TEMPLATE_OBJECT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "A c3600 Dynamips template object",
    "type": "object",
    "properties": C3600_DYNAMIPS_TEMPLATE_PROPERTIES,
    "required": ["chassis"],
    "additionalProperties": False
}

C2691_DYNAMIPS_TEMPLATE_PROPERTIES = {
    "ram": {
        "description": "Amount of RAM in MB",
        "type": "integer",
        "default": 192
    },
    "nvram": {
        "description": "Amount of NVRAM in KB",
        "type": "integer",
        "default": 256
    },
    "iomem": {
        "description": "I/O memory percentage",
        "type": "integer",
        "minimum": 0,
        "maximum": 100,
        "default": 5
    },
    "sparsemem": {
        "description": "Sparse memory feature",
        "type": "boolean",
        "default": True
    }
}

C2691_DYNAMIPS_TEMPLATE_PROPERTIES.update(DYNAMIPS_TEMPLATE_PROPERTIES)

C2691_DYNAMIPS_TEMPLATE_OBJECT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "A c2691 Dynamips template object",
    "type": "object",
    "properties": C2691_DYNAMIPS_TEMPLATE_PROPERTIES,
    "additionalProperties": False
}

C2600_DYNAMIPS_TEMPLATE_PROPERTIES = {
    "chassis": {
        "description": "Chassis type",
        "enum": ["2610", "2620", "2610XM", "2620XM", "2650XM", "2621", "2611XM", "2621XM", "2651XM"],
        "default": "2651XM"
    },
    "ram": {
        "description": "Amount of RAM in MB",
        "type": "integer",
        "default": 160
    },
    "nvram": {
        "description": "Amount of NVRAM in KB",
        "type": "integer",
        "default": 128
    },
    "iomem": {
        "description": "I/O memory percentage",
        "type": "integer",
        "minimum": 0,
        "maximum": 100,
        "default": 15
    },
    "sparsemem": {
        "description": "Sparse memory feature",
        "type": "boolean",
        "default": True
    }
}

C2600_DYNAMIPS_TEMPLATE_PROPERTIES.update(DYNAMIPS_TEMPLATE_PROPERTIES)

C2600_DYNAMIPS_TEMPLATE_OBJECT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "A c2600 Dynamips template object",
    "type": "object",
    "properties": C2600_DYNAMIPS_TEMPLATE_PROPERTIES,
    "required": ["chassis"],
    "additionalProperties": False
}

C1700_DYNAMIPS_TEMPLATE_PROPERTIES = {
    "chassis": {
        "description": "Chassis type",
        "enum": ["1720", "1721", "1750", "1751", "1760"],
        "default": "1760"
    },
    "ram": {
        "description": "Amount of RAM in MB",
        "type": "integer",
        "default": 160
    },
    "nvram": {
        "description": "Amount of NVRAM in KB",
        "type": "integer",
        "default": 128
    },
    "iomem": {
        "description": "I/O memory percentage",
        "type": "integer",
        "minimum": 0,
        "maximum": 100,
        "default": 15
    },
    "sparsemem": {
        "description": "Sparse memory feature",
        "type": "boolean",
        "default": False
    }
}

C1700_DYNAMIPS_TEMPLATE_PROPERTIES.update(DYNAMIPS_TEMPLATE_PROPERTIES)

C1700_DYNAMIPS_TEMPLATE_OBJECT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "A c1700 Dynamips template object",
    "type": "object",
    "properties": C1700_DYNAMIPS_TEMPLATE_PROPERTIES,
    "required": ["chassis"],
    "additionalProperties": False
}
