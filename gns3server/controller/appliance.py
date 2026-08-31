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
import logging

log = logging.getLogger(__name__)


class Appliance:

    def __init__(self, path, data, builtin=True):

        self._data = data.copy()
        self._id = self._data.get("appliance_id")
        self._path = path
        self._builtin = builtin
        if self.status != "broken":
            log.debug(f'Appliance "{self.name}" [{self._id}] loaded')

    @property
    def id(self):
        return self._id

    @property
    def path(self):
        return self._path

    @property
    def status(self):
        return self._data["status"]

    @property
    def registry_version(self):
        return self._data.get("registry_version")

    @property
    def symbol(self):
        return self._data.get("symbol")

    @property
    def name(self):
        return self._data.get("name")

    @property
    def images(self):
        return self._data.get("images")

    @property
    def versions(self):
        return self._data.get("versions")

    @symbol.setter
    def symbol(self, new_symbol):
        self._data["symbol"] = new_symbol

    @property
    def type(self):

        if self._data.get("registry_version", 0) >= 8:
            # registry version 8: the node type comes from the settings template_type,
            # the default settings take precedence over the other sets
            settings_list = self._data.get("settings") or []
            for settings in settings_list:
                if settings.get("default"):
                    return settings.get("template_type", "qemu")
            if settings_list:
                return settings_list[0].get("template_type", "qemu")
            return "qemu"

        if "iou" in self._data:
            return "iou"
        elif "dynamips" in self._data:
            return "dynamips"
        elif "docker" in self._data:
            return "docker"
        else:
            return "qemu"

    def asdict(self):
        """
        Appliance data (a hash)
        """

        data = copy.deepcopy(self._data)
        data["builtin"] = self._builtin
        return data
