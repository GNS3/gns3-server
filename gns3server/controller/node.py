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

import aiohttp
import asyncio
import html
import copy
import uuid
import os


from .compute import ComputeConflict, ComputeError
from .ports.port_factory import PortFactory, StandardPortFactory, DynamipsPortFactory
from ..utils.images import images_directories
from ..utils.qt import qt_font_to_style


import logging
log = logging.getLogger(__name__)


class Node:
    # This properties are used only on controller and are not forwarded to the compute
    CONTROLLER_ONLY_PROPERTIES = ["x", "y", "z", "width", "height", "symbol", "label", "console_host",
                                  "port_name_format", "first_port_name", "port_segment_size", "ports"]

    def __init__(self, project, compute, name, node_id=None, node_type=None, **kwargs):
        """
        :param project: Project of the node
        :param compute: Compute server where the server will run
        :param name: Node name
        :param node_id: UUID of the node (integer)
        :param node_type: Type of emulator
        :param kwargs: Node properties
        """

        assert node_type

        if node_id is None:
            self._id = str(uuid.uuid4())
        else:
            self._id = node_id

        self._project = project
        self._compute = compute
        self._node_type = node_type

        self._label = None
        self._links = set()
        self._name = None
        self.name = name
        self._console = None
        self._console_type = None
        self._properties = {}
        self._command_line = None
        self._node_directory = None
        self._status = "stopped"
        self._x = 0
        self._y = 0
        self._z = 0
        self._ports = None
        self._symbol = None
        if node_type == "iou":
            self._port_name_format = "Ethernet{segment0}/{port0}"
            self._port_by_adapter = 4
            self.port_segment_size = 4
        else:
            self._port_name_format = "Ethernet{0}"
            self._port_by_adapter = 1
            self._port_segment_size = 0
        self._first_port_name = None

        # This properties will be recompute
        ignore_properties = ("width", "height")

        # Update node properties with additional elements
        for prop in kwargs:
            if prop not in ignore_properties:
                try:
                    setattr(self, prop, kwargs[prop])
                except AttributeError as e:
                    log.critical("Can't set attribute %s", prop)
                    raise e

        if self._symbol is None:
            self.symbol = ":/symbols/computer.svg"

    @property
    def id(self):
        return self._id

    @property
    def status(self):
        return self._status

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, new_name):
        self._name = self._project.update_node_name(self, new_name)
        # The text in label need to be always the node name
        if self.label and self._label["text"] != self._name:
            self._label["text"] = self._name
            self._label["x"] = None  # Center text

    @property
    def node_type(self):
        return self._node_type

    @property
    def console(self):
        return self._console

    @console.setter
    def console(self, val):
        self._console = val

    @property
    def console_type(self):
        return self._console_type

    @console_type.setter
    def console_type(self, val):
        self._console_type = val

    @property
    def properties(self):
        return self._properties

    @properties.setter
    def properties(self, val):
        self._properties = val

    @property
    def project(self):
        return self._project

    @property
    def compute(self):
        return self._compute

    @property
    def host(self):
        """
        :returns: Domain or ip for console connection
        """
        return self._compute.host

    @property
    def ports(self):
        if self._ports is None:
            self._list_ports()
        return self._ports

    @property
    def x(self):
        return self._x

    @x.setter
    def x(self, val):
        self._x = val

    @property
    def y(self):
        return self._y

    @y.setter
    def y(self, val):
        self._y = val

    @property
    def z(self):
        return self._z

    @z.setter
    def z(self, val):
        self._z = val

    @property
    def width(self):
        return self._width

    @property
    def height(self):
        return self._height

    @property
    def symbol(self):
        return self._symbol

    @symbol.setter
    def symbol(self, val):
        if val is None:
            val = ":/symbols/computer.svg"

        # No abs path, fix them (bug of 1.X)
        if not val.startswith(":") and os.path.abspath(val):
            val = os.path.basename(val)

        self._symbol = val
        try:
            self._width, self._height, filetype = self._project.controller.symbols.get_size(val)
        # If symbol is invalid we replace it by default
        except (ValueError, OSError):
            self.symbol = ":/symbols/computer.svg"
        if self._label is None:
            # Apply to label user style or default
            try:
                style = qt_font_to_style(
                    self._project.controller.settings["GraphicsView"]["default_label_font"],
                    self._project.controller.settings["GraphicsView"]["default_label_color"])
            except KeyError:
                style = "font-size: 10;font-familly: Verdana"

            self._label = {
                "y": round(self._height / 2 + 10) * -1,
                "text": html.escape(self._name),
                "style": style,
                "x": None,  # None: mean the client should center it
                "rotation": 0
            }

    @property
    def label(self):
        return self._label

    @label.setter
    def label(self, val):
        # The text in label need to be always the node name
        val["text"] = self._name
        self._label = val

    @property
    def port_name_format(self):
        return self._port_name_format

    @port_name_format.setter
    def port_name_format(self, val):
        self._port_name_format = val

    @property
    def port_segment_size(self):
        return self._port_segment_size

    @port_segment_size.setter
    def port_segment_size(self, val):
        self._port_segment_size = val

    @property
    def first_port_name(self):
        return self._first_port_name

    @first_port_name.setter
    def first_port_name(self, val):
        self._first_port_name = val

    def add_link(self, link):
        """
        A link is connected to the node
        """
        self._links.add(link)

    def remove_link(self, link):
        """
        A link is connected to the node
        """
        self._links.remove(link)

    @property
    def link(self):
        return self._links

    @asyncio.coroutine
    def create(self):
        """
        Create the node on the compute server
        """
        data = self._node_data()
        data["node_id"] = self._id
        if self._node_type == "docker":
            timeout = None
        else:
            timeout = 120
        trial = 0
        while trial != 6:
            try:
                response = yield from self._compute.post("/projects/{}/{}/nodes".format(self._project.id, self._node_type), data=data, timeout=timeout)
            except ComputeConflict as e:
                if e.response.get("exception") == "ImageMissingError":
                    res = yield from self._upload_missing_image(self._node_type, e.response["image"])
                    if not res:
                        raise e
                else:
                    raise e
            else:
                yield from self.parse_node_response(response.json)
                return True
            trial += 1

    @asyncio.coroutine
    def update(self, **kwargs):
        """
        Update the node on the compute server

        :param kwargs: Node properties
        """

        # When updating properties used only on controller we don't need to call the compute
        update_compute = False

        old_json = self.__json__()

        compute_properties = None
        # Update node properties with additional elements
        for prop in kwargs:
            if getattr(self, prop) != kwargs[prop]:
                if prop not in self.CONTROLLER_ONLY_PROPERTIES:
                    update_compute = True

                # We update properties on the compute and wait for the anwser from the compute node
                if prop == "properties":
                    compute_properties = kwargs[prop]
                else:
                    setattr(self, prop, kwargs[prop])

        self._list_ports()
        # We send notif only if object has changed
        if old_json != self.__json__():
            self.project.controller.notification.emit("node.updated", self.__json__())
        if update_compute:
            data = self._node_data(properties=compute_properties)
            response = yield from self.put(None, data=data)
            yield from self.parse_node_response(response.json)
        self.project.dump()

    @asyncio.coroutine
    def parse_node_response(self, response):
        """
        Update the object with the remote node object
        """
        for key, value in response.items():
            if key == "console":
                self._console = value
            elif key == "node_directory":
                self._node_directory = value
            elif key == "command_line":
                self._command_line = value
            elif key == "status":
                self._status = value
            elif key == "console_type":
                self._console_type = value
            elif key == "name":
                self.name = value
            elif key in ["node_id", "project_id", "console_host"]:
                pass
            else:
                self._properties[key] = value
        self._list_ports()
        for link in self._links:
            yield from link.node_updated(self)

    def _node_data(self, properties=None):
        """
        Prepare node data to send to the remote controller

        :param properties: If properties is None use actual property otherwise use the parameter
        """
        if properties:
            data = copy.copy(properties)
        else:
            data = copy.copy(self._properties)
        data["name"] = self._name
        if self._console:
            # console is optional for builtin nodes
            data["console"] = self._console
        if self._console_type:
            data["console_type"] = self._console_type

        # None properties are not be send. Because it can mean the emulator doesn't support it
        for key in list(data.keys()):
            if data[key] is None or data[key] is {} or key in self.CONTROLLER_ONLY_PROPERTIES:
                del data[key]
        return data

    @asyncio.coroutine
    def destroy(self):
        yield from self.delete()

    @asyncio.coroutine
    def start(self):
        """
        Start a node
        """
        try:
            # For IOU we need to send the licence everytime
            if self.node_type == "iou":
                try:
                    licence = self._project.controller.settings["IOU"]["iourc_content"]
                except KeyError:
                    raise aiohttp.web.HTTPConflict(text="IOU licence is not configured")
                yield from self.post("/start", timeout=240, data={"iourc_content": licence})
            else:
                yield from self.post("/start", timeout=240)
        except asyncio.TimeoutError:
            raise aiohttp.web.HTTPRequestTimeout(text="Timeout when starting {}".format(self._name))

    @asyncio.coroutine
    def stop(self):
        """
        Stop a node
        """
        try:
            yield from self.post("/stop", timeout=240, dont_connect=True)
        # We don't care if a node is down at this step
        except (ComputeError, aiohttp.errors.ClientHttpProcessingError, aiohttp.web.HTTPError):
            pass
        except asyncio.TimeoutError:
            raise aiohttp.web.HTTPRequestTimeout(text="Timeout when stopping {}".format(self._name))

    @asyncio.coroutine
    def suspend(self):
        """
        Suspend a node
        """
        try:
            yield from self.post("/suspend", timeout=240)
        except asyncio.TimeoutError:
            raise aiohttp.web.HTTPRequestTimeout(text="Timeout when reloading {}".format(self._name))

    @asyncio.coroutine
    def reload(self):
        """
        Suspend a node
        """
        try:
            yield from self.post("/reload", timeout=240)
        except asyncio.TimeoutError:
            raise aiohttp.web.HTTPRequestTimeout(text="Timeout when reloading {}".format(self._name))

    @asyncio.coroutine
    def post(self, path, data=None, **kwargs):
        """
        HTTP post on the node
        """
        if data:
            return (yield from self._compute.post("/projects/{}/{}/nodes/{}{}".format(self._project.id, self._node_type, self._id, path), data=data, **kwargs))
        else:
            return (yield from self._compute.post("/projects/{}/{}/nodes/{}{}".format(self._project.id, self._node_type, self._id, path), **kwargs))

    @asyncio.coroutine
    def put(self, path, data=None, **kwargs):
        """
        HTTP post on the node
        """
        if path is None:
            path = "/projects/{}/{}/nodes/{}".format(self._project.id, self._node_type, self._id)
        else:
            path = "/projects/{}/{}/nodes/{}{}".format(self._project.id, self._node_type, self._id, path)
        if data:
            return (yield from self._compute.put(path, data=data, **kwargs))
        else:
            return (yield from self._compute.put(path, **kwargs))

    @asyncio.coroutine
    def delete(self, path=None, **kwargs):
        """
        HTTP post on the node
        """
        if path is None:
            return (yield from self._compute.delete("/projects/{}/{}/nodes/{}".format(self._project.id, self._node_type, self._id), **kwargs))
        else:
            return (yield from self._compute.delete("/projects/{}/{}/nodes/{}{}".format(self._project.id, self._node_type, self._id, path), **kwargs))

    @asyncio.coroutine
    def _upload_missing_image(self, type, img):
        """
        Search an image on local computer and upload it to remote compute
        if the image exists
        """
        for directory in images_directories(type):
            image = os.path.join(directory, img)
            if os.path.exists(image):
                self.project.controller.notification.emit("log.info", {"message": "Uploading missing image {}".format(img)})
                with open(image, 'rb') as f:
                    yield from self._compute.post("/{}/images/{}".format(self._node_type, os.path.basename(img)), data=f, timeout=None)
                self.project.controller.notification.emit("log.info", {"message": "Upload finished for {}".format(img)})
                return True
        return False

    @asyncio.coroutine
    def dynamips_auto_idlepc(self):
        """
        Compute the idle PC for a dynamips node
        """
        return (yield from self._compute.get("/projects/{}/{}/nodes/{}/auto_idlepc".format(self._project.id, self._node_type, self._id), timeout=240)).json

    @asyncio.coroutine
    def dynamips_idlepc_proposals(self):
        """
        Compute a list of potential idle PC
        """
        return (yield from self._compute.get("/projects/{}/{}/nodes/{}/idlepc_proposals".format(self._project.id, self._node_type, self._id), timeout=240)).json

    def get_port(self, adapter_number, port_number):
        """
        Return the port for this adapter_number and port_number
        or raise an HTTPNotFound
        """
        for port in self.ports:
            if port.adapter_number == adapter_number and port.port_number == port_number:
                return port
        raise aiohttp.web.HTTPNotFound(text="Port {}/{} for {} not found".format(adapter_number, port_number, self.name))

    def _list_ports(self):
        """
        Generate the list of port display in the client
        if the compute has sent a list we return it (use by
        node where you can not personnalize the port naming).
        """
        self._ports = []
        # Some special cases
        if self._node_type == "atm_switch":
            atm_port = set()
            # Mapping is like {"1:0:100": "10:0:200"}
            for source, dest in self._properties["mappings"].items():
                atm_port.add(int(source.split(":")[0]))
                atm_port.add(int(dest.split(":")[0]))
            atm_port = sorted(atm_port)
            for port in atm_port:
                self._ports.append(PortFactory("{}".format(port), 0, 0, port, "atm"))
            return

        elif self._node_type == "frame_relay_switch":
            frame_relay_port = set()
            # Mapping is like {"1:101": "10:202"}
            for source, dest in self._properties["mappings"].items():
                frame_relay_port.add(int(source.split(":")[0]))
                frame_relay_port.add(int(dest.split(":")[0]))
            frame_relay_port = sorted(frame_relay_port)
            for port in frame_relay_port:
                self._ports.append(PortFactory("{}".format(port), 0, 0, port, "frame_relay"))
            return
        elif self._node_type == "dynamips":
            self._ports = DynamipsPortFactory(self._properties)
            return
        elif self._node_type == "docker":
            for adapter_number in range(0, self._properties["adapters"]):
                self._ports.append(PortFactory("eth{}".format(adapter_number), 0, adapter_number, 0, "ethernet", short_name="eth{}".format(adapter_number)))
        elif self._node_type in ("ethernet_switch", "ethernet_hub"):
            # Basic node we don't want to have adapter number
            port_number = 0
            for port in self._properties["ports_mapping"]:
                self._ports.append(PortFactory(port["name"], 0, 0, port_number, "ethernet", short_name="e{}".format(port_number)))
                port_number += 1
        elif self._node_type in ("vpcs"):
            self._ports.append(PortFactory("Ethernet0", 0, 0, 0, "ethernet", short_name="e0"))
        elif self._node_type in ("cloud", "nat"):
            port_number = 0
            for port in self._properties["ports_mapping"]:
                self._ports.append(PortFactory(port["name"], 0, 0, port_number, "ethernet", short_name=port["name"]))
                port_number += 1
        else:
            self._ports = StandardPortFactory(self._properties, self._port_by_adapter, self._first_port_name, self._port_name_format, self._port_segment_size)

    def __repr__(self):
        return "<gns3server.controller.Node {} {}>".format(self._node_type, self._name)

    def __eq__(self, other):
        if not isinstance(other, Node):
            return False
        return self.id == other.id and other.project.id == self.project.id

    def _filter_properties(self):
        """
        Some properties are private and should not be exposed
        """
        PRIVATE_PROPERTIES = ("iourc_content", )
        prop = copy.copy(self._properties)
        for k in list(prop.keys()):
            if k in PRIVATE_PROPERTIES:
                del prop[k]
        return prop

    def __json__(self, topology_dump=False):
        """
        :param topology_dump: Filter to keep only properties require for saving on disk
        """
        if topology_dump:
            return {
                "compute_id": str(self._compute.id),
                "node_id": self._id,
                "node_type": self._node_type,
                "name": self._name,
                "console": self._console,
                "console_type": self._console_type,
                "properties": self._filter_properties(),
                "label": self._label,
                "x": self._x,
                "y": self._y,
                "z": self._z,
                "width": self._width,
                "height": self._height,
                "symbol": self._symbol,
                "port_name_format": self._port_name_format,
                "port_segment_size": self._port_segment_size,
                "first_port_name": self._first_port_name
            }
        return {
            "compute_id": str(self._compute.id),
            "project_id": self._project.id,
            "node_id": self._id,
            "node_type": self._node_type,
            "node_directory": self._node_directory,
            "name": self._name,
            "console": self._console,
            "console_host": str(self._compute.console_host),
            "console_type": self._console_type,
            "command_line": self._command_line,
            "properties": self._filter_properties(),
            "status": self._status,
            "label": self._label,
            "x": self._x,
            "y": self._y,
            "z": self._z,
            "width": self._width,
            "height": self._height,
            "symbol": self._symbol,
            "port_name_format": self._port_name_format,
            "port_segment_size": self._port_segment_size,
            "first_port_name": self._first_port_name,
            "ports": [port.__json__() for port in self.ports]
        }
