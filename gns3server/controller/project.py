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
import os
import json
import uuid
import shutil
import asyncio
import aiohttp
import tempfile

from uuid import UUID, uuid4

from .node import Node
from .compute import ComputeError
from .snapshot import Snapshot
from .drawing import Drawing
from .topology import project_to_topology, load_topology
from .udp_link import UDPLink
from ..config import Config
from ..utils.path import check_path_allowed, get_default_project_directory
from ..utils.asyncio.pool import Pool
from ..utils.asyncio import locked_coroutine
from .export_project import export_project
from .import_project import import_project


import logging
log = logging.getLogger(__name__)


def open_required(func):
    """
    Use this decorator to raise an error if the project is not opened
    """

    def wrapper(self, *args, **kwargs):
        if self._status == "closed":
            raise aiohttp.web.HTTPForbidden(text="The project is not opened")
        return func(self, *args, **kwargs)
    return wrapper


class Project:
    """
    A project inside a controller

    :param project_id: force project identifier (None by default auto generate an UUID)
    :param path: path of the project. (None use the standard directory)
    :param status: Status of the project (opened / closed)
    """

    def __init__(self, name=None, project_id=None, path=None, controller=None, status="opened",
                 filename=None, auto_start=False, auto_open=False, auto_close=True,
                 scene_height=1000, scene_width=2000):

        self._controller = controller
        assert name is not None
        self._name = name
        self._auto_start = auto_start
        self._auto_close = auto_close
        self._auto_open = auto_open
        self._status = status
        self._scene_height = scene_height
        self._scene_width = scene_width
        self._loading = False

        # Disallow overwrite of existing project
        if project_id is None and path is not None:
            if os.path.exists(path):
                raise aiohttp.web.HTTPForbidden(text="The path {} already exist.".format(path))

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

        if filename is not None:
            self._filename = filename
        else:
            self._filename = self.name + ".gns3"

        self.reset()

        # At project creation we write an empty .gns3
        if not os.path.exists(self._topology_file()):
            self.dump()

    @asyncio.coroutine
    def update(self, **kwargs):
        """
        Update the project
        :param kwargs: Project properties
        """

        old_json = self.__json__()

        for prop in kwargs:
            setattr(self, prop, kwargs[prop])

        # We send notif only if object has changed
        if old_json != self.__json__():
            self.controller.notification.emit("project.updated", self.__json__())
            self.dump()

    def reset(self):
        """
        Called when open/close a project. Cleanup internal stuff
        """
        self._allocated_node_names = set()
        self._nodes = {}
        self._links = {}
        self._drawings = {}
        self._snapshots = {}

        # List the available snapshots
        snapshot_dir = os.path.join(self.path, "snapshots")
        if os.path.exists(snapshot_dir):
            for snap in os.listdir(snapshot_dir):
                if snap.endswith(".gns3project"):
                    snapshot = Snapshot(self, filename=snap)
                    self._snapshots[snapshot.id] = snapshot

        # Create the project on demand on the compute node
        self._project_created_on_compute = set()

    @property
    def scene_height(self):
        return self._scene_height

    @scene_height.setter
    def scene_height(self, val):
        """
        Height of the drawing area
        """
        self._scene_height = val

    @property
    def scene_width(self):
        return self._scene_width

    @scene_width.setter
    def scene_width(self, val):
        """
        Width of the drawing area
        """
        self._scene_width = val

    @property
    def auto_start(self):
        """
        Should project auto start when opened
        """
        return self._auto_start

    @auto_start.setter
    def auto_start(self, val):
        self._auto_start = val

    @property
    def auto_close(self):
        """
        Should project automaticaly closed when client
        stop listening for notification
        """
        return self._auto_close

    @auto_close.setter
    def auto_close(self, val):
        self._auto_close = val

    @property
    def auto_open(self):
        return self._auto_open

    @auto_open.setter
    def auto_open(self, val):
        self._auto_open = val

    @property
    def controller(self):
        return self._controller

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, val):
        self._name = val

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
        Location of the captures files
        """
        path = os.path.join(self._path, "project-files", "captures")
        os.makedirs(path, exist_ok=True)
        return path

    @property
    def pictures_directory(self):
        """
        Location of the images files
        """
        path = os.path.join(self._path, "project-files", "images")
        os.makedirs(path, exist_ok=True)
        return path

    @property
    def computes(self):
        """
        :return: List of computes used by the project
        """
        return self._project_created_on_compute

    def remove_allocated_node_name(self, name):
        """
        Removes an allocated node name

        :param name: allocated node name
        """

        if name in self._allocated_node_names:
            self._allocated_node_names.remove(name)

    def update_allocated_node_name(self, base_name):
        """
        Updates a node name or generate a new if no node
        name is available.

        :param base_name: new node base name
        """

        if base_name is None:
            return None
        base_name = re.sub(r"[ ]", "", base_name)
        if '{0}' in base_name or '{id}' in base_name:
            # base name is a template, replace {0} or {id} by an unique identifier
            for number in range(1, 1000000):
                try:
                    name = base_name.format(number, id=number, name="Node")
                except KeyError as e:
                    raise aiohttp.web.HTTPConflict(text="{" + e.args[0] + "} is not a valid replacement string in the node name")
                except (ValueError, IndexError) as e:
                    raise aiohttp.web.HTTPConflict(text="{} is not a valid replacement string in the node name".format(base_name))
                if name not in self._allocated_node_names:
                    self._allocated_node_names.add(name)
                    return name
        else:
            if base_name not in self._allocated_node_names:
                self._allocated_node_names.add(base_name)
                return base_name
            # base name is not unique, let's find a unique name by appending a number
            for number in range(1, 1000000):
                name = base_name + str(number)
                if name not in self._allocated_node_names:
                    self._allocated_node_names.add(name)
                    return name
        raise aiohttp.web.HTTPConflict(text="A node name could not be allocated (node limit reached?)")

    def update_node_name(self, node, new_name):

        if new_name and node.name != new_name:
            self.remove_allocated_node_name(node.name)
            return self.update_allocated_node_name(new_name)
        return new_name

    @open_required
    @asyncio.coroutine
    def add_node(self, compute, name, node_id, dump=True, node_type=None, **kwargs):
        """
        Create a node or return an existing node

        :param dump: Dump topology to disk
        :param kwargs: See the documentation of node
        """
        if node_id in self._nodes:
            return self._nodes[node_id]

        # Due to a limitation all iou need to run on the same
        # compute server otherwise you have mac address conflict
        if node_type == "iou":
            for node in self._nodes.values():
                if node.node_type == node_type and node.compute != compute:
                    raise aiohttp.web.HTTPConflict(text="All IOU nodes need to run on the same server.")

        node = Node(self, compute, name, node_id=node_id, node_type=node_type, **kwargs)
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
        if dump:
            self.dump()
        return node

    @locked_coroutine
    def __delete_node_links(self, node):
        """
        Delete all link connected to this node.

        The operation use a lock to avoid cleaning links from
        multiple nodes at the same time.
        """
        for link in list(self._links.values()):
            if node in link.nodes:
                yield from self.delete_link(link.id)

    @open_required
    @asyncio.coroutine
    def delete_node(self, node_id):
        node = self.get_node(node_id)
        yield from self.__delete_node_links(node)
        self.remove_allocated_node_name(node.name)
        del self._nodes[node.id]
        yield from node.destroy()
        self.dump()
        self.controller.notification.emit("node.deleted", node.__json__())

    @open_required
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

    @property
    def drawings(self):
        """
        :returns: Dictionary of the drawings
        """
        return self._drawings

    @open_required
    @asyncio.coroutine
    def add_drawing(self, drawing_id=None, dump=True, **kwargs):
        """
        Create an drawing or return an existing drawing

        :param dump: Dump the topology to disk
        :param kwargs: See the documentation of drawing
        """
        if drawing_id not in self._drawings:
            drawing = Drawing(self, drawing_id=drawing_id, **kwargs)
            self._drawings[drawing.id] = drawing
            self.controller.notification.emit("drawing.created", drawing.__json__())
            if dump:
                self.dump()
            return drawing
        return self._drawings[drawing_id]

    @open_required
    def get_drawing(self, drawing_id):
        """
        Return the Drawing or raise a 404 if the drawing is unknown
        """
        try:
            return self._drawings[drawing_id]
        except KeyError:
            raise aiohttp.web.HTTPNotFound(text="Drawing ID {} doesn't exist".format(drawing_id))

    @open_required
    @asyncio.coroutine
    def delete_drawing(self, drawing_id):
        drawing = self.get_drawing(drawing_id)
        del self._drawings[drawing.id]
        self.dump()
        self.controller.notification.emit("drawing.deleted", drawing.__json__())

    @open_required
    @asyncio.coroutine
    def add_link(self, link_id=None, dump=True):
        """
        Create a link. By default the link is empty

        :param dump: Dump topology to disk
        """
        if link_id and link_id in self._links:
            return self._links[link_id]
        link = UDPLink(self, link_id=link_id)
        self._links[link.id] = link
        if dump:
            self.dump()
        return link

    @open_required
    @asyncio.coroutine
    def delete_link(self, link_id):
        link = self.get_link(link_id)
        del self._links[link.id]
        yield from link.delete()
        self.dump()
        self.controller.notification.emit("link.deleted", link.__json__())

    @open_required
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

    @property
    def snapshots(self):
        """
        :returns: Dictionary of snapshots
        """
        return self._snapshots

    @open_required
    def get_snapshot(self, snapshot_id):
        """
        Return the snapshot or raise a 404 if the snapshot is unknown
        """
        try:
            return self._snapshots[snapshot_id]
        except KeyError:
            raise aiohttp.web.HTTPNotFound(text="Snapshot ID {} doesn't exist".format(snapshot_id))

    @open_required
    @asyncio.coroutine
    def snapshot(self, name):
        """
        Snapshot the project

        :param name: Name of the snapshot
        """

        snapshot = Snapshot(self, name=name)
        try:
            if os.path.exists(snapshot.path):
                raise aiohttp.web_exceptions.HTTPConflict(text="The snapshot {} already exist".format(name))

            os.makedirs(os.path.join(self.path, "snapshots"), exist_ok=True)

            with tempfile.TemporaryDirectory() as tmpdir:
                zipstream = yield from export_project(self, tmpdir, keep_compute_id=True, allow_all_nodes=True)
                with open(snapshot.path, "wb+") as f:
                    for data in zipstream:
                        f.write(data)
        except OSError as e:
            raise aiohttp.web.HTTPInternalServerError(text="Could not create project directory: {}".format(e))

        self._snapshots[snapshot.id] = snapshot
        return snapshot

    @open_required
    @asyncio.coroutine
    def delete_snapshot(self, snapshot_id):
        snapshot = self.get_snapshot(snapshot_id)
        del self._snapshots[snapshot.id]
        os.remove(snapshot.path)

    @asyncio.coroutine
    def close(self, ignore_notification=False):
        yield from self.stop_all()
        for compute in list(self._project_created_on_compute):
            try:
                yield from compute.post("/projects/{}/close".format(self._id), dont_connect=True)
            # We don't care if a compute is down at this step
            except (ComputeError, aiohttp.web.HTTPError, aiohttp.ClientResponseError, TimeoutError):
                pass
        self._cleanPictures()
        self._status = "closed"
        if not ignore_notification:
            self.controller.notification.emit("project.closed", self.__json__())

    def _cleanPictures(self):
        """
        Delete unused images
        """

        # Project have been deleted
        if not os.path.exists(self.path):
            return
        try:
            pictures = set(os.listdir(self.pictures_directory))
            for drawing in self._drawings.values():
                try:
                    pictures.remove(drawing.ressource_filename)
                except KeyError:
                    pass

            for pict in pictures:
                os.remove(os.path.join(self.pictures_directory, pict))
        except OSError as e:
            log.warning(str(e))

    @asyncio.coroutine
    def delete(self):
        if self._status != "opened":
            yield from self.open()
        yield from self.delete_on_computes()
        yield from self.close()
        try:
            shutil.rmtree(self.path)
        except OSError as e:
            raise aiohttp.web.HTTPConflict(text="Can not delete project directory {}: {}".format(self.path, str(e)))

    @asyncio.coroutine
    def delete_on_computes(self):
        """
        Delete the project on computes but not on controller
        """
        for compute in list(self._project_created_on_compute):
            if compute.id != "local":
                yield from compute.delete("/projects/{}".format(self._id))
                self._project_created_on_compute.remove(compute)

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

    @locked_coroutine
    def open(self):
        """
        Load topology elements
        """
        if self._status == "opened":
            return

        self.reset()
        self._loading = True
        self._status = "opened"

        path = self._topology_file()
        if not os.path.exists(path):
            self._loading = False
            return
        try:
            shutil.copy(path, path + ".backup")
        except OSError:
            pass
        try:
            topology = load_topology(path)["topology"]
            for compute in topology.get("computes", []):
                yield from self.controller.add_compute(**compute)
            for node in topology.get("nodes", []):
                compute = self.controller.get_compute(node.pop("compute_id"))
                name = node.pop("name")
                node_id = node.pop("node_id", str(uuid.uuid4()))
                yield from self.add_node(compute, name, node_id, dump=False, **node)
            for link_data in topology.get("links", []):
                link = yield from self.add_link(link_id=link_data["link_id"])
                for node_link in link_data["nodes"]:
                    node = self.get_node(node_link["node_id"])
                    yield from link.add_node(node, node_link["adapter_number"], node_link["port_number"], label=node_link.get("label"), dump=False)
            for drawing_data in topology.get("drawings", []):
                yield from self.add_drawing(dump=False, **drawing_data)

            self.dump()
        # We catch all error to be able to rollback the .gns3 to the previous state
        except Exception as e:
            for compute in list(self._project_created_on_compute):
                try:
                    yield from compute.post("/projects/{}/close".format(self._id))
                # We don't care if a compute is down at this step
                except (ComputeError, aiohttp.web.HTTPNotFound, aiohttp.web.HTTPConflict):
                    pass
            try:
                if os.path.exists(path + ".backup"):
                    shutil.copy(path + ".backup", path)
            except (PermissionError, OSError):
                pass
            self._status = "closed"
            self._loading = False
            if isinstance(e, ComputeError):
                raise aiohttp.web.HTTPConflict(text=str(e))
            else:
                raise e
        try:
            os.remove(path + ".backup")
        except OSError:
            pass

        self._loading = False
        # Should we start the nodes when project is open
        if self._auto_start:
            # Start all in the background without waiting for completion
            # we ignore errors because we want to let the user open
            # their project and fix it
            asyncio.async(self.start_all())

    @asyncio.coroutine
    def wait_loaded(self):
        """
        Wait until the project finish loading
        """
        while self._loading:
            yield from asyncio.sleep(0.5)

    @asyncio.coroutine
    def duplicate(self, name=None, location=None):
        """
        Duplicate a project

        It's the save as feature of the 1.X. It's implemented on top of the
        export / import features. It will generate a gns3p and reimport it.
        It's a little slower but we have only one implementation to maintain.

        :param name: Name of the new project. A new one will be generated in case of conflicts
        :param location: Parent directory of the new project
        """
        # If the project was not open we open it temporary
        previous_status = self._status
        if self._status == "closed":
            yield from self.open()

        self.dump()
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                zipstream = yield from export_project(self, tmpdir, keep_compute_id=True, allow_all_nodes=True)
                with open(os.path.join(tmpdir, "project.gns3p"), "wb+") as f:
                    for data in zipstream:
                        f.write(data)
                with open(os.path.join(tmpdir, "project.gns3p"), "rb") as f:
                    project = yield from import_project(self._controller, str(uuid.uuid4()), f, location=location, name=name, keep_compute_id=True)
        except (OSError, UnicodeEncodeError) as e:
            raise aiohttp.web.HTTPConflict(text="Can not duplicate project: {}".format(str(e)))

        if previous_status == "closed":
            yield from self.close()

        return project

    def is_running(self):
        """
        If a node is started or paused return True
        """
        for node in self._nodes.values():
            # Some node type are always running we ignore them
            if node.status != "stopped" and node.node_type in ("qemu", "docker", "dynamips", "vpcs", "vmware", "virtualbox", "iou"):
                return True
        return False

    def dump(self):
        """
        Dump topology to disk
        """
        try:
            topo = project_to_topology(self)
            path = self._topology_file()
            log.debug("Write %s", path)
            with open(path + ".tmp", "w+", encoding="utf-8") as f:
                json.dump(topo, f, indent=4, sort_keys=True)
            shutil.move(path + ".tmp", path)
        except OSError as e:
            raise aiohttp.web.HTTPInternalServerError(text="Could not write topology: {}".format(e))

    @asyncio.coroutine
    def start_all(self):
        """
        Start all nodes
        """
        pool = Pool(concurrency=3)
        for node in self.nodes.values():
            pool.append(node.start)
        yield from pool.join()

    @asyncio.coroutine
    def stop_all(self):
        """
        Stop all nodes
        """
        pool = Pool(concurrency=3)
        for node in self.nodes.values():
            pool.append(node.stop)
        yield from pool.join()

    @asyncio.coroutine
    def suspend_all(self):
        """
        Suspend all nodes
        """
        pool = Pool(concurrency=3)
        for node in self.nodes.values():
            pool.append(node.suspend)
        yield from pool.join()

    def __json__(self):

        return {
            "name": self._name,
            "project_id": self._id,
            "path": self._path,
            "filename": self._filename,
            "status": self._status,
            "auto_start": self._auto_start,
            "auto_close": self._auto_close,
            "auto_open": self._auto_open,
            "scene_height": self._scene_height,
            "scene_width": self._scene_width
        }

    def __repr__(self):
        return "<gns3server.controller.Project {} {}>".format(self._name, self._id)
