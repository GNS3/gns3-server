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

import uuid
import asyncio


class Link:

    def __init__(self):
        self._id = str(uuid.uuid4())
        self._vms = []

    @asyncio.coroutine
    def addVM(self, vm, adapter_number, port_number):
        """
        Add a VM to the link
        """
        self._vms.append({
            "vm": vm,
            "adapter_number": adapter_number,
            "port_number": port_number
        })

    @property
    def id(self):
        return self._id

    def __json__(self):
        res = []
        for side in self._vms:
            res.append({
                "vm_id": side["vm"].id,
                "adapter_number": side["adapter_number"],
                "port_number": side["port_number"]
            })
        return {"vms": res, "link_id": self._id}
