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

import os
import re
import uuid
import asyncio


import logging
log = logging.getLogger(__name__)


class Link:

    def __init__(self, project):
        self._id = str(uuid.uuid4())
        self._vms = []
        self._project = project
        self._capturing = False
        self._capture_file_name = None

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
    def start_capture(self, data_link_type="DLT_EN10MB", capture_file_name=None):
        """
        Start capture on the link

        :returns: Capture object
        """
        self._capturing = True
        self._capture_file_name = capture_file_name
        self._streaming_pcap = asyncio.async(self._start_streaming_pcap())

    @asyncio.coroutine
    def _start_streaming_pcap(self):
        """
        Dump the pcap file on disk
        """
        stream = yield from self.read_pcap_from_source()
        with open(self.capture_file_path, "wb+") as f:
            while self._capturing:
                # We read 1 bytes by 1 otherwise if the traffic stop the remaining data is not read
                # this is slow
                data = yield from stream.read(1)
                if data:
                    f.write(data)
                    # Flush to disk otherwise the live is not really live
                    f.flush()
                else:
                    break
            yield from stream.close()

    @asyncio.coroutine
    def stop_capture(self):
        """
        Stop capture on the link
        """
        self._capturing = False

    @asyncio.coroutine
    def read_pcap_from_source(self):
        """
        Return a FileStream of the Pcap from the compute node
        """
        raise NotImplementedError

    def default_capture_file_name(self):
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

    @property
    def capturing(self):
        return self._capturing

    @property
    def capture_file_path(self):
        """
        Get the path of the capture
        """
        if self._capture_file_name:
            return os.path.join(self._project.captures_directory, self._capture_file_name)
        else:
            return None

    def __json__(self):
        res = []
        for side in self._vms:
            res.append({
                "vm_id": side["vm"].id,
                "adapter_number": side["adapter_number"],
                "port_number": side["port_number"]
            })
        return {
            "vms": res, "link_id": self._id,
            "capturing": self._capturing,
            "capture_file_name": self._capture_file_name,
            "capture_file_path": self.capture_file_path
        }
