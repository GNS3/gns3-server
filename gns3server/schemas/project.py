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

import copy

SUPPLIER_OBJECT_SCHEMA = {
    "type": ["object", "null"],
    "description": "Supplier of the project",
    "properties": {
        "logo": {
            "type": "string",
            "description": "Path to the project supplier logo"
        },
        "url": {
            "type": "string",
            "description": "URL to the project supplier site"
        }
    }
}


VARIABLES_OBJECT_SCHEMA = {
    "type": ["array", "null"],
    "description": "Variables required to run the project",
    "items": {
        "properties": {
            "name": {
                "type": "string",
                "description": "Variable name",
                "minLength": 1
            },
            "value": {
                "type": "string",
                "description": "Variable value"
            }
        },
        "required": ["name"]
    }
}


PROJECT_CREATE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to create a new Project instance",
    "type": "object",
    "properties": {
        "name": {
            "description": "Project name",
            "type": ["string", "null"],
            "minLength": 1
        },
        "path": {
            "description": "Project directory",
            "type": ["string", "null"],
            "minLength": 1
        },
        "auto_close": {
            "description": "Project auto close",
            "type": "boolean"
        },
        "auto_open": {
            "description": "Project open when GNS3 start",
            "type": "boolean"
        },
        "auto_start": {
            "description": "Project start when opened",
            "type": "boolean"
        },
        "project_id": {
            "description": "Project UUID",
            "type": ["string", "null"],
            "minLength": 36,
            "maxLength": 36,
            "pattern": "^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$"
        },
        "scene_height": {
            "type": "integer",
            "description": "Height of the drawing area"
        },
        "scene_width": {
            "type": "integer",
            "description": "Width of the drawing area"
        },
        "zoom": {
            "type": "integer",
            "description": "Zoom of the drawing area"
        },
        "show_layers": {
            "type": "boolean",
            "description": "Show layers on the drawing area"
        },
        "snap_to_grid": {
            "type": "boolean",
            "description": "Snap to grid on the drawing area"
        },
        "show_grid": {
            "type": "boolean",
            "description": "Show the grid on the drawing area"
        },
        "grid_size": {
            "type": "integer",
            "description": "Grid size for the drawing area for nodes"
        },
        "drawing_grid_size": {
            "type": "integer",
            "description": "Grid size for the drawing area for drawings"
        },
        "show_interface_labels": {
            "type": "boolean",
            "description": "Show interface labels on the drawing area"
        },
        "supplier": SUPPLIER_OBJECT_SCHEMA,
        "variables": VARIABLES_OBJECT_SCHEMA
    },
    "additionalProperties": False,
    "required": ["name"]
}

# Create a project duplicate schema based on create schema and add "reset_mac_addresses" properties
PROJECT_DUPLICATE_SCHEMA = copy.deepcopy(PROJECT_CREATE_SCHEMA)
PROJECT_DUPLICATE_SCHEMA["description"] = "Request validation to duplicate a Project instance"
PROJECT_DUPLICATE_SCHEMA["properties"].update({"reset_mac_addresses": {"type": "boolean",
                                                                       "description": "Reset MAC addresses for this project"
                                                                      }})

PROJECT_UPDATE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to update a Project instance",
    "type": "object",
    "properties": {
        "name": {
            "description": "Project name",
            "type": ["string", "null"],
            "minLength": 1
        },
        "path": {
            "description": "Path of the project on the server (work only with --local)",
            "type": ["string", "null"]
        },
        "auto_close": {
            "description": "Project auto close when client cut off the notifications feed",
            "type": "boolean"
        },
        "auto_open": {
            "description": "Project open when GNS3 start",
            "type": "boolean"
        },
        "auto_start": {
            "description": "Project start when opened",
            "type": "boolean"
        },
        "scene_height": {
            "type": "integer",
            "description": "Height of the drawing area"
        },
        "scene_width": {
            "type": "integer",
            "description": "Width of the drawing area"
        },
        "zoom": {
            "type": "integer",
            "description": "Zoom of the drawing area"
        },
        "show_layers": {
            "type": "boolean",
            "description": "Show layers on the drawing area"
        },
        "snap_to_grid": {
            "type": "boolean",
            "description": "Snap to grid on the drawing area"
        },
        "show_grid": {
            "type": "boolean",
            "description": "Show the grid on the drawing area"
        },
        "grid_size": {
            "type": "integer",
            "description": "Grid size for the drawing area for nodes"
        },
        "drawing_grid_size": {
            "type": "integer",
            "description": "Grid size for the drawing area for drawings"
        },
        "show_interface_labels": {
            "type": "boolean",
            "description": "Show interface labels on the drawing area"
        },
        "supplier": SUPPLIER_OBJECT_SCHEMA,
        "variables": VARIABLES_OBJECT_SCHEMA
    },
    "additionalProperties": False,
}

PROJECT_OBJECT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Project instance",
    "type": "object",
    "properties": {
        "name": {
            "description": "Project name",
            "type": ["string", "null"],
            "minLength": 1
        },
        "project_id": {
            "description": "Project UUID",
            "type": "string",
            "minLength": 36,
            "maxLength": 36,
            "pattern": "^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$"
        },
        "path": {
            "description": "Project directory",
            "type": ["string", "null"],
            "minLength": 1
        },
        "filename": {
            "description": "Project filename",
            "type": ["string", "null"],
            "minLength": 1
        },
        "status": {
            "description": "Project status Read only",
            "enum": ["opened", "closed"]
        },
        "auto_close": {
            "description": "Project auto close when client cut off the notifications feed",
            "type": "boolean"
        },
        "auto_open": {
            "description": "Project open when GNS3 start",
            "type": "boolean"
        },
        "auto_start": {
            "description": "Project start when opened",
            "type": "boolean"
        },
        "scene_height": {
            "type": "integer",
            "description": "Height of the drawing area"
        },
        "scene_width": {
            "type": "integer",
            "description": "Width of the drawing area"
        },
        "zoom": {
            "type": "integer",
            "description": "Zoom of the drawing area"
        },
        "show_layers": {
            "type": "boolean",
            "description": "Show layers on the drawing area"
        },
        "snap_to_grid": {
            "type": "boolean",
            "description": "Snap to grid on the drawing area"
        },
        "show_grid": {
            "type": "boolean",
            "description": "Show the grid on the drawing area"
        },
        "grid_size": {
            "type": "integer",
            "description": "Grid size for the drawing area for nodes"
        },
        "drawing_grid_size": {
            "type": "integer",
            "description": "Grid size for the drawing area for drawings"
        },
        "show_interface_labels": {
            "type": "boolean",
            "description": "Show interface labels on the drawing area"
        },
        "supplier": SUPPLIER_OBJECT_SCHEMA,
        "variables": VARIABLES_OBJECT_SCHEMA
    },
    "additionalProperties": False,
    "required": ["project_id"]
}

PROJECT_LOAD_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Load a project",
    "type": "object",
    "properties": {
        "path": {
            "description": ".gns3 path",
            "type": "string",
            "minLength": 1
        }
    },
    "additionalProperties": False,
    "required": ["path"]
}

PROJECT_LIST_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "List of projects",
    "type": "array",
    "items": PROJECT_OBJECT_SCHEMA
}

PROJECT_FILE_LIST_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "List files in the project",
    "type": "array",
    "items": [
        {
            "type": "object",
            "properties": {
                "path": {
                    "description": "File path",
                    "type": ["string"]
                },
                "md5sum": {
                    "description": "MD5 hash of the file",
                    "type": ["string"]
                },

            },
        }
    ],
    "additionalProperties": False,
}
