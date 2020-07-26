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
import copy
import shutil
import time
import asyncio
import aiohttp
import aiofiles
import tempfile
import zipfile

from uuid import UUID, uuid4

from .node import Node
from .compute import ComputeError
from .snapshot import Snapshot
from .drawing import Drawing
from .topology import project_to_topology, load_topology
from .udp_link import UDPLink
from ..config import Config
from ..utils.path import check_path_allowed, get_default_project_directory
from ..utils.application_id import get_next_application_id
from ..utils.asyncio.pool import Pool
from ..utils.asyncio import locking
from ..utils.asyncio import aiozipstream
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
                 scene_height=1000, scene_width=2000, zoom=100, show_layers=False, snap_to_grid=False, show_grid=False,
                 grid_size=75, drawing_grid_size=25, show_interface_labels=False, variables=None, supplier=None):

        self._controller = controller
        assert name is not None
        self._name = name
        self._auto_start = auto_start
        self._auto_close = auto_close
        self._auto_open = auto_open
        self._status = status
        self._scene_height = scene_height
        self._scene_width = scene_width
        self._zoom = zoom
        self._show_layers = show_layers
        self._snap_to_grid = snap_to_grid
        self._show_grid = show_grid
        self._grid_size = grid_size
        self._drawing_grid_size = drawing_grid_size
        self._show_interface_labels = show_interface_labels
        self._variables = variables
        self._supplier = supplier

        self._loading = False
        self._closing = False

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

        # At project creation we write an empty .gns3 with the meta
        if not os.path.exists(self._topology_file()):
            assert self._status != "closed"
            self.dump()

        self._iou_id_lock = asyncio.Lock()

        log.debug('Project "{name}" [{id}] loaded'.format(name=self.name, id=self._id))

    def emit_notification(self, action, event):
        """
        Emit a notification to all clients using this project.

        :param action: Action name
        :param event: Event to send
        """

        self.controller.notification.project_emit(action, event, project_id=self.id)

    async def update(self, **kwargs):
        """
        Update the project
        :param kwargs: Project properties
        """

        old_json = self.__json__()

        for prop in kwargs:
            setattr(self, prop, kwargs[prop])

        # We send notif only if object has changed
        if old_json != self.__json__():
            self.emit_notification("project.updated", self.__json__())
            self.dump()

            # update on computes
            for compute in list(self._project_created_on_compute):
                await compute.put(
                    "/projects/{}".format(self._id), {
                        "variables": self.variables
                    }
                )

    def reset(self):
        """
        Called when open/close a project. Cleanup internal stuff
        """
        self._allocated_node_names = set()
        self._nodes = {}
        self._links = {}
        self._drawings = {}
        self._snapshots = {}
        self._computes = []

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
    def zoom(self):
        """
        Zoom level in percentage
        :return: integer > 0
        """
        return self._zoom

    @zoom.setter
    def zoom(self, zoom):
        """
        Setter for zoom level in percentage
        """
        self._zoom = zoom

    @property
    def show_layers(self):
        """
        Show layers mode
        :return: bool
        """
        return self._show_layers

    @show_layers.setter
    def show_layers(self, show_layers):
        """
        Setter for show layers mode
        """
        self._show_layers = show_layers

    @property
    def snap_to_grid(self):
        """
        Snap to grid mode
        :return: bool
        """
        return self._snap_to_grid

    @snap_to_grid.setter
    def snap_to_grid(self, snap_to_grid):
        """
        Setter for snap to grid mode
        """
        self._snap_to_grid = snap_to_grid

    @property
    def show_grid(self):
        """
        Show grid mode
        :return: bool
        """
        return self._show_grid

    @show_grid.setter
    def show_grid(self, show_grid):
        """
        Setter for showing the grid mode
        """
        self._show_grid = show_grid

    @property
    def grid_size(self):
        """
        Grid size
        :return: integer
        """
        return self._grid_size

    @grid_size.setter
    def grid_size(self, grid_size):
        """
        Setter for grid size
        """
        self._grid_size = grid_size

    @property
    def drawing_grid_size(self):
        """
        Grid size
        :return: integer
        """
        return self._drawing_grid_size

    @drawing_grid_size.setter
    def drawing_grid_size(self, grid_size):
        """
        Setter for grid size
        """
        self._drawing_grid_size = grid_size

    @property
    def show_interface_labels(self):
        """
        Show interface labels mode
        :return: bool
        """
        return self._show_interface_labels

    @show_interface_labels.setter
    def show_interface_labels(self, show_interface_labels):
        """
        Setter for show interface labels
        """
        self._show_interface_labels = show_interface_labels

    @property
    def variables(self):
        """
        Variables applied to the project
        :return: list
        """
        return self._variables

    @variables.setter
    def variables(self, variables):
        """
        Setter for variables applied to the project
        """
        self._variables = variables

    @property
    def supplier(self):
        """
        Supplier of the project
        :return: dict
        """
        return self._supplier

    @supplier.setter
    def supplier(self, supplier):
        """
        Setter for supplier of the project
        """
        self._supplier = supplier

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
        Should project automatically closed when client
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

        if self._status == "closed":
            return self._get_closed_data("computes", "compute_id").values()
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
        if base_name in self._allocated_node_names:
            base_name = re.sub(r"[0-9]+$", "{0}", base_name)

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
    async def add_node_from_template(self, template_id, x=0, y=0, name=None, compute_id=None):
        """
        Create a node from a template.
        """
        try:
            template = copy.deepcopy(self.controller.template_manager.templates[template_id].settings)
        except KeyError:
            msg = "Template {} doesn't exist".format(template_id)
            log.error(msg)
            raise aiohttp.web.HTTPNotFound(text=msg)
        template["x"] = x
        template["y"] = y
        node_type = template.pop("template_type")
        if template.pop("builtin", False) is True:
            # compute_id is selected by clients for builtin templates
            compute = self.controller.get_compute(compute_id)
        else:
            compute = self.controller.get_compute(template.pop("compute_id", compute_id))
        template_name = template.pop("name")
        default_name_format = template.pop("default_name_format", "{name}-{0}")
        if name is None:
            name = default_name_format.replace("{name}", template_name)
        node_id = str(uuid.uuid4())
        node = await self.add_node(compute, name, node_id, node_type=node_type, **template)
        return node

    async def _create_node(self, compute, name, node_id, node_type=None, **kwargs):

        node = Node(self, compute, name, node_id=node_id, node_type=node_type, **kwargs)
        if compute not in self._project_created_on_compute:
            # For a local server we send the project path
            if compute.id == "local":
                data = {
                    "name": self._name,
                    "project_id": self._id,
                    "path": self._path
                }
            else:
                data = {
                    "name": self._name,
                    "project_id": self._id
                }

            if self._variables:
                data["variables"] = self._variables

            await compute.post("/projects", data=data)
            self._project_created_on_compute.add(compute)

        await node.create()
        self._nodes[node.id] = node

        return node

    @open_required
    async def add_node(self, compute, name, node_id, dump=True, node_type=None, **kwargs):
        """
        Create a node or return an existing node

        :param dump: Dump topology to disk
        :param kwargs: See the documentation of node
        """

        if node_id in self._nodes:
            return self._nodes[node_id]

        if compute.id not in self._computes:
            self._computes.append(compute.id)

        if node_type == "iou":
            async with self._iou_id_lock:
                # wait for a IOU node to be completely created before adding a new one
                # this is important otherwise we allocate the same application ID (used
                # to generate MAC addresses) when creating multiple IOU node at the same time
                if "properties" in kwargs.keys():
                    # allocate a new application id for nodes loaded from the project
                    kwargs.get("properties")["application_id"] = get_next_application_id(self._controller.projects, self._computes)
                elif "application_id" not in kwargs.keys() and not kwargs.get("properties"):
                    # allocate a new application id for nodes added to the project
                    kwargs["application_id"] = get_next_application_id(self._controller.projects, self._computes)
                node = await self._create_node(compute, name, node_id, node_type, **kwargs)
        else:
            node = await self._create_node(compute, name, node_id, node_type, **kwargs)
        self.emit_notification("node.created", node.__json__())
        if dump:
            self.dump()
        return node

    @locking
    async def __delete_node_links(self, node):
        """
        Delete all link connected to this node.

        The operation use a lock to avoid cleaning links from
        multiple nodes at the same time.
        """
        for link in list(self._links.values()):
            if node in link.nodes:
                await self.delete_link(link.id, force_delete=True)

    @open_required
    async def delete_node(self, node_id):
        node = self.get_node(node_id)
        if node.locked:
            raise aiohttp.web.HTTPConflict(text="Node {} cannot be deleted because it is locked".format(node.name))
        await self.__delete_node_links(node)
        self.remove_allocated_node_name(node.name)
        del self._nodes[node.id]
        await node.destroy()
        # refresh the compute IDs list
        self._computes = [n.compute.id for n in self.nodes.values()]
        self.dump()
        self.emit_notification("node.deleted", node.__json__())

    @open_required
    def get_node(self, node_id):
        """
        Return the node or raise a 404 if the node is unknown
        """
        try:
            return self._nodes[node_id]
        except KeyError:
            raise aiohttp.web.HTTPNotFound(text="Node ID {} doesn't exist".format(node_id))

    def _get_closed_data(self, section, id_key):
        """
        Get the data for a project from the .gns3 when
        the project is close

        :param section: The section name in the .gns3
        :param id_key: The key for the element unique id
        """

        try:
            path = self._topology_file()
            with open(path, "r") as f:
                topology = json.load(f)
        except OSError as e:
            raise aiohttp.web.HTTPInternalServerError(text="Could not load topology: {}".format(e))

        try:
            data = {}
            for elem in topology["topology"][section]:
                data[elem[id_key]] = elem
            return data
        except KeyError:
            raise aiohttp.web.HTTPNotFound(text="Section {} not found in the topology".format(section))

    @property
    def nodes(self):
        """
        :returns: Dictionary of the nodes
        """
        if self._status == "closed":
            return self._get_closed_data("nodes", "node_id")
        return self._nodes

    @property
    def drawings(self):
        """
        :returns: Dictionary of the drawings
        """
        if self._status == "closed":
            return self._get_closed_data("drawings", "drawing_id")
        return self._drawings

    @open_required
    async def add_drawing(self, drawing_id=None, dump=True, **kwargs):
        """
        Create an drawing or return an existing drawing

        :param dump: Dump the topology to disk
        :param kwargs: See the documentation of drawing
        """
        if drawing_id not in self._drawings:
            drawing = Drawing(self, drawing_id=drawing_id, **kwargs)
            self._drawings[drawing.id] = drawing
            self.emit_notification("drawing.created", drawing.__json__())
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
    async def delete_drawing(self, drawing_id):
        drawing = self.get_drawing(drawing_id)
        if drawing.locked:
            raise aiohttp.web.HTTPConflict(text="Drawing ID {} cannot be deleted because it is locked".format(drawing_id))
        del self._drawings[drawing.id]
        self.dump()
        self.emit_notification("drawing.deleted", drawing.__json__())

    @open_required
    async def add_link(self, link_id=None, dump=True):
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
    async def delete_link(self, link_id, force_delete=False):
        link = self.get_link(link_id)
        del self._links[link.id]
        try:
            await link.delete()
        except Exception:
            if force_delete is False:
                raise
        self.dump()
        self.emit_notification("link.deleted", link.__json__())

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
        if self._status == "closed":
            return self._get_closed_data("links", "link_id")
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
    async def snapshot(self, name):
        """
        Snapshot the project

        :param name: Name of the snapshot
        """

        if name in [snap.name for snap in self._snapshots.values()]:
            raise aiohttp.web.HTTPConflict(text="The snapshot name {} already exists".format(name))
        snapshot = Snapshot(self, name=name)
        await snapshot.create()
        self._snapshots[snapshot.id] = snapshot
        return snapshot

    @open_required
    async def delete_snapshot(self, snapshot_id):
        snapshot = self.get_snapshot(snapshot_id)
        del self._snapshots[snapshot.id]
        os.remove(snapshot.path)

    @locking
    async def close(self, ignore_notification=False):
        if self._status == "closed" or self._closing:
            return
        if self._loading:
            log.warning("Closing project '{}' ignored because it is being loaded".format(self.name))
            return
        self._closing = True
        await self.stop_all()
        for compute in list(self._project_created_on_compute):
            try:
                await compute.post("/projects/{}/close".format(self._id), dont_connect=True)
            # We don't care if a compute is down at this step
            except (ComputeError, aiohttp.web.HTTPError, aiohttp.ClientResponseError, TimeoutError):
                pass
        self._clean_pictures()
        self._status = "closed"
        if not ignore_notification:
            self.emit_notification("project.closed", self.__json__())
        self.reset()
        self._closing = False

    def _clean_pictures(self):
        """
        Delete unused pictures.
        """

        # Project have been deleted or is loading or is not opened
        if not os.path.exists(self.path) or self._loading or self._status != "opened":
            return
        try:
            pictures = set(os.listdir(self.pictures_directory))
            for drawing in self._drawings.values():
                try:
                    resource_filename = drawing.resource_filename
                    if resource_filename:
                        pictures.remove(resource_filename)
                except KeyError:
                    pass

            # don't remove supplier's logo
            if self.supplier:
                try:
                    logo = self.supplier['logo']
                    pictures.remove(logo)
                except KeyError:
                    pass

            for pic_filename in pictures:
                path = os.path.join(self.pictures_directory, pic_filename)
                log.info("Deleting unused picture '{}'".format(path))
                os.remove(path)
        except OSError as e:
            log.warning("Could not delete unused pictures: {}".format(e))

    async def delete(self):

        if self._status != "opened":
            try:
                await self.open()
            except aiohttp.web.HTTPConflict as e:
                # ignore missing images or other conflicts when deleting a project
                log.warning("Conflict while deleting project: {}".format(e.text))
        await self.delete_on_computes()
        await self.close()
        try:
            project_directory = get_default_project_directory()
            if not os.path.commonprefix([project_directory, self.path]) == project_directory:
                raise aiohttp.web.HTTPConflict(text="Project '{}' cannot be deleted because it is not in the default project directory: '{}'".format(self._name, project_directory))
            shutil.rmtree(self.path)
        except OSError as e:
            raise aiohttp.web.HTTPConflict(text="Cannot delete project directory {}: {}".format(self.path, str(e)))

    async def delete_on_computes(self):
        """
        Delete the project on computes but not on controller
        """
        for compute in list(self._project_created_on_compute):
            if compute.id != "local":
                await compute.delete("/projects/{}".format(self._id))
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

    @locking
    async def open(self):
        """
        Load topology elements
        """

        if self._closing is True:
            raise aiohttp.web.HTTPConflict(text="Project is closing, please try again in a few seconds...")

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
            project_data = load_topology(path)

            #load meta of project
            keys_to_load = [
                "auto_start",
                "auto_close",
                "auto_open",
                "scene_height",
                "scene_width",
                "zoom",
                "show_layers",
                "snap_to_grid",
                "show_grid",
                "grid_size",
                "drawing_grid_size",
                "show_interface_labels"
            ]

            for key in keys_to_load:
                val = project_data.get(key, None)
                if val is not None:
                    setattr(self, key, val)

            topology = project_data["topology"]
            for compute in topology.get("computes", []):
                await self.controller.add_compute(**compute)

            # Get all compute used in the project
            # used to allocate application IDs for IOU nodes.
            for node in topology.get("nodes", []):
                compute_id = node.get("compute_id")
                if compute_id not in self._computes:
                    self._computes.append(compute_id)

            for node in topology.get("nodes", []):
                compute = self.controller.get_compute(node.pop("compute_id"))
                name = node.pop("name")
                node_id = node.pop("node_id", str(uuid.uuid4()))
                await self.add_node(compute, name, node_id, dump=False, **node)
            for link_data in topology.get("links", []):
                if 'link_id' not in link_data.keys():
                    # skip the link
                    continue
                link = await self.add_link(link_id=link_data["link_id"])
                if "filters" in link_data:
                    await link.update_filters(link_data["filters"])
                if "link_style" in link_data:
                    await link.update_link_style(link_data["link_style"])
                for node_link in link_data.get("nodes", []):
                    node = self.get_node(node_link["node_id"])
                    port = node.get_port(node_link["adapter_number"], node_link["port_number"])
                    if port is None:
                        log.warning("Port {}/{} for {} not found".format(node_link["adapter_number"], node_link["port_number"], node.name))
                        continue
                    if port.link is not None:
                        log.warning("Port {}/{} is already connected to link ID {}".format(node_link["adapter_number"], node_link["port_number"], port.link.id))
                        continue
                    await link.add_node(node, node_link["adapter_number"], node_link["port_number"], label=node_link.get("label"), dump=False)
                if len(link.nodes) != 2:
                    # a link should have 2 attached nodes, this can happen with corrupted projects
                    await self.delete_link(link.id, force_delete=True)
            for drawing_data in topology.get("drawings", []):
                await self.add_drawing(dump=False, **drawing_data)

            self.dump()
        # We catch all error to be able to rollback the .gns3 to the previous state
        except Exception as e:
            for compute in list(self._project_created_on_compute):
                try:
                    await compute.post("/projects/{}/close".format(self._id))
                # We don't care if a compute is down at this step
                except (ComputeError, aiohttp.web.HTTPNotFound, aiohttp.web.HTTPConflict, aiohttp.ServerDisconnectedError):
                    pass
            try:
                if os.path.exists(path + ".backup"):
                    shutil.copy(path + ".backup", path)
            except OSError:
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
            asyncio.ensure_future(self.start_all())

    async def wait_loaded(self):
        """
        Wait until the project finish loading
        """
        while self._loading:
            await asyncio.sleep(0.5)

    async def duplicate(self, name=None, location=None, reset_mac_addresses=True):
        """
        Duplicate a project

        It's the save as feature of the 1.X. It's implemented on top of the
        export / import features. It will generate a gns3p and reimport it.
        It's a little slower but we have only one implementation to maintain.

        :param name: Name of the new project. A new one will be generated in case of conflicts
        :param location: Parent directory of the new project
        :param reset_mac_addresses: Reset MAC addresses for the new project
        """
        # If the project was not open we open it temporary
        previous_status = self._status
        if self._status == "closed":
            await self.open()

        self.dump()
        assert self._status != "closed"
        try:
            begin = time.time()

            # use the parent directory of the project we are duplicating as a
            # temporary directory to avoid no space left issues when '/tmp'
            # is location on another partition.
            if location:
                working_dir = os.path.abspath(os.path.join(location, os.pardir))
            else:
                working_dir = os.path.abspath(os.path.join(self.path, os.pardir))

            with tempfile.TemporaryDirectory(dir=working_dir) as tmpdir:
                # Do not compress the exported project when duplicating
                with aiozipstream.ZipFile(compression=zipfile.ZIP_STORED) as zstream:
                    await export_project(zstream, self, tmpdir, keep_compute_id=True, allow_all_nodes=True, reset_mac_addresses=reset_mac_addresses)

                    # export the project to a temporary location
                    project_path = os.path.join(tmpdir, "project.gns3p")
                    log.info("Exporting project to '{}'".format(project_path))
                    async with aiofiles.open(project_path, 'wb') as f:
                        async for chunk in zstream:
                            await f.write(chunk)

                    # import the temporary project
                    with open(project_path, "rb") as f:
                        project = await import_project(self._controller, str(uuid.uuid4()), f, location=location, name=name, keep_compute_id=True)

            log.info("Project '{}' duplicated in {:.4f} seconds".format(project.name, time.time() - begin))
        except (ValueError, OSError, UnicodeEncodeError) as e:
            raise aiohttp.web.HTTPConflict(text="Cannot duplicate project: {}".format(str(e)))

        if previous_status == "closed":
            await self.close()

        return project

    def is_running(self):
        """
        If a node is started or paused return True
        """
        for node in self._nodes.values():
            # Some node type are always running we ignore them
            if node.status != "stopped" and not node.is_always_running():
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

    @open_required
    async def start_all(self):
        """
        Start all nodes
        """
        pool = Pool(concurrency=3)
        for node in self.nodes.values():
            pool.append(node.start)
        await pool.join()

    @open_required
    async def stop_all(self):
        """
        Stop all nodes
        """
        pool = Pool(concurrency=3)
        for node in self.nodes.values():
            pool.append(node.stop)
        await pool.join()

    @open_required
    async def suspend_all(self):
        """
        Suspend all nodes
        """
        pool = Pool(concurrency=3)
        for node in self.nodes.values():
            pool.append(node.suspend)
        await pool.join()

    @open_required
    async def reset_console_all(self):
        """
        Reset console for all nodes
        """

        pool = Pool(concurrency=3)
        for node in self.nodes.values():
            pool.append(node.reset_console)
        await pool.join()

    @open_required
    async def duplicate_node(self, node, x, y, z):
        """
        Duplicate a node

        :param node: Node instance
        :param x: X position
        :param y: Y position
        :param z: Z position
        :returns: New node
        """
        if node.status != "stopped" and not node.is_always_running():
            raise aiohttp.web.HTTPConflict(text="Cannot duplicate node data while the node is running")

        data = copy.deepcopy(node.__json__(topology_dump=True))
        # Some properties like internal ID should not be duplicated
        for unique_property in (
                'node_id',
                'name',
                'mac_addr',
                'mac_address',
                'compute_id',
                'application_id',
                'dynamips_id'):
            data.pop(unique_property, None)
            if 'properties' in data:
                data['properties'].pop(unique_property, None)
        node_type = data.pop('node_type')
        data['x'] = x
        data['y'] = y
        data['z'] = z
        data['locked'] = False  # duplicated node must not be locked
        new_node_uuid = str(uuid.uuid4())
        new_node = await self.add_node(node.compute,
                                       node.name,
                                       new_node_uuid,
                                       node_type=node_type,
                                       **data)
        try:
            await node.post("/duplicate", timeout=None, data={
                "destination_node_id": new_node_uuid
            })
        except aiohttp.web.HTTPNotFound as e:
            await self.delete_node(new_node_uuid)
            raise aiohttp.web.HTTPConflict(text="This node type cannot be duplicated")
        except aiohttp.web.HTTPConflict as e:
            await self.delete_node(new_node_uuid)
            raise e
        return new_node

    def stats(self):

        return {
            "nodes": len(self._nodes),
            "links": len(self._links),
            "drawings": len(self._drawings),
            "snapshots": len(self._snapshots)
        }

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
            "scene_width": self._scene_width,
            "zoom": self._zoom,
            "show_layers": self._show_layers,
            "snap_to_grid": self._snap_to_grid,
            "show_grid": self._show_grid,
            "grid_size": self._grid_size,
            "drawing_grid_size": self._drawing_grid_size,
            "show_interface_labels": self._show_interface_labels,
            "supplier": self._supplier,
            "variables": self._variables
        }

    def __repr__(self):
        return "<gns3server.controller.Project {} {}>".format(self._name, self._id)
