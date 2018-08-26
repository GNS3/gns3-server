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
import html
import asyncio
import aiohttp

from gns3server.utils.asyncio import asyncio_ensure_future

import logging
log = logging.getLogger(__name__)


FILTERS = [
    {
        "type": "frequency_drop",
        "name": "Frequency drop",
        "description": "It will drop everything with a -1 frequency, drop every Nth packet with a positive frequency, or drop nothing",
        "parameters": [
            {
                "name": "Frequency",
                "minimum": -1,
                "maximum": 32767,
                "type": "int",
                "unit": "th packet"
            }
        ]
    },
    {
        "type": "packet_loss",
        "name": "Packet loss",
        "description": "The percentage represents the chance for a packet to be lost",
        "parameters": [
            {
                "name": "Chance",
                "minimum": 0,
                "maximum": 100,
                "type": "int",
                "unit": "%"
            }
        ]
    },
    {
        "type": "delay",
        "name": "Delay",
        "description": "Delay packets in milliseconds. You can add jitter in milliseconds (+/-) of the delay",
        "parameters": [
            {
                "name": "Latency",
                "minimum": 0,
                "maximum": 32767,
                "unit": "ms",
                "type": "int"
            },
            {
                "name": "Jitter (-/+)",
                "minimum": 0,
                "maximum": 32767,
                "unit": "ms",
                "type": "int"
            }
        ]
    },
    {
        "type": "corrupt",
        "name": "Corrupt",
        "description": "The percentage represents the chance for a packet to be corrupted",
        "parameters": [
            {
                "name": "Chance",
                "minimum": 0,
                "maximum": 100,
                "unit": "%",
                "type": "int"
            }
        ]
    },
    {
        "type": "bpf",
        "name": "Berkeley Packet Filter (BPF)",
        "description": "This filter will drop any packet matching a BPF expression. Put one expression per line",
        "parameters": [
            {
                "name": "Filters",
                "type": "text"
            }
        ]
    }
]


class Link:
    """
    Base class for links.
    """

    def __init__(self, project, link_id=None):

        if link_id:
            self._id = link_id
        else:
            self._id = str(uuid.uuid4())
        self._nodes = []
        self._project = project
        self._capturing = False
        self._capture_file_name = None
        self._streaming_pcap = None
        self._created = False
        self._link_type = "ethernet"
        self._suspend = False
        self._filters = {}

    @property
    def filters(self):
        """
        Get an array of filters
        """
        return self._filters

    @property
    def nodes(self):
        """
        Get the current nodes attached to this link
        """
        return self._nodes

    def get_active_filters(self):
        """
        Return the active filters.
        Filters are overridden if the link is suspended.
        """
        if self._suspend:
            return {"frequency_drop": [-1]}
        return self._filters

    @asyncio.coroutine
    def update_filters(self, filters):
        """
        Modify the filters list.

        Filter with value 0 will be dropped because not active
        """
        new_filters = {}
        for (filter, values) in filters.items():
            new_values = []
            for value in values:
                if isinstance(value, str):
                    new_values.append(value.strip("\n "))
                else:
                    new_values.append(int(value))
            values = new_values
            if len(values) != 0 and values[0] != 0 and values[0] != '':
                new_filters[filter] = values

        if new_filters != self.filters:
            self._filters = new_filters
            if self._created:
                yield from self.update()
                self._project.controller.notification.emit("link.updated", self.__json__())
                self._project.dump()

    @asyncio.coroutine
    def update_suspend(self, value):
        if value != self._suspend:
            self._suspend = value
            yield from self.update()
            self._project.controller.notification.emit("link.updated", self.__json__())
            self._project.dump()

    @property
    def created(self):
        """
        :returns: True the link has been created on the computes
        """
        return self._created

    @asyncio.coroutine
    def add_node(self, node, adapter_number, port_number, label=None, dump=True):
        """
        Add a node to the link

        :param dump: Dump project on disk
        """

        port = node.get_port(adapter_number, port_number)
        if port is None:
            raise aiohttp.web.HTTPNotFound(text="Port {}/{} for {} not found".format(adapter_number, port_number, node.name))
        if port.link is not None:
            raise aiohttp.web.HTTPConflict(text="Port is already used")

        self._link_type = port.link_type

        for other_node in self._nodes:
            if other_node["node"] == node:
                raise aiohttp.web.HTTPConflict(text="Cannot connect to itself")

            if node.node_type in ["nat", "cloud"]:
                if other_node["node"].node_type in ["nat", "cloud"]:
                    raise aiohttp.web.HTTPConflict(text="It's not allowed to connect a {} to a {}".format(other_node["node"].node_type, node.node_type))

            # Check if user is not connecting serial => ethernet
            other_port = other_node["node"].get_port(other_node["adapter_number"], other_node["port_number"])
            if other_port is None:
                raise aiohttp.web.HTTPNotFound(text="Port {}/{} for {} not found".format(other_node["adapter_number"], other_node["port_number"], other_node["node"].name))
            if port.link_type != other_port.link_type:
                raise aiohttp.web.HTTPConflict(text="It's not allowed to connect a {} to a {}".format(other_port.link_type, port.link_type))

        if label is None:
            label = {
                "x": -10,
                "y": -10,
                "rotation": 0,
                "text": html.escape("{}/{}".format(adapter_number, port_number)),
                "style": "font-size: 10; font-style: Verdana"
            }

        self._nodes.append({
            "node": node,
            "adapter_number": adapter_number,
            "port_number": port_number,
            "port": port,
            "label": label
        })

        if len(self._nodes) == 2:
            yield from self.create()
            for n in self._nodes:
                n["node"].add_link(self)
                n["port"].link = self
            self._created = True
            self._project.controller.notification.emit("link.created", self.__json__())

        if dump:
            self._project.dump()

    @asyncio.coroutine
    def update_nodes(self, nodes):
        for node_data in nodes:
            node = self._project.get_node(node_data["node_id"])
            for port in self._nodes:
                if port["node"] == node:
                    label = node_data.get("label")
                    if label:
                        port["label"] = label
        self._project.controller.notification.emit("link.updated", self.__json__())
        self._project.dump()

    @asyncio.coroutine
    def create(self):
        """
        Create the link
        """

        raise NotImplementedError

    @asyncio.coroutine
    def update(self):
        """
        Update a link
        """
        raise NotImplementedError

    @asyncio.coroutine
    def delete(self):
        """
        Delete the link
        """
        for n in self._nodes:
            # It could be different of self if we rollback an already existing link
            if n["port"].link == self:
                n["port"].link = None
                n["node"].remove_link(self)

    @asyncio.coroutine
    def start_capture(self, data_link_type="DLT_EN10MB", capture_file_name=None):
        """
        Start capture on the link

        :returns: Capture object
        """

        self._capturing = True
        self._capture_file_name = capture_file_name
        self._streaming_pcap = asyncio_ensure_future(self._start_streaming_pcap())
        self._project.controller.notification.emit("link.updated", self.__json__())

    @asyncio.coroutine
    def _start_streaming_pcap(self):
        """
        Dump a pcap file on disk
        """

        if os.path.exists(self.capture_file_path):
            try:
                os.remove(self.capture_file_path)
            except OSError as e:
                raise aiohttp.web.HTTPConflict(text="Could not delete old capture file '{}': {}".format(self.capture_file_path, e))

        try:
            stream_content = yield from self.read_pcap_from_source()
        except aiohttp.web.HTTPException as e:
            error_msg = "Could not stream PCAP file: error {}: {}".format(e.status, e.text)
            log.error(error_msg)
            self._capturing = False
            self._project.notification.emit("log.error", {"message": error_msg})
            self._project.controller.notification.emit("link.updated", self.__json__())

        with stream_content as stream:
            try:
                with open(self.capture_file_path, "wb") as f:
                    while self._capturing:
                        # We read 1 bytes by 1 otherwise the remaining data is not read if the traffic stops
                        data = yield from stream.read(1)
                        if data:
                            f.write(data)
                            # Flush to disk otherwise the live is not really live
                            f.flush()
                        else:
                            break
            except OSError as e:
                raise aiohttp.web.HTTPConflict(text="Could not write capture file '{}': {}".format(self.capture_file_path, e))

    @asyncio.coroutine
    def stop_capture(self):
        """
        Stop capture on the link
        """

        self._capturing = False
        self._project.controller.notification.emit("link.updated", self.__json__())

    @asyncio.coroutine
    def _read_pcap_from_source(self):
        """
        Return a FileStream of the Pcap from the compute server
        """

        raise NotImplementedError

    @asyncio.coroutine
    def node_updated(self, node):
        """
        Called when a node member of the link is updated
        """
        raise NotImplementedError

    def default_capture_file_name(self):
        """
        :returns: File name for a capture on this link
        """

        capture_file_name = "{}_{}-{}_to_{}_{}-{}".format(self._nodes[0]["node"].name,
                                                          self._nodes[0]["adapter_number"],
                                                          self._nodes[0]["port_number"],
                                                          self._nodes[1]["node"].name,
                                                          self._nodes[1]["adapter_number"],
                                                          self._nodes[1]["port_number"])
        return re.sub("[^0-9A-Za-z_-]", "", capture_file_name) + ".pcap"

    @property
    def id(self):
        return self._id

    @property
    def nodes(self):
        return [node['node'] for node in self._nodes]

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

    def available_filters(self):
        """
        Return the list of filters compatible with this link

        :returns: Array of filters
        """
        filter_node = self._get_filter_node()
        if filter_node:
            return FILTERS
        return []

    def _get_filter_node(self):
        """
        Return the node where the filter will run

        :returns: None if no node support filtering else the node
        """
        for node in self._nodes:
            if node["node"].node_type in ('vpcs',
                                          'traceng',
                                          'vmware',
                                          'dynamips',
                                          'qemu',
                                          'iou',
                                          'cloud',
                                          'nat',
                                          'virtualbox',
                                          'docker'):
                return node["node"]
        return None

    def __eq__(self, other):
        if not isinstance(other, Link):
            return False
        return self.id == other.id

    def __hash__(self):
        return hash(self._id)

    def __json__(self, topology_dump=False):
        """
        :param topology_dump: Filter to keep only properties require for saving on disk
        """
        res = []
        for side in self._nodes:
            res.append({
                "node_id": side["node"].id,
                "adapter_number": side["adapter_number"],
                "port_number": side["port_number"],
                "label": side["label"]
            })
        if topology_dump:
            return {
                "nodes": res,
                "link_id": self._id,
                "filters": self._filters,
                "suspend": self._suspend
            }
        return {
            "nodes": res,
            "link_id": self._id,
            "project_id": self._project.id,
            "capturing": self._capturing,
            "capture_file_name": self._capture_file_name,
            "capture_file_path": self.capture_file_path,
            "link_type": self._link_type,
            "filters": self._filters,
            "suspend": self._suspend
        }
