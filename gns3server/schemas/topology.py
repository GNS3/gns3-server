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

#
# This file contains the validation for checking a .gns3 file
#

from gns3server.schemas.compute import COMPUTE_OBJECT_SCHEMA
from gns3server.schemas.drawing import DRAWING_OBJECT_SCHEMA
from gns3server.schemas.link import LINK_OBJECT_SCHEMA
from gns3server.schemas.node import NODE_OBJECT_SCHEMA
from gns3server.schemas.project import VARIABLES_OBJECT_SCHEMA
from gns3server.schemas.project import SUPPLIER_OBJECT_SCHEMA


TOPOLOGY_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "The topology",
    "type": "object",
    "properties": {
        "project_id": {
            "description": "Project UUID",
            "type": "string",
            "minLength": 36,
            "maxLength": 36,
            "pattern": "^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$"
        },
        "type": {
            "description": "Type of file. It's always topology",
            "enum": ["topology"]
        },
        "auto_start": {
            "description": "Start the topology when opened",
            "type": "boolean"
        },
        "auto_close": {
            "description": "Close the topology when no client is connected",
            "type": "boolean"
        },
        "auto_open": {
            "description": "Open the topology with GNS3",
            "type": "boolean"
        },
        "revision": {
            "description": "Version of the .gns3 specification.",
            "type": "integer"
        },
        "version": {
            "description": "Version of the GNS3 software which have update the file for the last time",
            "type": "string"
        },
        "name": {
            "type": "string",
            "description": "Name of the project"
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
        "variables": VARIABLES_OBJECT_SCHEMA,
        "topology": {
            "description": "The topology content",
            "type": "object",
            "properties": {
                "computes": {
                    "description": "Computes servers",
                    "type": "array",
                    "items": COMPUTE_OBJECT_SCHEMA
                },
                "drawings": {
                    "description": "Drawings elements",
                    "type": "array",
                    "items": DRAWING_OBJECT_SCHEMA
                },
                "links": {
                    "description": "Link elements",
                    "type": "array",
                    "items": LINK_OBJECT_SCHEMA
                },
                "nodes": {
                    "description": "Nodes elements",
                    "type": "array",
                    "items": NODE_OBJECT_SCHEMA
                }
            },
            "required": ["nodes", "links", "drawings", "computes"],
            "additionalProperties": False
        }
    },
    "required": [
        "project_id", "type", "revision", "version", "name", "topology"
    ],
    "additionalProperties": False
}


def main():
    import jsonschema
    import json
    import sys

    with open(sys.argv[1]) as f:
        data = json.load(f)
        jsonschema.validate(data, TOPOLOGY_SCHEMA)


if __name__ == '__main__':
    main()
