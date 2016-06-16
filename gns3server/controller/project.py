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
import json
import asyncio
import aiohttp
import shutil

from uuid import UUID, uuid4

from .node import Node
from .topology import project_to_topology, load_topology
from .udp_link import UDPLink
from ..config import Config
from ..utils.path import check_path_allowed, get_default_project_directory


import logging
log = logging.getLogger(__name__)


class Project:
    """
    A project inside a controller

    :param project_id: force project identifier (None by default auto generate an UUID)
    :param path: path of the project. (None use the standard directory)
    :param status: Status of the project (opened / closed)
    """

    def __init__(self, name=None, project_id=None, path=None, controller=None, status="opened", filename=None):

        self._controller = controller
        self._name = name
        self._status = status
        if project_id is None:
            self._id = str(uuid4())
        else:
            try:
                UUID(project_id, version=4)
            except ValueError:
                raise aiohttp.web.HTTPBadRequest(text="{} is not a valid UUID".format(project_id))
            self._id = project_id

        if path is None:
            path = os.path.join(get_default_project_directory(), self._id)
        self.path = path

        if filename is None and name is None:
            self._filename = "project.gns3"
        elif filename is not None:
            self._filename = filename
        else:
            self._filename = self.name + ".gns3"
        self.reset()

    def reset(self):
        """
        Called when open/close a project. Cleanup internal stuff
        """
        self._allocated_node_names = set()
        self._nodes = {}
        self._links = {}

        # Create the project on demand on the compute node
        self._project_created_on_compute = set()

    @property
    def controller(self):
        return self._controller

    @property
    def name(self):
        return self._name

    @property
    def id(self):
        return self._id

    @property
    def path(self):
        return self._path

    @property
    def status(self):
        return self._status

    @path.setter
    def path(self, path):
        check_path_allowed(path)
        try:
            os.makedirs(path, exist_ok=True)
        except OSError as e:
            raise aiohttp.web.HTTPInternalServerError(text="Could not create project directory: {}".format(e))

        if '"' in path:
            raise aiohttp.web.HTTPForbidden(text="You are not allowed to use \" in the project directory path. Not supported by Dynamips.")

        self._path = path

    def _config(self):
        return Config.instance().get_section_config("Server")

    @property
    def captures_directory(self):
        """
        Location of the captures file
        """
        path = os.path.join(self._path, "project-files", "captures")
        os.makedirs(path, exist_ok=True)
        return path

    @property
    def computes(self):
        """
        :return: Dictonnary of computes used by the project
        """
        return self._computes

    def allocate_node_name(self, base_name):
        """
        Allocates a new unique name for a node in this project.

        :param base_name: base name for the node which will be completed with a unique number.

        :returns: allocated name or None if one could not be found
        """

        if '{0}' in base_name or '{id}' in base_name:
            # base name is a template, replace {0} or {id} by an unique identifier
            for number in range(1, 1000000):
                name = base_name.format(number, id=number)
                if name not in self._allocated_node_names:
                    self._allocated_node_names.add(name)
                    return name
        else:
            if base_name not in self._allocated_node_names:
                return base_name
            # base name is not unique, let's find a unique name by appending a number
            for number in range(1, 1000000):
                name = base_name + str(number)
                if name not in self._allocated_node_names:
                    self._allocated_node_names.add(name)
                    return name
        return None

    def remove_allocated_node_name(self, name):
        """
        Removes an allocated node name

        :param name: allocated node name
        """

        if name in self._allocated_node_names:
            self._allocated_node_names.remove(name)

    def update_allocated_node_name(self, name):
        """
        Updates a node name

        :param name: new node name
        """

        self.remove_allocated_node_name(name)
        self._allocated_node_names.add(name)

    def has_allocated_node_name(self, name):
        """
        Returns either a node name is already allocated or not.

        :param name: node name

        :returns: boolean
        """

        if name in self._allocated_node_names:
            return True
        return False

    def update_node_name(self, node, new_name):

        if new_name and node.name != new_name:
            if self.has_allocated_node_name(new_name):
                raise aiohttp.web.HTTPConflict(text="{} node name is already allocated in this project".format(new_name))
            self.update_allocated_node_name(new_name)
            return True
        return False

    @asyncio.coroutine
    def add_node(self, compute, name, node_id, **kwargs):
        """
        Create a node or return an existing node

        :param kwargs: See the documentation of node
        """
        if node_id not in self._nodes:

            name = self.allocate_node_name(name)
            if not name:
                raise aiohttp.web.HTTPConflict(text="A node name could not be allocated (node limit reached?)")

            node = Node(self, compute, name, node_id=node_id, **kwargs)
            if compute not in self._project_created_on_compute:
                # For a local server we send the project path
                if compute.id == "local":
                    yield from compute.post("/projects", data={
                        "name": self._name,
                        "project_id": self._id,
                        "path": self._path
                    })
                else:
                    yield from compute.post("/projects", data={
                        "name": self._name,
                        "project_id": self._id,
                    })

                self._project_created_on_compute.add(compute)
            yield from node.create()
            self._nodes[node.id] = node
            self.controller.notification.emit("node.created", node.__json__())
            self.dump()
            return node
        return self._nodes[node_id]

    @asyncio.coroutine
    def delete_node(self, node_id):

        node = self.get_node(node_id)
        self.remove_allocated_node_name(node.name)
        del self._nodes[node.id]
        yield from node.destroy()
        self.dump()
        self.controller.notification.emit("node.deleted", node.__json__())

    def get_node(self, node_id):
        """
        Return the node or raise a 404 if the node is unknown
        """
        try:
            return self._nodes[node_id]
        except KeyError:
            raise aiohttp.web.HTTPNotFound(text="Node ID {} doesn't exist".format(node_id))

    @property
    def nodes(self):
        """
        :returns: Dictionary of the nodes
        """
        return self._nodes

    @asyncio.coroutine
    def add_link(self, link_id=None):
        """
        Create a link. By default the link is empty
        """
        if link_id and link_id in self._links:
            return self._links[link.id]
        link = UDPLink(self, link_id=link_id)
        self._links[link.id] = link
        self.dump()
        return link

    @asyncio.coroutine
    def delete_link(self, link_id):
        link = self.get_link(link_id)
        del self._links[link.id]
        yield from link.delete()
        self.dump()
        self.controller.notification.emit("link.deleted", link.__json__())

    def get_link(self, link_id):
        """
        Return the Link or raise a 404 if the link is unknown
        """
        try:
            return self._links[link_id]
        except KeyError:
            raise aiohttp.web.HTTPNotFound(text="Link ID {} doesn't exist".format(link_id))

    @property
    def links(self):
        """
        :returns: Dictionary of the Links
        """
        return self._links

    @asyncio.coroutine
    def close(self):
        for compute in self._project_created_on_compute:
            yield from compute.post("/projects/{}/close".format(self._id))
        self.reset()
        self._status = "closed"

    @asyncio.coroutine
    def delete(self):
        yield from self.close()
        for compute in self._project_created_on_compute:
            yield from compute.delete("/projects/{}".format(self._id))
        shutil.rmtree(self.path, ignore_errors=True)

    @classmethod
    def _get_default_project_directory(cls):
        """
        Return the default location for the project directory
        depending of the operating system
        """

        server_config = Config.instance().get_section_config("Server")
        path = os.path.expanduser(server_config.get("projects_path", "~/GNS3/projects"))
        path = os.path.normpath(path)
        try:
            os.makedirs(path, exist_ok=True)
        except OSError as e:
            raise aiohttp.web.HTTPInternalServerError(text="Could not create project directory: {}".format(e))
        return path

    def _topology_file(self):
        return os.path.join(self.path, self._filename)

    @asyncio.coroutine
    def open(self):
        """
        Load topology elements
        """
        self.reset()
        path = self._topology_file()
        if os.path.exists(path):
            topology = load_topology(path)["topology"]
            for compute in topology["computes"]:
                yield from self.controller.add_compute(**compute)
            for node in topology["nodes"]:
                compute = self.controller.get_compute(node.pop("compute_id"))
                name = node.pop("name")
                node_id = node.pop("node_id")
                yield from self.add_node(compute, name, node_id, **node)
            for link_data in topology["links"]:
                link = yield from self.add_link(link_id=link_data["link_id"])
                for node_link in link_data["nodes"]:
                    node = self.get_node(node_link["node_id"])
                    yield from link.add_node(node, node_link["adapter_number"], node_link["port_number"])
        self._status = "opened"

    def dump(self):
        """
        Dump topology to disk
        """
        try:
            topo = project_to_topology(self)
            path = self._topology_file()
            log.debug("Write %s", path)
            with open(path, "w+") as f:
                json.dump(topo, f, indent=4, sort_keys=True)
        except OSError as e:
            raise aiohttp.web.HTTPInternalServerError(text="Could not write topology: {}".format(e))

    def __json__(self):

        return {
            "name": self._name,
            "project_id": self._id,
            "path": self._path,
            "filename": self._filename,
            "status": self._status
        }
