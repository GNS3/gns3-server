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

ID_TO_CATEGORY = {
    3: "firewall",
    2: "guest",
    1: "switch",
    0: "router"
}


class Appliance:

    def __init__(self, appliance_id, settings, builtin=False):

        if appliance_id is None:
            self._id = str(uuid.uuid4())
        elif isinstance(appliance_id, uuid.UUID):
            self._id = str(appliance_id)
        else:
            self._id = appliance_id

        self._settings = copy.deepcopy(settings)

        # Version of the gui before 2.1 use linked_base
        # and the server linked_clone
        if "linked_base" in self.settings:
            linked_base = self._settings.pop("linked_base")
            if "linked_clone" not in self._settings:
                self._settings["linked_clone"] = linked_base

        # Convert old GUI category to text category
        try:
            self._settings["category"] = ID_TO_CATEGORY[self._settings["category"]]
        except KeyError:
            pass

        # The "server" setting has been replaced by "compute_id" setting in version 2.2
        if "server" in self._settings:
            self._settings["compute_id"] = self._settings.pop("server")

        # The "node_type" setting has been replaced by "appliance_type" setting in version 2.2
        if "node_type" in self._settings:
            self._settings["appliance_type"] = self._settings.pop("node_type")

        # Remove an old IOU setting
        if self._settings["appliance_type"] == "iou" and "image" in self._settings:
            del self._settings["image"]

        self._builtin = builtin

    @property
    def id(self):
        return self._id

    @property
    def settings(self):
        return self._settings

    @settings.setter
    def settings(self, settings):
        self._settings.update(settings)

    @property
    def name(self):
        return self._settings["name"]

    @property
    def compute_id(self):
        return self._settings["compute_id"]

    @property
    def appliance_type(self):
        return self._settings["appliance_type"]

    @property
    def builtin(self):
        return self._builtin

    def update(self, **kwargs):
        self._settings.update(kwargs)

    def __json__(self):
        """
        Appliance settings.
        """

        settings = self._settings
        settings.update({"appliance_id": self._id,
                         "default_name_format": settings.get("default_name_format", "{name}-{0}"),
                         "symbol": settings.get("symbol", ":/symbols/computer.svg"),
                         "builtin": self.builtin})

        if not self.builtin:
            settings["compute_id"] = self.compute_id

        return settings
