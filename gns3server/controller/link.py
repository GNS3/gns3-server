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

import re
import uuid
import asyncio


class Link:

    def __init__(self, project, data_link_type="DLT_EN10MB"):
        self._id = str(uuid.uuid4())
        self._vms = []
        self._project = project
        self._data_link_type = data_link_type

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

    @asyncio.coroutine
    def create(self):
        """
        Create the link
        """
        raise NotImplementedError

    @asyncio.coroutine
    def delete(self):
        """
        Delete the link
        """
        raise NotImplementedError

    @asyncio.coroutine
    def start_capture(self):
        """
        Start capture on the link

        :returns: Capture object
        """
        raise NotImplementedError

    @asyncio.coroutine
    def stop_capture(self):
        """
        Stop capture on the link
        """
        raise NotImplementedError

    def capture_file_name(self):
        """
        :returns: File name for a capture on this link
        """
        capture_file_name = "{}_{}-{}_to_{}_{}-{}".format(
            self._vms[0]["vm"].name,
            self._vms[0]["adapter_number"],
            self._vms[0]["port_number"],
            self._vms[1]["vm"].name,
            self._vms[1]["adapter_number"],
            self._vms[1]["port_number"])
        return re.sub("[^0-9A-Za-z_-]", "", capture_file_name) + ".pcap"

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
        return {"vms": res, "link_id": self._id, "data_link_type": self._data_link_type}
