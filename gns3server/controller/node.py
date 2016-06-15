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

import asyncio
import copy
import uuid
import os


from .compute import ComputeConflict
from ..utils.images import images_directories


import logging
log = logging.getLogger(__name__)


class Node:
    # This properties are used only on controller and are not forwarded to the compute
    CONTROLLER_ONLY_PROPERTIES = ["x", "y", "z", "symbol", "label", "console_host"]

    def __init__(self, project, compute, name, node_id=None, node_type=None, **kwargs):
        """
        :param project: Project of the node
        :param compute: Compute server where the server will run
        :param name: Node name
        :param node_id: UUID of the node (integer)
        :param node_type: Type of emulator
        :param kwargs: Node properties
        """

        if node_id is None:
            self._id = str(uuid.uuid4())
        else:
            self._id = node_id

        self._project = project
        self._compute = compute
        self._node_type = node_type

        self._name = name
        self._console = None
        self._console_type = None
        self._properties = {}
        self._command_line = None
        self._node_directory = None
        self._status = "stopped"
        self._x = 0
        self._y = 0
        self._z = 0
        self._symbol = ":/symbols/computer.svg"
        self._label = {
            "color": "#ff000000",
            "y": -25.0,
            "text": "",
            "font": "TypeWriter,10,-1,5,75,0,0,0,0,0",
            "x": -17.0234375
        }
        # Update node properties with additional elements
        for prop in kwargs:
            try:
                setattr(self, prop, kwargs[prop])
            except AttributeError as e:
                log.critical("Can't set attribute %s", prop)
                raise e

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
        self._project.update_node_name(self, new_name)
        self._name = new_name
        # The text in label need to be always the node name
        self._label["text"] = new_name

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
    def symbol(self):
        return self._symbol

    @symbol.setter
    def symbol(self, val):
        self._symbol = val

    @property
    def label(self):
        return self._label

    @label.setter
    def label(self, val):
        # The text in label need to be always the node name
        val["text"] = self._name
        self._label = val

    @asyncio.coroutine
    def create(self):
        """
        Create the node on the compute server
        """
        data = self._node_data()
        data["node_id"] = self._id
        trial = 0
        while trial != 6:
            try:
                response = yield from self._compute.post("/projects/{}/{}/nodes".format(self._project.id, self._node_type), data=data)
            except ComputeConflict as e:
                if e.response.get("exception") == "ImageMissingError":
                    res = yield from self._upload_missing_image(self._node_type, e.response["image"])
                    if not res:
                        raise e
            else:
                self.parse_node_response(response.json)
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

        self.project.controller.notification.emit("node.updated", self.__json__())
        if update_compute:
            data = self._node_data(properties=compute_properties)
            response = yield from self.put(None, data=data)
            self.parse_node_response(response.json)
        self.project.dump()

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
                self._name = value
            elif key in ["node_id", "project_id", "console_host"]:
                pass
            else:
                self._properties[key] = value

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
        yield from self.post("/start")

    @asyncio.coroutine
    def stop(self):
        """
        Stop a node
        """
        yield from self.post("/stop")

    @asyncio.coroutine
    def suspend(self):
        """
        Suspend a node
        """
        yield from self.post("/suspend")

    @asyncio.coroutine
    def reload(self):
        """
        Suspend a node
        """
        yield from self.post("/reload")

    @asyncio.coroutine
    def post(self, path, data=None):
        """
        HTTP post on the node
        """
        if data:
            return (yield from self._compute.post("/projects/{}/{}/nodes/{}{}".format(self._project.id, self._node_type, self._id, path), data=data))
        else:
            return (yield from self._compute.post("/projects/{}/{}/nodes/{}{}".format(self._project.id, self._node_type, self._id, path)))

    @asyncio.coroutine
    def put(self, path, data=None):
        """
        HTTP post on the node
        """
        if path is None:
            path = "/projects/{}/{}/nodes/{}".format(self._project.id, self._node_type, self._id)
        else:
            path = "/projects/{}/{}/nodes/{}{}".format(self._project.id, self._node_type, self._id, path)
        if data:
            return (yield from self._compute.put(path, data=data))
        else:
            return (yield from self._compute.put(path))

    @asyncio.coroutine
    def delete(self, path=None):
        """
        HTTP post on the node
        """
        if path is None:
            return (yield from self._compute.delete("/projects/{}/{}/nodes/{}".format(self._project.id, self._node_type, self._id)))
        else:
            return (yield from self._compute.delete("/projects/{}/{}/nodes/{}{}".format(self._project.id, self._node_type, self._id, path)))

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

    def __repr__(self):
        return "<gns3server.controller.Node {} {}>".format(self._node_type, self._name)

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
                "properties": self._properties,
                "label": self._label,
                "x": self._x,
                "y": self._y,
                "z": self._z,
                "symbol": self._symbol
            }
        return {
            "compute_id": str(self._compute.id),
            "project_id": self._project.id,
            "node_id": self._id,
            "node_type": self._node_type,
            "node_directory": self._node_directory,
            "name": self._name,
            "console": self._console,
            "console_host": str(self._compute.host),
            "console_type": self._console_type,
            "command_line": self._command_line,
            "properties": self._properties,
            "status": self._status,
            "label": self._label,
            "x": self._x,
            "y": self._y,
            "z": self._z,
            "symbol": self._symbol
        }
