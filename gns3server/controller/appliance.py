#!/usr/bin/env python
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
import uuid


# Convert old GUI category to text category
ID_TO_CATEGORY = {
    3: "firewall",
    2: "guest",
    1: "switch",
    0: "router"
}


class Appliance:

    def __init__(self, appliance_id, data, builtin=False):
        if appliance_id is None:
            self._id = str(uuid.uuid4())
        elif isinstance(appliance_id, uuid.UUID):
            self._id = str(appliance_id)
        else:
            self._id = appliance_id
        self._data = data.copy()
        if "appliance_id" in self._data:
            del self._data["appliance_id"]

        # Version of the gui before 2.1 use linked_base
        # and the server linked_clone
        if "linked_base" in self._data:
            self._data["linked_clone"] = self._data.pop("linked_base")
        if data["node_type"] == "iou" and "image" in data:
            del self._data["image"]
        self._builtin = builtin

    @property
    def id(self):
        return self._id

    @property
    def data(self):
        return copy.deepcopy(self._data)

    @property
    def name(self):
        return self._data["name"]

    @property
    def compute_id(self):
        return self._data.get("server")

    @property
    def builtin(self):
        return self._builtin

    def __json__(self):
        """
        Appliance data (a hash)
        """
        try:
            category = ID_TO_CATEGORY[self._data["category"]]
        except KeyError:
            category = self._data["category"]

        return {
            "appliance_id": self._id,
            "node_type": self._data["node_type"],
            "name": self._data["name"],
            "default_name_format": self._data.get("default_name_format", "{name}-{0}"),
            "category": category,
            "symbol": self._data.get("symbol", ":/symbols/computer.svg"),
            "compute_id": self.compute_id,
            "builtin": self._builtin,
            "platform": self._data.get("platform", None)
        }
