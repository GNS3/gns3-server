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

SERVER_STATISTICS_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type": "object",
    "required": ["memory_total",
                 "memory_free",
                 "memory_used",
                 "swap_total",
                 "swap_free",
                 "swap_used",
                 "cpu_usage_percent",
                 "memory_usage_percent",
                 "swap_usage_percent",
                 "disk_usage_percent",
                 "load_average_percent"],
    "additionalProperties": False,
    "properties": {
        "memory_total": {
            "description": "Total physical memory (exclusive swap) in bytes",
            "type": "integer",
        },
        "memory_free": {
            "description": "Free memory in bytes",
            "type": "integer",
        },
        "memory_used": {
            "description": "Memory used in bytes",
            "type": "integer",
        },
        "swap_total": {
            "description": "Total swap memory in bytes",
            "type": "integer",
        },
        "swap_free": {
            "description": "Free swap memory in bytes",
            "type": "integer",
        },
        "swap_used": {
            "description": "Swap memory used in bytes",
            "type": "integer",
        },
        "cpu_usage_percent": {
            "description": "CPU usage in percent",
            "type": "integer",
        },
        "memory_usage_percent": {
            "description": "Memory usage in percent",
            "type": "integer",
        },
        "swap_usage_percent": {
            "description": "Swap usage in percent",
            "type": "integer",
        },
        "disk_usage_percent": {
            "description": "Disk usage in percent",
            "type": "integer",
        },
        "load_average_percent": {
            "description": "Average system load over the last 1, 5 and 15 minutes",
            "type": "array",
            "items": [{"type": "integer"}],
            "minItems": 3,
            "maxItems": 3
        },
    }
}
