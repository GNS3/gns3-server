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


class Node:

    def __init__(self, project, compute, node_id=None, node_type=None, name=None, console=None, console_type=None, properties={}):
        """
        :param project: Project of the node
        :param compute: Compute server where the server will run
        :param node_id: UUID of the node (integer)
        :param node_type: Type of emulator
        :param name: Name of the node
        :param console: TCP port of the console
        :param console_type: Type of the console (telnet, vnc, serial..)
        :param properties: Emulator specific properties of the node
        """

        if node_id is None:
            self._id = str(uuid.uuid4())
        else:
            self._id = node_id

        self._name = name
        self._project = project
        self._compute = compute
        self._node_type = node_type
        self._console = console
        self._console_type = console_type
        self._properties = properties
        self._command_line = None
        self._node_directory = None
        self._status = "stopped"

    @property
    def id(self):
        return self._id

    @property
    def status(self):
        return self._status

    @property
    def name(self):
        return self._name

    @property
    def node_type(self):
        return self._node_type

    @property
    def console(self):
        return self._console

    @property
    def console_type(self):
        return self._console_type

    @property
    def properties(self):
        return self._properties

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

    @asyncio.coroutine
    def create(self):
        """
        Create the node on the compute server
        """
        data = self._node_data()
        data["node_id"] = self._id
        response = yield from self._compute.post("/projects/{}/{}/nodes".format(self._project.id, self._node_type), data=data)
        self.parse_node_response(response.json)

    @asyncio.coroutine
    def update(self, name=None, console=None, console_type="telnet", properties={}):
        """
        Update the node on the compute server

        :param node_id: UUID of the node
        :param node_type: Type of emulator
        :param name: Name of the node
        :param console: TCP port of the console
        :param console_type: Type of the console (telnet, vnc, serial..)
        :param properties: Emulator specific properties of the node

        """
        if name:
            self._name = name
        if console:
            self._console = console
        if console_type:
            self._console_type = console_type
        if properties != {}:
            self._properties = properties

        data = self._node_data()
        response = yield from self.put(None, data=data)
        self.parse_node_response(response.json)

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

    def _node_data(self):
        """
        Prepare node data to send to the remote controller
        """
        data = copy.copy(self._properties)
        data["name"] = self._name
        if self._console:
            # console is optional for builtin nodes
            data["console"] = self._console
        if self._console_type:
            data["console_type"] = self._console_type

        # None properties are not be send. Because it can mean the emulator doesn't support it
        for key in list(data.keys()):
            if data[key] is None or key in ["console_host"]:
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

    def __json__(self):
        return {
            "compute_id": self._compute.id,
            "project_id": self._project.id,
            "node_id": self._id,
            "node_type": self._node_type,
            "node_directory": self._node_directory,
            "name": self._name,
            "console": self._console,
            "console_host": self._compute.host,
            "console_type": self._console_type,
            "command_line": self._command_line,
            "properties": self._properties,
            "status": self._status
        }
