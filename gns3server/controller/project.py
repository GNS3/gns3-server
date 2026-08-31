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
import aiofiles
import tempfile
import zipfile
import pathlib

from uuid import UUID, uuid4
from fastapi import HTTPException, status

from .node import Node
from .compute import ComputeError
from .snapshot import Snapshot
from .drawing import Drawing
from .topology import project_to_topology, load_topology
from .udp_link import UDPLink
from .link import _UNSET
from ..config import Config
from ..utils.path import check_path_allowed, get_default_project_directory
from ..utils.application_id import get_next_application_id
from ..utils.asyncio.pool import Pool
from ..utils.packet_filter_validation import validate_bpf_syntax
from ..utils.asyncio import locking
from ..utils.asyncio import aiozipstream
from ..utils.asyncio import wait_run_in_executor
from .export_project import export_project
from .import_project import import_project, update_snapshots, regenerate_topology_ids
from .controller_error import ControllerError, ControllerForbiddenError, ControllerNotFoundError
from gns3server.agent.web_wireshark.manager import WebWiresharkManager

import logging

log = logging.getLogger(__name__)


def open_required(func):
    """
    Use this decorator to raise an error if the project is not opened
    """

    def wrapper(self, *args, **kwargs):
        if self._status == "closed":
            raise ControllerForbiddenError("The project is not opened")
        return func(self, *args, **kwargs)

    return wrapper


class Project:
    """
    A project inside a controller

    :param project_id: force project identifier (None by default auto generate an UUID)
    :param path: path of the project. (None use the standard directory)
    :param status: Status of the project (opened / closed)
    """

    def __init__(
        self,
        name=None,
        project_id=None,
        path=None,
        controller=None,
        status="opened",
        filename=None,
        auto_start=False,
        auto_open=False,
        auto_close=True,
        scene_height=1000,
        scene_width=2000,
        zoom=100,
        show_layers=False,
        snap_to_grid=False,
        show_grid=False,
        grid_size=75,
        drawing_grid_size=25,
        show_interface_labels=True,
        variables=None,
        supplier=None,
        created_by=None,
    ):

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
        self._created_by = created_by
        self._snapshots_config_file = "snapshots.conf"

        self._loading = False
        self._closing = False

        # Disallow overwrite of existing project
        if project_id is None and path is not None:
            if os.path.exists(path):
                raise ControllerForbiddenError(f"The path {path} already exists")
            else:
                raise ControllerForbiddenError("Providing a path to create a new project is deprecated.")

        if project_id is None:
            self._id = str(uuid4())
        else:
            try:
                UUID(project_id, version=4)
            except ValueError:
                raise ControllerError(f"{project_id} is not a valid UUID")
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
        # Serialise the "ensure project exists on this compute" check in
        # _create_node: without it, concurrent node creations all pass the
        # `compute not in _project_created_on_compute` check before any has
        # registered, and each fires a redundant POST /projects at the compute.
        self._create_node_lock = asyncio.Lock()
        self._preallocated_udp_ports = {}  # compute_id -> list of pre-allocated UDP ports
        log.debug(f'Project "{self.name}" [{self._id}] loaded')
        self.emit_controller_notification("project.created", self.asdict())

    def emit_notification(self, action, event):
        """
        Emit a project notification to all clients using this project.

        :param action: Action name
        :param event: Event to send
        """

        self._controller.notification.project_emit(action, event, project_id=self.id)

    def emit_controller_notification(self, action, event):
        """
        Emit a controller notification, all clients will see it.

        :param action: Action name
        :param event: Event to send
        """

        self._controller.notification.controller_emit(action, event)

    async def update(self, **kwargs):
        """
        Update the project
        :param kwargs: Project properties
        """

        old_json = self.asdict()

        for prop in kwargs:
            setattr(self, prop, kwargs[prop])

        # We send notif only if object has changed
        if old_json != self.asdict():
            self.emit_controller_notification("project.updated", self.asdict())
            self.dump()

            # Only notify computes if variables actually changed and have content
            # None and empty list are semantically equivalent (no variables) and don't affect running nodes
            if "variables" in kwargs and kwargs["variables"]:
                for compute in list(self._project_created_on_compute):
                    await compute.put(f"/projects/{self._id}", {"variables": self.variables})

    def reset(self):
        """
        Called when open/close a project. Cleanup internal stuff
        """
        self._allocated_node_names = set()
        self._nodes = {}
        self._links = {}
        self._marker_definitions = {}  # name → {bpf, tag, color, highlight_duration}
        self._drawings = {}
        self._snapshots = {}
        self._computes = []
        self._load_snapshot_config()
        # Create the project on demand on the compute node
        self._project_created_on_compute = set()
        self._preallocated_udp_ports = {}

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
    def created_by(self):
        """
        Username of the user who created the project
        :return: str or None
        """
        return self._created_by

    @created_by.setter
    def created_by(self, created_by):
        """
        Setter for the username of the user who created the project
        """
        self._created_by = created_by

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
        old_filename = self._filename
        self._name = val
        self._filename = val + ".gns3"

        # Rename the .gns3 file on disk when the project name changes
        if old_filename != self._filename:
            old_path = os.path.join(self._path, old_filename)
            new_path = os.path.join(self._path, self._filename)
            if os.path.exists(old_path):
                try:
                    shutil.move(old_path, new_path)
                    log.info(f"Project file renamed from '{old_filename}' to '{self._filename}'")
                except OSError as e:
                    log.warning(f"Could not rename project file from '{old_filename}' to '{self._filename}': {e}")
                    self._filename = old_filename

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

        # The projects directory itself (or one of its ancestors) must
        # never become a project directory: deleting such a "project"
        # would wipe every project on the controller.
        real_path = os.path.realpath(path)
        real_projects_path = os.path.realpath(get_default_project_directory())
        if os.path.commonpath([real_path, real_projects_path]) == real_path:
            raise ControllerForbiddenError(
                f"The project directory cannot be '{path}': it must be a subdirectory "
                f"of '{real_projects_path}', not the projects directory itself or one of its parents"
            )

        try:
            os.makedirs(path, exist_ok=True)
        except OSError as e:
            raise ControllerError(f"Could not create project directory: {e}")

        if '"' in path:
            raise ControllerForbiddenError(
                'You are not allowed to use " in the project directory path. Not supported by Dynamips.'
            )

        self._path = path

    @property
    def captures_directory(self):
        """
        Location of the captures files
        """
        path = os.path.join(self._path, "project-files", "captures")
        os.makedirs(path, exist_ok=True)
        return path

    @property
    def markers_directory(self):
        """
        Location of the marker pcap files (same layout the compute side writes
        via ``markers_working_directory`` — single-server deployments share the
        project directory, which is what tag replay reads).
        """
        path = os.path.join(self._path, "project-files", "markers")
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
        base_name = re.sub(r"[ ]", "", base_name)  # remove spaces in node name
        if base_name in self._allocated_node_names:
            base_name = re.sub(r"[0-9]+$", "{0}", base_name)

        if "{0}" in base_name or "{id}" in base_name:
            # base name is a template, replace {0} or {id} by an unique identifier
            for number in range(1, 1000000):
                try:
                    name = base_name.format(number, id=number, name="Node")
                except KeyError as e:
                    raise ControllerError("{" + e.args[0] + "} is not a valid replacement string in the node name")
                except (ValueError, IndexError):
                    raise ControllerError(f"{base_name} is not a valid replacement string in the node name")
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
        raise ControllerError("A node name could not be allocated (node limit reached?)")

    def update_node_name(self, node, new_name):

        if new_name and node.name != new_name:
            self.remove_allocated_node_name(node.name)
            return self.update_allocated_node_name(new_name)
        return new_name

    @open_required
    async def add_node_from_template(self, template, x=0, y=0, name=None, compute_id=None):
        """
        Create a node from a template.
        """
        template["x"] = x
        template["y"] = y
        node_type = template.pop("template_type")

        if compute_id:
            compute = self.controller.get_compute(compute_id)
        else:
            compute = self.controller.get_compute(template.pop("compute_id"))
        template_name = template.pop("name")
        log.info(f'Creating node from template "{template_name}" on compute "{compute.name}" [{compute.id}]')
        default_name_format = template.pop("default_name_format", "{name}-{0}")
        if name is None:
            name = default_name_format.replace("{name}", template_name)
        # the appliance metadata stays template level: only the default
        # credentials are seeded on the node (where they can be overridden)
        appliance_metadata = template.pop("appliance_metadata", None) or {}
        for field in ("default_username", "default_password"):
            if appliance_metadata.get(field):
                template[field] = appliance_metadata[field]
        node_id = str(uuid.uuid4())
        node = await self.add_node(compute, name, node_id, node_type=node_type, **template)
        return node

    async def _create_node(self, compute, name, node_id, node_type=None, **kwargs):

        node = Node(self, compute, name, node_id=node_id, node_type=node_type, **kwargs)
        # Hold the lock across the check + POST + register so that concurrent
        # node creations on the same compute don't all race past the check and
        # each POST /projects (the compute-side sync handler then instantiated
        # the Project N times). Once one creation registers the compute, the
        # rest see it in the set and return immediately.
        async with self._create_node_lock:
            if compute not in self._project_created_on_compute:
                if compute.id == "local":
                    data = {"name": self._name, "project_id": self._id, "path": self._path}
                else:
                    data = {"name": self._name, "project_id": self._id}
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
                # IOU application IDs must be allocated serially to avoid duplicates.
                # The lock must also cover _create_node() because get_next_application_id()
                # checks in-memory nodes (self._nodes), which are only registered
                # after _create_node() completes.
                if "properties" in kwargs.keys():
                    kwargs.get("properties")["application_id"] = get_next_application_id(
                        self._controller.projects, self._computes
                    )
                elif "application_id" not in kwargs.keys() and not kwargs.get("properties"):
                    kwargs["application_id"] = get_next_application_id(self._controller.projects, self._computes)
                node = await self._create_node(compute, name, node_id, node_type, **kwargs)
        else:
            node = await self._create_node(compute, name, node_id, node_type, **kwargs)
        self.emit_notification("node.created", node.asdict())
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
            raise ControllerError(f"Node {node.name} cannot be deleted because it is locked")
        await self.__delete_node_links(node)
        self.remove_allocated_node_name(node.name)
        del self._nodes[node.id]
        await node.destroy()
        # refresh the compute IDs list
        self._computes = [n.compute.id for n in self.nodes.values()]
        self.dump()
        self.emit_notification("node.deleted", node.asdict())

    @open_required
    def get_node(self, node_id):
        """
        Return the node or raise a 404 if the node is unknown
        """
        try:
            return self._nodes[node_id]
        except KeyError:
            raise ControllerNotFoundError(f"Node ID {node_id} doesn't exist")

    def _get_closed_data(self, section, id_key):
        """
        Get the data for a project from the .gns3 when
        the project is closed

        :param section: The section name in the .gns3
        :param id_key: The key for the element unique id
        """

        try:
            path = self._topology_file()
            with open(path) as f:
                topology = json.load(f)
        except OSError as e:
            raise ControllerError(f"Could not load topology: {e}")

        try:
            data = {}
            for elem in topology["topology"][section]:
                data[elem[id_key]] = elem
            return data
        except KeyError:
            raise ControllerNotFoundError(f"Section {section} not found in the topology")

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
            self.emit_notification("drawing.created", drawing.asdict())
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
            raise ControllerNotFoundError(f"Drawing ID {drawing_id} doesn't exist")

    @open_required
    async def delete_drawing(self, drawing_id):
        drawing = self.get_drawing(drawing_id)
        if drawing.locked:
            raise ControllerError(f"Drawing ID {drawing_id} cannot be deleted because it is locked")
        del self._drawings[drawing.id]
        self.dump()
        self.emit_notification("drawing.deleted", drawing.asdict())

    async def _create_link_from_topology_data(self, link_data):
        """
        Create a link from topology data (used during project loading).

        Extracted into a separate method so links can be created in parallel
        via Pool() during project.open().

        :param link_data: Link data from the topology file
        """
        link = await self.add_link(link_id=link_data["link_id"])
        if "filters" in link_data:
            try:
                await link.update_filters(link_data["filters"])
            except ControllerError as e:
                log.warning(
                    "Dropping invalid filters on link %s: %s",
                    link_data.get("link_id"), e
                )
        # Restore traffic-insight markers directly into link state (mirrors how
        # filters are restored via update_filters). The capture_node_id persisted
        # last time is reused for NIO routing; no side resolution is possible here
        # because the link's nodes are added later. The marker is applied to
        # uBridge by _ubridge_apply_markers when create() runs. Invalid BPF is
        # dropped (like invalid filters).
        for name, marker in (link_data.get("markers") or {}).items():
            bpf = marker.get("bpf")
            if not bpf:
                log.warning("Dropping marker %s on link %s: missing bpf", name, link_data.get("link_id"))
                continue
            result = validate_bpf_syntax(bpf)
            if not result.get("valid"):
                log.warning(
                    "Dropping marker %s on link %s: invalid BPF (%s)",
                    name, link_data.get("link_id"), result.get("error")
                )
                continue
            link._markers[name] = {
                "bpf": bpf,
                "tag": marker.get("tag"),
                "enabled": marker.get("enabled", True),
                "color": marker.get("color"),
                "highlight_duration": marker.get("highlight_duration"),
                "capture_node_id": marker.get("capture_node_id"),
                "direction": marker.get("direction"),
            }
        if "link_style" in link_data:
            await link.update_link_style(link_data["link_style"])
        if "show_filters_icon" in link_data:
            await link.update_show_filters_icon(link_data["show_filters_icon"])
        for node_link in link_data.get("nodes", []):
            node = self.get_node(node_link["node_id"])
            port = node.get_port(node_link["adapter_number"], node_link["port_number"])
            if port is None:
                log.warning(
                    "Port {}/{} for {} not found".format(
                        node_link["adapter_number"], node_link["port_number"], node.name
                    )
                )
                continue
            if port.link is not None:
                log.warning(
                    "Port {}/{} is already connected to link ID {}".format(
                        node_link["adapter_number"], node_link["port_number"], port.link.id
                    )
                )
                continue
            await link.add_node(
                node,
                node_link["adapter_number"],
                node_link["port_number"],
                label=node_link.get("label"),
                dump=False,
            )
        if len(link.nodes) != 2:
            # a link should have 2 attached nodes, this can happen with corrupted projects
            await self.delete_link(link.id, force_delete=True)

    async def _prepare_link_from_topology(self, link_data):
        """
        Build a link locally from topology data WITHOUT dispatching NIOs to the
        computes.  Returns ``(link, entries)`` where ``entries`` is the list of
        ``(node, adapter_number, port_number, nio_data)`` tuples produced by
        ``UDPLink._prepare()``, or ``None`` if the link is invalid/incomplete.

        Used by the project-open bulk path so all NIOs can be sent in a single
        batch HTTP call per compute instead of one round-trip per link.
        """

        link = await self.add_link(link_id=link_data["link_id"], dump=False)
        if "filters" in link_data:
            try:
                await link.update_filters(link_data["filters"])
            except ControllerError as e:
                log.warning("Dropping invalid filters on link %s: %s", link_data.get("link_id"), e)
        for name, marker in (link_data.get("markers") or {}).items():
            bpf = marker.get("bpf")
            if not bpf:
                log.warning("Dropping marker %s on link %s: missing bpf", name, link_data.get("link_id"))
                continue
            result = validate_bpf_syntax(bpf)
            if not result.get("valid"):
                log.warning(
                    "Dropping marker %s on link %s: invalid BPF (%s)",
                    name, link_data.get("link_id"), result.get("error")
                )
                continue
            link._markers[name] = {
                "bpf": bpf,
                "tag": marker.get("tag"),
                "enabled": marker.get("enabled", True),
                "color": marker.get("color"),
                "highlight_duration": marker.get("highlight_duration"),
                "capture_node_id": marker.get("capture_node_id"),
                "direction": marker.get("direction"),
            }
        # Set style/icon directly: the update_* helpers unconditionally dump
        # the whole topology and emit "link.updated", neither of which is
        # appropriate mid-prepare (the link is finalised, notified and the
        # project dumped once at the end of open).
        if "link_style" in link_data:
            link._link_style = link_data["link_style"]
        if "show_filters_icon" in link_data:
            link._show_filters_icon = link_data["show_filters_icon"]
        for node_link in link_data.get("nodes", []):
            node = self.get_node(node_link["node_id"])
            port = node.get_port(node_link["adapter_number"], node_link["port_number"])
            if port is None:
                log.warning(
                    "Port {}/{} for {} not found".format(
                        node_link["adapter_number"], node_link["port_number"], node.name
                    )
                )
                continue
            if port.link is not None:
                log.warning(
                    "Port {}/{} is already connected to link ID {}".format(
                        node_link["adapter_number"], node_link["port_number"], port.link.id
                    )
                )
                continue
            # batch=True: attach the node without triggering per-link NIO HTTP
            await link.add_node(
                node,
                node_link["adapter_number"],
                node_link["port_number"],
                label=node_link.get("label"),
                dump=False,
                batch=True,
            )
        if len(link.nodes) != 2:
            # a link should have 2 attached nodes, this can happen with corrupted projects
            await self.delete_link(link.id, force_delete=True)
            return None
        # Apply project-level marker definitions onto the link's memory
        # (memory_only) before _prepare() so the inherited markers ride the
        # batch NIO dispatch — zero extra HTTP round-trips.  The final
        # apply_defs_to_new_link in finalize is removed.
        for def_name, d in self._marker_definitions.items():
            try:
                await link.inherit_marker(def_name, d, dump=False, memory_only=True)
            except ControllerError as e:
                log.warning("Marker definition '%s' could not be applied to link %s: %s", def_name, link.id, e)
        entries = await link._prepare()
        return (link, entries)

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

    async def preallocate_udp_ports_for_compute(self, compute, count):
        """
        Pre-allocate UDP ports from a compute in a single batch call.

        Used during project loading to reduce HTTP round-trips when
        creating many links.

        :param compute: Compute instance
        :param count: Number of UDP ports to pre-allocate
        """
        if count <= 0:
            return
        response = await compute.post(f"/projects/{self._id}/ports/udp/batch", data={"count": count})
        ports = response.json["udp_ports"]
        self._preallocated_udp_ports.setdefault(compute.id, [])
        self._preallocated_udp_ports[compute.id].extend(ports)

    def pop_preallocated_udp_port(self, compute_id):
        """
        Pop a pre-allocated UDP port for a compute.

        :param compute_id: Compute ID
        :returns: UDP port number or None if no pre-allocated port is available
        """
        ports = self._preallocated_udp_ports.get(compute_id, [])
        if ports:
            return ports.pop()
        return None

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
        self.emit_notification("link.deleted", link.asdict())

    @open_required
    def get_link(self, link_id):
        """
        Return the Link or raise a 404 if the link is unknown
        """
        try:
            return self._links[link_id]
        except KeyError:
            raise ControllerNotFoundError(f"Link ID {link_id} doesn't exist")

    @property
    def links(self):
        """
        :returns: Dictionary of the Links
        """
        if self._status == "closed":
            return self._get_closed_data("links", "link_id")
        return self._links

    @property
    def markers(self):
        """
        Project-level read-only aggregation of all markers across every link.

        Each entry is keyed ``"{link_id}/{marker_name}"`` so the flat dict is
        globally unique within the project.  The value is a clone of the link's
        per-marker dict plus ``link_id`` and ``node_id`` (the capture-side node)
        for convenience — the frontend can filter/group by link or node without
        extra round-trips.

        :returns: dict[str, dict] — keyed by "{link_id}/{marker_name}"
        """
        result = {}
        for link_id, link in self._links.items():
            for name, info in link.markers.items():
                key = f"{link_id}/{name}"
                result[key] = {
                    **info,
                    "link_id": link_id,
                    "node_id": info.get("capture_node_id"),
                }
        return result

    async def pause_marker_definition(self, name):
        """
        Pause every inherited copy of a definition (``global-{name}``) on every
        link: toggle each filter off in place via ``update_marker(enabled=False)``
        — uBridge ``enable_packet_filter off``, no NIO rebuild, pcap/emitted
        preserved. The definition's ``paused`` flag is persisted, so links
        created later inherit the marker already paused.
        """

        if name not in self._marker_definitions:
            raise ControllerError(f"Marker definition '{name}' not found")
        self._marker_definitions[name]["paused"] = True
        marker_name = f"global-{name}"
        affected = [
            link for link in self._links.values()
            if marker_name in link.markers and link.markers[marker_name].get("inherited_from") == name
        ]
        await self._marker_apply_concurrently(
            affected,
            lambda link: link.update_marker(marker_name, enabled=False, inherited=True, dump=False),
            lambda link, e: f"Failed to pause marker {marker_name} on link {link.id}: {e}",
        )
        self.dump()
        self.emit_notification("project.updated", self.asdict())

    async def resume_marker_definition(self, name):
        """Resume every inherited copy of a definition (toggle on)."""

        if name not in self._marker_definitions:
            raise ControllerError(f"Marker definition '{name}' not found")
        self._marker_definitions[name]["paused"] = False
        marker_name = f"global-{name}"
        affected = [
            link for link in self._links.values()
            if marker_name in link.markers and link.markers[marker_name].get("inherited_from") == name
        ]
        await self._marker_apply_concurrently(
            affected,
            lambda link: link.update_marker(marker_name, enabled=True, inherited=True, dump=False),
            lambda link, e: f"Failed to resume marker {marker_name} on link {link.id}: {e}",
        )
        self.dump()
        self.emit_notification("project.updated", self.asdict())

    @property
    def marker_definitions(self):
        """
        :returns: dict of project-level marker definitions (name → {bpf, tag, color, highlight_duration})
        """
        return self._marker_definitions

    def _validate_marker_definition_bpf(self, name, bpf):
        """
        Validate a marker definition's BPF once, here, so the fan-out to every
        link (``_apply_def_to_all_links`` → ``inherit_marker`` → ``start_marker``)
        and the per-link sync (``update_marker_definition`` → ``update_marker``)
        can skip re-validation for the inherited copies — otherwise one
        ``tcpdump -d`` subprocess runs per link for the same expression. A
        private per-link marker still validates in ``start_marker``/``update_marker``.
        """
        result = validate_bpf_syntax(bpf)
        if not result.get("valid"):
            raise ControllerError(
                f"Marker definition '{name}': invalid BPF — {result.get('error', 'unknown error')}"
            )

    def _validate_marker_definition_direction(self, name, direction):
        """
        Reject tx/rx on a marker definition: a definition fans out to every link
        and auto-selects its capture node on each (``_choose_marker_side``),
        while tx/rx is relative to that node, so a fixed direction has no
        consistent meaning across links. Only 'both' (the default, = ``None``)
        is allowed — encode the direction in the BPF instead (e.g.
        ``icmp[icmptype]==8`` for echo requests), or use a per-link marker whose
        capture node is pinned.
        """
        if direction in ("tx", "rx"):
            raise ControllerError(
                f"Marker definition '{name}': direction '{direction}' is not allowed. "
                "A definition fans out to every link and auto-selects its capture node on each, "
                "but tx/rx is relative to that node, so a fixed direction has no consistent "
                "meaning across links. Keep 'both' (the default) and encode the direction in "
                "the BPF instead, e.g. 'icmp and icmp[icmptype]==8' for echo requests only. "
                "For a capture-node-relative direction on a single link, use a per-link marker."
            )

    async def create_marker_definition(self, name, bpf, tag=None, direction=None, color=None, highlight_duration=None, data_link_type="DLT_EN10MB"):
        """
        Create a project-level marker definition and fan out to every existing
        link that has a capable node.  Links without a capable node are silently
        skipped.
        """

        if name in self._marker_definitions:
            raise ControllerError(
                f"Marker definition '{name}' already exists in this project"
            )

        self._validate_marker_definition_bpf(name, bpf)
        self._validate_marker_definition_direction(name, direction)
        self._marker_definitions[name] = {"bpf": bpf, "tag": tag, "direction": direction, "color": color, "highlight_duration": highlight_duration, "data_link_type": data_link_type, "paused": False}
        await self._apply_def_to_all_links(name)
        self.dump()
        self.emit_notification("project.updated", self.asdict())

    async def update_marker_definition(self, name, bpf=None, tag=None, direction=_UNSET, color=None, highlight_duration=None, data_link_type=_UNSET):
        """
        Update a marker definition and sync every inherited copy on every link.
        """

        if name not in self._marker_definitions:
            raise ControllerNotFoundError(
                f"Marker definition '{name}' not found in this project"
            )

        d = self._marker_definitions[name]
        if bpf is not None:
            self._validate_marker_definition_bpf(name, bpf)
            d["bpf"] = bpf
        if tag is not None:
            d["tag"] = tag
        if color is not None:
            d["color"] = color
        if highlight_duration is not None:
            d["highlight_duration"] = highlight_duration
        if direction is not _UNSET:
            self._validate_marker_definition_direction(name, direction)
            d["direction"] = direction  # None = clear back to both directions
        if data_link_type is not _UNSET:
            d["data_link_type"] = data_link_type

        # Links that currently carry an inherited copy of this definition.
        affected = [
            link for link in self._links.values()
            if f"global-{name}" in link.markers
            and link.markers[f"global-{name}"].get("inherited_from") == name
        ]

        if data_link_type is not _UNSET:
            # data_link_type decides which links host an inherited copy (serial
            # links are skipped unless a WAN encapsulation is chosen), so a change
            # needs a full re-fan-out: drop every copy, then re-apply.
            for link in affected:
                try:
                    await link.stop_marker(f"global-{name}", inherited=True, dump=False, memory_only=True)
                except ControllerError as e:
                    log.warning("Failed to remove inherited marker global-%s from link %s: %s", name, link.id, e)
            await self._apply_def_to_all_links(name)
        else:
            # Sync: update every inherited copy across all links in memory, then
            # batch-push to computes (one PUT /nios/batch per compute).
            for link in affected:
                try:
                    await link.update_marker(
                        f"global-{name}", bpf=d["bpf"], tag=d.get("tag"), direction=d.get("direction"),
                        color=d.get("color"), highlight_duration=d.get("highlight_duration"), inherited=True,
                        dump=False, memory_only=True
                    )
                except ControllerError as e:
                    log.warning("Failed to sync marker global-%s on link %s: %s", name, link.id, e)
            await self._batch_update_link_nios(affected)
        self.dump()
        self.emit_notification("project.updated", self.asdict())

    async def delete_marker_definition(self, name):
        """
        Delete a marker definition and remove every inherited copy from every link.
        """

        if name not in self._marker_definitions:
            raise ControllerNotFoundError(
                f"Marker definition '{name}' not found in this project"
            )

        del self._marker_definitions[name]

        affected = [
            link for link in self._links.values()
            if f"global-{name}" in link.markers
            and link.markers[f"global-{name}"].get("inherited_from") == name
        ]
        for link in affected:
            try:
                await link.stop_marker(f"global-{name}", inherited=True, memory_only=True)
            except ControllerError as e:
                # A missing compute or broken link shouldn't block the delete.
                log.warning("Failed to remove inherited marker global-%s from link %s: %s", name, link.id, e)
        await self._batch_update_link_nios(affected)

        self.dump()
        self.emit_notification("project.updated", self.asdict())

    async def _apply_def_to_all_links(self, def_name):
        """
        Fan out a single marker definition to every existing link in the project.
        Links that have no capable node (``_MARKER_CAPABLE_TYPES``) are silently
        skipped — the marker can only live on a uBridge bridge.

        Two-phase to avoid one HTTP round-trip per link end: (1) write the
        inherited marker into each link's memory (``memory_only`` refreshes
        ``_link_data`` without pushing), then (2) batch-update every affected
        NIO via a single ``PUT /projects/{id}/nios/batch`` per compute.
        """

        d = self._marker_definitions[def_name]
        affected = []
        for link in self._links.values():
            try:
                await link.inherit_marker(def_name, d, dump=False, memory_only=True)
                affected.append(link)
            except ControllerError as e:
                log.warning("Marker definition '%s' could not be applied to link %s: %s", def_name, link.id, e)
        await self._batch_update_link_nios(affected)

    async def _batch_update_link_nios(self, links):
        """
        Push the current ``_link_data`` (markers/filters) of *links* to their
        computes in one ``PUT /projects/{id}/nios/batch`` per compute — replacing
        one PUT /nio round-trip per link end. Started nodes re-apply uBridge;
        stopped nodes update in memory.
        """

        per_compute = {}
        for link in links:
            if len(link._link_data) < 2:
                continue
            for i, side in enumerate(link._nodes):
                node = side["node"]
                per_compute.setdefault(node.compute, []).append(
                    {
                        "node_id": node.id,
                        "adapter_number": side["adapter_number"],
                        "port_number": side["port_number"],
                        "nio": link._link_data[i],
                    }
                )

        async def _dispatch(compute, entries):
            await compute.put(
                f"/projects/{self._id}/nios/batch",
                data={"nios": entries},
                timeout=300,
            )

        if per_compute:
            await asyncio.gather(
                *[_dispatch(c, n) for c, n in per_compute.items()]
            )

    async def apply_defs_to_new_link(self, link):
        """
        Apply every active marker definition to a newly created link so it
        inherits project-level rules automatically.

        Deliberately serial: all definitions share the same link, and each
        ``inherit_marker`` pushes the link's full marker set — concurrent
        pushes would race (a later push overwriting an earlier one's spec and
        losing markers).
        """

        for def_name, d in self._marker_definitions.items():
            try:
                # dump=False: the caller (link create / project open) dumps once
                # after; per-def dumps here would be N full topology writes.
                await link.inherit_marker(def_name, d, dump=False)
            except ControllerError as e:
                log.warning(
                    "Marker definition '%s' could not be applied to new link %s: %s",
                    def_name, link.id, e
                )

    async def _marker_apply_concurrently(self, links, operation, fail_msg):
        """
        Run an async per-link marker operation across *links* with bounded
        concurrency. A serial loop takes N sequential compute round-trips — a
        definition over 1000 links would take minutes on remote computes — so
        fan out in parallel batches. Links are independent (own ``_markers`` /
        ``_link_data``), so this is race-free; per-link ``ControllerError`` is
        logged and skipped, preserving the serial loop's isolation semantics.
        ``Project.dump`` is synchronous and writes atomically (tmp + rename),
        so concurrent dumps from the fan-out cannot corrupt the topology file.

        :param links: iterable of links to operate on
        :param operation: async callable ``(link) -> coroutine``
        :param fail_msg: callable ``(link, error) -> log message``
        """

        links = list(links)
        if not links:
            return
        _t0 = time.time()
        log.info(
            "Project '%s' [%s]: fanning out marker operation to %d links...",
            self._name, self._id, len(links)
        )
        sem = asyncio.Semaphore(32)

        async def guarded(link):
            async with sem:
                try:
                    await operation(link)
                except ControllerError as e:
                    log.warning(fail_msg(link, e))

        await asyncio.gather(*(guarded(link) for link in links))
        log.info(
            "Project '%s' [%s]: marker fan-out done in %.2fs",
            self._name, self._id, time.time() - _t0
        )

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
            raise ControllerNotFoundError(f"Snapshot ID {snapshot_id} doesn't exist")

    def _load_snapshot_config(self):

        snapshot_dir = os.path.join(self.path, "snapshots")
        self._snapshot_conf_path = os.path.join(snapshot_dir, self._snapshots_config_file)
        self._snapshot_conf = []
        if os.path.isfile(self._snapshot_conf_path):
            try:
                with open(self._snapshot_conf_path, encoding="utf-8") as f:
                    self._snapshot_conf = json.load(f)
            except (OSError, UnicodeDecodeError, ValueError) as e:
                raise ControllerError(f"Could not read snapshot config {e}")

        # Load all legacy snapshots (.gns3project files) to create an initial snapshot config if it doesn't exist
        if os.path.exists(snapshot_dir) and not self._snapshot_conf:
            for snap in os.listdir(snapshot_dir):
                if snap.endswith(".gns3project"):
                    try:
                        snapshot = Snapshot(self, filename=snap)
                    except ValueError:
                        log.error("Invalid snapshot file: {}".format(snap))
                        continue
                    self._snapshots[snapshot.id] = snapshot
        else:
            # Create the Snapshot instances from the snapshot config file
            for snapshot_entry in self._snapshot_conf:
                try:
                    path = os.path.join(snapshot_dir, snapshot_entry["filename"])
                    if not os.path.isfile(path):
                        log.warning("Snapshot file '{}' does not exist".format(path))
                        continue
                    snapshot_entry.pop("project_id")
                    snapshot = Snapshot(self, **snapshot_entry)
                    self._snapshots[snapshot.id] = snapshot
                except KeyError:
                    log.error("Invalid entry in snapshot config file: {}".format(snapshot_entry))
                    continue

        self._save_snapshot_config()

    def _save_snapshot_config(self):

        if not self._snapshots:
            return

        self._snapshot_conf = []
        for snapshot in self._snapshots.values():
            self._snapshot_conf.append(snapshot.asdict())
        try:
            with open(self._snapshot_conf_path, 'w+') as f:
                json.dump(self._snapshot_conf, f, indent=4)
        except OSError as e:
            log.error("Cannot write snapshot config '{}': {}".format(self._snapshot_conf_path, e))

    @open_required
    async def snapshot(self, name):
        """
        Snapshot the project

        :param name: Name of the snapshot
        """

        if name in [snap.name for snap in self._snapshots.values()]:
            raise ControllerError(f"The snapshot name {name} already exists")
        snapshot = Snapshot(self, name=name)
        await snapshot.create()
        self._snapshots[snapshot.id] = snapshot
        self._save_snapshot_config()
        return snapshot

    @open_required
    async def delete_snapshot(self, snapshot_id):
        snapshot = self.get_snapshot(snapshot_id)
        del self._snapshots[snapshot.id]
        self._save_snapshot_config()
        os.remove(snapshot.path)

    @locking
    async def close(self, ignore_notification=False):
        if self._status == "closed" or self._closing:
            return
        if self._loading:
            log.warning(f"Closing project '{self.name}' ignored because it is being loaded")
            return
        self._closing = True
        log.info("Project '%s' [%s]: closing...", self._name, self._id)
        try:
            await self.stop_all()
        except HTTPException as e:
            if not e.status_code == status.HTTP_405_METHOD_NOT_ALLOWED:
                raise
        for compute in list(self._project_created_on_compute):
            try:
                await compute.post(f"/projects/{self._id}/close", dont_connect=True)
            except (ComputeError, ControllerError, TimeoutError) as e:
                log.warning(f"Could not close project '{self._id}' on compute '{compute.id}': {e}")
        self._clean_pictures()
        self._status = "closed"
        if not ignore_notification:
            self.emit_controller_notification("project.closed", self.asdict())

        # Stop Web Wireshark container (all xpra sessions terminate with container)
        await self._stop_web_wireshark_container()

        # Cleanup GNS3 Copilot AgentService for this project
        await self._cleanup_copilot_agent()

        self.reset()
        self._closing = False
        log.info("Project '%s' [%s]: closed", self._name, self._id)

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
                    logo = self.supplier["logo"]
                    pictures.remove(logo)
                except KeyError:
                    pass

            for pic_filename in pictures:
                path = os.path.join(self.pictures_directory, pic_filename)
                log.info(f"Deleting unused picture '{path}'")
                os.remove(path)
        except OSError as e:
            log.warning(f"Could not delete unused pictures: {e}")

    async def _cleanup_web_wireshark_xpra_sessions(self):
        """
        Cleanup all Web Wireshark xpra sessions (without deleting container).

        Called when project is closed to stop all xpra sessions and Wireshark processes,
        while keeping the container for quick reuse when project is reopened.
        """
        try:
            log.info("Stopping xpra sessions for project '%s' (%s)", self.name, self._id)

            manager = WebWiresharkManager()
            try:
                await manager.stop_all_sessions(self._id)
                log.info("Web Wireshark xpra sessions stopped successfully")
            finally:
                await manager.close()

        except Exception as e:
            # Don't raise exception to avoid affecting project close flow
            log.warning("Failed to cleanup xpra sessions for project '%s': %s", self.name, e)

    async def _stop_web_wireshark_container(self):
        """
        Stop Web Wireshark container (without deleting).

        Called when project is closed to stop the container and free memory,
        while keeping the container for quick startup when project is reopened.
        """
        try:
            container_name = f"gns3-wireshark-{self._id}"
            log.info("Stopping Web Wireshark container '%s' for project '%s'", container_name, self.name)

            manager = WebWiresharkManager()
            try:
                await manager.stop_container(self._id)
                log.info("Web Wireshark container stopped successfully")
            finally:
                await manager.close()

        except Exception as e:
            # Don't fail project close if container stop fails
            log.warning("Failed to stop container for project '%s': %s", self.name, e)

    async def _cleanup_web_wireshark_container(self):
        """
        Delete Web Wireshark container.

        Called when project is deleted to stop and remove the container.
        """
        try:
            container_name = f"gns3-wireshark-{self._id}"
            log.info("Deleting Web Wireshark container '%s' for project '%s'", container_name, self.name)

            manager = WebWiresharkManager()
            try:
                await manager.delete_container(self._id)
                log.info("Web Wireshark container deleted successfully")
            finally:
                await manager.close()

        except Exception as e:
            # Don't fail project delete if container cleanup fails
            log.warning("Failed to delete container for project '%s': %s", self.name, e)

    async def _cleanup_copilot_agent(self):
        """
        Cleanup GNS3 Copilot AgentService for this project.

        This should be called when the project is closed to free resources.
        """
        try:
            from gns3server.agent.gns3_copilot.project_agent_manager import get_project_agent_manager

            agent_manager = await get_project_agent_manager()
            if agent_manager.has_agent(self._id):
                log.info("Cleaning up AgentService for project '%s' (%s)", self.name, self._id)
                await agent_manager.remove_agent(self._id)
        except Exception as e:
            # Don't fail project close if agent cleanup fails
            log.warning("Failed to cleanup AgentService for project '%s': %s", self.name, e)

    async def delete(self):

        # Check compute connectivity before open() to avoid 120s timeout
        # when remote computes are unreachable
        disconnected = self._get_disconnected_computes()
        if disconnected:
            compute_names = ", ".join([f"'{c.name}'" for c in disconnected])
            raise ControllerForbiddenError(
                f"Cannot delete project '{self.name}': {len(disconnected)} compute(s) are disconnected: {compute_names}. "
                f"Please fix the connection or delete the project manually on those computes."
            )

        if self._status != "opened":
            try:
                await self.open(auto_start=False)
            except ControllerError as e:
                # ignore missing images or other conflicts when deleting a project
                log.warning(f"Conflict while deleting project: {e}")

        await self.delete_on_computes()
        await self.close()

        # Delete Web Wireshark container
        await self._cleanup_web_wireshark_container()

        try:
            project_directory = os.path.realpath(get_default_project_directory())
            path = os.path.realpath(self.path)
            if os.path.commonpath([path, project_directory]) != project_directory:
                raise ControllerError(
                    f"Project '{self._name}' cannot be deleted because it is not in the default project directory: '{project_directory}'"
                )
            if path == project_directory:
                # A poisoned or hand-crafted entry whose path is the
                # projects root itself must never be deletable: rmtree
                # would wipe every project on the controller.
                raise ControllerError(
                    f"Project '{self._name}' cannot be deleted because its directory is the projects directory itself: '{path}'"
                )
            shutil.rmtree(self.path)
        except OSError as e:
            raise ControllerError(f"Cannot delete project directory {self.path}: {str(e)}")
        self.emit_controller_notification("project.deleted", self.asdict())

    def _get_disconnected_computes(self):
        """
        Check compute connectivity by reading the topology file directly,
        without opening the project (which would try to connect to computes).
        Returns a list of disconnected Compute objects.
        """
        if self._status == "opened":
            # Project is already open, use the already-loaded _computes list
            compute_ids = self._computes
        else:
            # Read compute IDs from topology file without connecting
            path = self._topology_file()
            if not os.path.exists(path):
                return []
            try:
                project_data = load_topology(path)
            except (ValueError, OSError) as e:
                log.warning(f"Could not read topology file for project '{self._name}': {e}")
                return []
            topology = project_data.get("topology", {})
            compute_ids = set()
            for node in topology.get("nodes", []):
                compute_id = node.get("compute_id")
                if compute_id:
                    compute_ids.add(compute_id)

        disconnected = []
        for compute_id in compute_ids:
            try:
                compute = self._controller.get_compute(compute_id)
                if not compute.connected:
                    disconnected.append(compute)
            except ControllerError:
                log.warning(f"Compute '{compute_id}' not found in controller")
        return disconnected

    async def delete_on_computes(self):
        """
        Delete the project on computes but not on controller
        """
        for compute in list(self._project_created_on_compute):
            if compute.id != "local":
                try:
                    await compute.delete(f"/projects/{self._id}")
                except (ComputeError, TimeoutError) as e:
                    log.warning(f"Could not delete project '{self._id}' on compute '{compute.id}': {e}")
                self._project_created_on_compute.remove(compute)

    @classmethod
    def _get_default_project_directory(cls):
        """
        Return the default location for the project directory
        depending on the operating system
        """

        server_config = Config.instance().settings.Server
        path = os.path.expanduser(server_config.projects_path)
        path = os.path.normpath(path)
        try:
            os.makedirs(path, exist_ok=True)
        except OSError as e:
            raise ControllerError(f"Could not create project directory: {e}")
        return path

    def _topology_file(self):
        return os.path.join(self.path, self._filename)

    @property
    def topology_file(self):
        """
        Absolute path of the .gns3 topology file
        """

        return self._topology_file()

    @locking
    async def open(self, auto_start=True):
        """
        Load topology elements

        :param auto_start: whether the nodes may be started when the project
            has auto start enabled
        """

        if self._closing is True:
            raise ControllerError("Project is closing, please try again in a few seconds...")

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

            # load meta of project
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
                "show_interface_labels",
            ]

            for key in keys_to_load:
                val = project_data.get(key, None)
                if val is not None:
                    setattr(self, key, val)

            # marker_definitions is loaded separately (it is not a __init__ kwarg
            # nor a simple attribute — it backs a read-only property). Each BPF
            # is validated once here so the inherited fan-out (start_marker) can
            # skip re-validation; an invalid definition is dropped with a warning
            # rather than failing the open — it could not fan out anyway.
            defs = project_data.get("marker_definitions")
            if isinstance(defs, dict):
                clean_defs = {}
                for def_name, d in defs.items():
                    bpf = d.get("bpf")
                    if not bpf:
                        log.warning("Dropping marker definition '%s' on load: missing bpf", def_name)
                        continue
                    result = validate_bpf_syntax(bpf)
                    if not result.get("valid"):
                        log.warning(
                            "Dropping marker definition '%s' on load: invalid BPF (%s)",
                            def_name, result.get("error")
                        )
                        continue
                    clean_defs[def_name] = d
                self._marker_definitions = clean_defs

            topology = project_data["topology"]
            for compute in topology.get("computes", []):
                compute_id = compute.get("compute_id")
                if compute_id not in self._controller._computes:
                    await self.controller.add_compute(**compute)

            # Get all compute used in the project
            # used to allocate application IDs for IOU nodes.
            for node in topology.get("nodes", []):
                compute_id = node.get("compute_id")
                if compute_id not in self._computes:
                    self._computes.append(compute_id)

            # Check compute connectivity before creating nodes to avoid
            # 120-second timeout when a remote compute is unreachable
            disconnected = self._get_disconnected_computes()
            if disconnected:
                compute_names = ", ".join([f"'{c.name}'" for c in disconnected])
                raise ControllerError(
                    f"Cannot open project '{self.name}': {len(disconnected)} compute(s) are disconnected: {compute_names}. "
                    f"Please check the connection and try again."
                )

            # Parallel node creation for improved performance
            # especially for projects with multiple Docker containers
            nodes_to_create = []
            for node in topology.get("nodes", []):
                compute = self.controller.get_compute(node.pop("compute_id"))
                name = node.pop("name")
                node_id = node.pop("node_id", str(uuid.uuid4()))
                nodes_to_create.append((compute, name, node_id, node))

            # Create nodes in parallel with limited concurrency
            # to avoid overwhelming the system with too many simultaneous operations
            log.info("Project '%s' [%s]: loading %d nodes...", self._name, self._id, len(nodes_to_create))
            pool = Pool(concurrency=100)
            for compute, name, node_id, node_data in nodes_to_create:
                pool.append(self.add_node, compute, name, node_id, dump=False, **node_data)
            await pool.join()
            log.info("Project '%s' [%s]: loaded %d nodes", self._name, self._id, len(nodes_to_create))
            # Pre-allocate UDP ports for all links in batch to reduce HTTP round-trips
            ports_per_compute = {}
            for link_data in topology.get("links", []):
                if "link_id" not in link_data.keys():
                    continue
                for node_link in link_data.get("nodes", []):
                    node = self._nodes.get(node_link["node_id"])
                    if node:
                        ports_per_compute[node.compute.id] = ports_per_compute.get(node.compute.id, 0) + 1
            for compute in self.computes:
                count = ports_per_compute.get(compute.id, 0)
                if count > 0:
                    await self.preallocate_udp_ports_for_compute(compute, count)
            # Create links via the bulk path: build every link locally (no NIO
            # HTTP), then dispatch all NIOs to each compute in a single batch
            # request. This replaces one HTTP round-trip per link (~5000 for a
            # 2500-link topology) with one round-trip per compute.
            link_data_list = [d for d in topology.get("links", []) if "link_id" in d.keys()]
            log.info("Project '%s' [%s]: creating %d links...", self._name, self._id, len(link_data_list))
            sem = asyncio.Semaphore(100)

            async def _prepare_one(data):
                async with sem:
                    try:
                        return await self._prepare_link_from_topology(data)
                    except Exception as e:
                        log.warning("Could not load link %s: %s", data.get("link_id"), e)
                        return None

            prepared = await asyncio.gather(*[_prepare_one(d) for d in link_data_list])
            valid = [p for p in prepared if p is not None]

            # Group the prepared NIO entries by destination compute and send
            # each compute a single /nios/batch request.
            per_compute = {}  # compute -> list of {node_id, adapter_number, port_number, nio}
            for link, entries in valid:
                for node, adapter_number, port_number, nio_data in entries:
                    per_compute.setdefault(node.compute, []).append(
                        {
                            "node_id": node.id,
                            "adapter_number": adapter_number,
                            "port_number": port_number,
                            "nio": nio_data,
                        }
                    )

            async def _dispatch_batch(compute, nio_entries):
                await compute.post(
                    f"/projects/{self._id}/nios/batch",
                    data={"nios": nio_entries},
                    timeout=300,
                )

            if per_compute:
                await asyncio.gather(
                    *[_dispatch_batch(c, n) for c, n in per_compute.items()]
                )

            # Finalise every link: wire node/port back-references, mark created,
            # notify clients, and apply project-level marker definitions.
            for link, _entries in valid:
                for n in link._nodes:
                    n["node"].add_link(link)
                    n["port"].link = link
                link._created = True
                self.emit_notification("link.created", link.asdict())
            log.info("Project '%s' [%s]: created %d links", self._name, self._id, len(valid))
            # Release any pre-allocated UDP ports that were not consumed by links
            for compute_id, ports in self._preallocated_udp_ports.items():
                if ports:
                    log.warning(f"Releasing {len(ports)} unconsumed pre-allocated UDP ports on compute {compute_id}")
            self._preallocated_udp_ports.clear()
            for drawing_data in topology.get("drawings", []):
                await self.add_drawing(dump=False, **drawing_data)

            # Note: project-level marker definitions are applied to each link
            # inside UDPLink.create() (the inheritance hook), so they are
            # already present once links are loaded — no separate fan-out here.

            self.dump()
        # We catch all error to be able to roll back the .gns3 to the previous state
        except Exception as e:
            for compute in list(self._project_created_on_compute):
                try:
                    await compute.post(f"/projects/{self._id}/close")
                # We don't care if a compute is down at this step
                except ComputeError:
                    pass
            try:
                if os.path.exists(path + ".backup"):
                    shutil.copy(path + ".backup", path)
            except OSError:
                pass
            self._status = "closed"
            self._loading = False
            if isinstance(e, ComputeError):
                raise ControllerError(str(e))
            else:
                raise e
        try:
            os.remove(path + ".backup")
        except OSError:
            pass

        self._loading = False
        self.emit_controller_notification("project.opened", self.asdict())
        # Should we start the nodes when project is open
        if self._auto_start and auto_start:
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

    async def duplicate(self, name=None, reset_mac_addresses=True):
        """
        Duplicate a project

        Implemented on top of the export / import features. It will generate a gns3p and reimport it.

        NEW: fast duplication is used if possible (when there are no remote computes).
        If not, the project is exported and reimported as explained above.

        :param name: Name of the new project. A new one will be generated in case of conflicts
        :param reset_mac_addresses: Reset MAC addresses for the new project
        """

        # If the project was not open we open it temporary
        previous_status = self._status
        if self._status == "closed":
            await self.open()

        self.dump()
        assert self._status != "closed"

        try:
            proj = await self._fast_duplication(name, reset_mac_addresses)
            if proj:
                if previous_status == "closed":
                    await self.close()
                return proj
            else:
                log.info("Fast duplication failed, fallback to normal duplication")
        except Exception as e:
            raise ControllerError(f"Cannot duplicate project: {str(e)}")

        try:
            begin = time.time()

            # use the parent directory of the project we are duplicating as a
            # temporary directory to avoid no space left issues when '/tmp'
            # is located on another partition.
            working_dir = os.path.abspath(os.path.join(self.path, os.pardir))

            with tempfile.TemporaryDirectory(dir=working_dir) as tmpdir:
                # Do not compress the exported project when duplicating
                with aiozipstream.ZipFile(compression=zipfile.ZIP_STORED) as zstream:
                    await export_project(
                        zstream,
                        self,
                        tmpdir,
                        keep_compute_ids=True,
                        include_snapshots=True,
                        allow_all_nodes=True
                    )

                    # export the project to a temporary location
                    project_path = os.path.join(tmpdir, "project.gns3p")
                    log.info(f"Exporting project to '{project_path}'")
                    async with aiofiles.open(project_path, "wb") as f:
                        async for chunk in zstream:
                            await f.write(chunk)

                    new_project_id = str(uuid.uuid4())
                    # import the duplicated project
                    with open(project_path, "rb") as f:
                        project = await import_project(
                            self._controller,
                            new_project_id,
                            f,
                            name=name,
                            reset_mac_addresses=reset_mac_addresses,
                            keep_compute_ids=True
                        )

            log.info(f"Project '{project.name}' duplicated in {time.time() - begin:.4f} seconds")
        except (ValueError, OSError, UnicodeEncodeError) as e:
            raise ControllerError(f"Cannot duplicate project: {str(e)}")

        if previous_status == "closed":
            await self.close()

        return project

    async def _fast_duplication(self, name=None, location=None, reset_mac_addresses=True):
        """
        Fast duplication of a project.

        Copy the project files directly rather than in an import-export fashion.

        :param name: Name of the new project. A new one will be generated in case of conflicts
        :param location: Parent directory of the new project
        :param reset_mac_addresses: Reset MAC addresses for the duplicated project
        """

        # We don't duplicate a running project
        if self.is_running():
            raise ControllerError("Project must be stopped in order to duplicate it")

        # remote replication is not supported with remote computes
        for compute in self.computes:
            if compute.id != "local":
                log.warning("Fast duplication is not supported with remote compute: '{}'".format(compute.id))
                return None
        # work dir
        p_work = pathlib.Path(location or self.path).parent.absolute()
        t0 = time.time()
        new_project_id = str(uuid.uuid4())
        if location:
            new_project_path = p_work.joinpath(location)
        else:
            new_project_path = p_work.joinpath(new_project_id)
        # copy dir
        await wait_run_in_executor(shutil.copytree, self.path, new_project_path.as_posix(), symlinks=True, ignore_dangling_symlinks=True)
        log.info("Project content copied from '{}' to '{}' in {}s".format(self.path, new_project_path, time.time() - t0))

        # Read the topology file using the actual filename (self._filename), not self.name
        # This handles the case where a project has been renamed but we need to read the actual file
        old_gns3_file = new_project_path.joinpath(self._filename)
        topology = json.loads(old_gns3_file.read_bytes())
        project_name = name or topology["name"]
        # If the project name is already used we generate a new one
        project_name = self.controller.get_free_project_name(project_name)
        topology["name"] = project_name
        # To avoid unexpected behavior (project start without manual operations just after import)
        topology["auto_start"] = False
        topology["auto_open"] = False
        topology["auto_close"] = False

        # regenerate IDs for the duplicated project
        regenerate_topology_ids(topology, new_project_path, reset_mac_addresses)

        # dump the updated .gns3 project file
        dot_gns3_path = new_project_path.joinpath('{}.gns3'.format(project_name))
        topology["project_id"] = new_project_id
        with open(dot_gns3_path, "w+") as f:
            json.dump(topology, f, indent=4, sort_keys=True)

        # update the snapshots with new IDs
        snapshots_dir = os.path.join(new_project_path, "snapshots")
        if os.path.isdir(snapshots_dir):
            await update_snapshots(snapshots_dir, new_project_path, project_name, new_project_id)

        # Remove the old .gns3 file (which has the original project name)
        os.remove(old_gns3_file)
        project = await self.controller.load_project(dot_gns3_path, load=False)
        log.info("Project '{}': fast duplicated in {:.4f} seconds".format(project.name, time.time() - t0))
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

    @open_required
    def lock(self):
        """
        Lock all drawings and nodes
        """

        for drawing in self._drawings.values():
            if not drawing.locked:
                drawing.locked = True
                self.emit_notification("drawing.updated", drawing.asdict())
        for node in self.nodes.values():
            if not node.locked:
                node.locked = True
                self.emit_notification("node.updated", node.asdict())
        self.dump()

    @open_required
    def unlock(self):
        """
        Unlock all drawings and nodes
        """

        for drawing in self._drawings.values():
            if drawing.locked:
                drawing.locked = False
                self.emit_notification("drawing.updated", drawing.asdict())
        for node in self.nodes.values():
            if node.locked:
                node.locked = False
                self.emit_notification("node.updated", node.asdict())
        self.dump()

    @property
    @open_required
    def locked(self):
        """
        Check if all items in a project are locked and not
        """

        if not self._drawings and not self._nodes:
            # a project without drawings or nodes has nothing to lock and would
            # otherwise always report as locked, even after unlocking it
            return False
        for drawing in self._drawings.values():
            if not drawing.locked:
                return False
        for node in self.nodes.values():
            if not node.locked:
                return False
        return True

    def dump(self):
        """
        Dump topology to disk
        """
        try:
            topo = project_to_topology(self)
            path = self._topology_file()
            log.debug(f"Write topology file '{path}'")
            with open(path + ".tmp", "w+", encoding="utf-8") as f:
                json.dump(topo, f, indent=4, sort_keys=True)
            shutil.move(path + ".tmp", path)
        except OSError as e:
            raise ControllerError(f"Could not write topology: {e}")

    @open_required
    async def start_all(self):
        """
        Start all nodes (except always-running types like Ethernet switch, Cloud, NAT, etc.)
        """
        nodes_to_start = [n for n in self.nodes.values() if not n.is_always_running()]
        if not nodes_to_start:
            return
        log.info("Project '%s' [%s]: starting %d nodes...", self._name, self._id, len(nodes_to_start))
        pool = Pool(concurrency=10)
        for node in nodes_to_start:
            pool.append(node.start)
        await pool.join()
        log.info("Project '%s' [%s]: started %d nodes", self._name, self._id, len(nodes_to_start))

    @open_required
    async def stop_all(self):
        """
        Stop all nodes (except always-running types like Ethernet switch, Cloud, NAT, etc.)
        """
        nodes_to_stop = [n for n in self.nodes.values() if not n.is_always_running()]
        if not nodes_to_stop:
            return
        log.info("Project '%s' [%s]: stopping %d nodes...", self._name, self._id, len(nodes_to_stop))
        pool = Pool(concurrency=100)
        for node in nodes_to_stop:
            pool.append(node.stop)
        await pool.join()
        log.info("Project '%s' [%s]: stopped %d nodes", self._name, self._id, len(nodes_to_stop))

    @open_required
    async def suspend_all(self):
        """
        Suspend all nodes
        """
        pool = Pool(concurrency=50)
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

        data = copy.deepcopy(node.asdict(topology_dump=True))
        # Some properties like internal ID should not be duplicated
        for unique_property in (
            "node_id",
            "name",
            "mac_addr",
            "mac_address",
            "compute_id",
            "application_id",
            "dynamips_id",
        ):
            data.pop(unique_property, None)
            if "properties" in data:
                data["properties"].pop(unique_property, None)
        node_type = data.pop("node_type")
        data["x"] = x
        data["y"] = y
        data["z"] = z
        data["locked"] = False  # duplicated node must not be locked
        new_node_uuid = str(uuid.uuid4())
        new_node = await self.add_node(
            node.compute,
            node.name,
            new_node_uuid,
            node_type=node_type,
            **data
        )
        try:
            await node.post("/duplicate", timeout=None, data={"destination_node_id": new_node_uuid})
        except ControllerNotFoundError:
            await self.delete_node(new_node_uuid)
            raise ControllerError("This node type cannot be duplicated")
        except ControllerError as e:
            await self.delete_node(new_node_uuid)
            raise e
        return new_node

    def stats(self):

        return {
            "nodes": len(self._nodes),
            "links": len(self._links),
            "drawings": len(self._drawings),
            "snapshots": len(self._snapshots),
            "markers": sum(len(link.markers) for link in self._links.values()),
        }

    def asdict(self):
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
            "variables": self._variables,
            "created_by": self._created_by,
            "marker_definitions": self._marker_definitions,
        }

    def __repr__(self):
        return f"<gns3server.controller.Project {self._name} {self._id}>"

