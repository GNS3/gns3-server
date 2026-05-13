#!/usr/bin/env python
#
# Copyright (C) 2026 GNS3 Technologies Inc.
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

"""
Shared node type constants used across the controller.
"""

# Node types that are always running (builtin/virtual switch nodes).
# These nodes do not require explicit start/stop and have limited feature support.
BUILTIN_NODE_TYPES = frozenset({
    "cloud",
    "nat",
    "ethernet_switch",
    "ethernet_hub",
    "frame_relay_switch",
    "atm_switch",
})