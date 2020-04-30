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

import logging
log = logging.getLogger(__name__)


class Appliance:

    def __init__(self, appliance_id, data, builtin=True):
        if appliance_id is None:
            self._id = str(uuid.uuid4())
        elif isinstance(appliance_id, uuid.UUID):
            self._id = str(appliance_id)
        else:
            self._id = appliance_id
        self._data = data.copy()
        self._builtin = builtin
        if "appliance_id" in self._data:
            del self._data["appliance_id"]

        if self.status != 'broken':
            log.debug('Appliance "{name}" [{id}] loaded'.format(name=self.name, id=self._id))

    @property
    def id(self):
        return self._id

    @property
    def status(self):
        return self._data["status"]

    @property
    def symbol(self):
        return self._data.get("symbol")

    @property
    def name(self):
        return self._data.get("name")

    @symbol.setter
    def symbol(self, new_symbol):
        self._data["symbol"] = new_symbol

    def __json__(self):
        """
        Appliance data (a hash)
        """
        data = copy.deepcopy(self._data)
        data["builtin"] = self._builtin
        return data
