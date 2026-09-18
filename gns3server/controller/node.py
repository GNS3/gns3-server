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
import html
import copy
import uuid
import os

from .controller_error import (
    ControllerError,
    ControllerTimeoutError,
    ComputeError,
    ComputeConflictError
)
from .node_types import BUILTIN_NODE_TYPES
from .ports.port_factory import PortFactory, StandardPortFactory, DynamipsPortFactory
from ..utils.images import images_directories
from ..utils.application_id import is_iol_runner_environment
from ..utils import macaddress_to_int, int_to_macaddress
from ..config import Config


import logging

log = logging.getLogger(__name__)


# Image properties of a node, mapped by node type. The value is the image
# "type" used by the image manager (see utils.images). Docker images are not
# registered in the image database, they are matched by tag instead.
IMAGE_PROPERTIES_BY_NODE_TYPE = {
    "qemu": {
        "hda_disk_image": "qemu",
        "hdb_disk_image": "qemu",
        "hdc_disk_image": "qemu",
        "hdd_disk_image": "qemu",
        "cdrom_image": "qemu",
        "initrd": "qemu",
        "kernel_image": "qemu",
        "bios_image": "qemu",
    },
    "dynamips": {"image": "ios"},
    "iou": {"path": "iou"},
    "docker": {"image": "docker"},
}


def _extract_iol_startup_config_knob(environment):
    """
    Split the GNS3_IOL_STARTUP_CONFIG knob out of a Docker environment
    (iol-runner images): the value is a config file name, resolved by the
    controller in its configs directory.

    :returns: (filename, environment without the knob line); filename is None
        when the knob is absent or empty.
    """

    if not environment or "GNS3_IOL_STARTUP_CONFIG=" not in environment:
        return None, environment
    filename = None
    kept = []
    for line in environment.splitlines():
        stripped = line.strip().rstrip(",")
        if stripped.startswith("GNS3_IOL_STARTUP_CONFIG="):
            if filename is None:
                filename = stripped.split("=", 1)[1].strip()
        else:
            kept.append(line)
    return filename or None, "\n".join(kept)


class Node:
    # These properties are used only on controller and are not forwarded to the compute
    CONTROLLER_ONLY_PROPERTIES = [
        "x",
        "y",
        "z",
        "locked",
        "width",
        "height",
        "symbol",
        "label",
        "console_host",
        "port_name_format",
        "first_port_name",
        "port_segment_size",
        "ports",
        "category",
        "console_auto_start",
        "netmiko_device_type",
        "default_username",
        "default_password",
    ]

    def __init__(self, project, compute, name, node_id=None, node_type=None, template_id=None, **kwargs):
        """
        :param project: Project of the node
        :param compute: Compute where the server will run
        :param name: Node name
        :param node_id: UUID of the node (integer)
        :param node_type: Type of emulator
        :param template_id: Template ID used to create this node
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
        self._aux = None
        self._aux_type = None
        self._properties = None
        self._command_line = None
        self._node_directory = None
        self._status = "stopped"
        self._template_id = template_id
        self._x = 0
        self._y = 0
        self._z = 1  # default z value is 1
        self._locked = False
        self._tags = []
        self._ports = None
        self._symbol = None
        self._custom_adapters = []
        if node_type == "iou":
            self._port_name_format = "Ethernet{segment0}/{port0}"
            self._port_by_adapter = 4
            self.port_segment_size = 4
        else:
            self._port_name_format = "Ethernet{0}"
            self._port_by_adapter = 1
            self._port_segment_size = 0
        self._first_port_name = None
        self._console_auto_start = False
        self._netmiko_device_type = None
        self._default_username = None
        self._default_password = None
        # Set when the node cannot be created on its compute because one or
        # more of its images are missing. The node is kept on the controller
        # (topology and links are preserved) until the user provides a
        # compatible replacement image.
        self._missing_images = []

        # This properties will be recomputed
        ignore_properties = ("width", "height", "hover_symbol")
        self.properties = kwargs.pop("properties", {})

        # Update node properties with additional elements
        for prop in kwargs:
            if prop and prop not in ignore_properties:
                if hasattr(self, prop):
                    try:
                        setattr(self, prop, kwargs[prop])
                    except AttributeError as e:
                        log.critical(f"Cannot set attribute '{prop}'")
                        raise e
                else:
                    if prop not in self.CONTROLLER_ONLY_PROPERTIES and kwargs[prop] is not None and kwargs[prop] != "":
                        self.properties[prop] = kwargs[prop]

        if self._symbol is None:
            # compatibility with old node templates
            if "default_symbol" in self.properties:
                default_symbol = self.properties.pop("default_symbol")
                if default_symbol.endswith("normal.svg"):
                    self.symbol = default_symbol[:-11] + ".svg"
                else:
                    self.symbol = default_symbol
            else:
                self.symbol = ":/symbols/computer.svg"

    def is_always_running(self):
        """
        :returns: Boolean True if the node is always running
        like ethernet switch
        """
        return self.node_type not in ("qemu", "docker", "dynamips", "vpcs", "vmware", "virtualbox", "iou")

    @property
    def id(self):
        return self._id

    @property
    def status(self):
        return self._status

    @property
    def missing_image(self):
        """
        :returns: True if at least one image required by this node is missing
            and the node could therefore not be created on its compute.
        """
        return len(self._missing_images) > 0

    @property
    def missing_images(self):
        return self._missing_images

    @property
    def template_id(self):
        return self._template_id

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
    def aux(self):
        return self._aux

    @aux.setter
    def aux(self, val):
        self._aux = val

    @property
    def console_type(self):
        return self._console_type

    @console_type.setter
    def console_type(self, val):
        self._console_type = val

    @property
    def aux_type(self):
        return self._aux_type

    @aux_type.setter
    def aux_type(self, val):
        self._aux_type = val

    @property
    def console_auto_start(self):
        return self._console_auto_start

    @console_auto_start.setter
    def console_auto_start(self, val):
        self._console_auto_start = val

    @property
    def netmiko_device_type(self):
        return self._netmiko_device_type

    @netmiko_device_type.setter
    def netmiko_device_type(self, val):
        self._netmiko_device_type = val

    @property
    def default_username(self):
        return self._default_username

    @default_username.setter
    def default_username(self, val):
        self._default_username = val

    @property
    def default_password(self):
        return self._default_password

    @default_password.setter
    def default_password(self, val):
        self._default_password = val

    @property
    def properties(self):
        return self._properties

    @properties.setter
    def properties(self, val):
        self._properties = val

    @property
    def tags(self):
        return self._tags

    @tags.setter
    def tags(self, val):
        self._tags = val

    def _base_config_file_content(self, path):
        if not os.path.isabs(path):
            path = os.path.join(self.project.controller.configs_path(), path)
        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                return f.read()
        except OSError:
            return None

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
    def locked(self):
        return self._locked

    @locked.setter
    def locked(self, val):
        self._locked = val

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

        try:
            if not val.startswith(":") and os.path.isabs(val):
                default_symbol_directory = Config.instance().settings.Server.symbols_path
                if os.path.commonprefix([default_symbol_directory, val]) != default_symbol_directory:
                    val = os.path.basename(val)
        except OSError:
            pass

        self._symbol = val
        try:
            self._width, self._height, filetype = self._project.controller.symbols.get_size(val)
        except (ValueError, OSError) as e:
            log.error(f"Could not set symbol: {e}")
            # If symbol is invalid we replace it by the default
            self.symbol = ":/symbols/computer.svg"
        if self._label is None:
            # Apply to label user style or default
            try:
                style = None  # FIXME: allow configuration of default label font & color on controller
                # style = qt_font_to_style(self._project.controller.settings["GraphicsView"]["default_label_font"],
                #                         self._project.controller.settings["GraphicsView"]["default_label_color"])
            except KeyError:
                style = "font-family: TypeWriter;font-size: 10.0;font-weight: bold;fill: #000000;fill-opacity: 1.0;"

            self._label = {
                "y": round(self._height / 2 + 10) * -1,
                "text": html.escape(self._name),
                "style": style,  # None: means the client will apply its default style
                "x": None,  # None: means the client should center it
                "rotation": 0,
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

    @property
    def custom_adapters(self):
        return self._custom_adapters

    @custom_adapters.setter
    def custom_adapters(self, val):
        self._custom_adapters = val

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
    def links(self):
        return self._links

    async def create(self, allow_missing_image=False):
        """
        Create the node on the compute

        :param allow_missing_image: when True, if an image is missing and
            cannot be uploaded/synced, the node is not created on the compute
            but is kept on the controller and flagged with the missing image(s)
            instead of raising.
        """
        data = self._node_data()
        data["node_id"] = self._id
        if self._node_type == "docker":
            timeout = None
            await self._add_docker_image_digest(data)
        else:
            timeout = 1200
        trial = 0
        last_missing_image = None
        last_missing_error = None
        while trial != 6:
            try:
                response = await self._compute.post(
                    f"/projects/{self._project.id}/{self._node_type}/nodes", data=data, timeout=timeout
                )
            except ComputeConflictError as e:
                response = e.response()
                if response.get("exception") == "ImageMissingError":
                    last_missing_error = e
                    last_missing_image = response.get("image")
                    res = False
                    if last_missing_image:
                        try:
                            res = await self._upload_missing_image(self._node_type, last_missing_image)
                        except ControllerError as upload_error:
                            # For Docker the image is pulled from a registry: a
                            # failed pull (unknown tag, no network, private image)
                            # must not abort the whole project. Treat it as a
                            # missing image so the user can pick another one.
                            if not allow_missing_image:
                                raise
                            log.warning(
                                "Could not provide missing image '%s' for node '%s' [%s]: %s",
                                last_missing_image, self._name, self._id, upload_error
                            )
                    if not res:
                        if allow_missing_image:
                            missing_images = self._compute_missing_images(last_missing_image)
                            # A degraded node must always identify at least one
                            # missing image. Otherwise the controller would keep
                            # a node that was never created on the compute while
                            # exposing it as healthy.
                            if not missing_images:
                                raise e
                            self._missing_images = missing_images
                            log.warning(
                                "Node '%s' [%s] is kept in degraded state, missing image(s): %s",
                                self._name, self._id, ", ".join(m["image"] for m in self._missing_images)
                            )
                            return False
                        raise e
                else:
                    raise e
            else:
                await self.parse_node_response(response.json)
                self._missing_images = []
                return True
            trial += 1
        if allow_missing_image:
            # The image was repeatedly reported missing (e.g. the upload/sync
            # seemed to succeed but did not). Keep the node in degraded state.
            self._missing_images = self._compute_missing_images(last_missing_image)
            log.warning(
                "Node '%s' [%s] could not be created, missing image(s): %s",
                self._name, self._id, ", ".join(m["image"] for m in self._missing_images)
            )
        elif last_missing_error is not None:
            # Uploading appeared to succeed, but the compute rejected every
            # retry. Do not let the caller register a controller-only node as
            # healthy.
            raise last_missing_error
        return False

    def _image_available(self, image_type, image):
        """
        Check whether an image is available on the controller (and can
        therefore be uploaded to the compute when needed).

        :param image_type: image type (e.g. "qemu", "ios", "iou")
        :param image: image filename or path
        """

        if not image:
            return True
        if image_type == "docker":
            # Docker images are not stored on the controller filesystem
            return True
        try:
            directories = images_directories(image_type)
        except NotImplementedError:
            return True
        for directory in directories:
            if os.path.exists(os.path.join(directory, image)):
                return True
        return False

    def _compute_missing_images(self, fallback_image=None):
        """
        Build the list of images referenced by this node that are not
        available on the controller.

        :param fallback_image: image reported as missing by the compute, always
            included (used for Docker images and images not directly mapped to
            a node property).
        """

        missing = []
        mapping = IMAGE_PROPERTIES_BY_NODE_TYPE.get(self._node_type, {})
        properties = self._properties or {}
        for prop, image_type in mapping.items():
            value = properties.get(prop)
            if not value:
                continue
            if not self._image_available(image_type, value):
                missing.append({"property": prop, "image": value, "image_type": image_type})
        if fallback_image:
            prop = next((p for p in mapping if properties.get(p) == fallback_image), None)
            if prop is None:
                fallback_basename = os.path.basename(fallback_image)
                prop = next(
                    (
                        p
                        for p in mapping
                        if properties.get(p) and os.path.basename(properties[p]) == fallback_basename
                    ),
                    None,
                )
            if prop is None and mapping:
                prop = next(iter(mapping))
            already_reported = any(
                m["image"] == fallback_image or (prop is not None and m["property"] == prop)
                for m in missing
            )
            if not already_reported:
                image_type = mapping.get(prop, self._node_type)
                missing.append({"property": prop, "image": fallback_image, "image_type": image_type})
        return missing

    async def update(self, **kwargs):
        """
        Update the node on the compute

        :param kwargs: Node properties
        """

        # When updating properties used only on controller we don't need to call the compute
        update_compute = False
        old_json = self.asdict()
        old_name = self._name
        old_properties = copy.deepcopy(self._properties)
        old_custom_adapters = copy.deepcopy(self._custom_adapters)
        old_missing_images = copy.deepcopy(self._missing_images)

        compute_properties = None
        # Update node properties with additional elements
        for prop in kwargs:
            if getattr(self, prop) != kwargs[prop]:
                if prop not in self.CONTROLLER_ONLY_PROPERTIES:
                    update_compute = True

                # We update properties on the compute and wait for the answer from the compute node
                if prop == "properties":
                    compute_properties = kwargs[prop]
                else:
                    if (
                        prop == "name"
                        and self.status == "started"
                        and self._node_type not in BUILTIN_NODE_TYPES
                    ):
                        raise ControllerError("Sorry, it is not possible to rename a node that is already powered on")
                    setattr(self, prop, kwargs[prop])

        if compute_properties and "custom_adapters" in compute_properties:
            # we need to check custom adapters to update the custom port names
            self.custom_adapters = compute_properties["custom_adapters"]
        if self.missing_image and compute_properties is not None:
            # The node was never created on the compute (missing image). Apply
            # the new properties locally so create() can use them.
            self._properties = compute_properties
        self._list_ports()
        if update_compute:
            if self.missing_image:
                # Try to create the node on the compute now that an image may
                # have been provided. If it is still missing the node simply
                # remains in its degraded state.
                try:
                    created = await self.create(allow_missing_image=True)
                except Exception:
                    # create() can reject the replacement for reasons other
                    # than a missing image. Keep the controller state aligned
                    # with the node that is still absent from the compute.
                    self._properties = old_properties
                    self._custom_adapters = old_custom_adapters
                    self._missing_images = old_missing_images
                    self._list_ports()
                    raise
                if created:
                    await self.project.restore_deferred_links(self)
                self.project.emit_notification("node.updated", self.asdict())
                self.project.dump()
                return
            data = self._node_data(properties=compute_properties)
            try:
                response = await self.put(None, data=data)
            except ComputeConflictError:
                if old_name != self.name:
                    # special case when the new name is already updated on controller but refused by the compute
                    self.name = old_name
                raise
            await self.parse_node_response(response.json)
        elif old_json != self.asdict():
            # We send notif only if object has changed
            self.project.emit_notification("node.updated", self.asdict())
        self.project.dump()

    async def parse_node_response(self, response):
        """
        Update the object with the remote node object
        """

        for key, value in response.items():
            if key == "console":
                self._console = value
            elif key == "aux":
                self._aux = value
            elif key == "node_directory":
                self._node_directory = value
            elif key == "command_line":
                self._command_line = value
            elif key == "status":
                self._status = value
            elif key == "console_type":
                self._console_type = value
            elif key == "aux_type":
                self._aux_type = value
            elif key == "name":
                self.name = value
            elif key in [
                "node_id",
                "project_id",
                "console_host",
                "startup_config_content",
                "private_config_content",
                "startup_script",
                "custom_adapters"
            ]:
                if key in self._properties:
                    del self._properties[key]
            else:
                self._properties[key] = value
        self._list_ports()
        for link in self._links:
            await link.node_updated(self)

    def _node_data(self, properties=None):
        """
        Prepare node data to send to the remote controller

        :param properties: If properties is None use actual property otherwise use the parameter
        """
        if properties:
            data = copy.copy(properties)
        else:
            data = copy.copy(self._properties)
            # We replace the startup script name by the content of the file
            mapping = {
                "base_script_file": "startup_script",
                "startup_config": "startup_config_content",
                "private_config": "private_config_content",
            }
            for k, v in mapping.items():
                if k in list(self._properties.keys()):
                    data[v] = self._base_config_file_content(self._properties[k])
                    del data[k]
                    del self._properties[k]  # We send the file only one time

            # IOL runner (Docker) startup-config: translate the config file
            # referenced by the GNS3_IOL_STARTUP_CONFIG environment knob into
            # content, like the mappings above. Sent only once — afterwards
            # the node's configuration lives in its NVRAM on the compute (a
            # reloaded node is recreated without the knob and boots from the
            # persistent NVRAM, preserving `write memory`).
            if self._node_type == "docker":
                filename, environment = _extract_iol_startup_config_knob(self._properties.get("environment"))
                if filename:
                    content = self._base_config_file_content(filename)
                    if content:
                        data["startup_config_content"] = content
                        data["environment"] = environment
                        self._properties["environment"] = environment
                    else:
                        log.warning(
                            f"Cannot load IOL startup-config file '{filename}' for node '{self._name}': file not found"
                        )
        data["name"] = self._name

        # For remote computes, convert absolute image paths to relative paths
        # The remote compute will search for the image in its own configured directories
        if self._compute.id != "local":
            # Image path fields for various node types
            image_path_fields = {
                # Common fields (IOU, Docker, etc.)
                "path", "image",
                # QEMU-specific fields
                "hda_disk_image", "hdb_disk_image", "hdc_disk_image", "hdd_disk_image",
                "cdrom_image", "bios_image", "initrd", "kernel_image",
                # VMware-specific fields
                "vmx_path",
            }

            for field in image_path_fields:
                if field in data and data[field] and os.path.isabs(data[field]):
                    data[field] = os.path.basename(data[field])

        if self._console:
            # console is optional for builtin nodes
            data["console"] = self._console
        if self._console_type and self._node_type not in (BUILTIN_NODE_TYPES - {"ethernet_switch"}):
            # console_type is not supported by all builtin nodes excepting Ethernet switch
            data["console_type"] = self._console_type
        if self._aux:
            # aux is optional for builtin nodes
            data["aux"] = self._aux
        if self._aux_type and self._node_type not in BUILTIN_NODE_TYPES:
            # aux_type is not supported by all builtin nodes
            data["aux_type"] = self._aux_type
        if self.custom_adapters:
            data["custom_adapters"] = self.custom_adapters

        # None properties are not be sent because it can mean the emulator doesn't support it
        for key, value in list(data.items()):
            if value is None or value == {} or key in self.CONTROLLER_ONLY_PROPERTIES:
                del data[key]

        return data

    async def destroy(self):
        await self.delete()

    async def start(self, data=None):
        """
        Start a node
        """
        if self.missing_image:
            images = ", ".join(m["image"] for m in self._missing_images)
            raise ControllerError(
                f"Cannot start node '{self._name}': the required image(s) ({images}) "
                f"are missing. Please provide a compatible image."
            )
        deferred_links = [link for link in self.links if link.deferred]
        if deferred_links:
            await self.project.restore_deferred_links(self)
            failed_links = [
                link
                for link in deferred_links
                if link.deferred and not any(endpoint["node"].missing_image for endpoint in link._nodes)
            ]
            if failed_links:
                raise ControllerError(
                    f"Cannot start node '{self._name}': {len(failed_links)} deferred link(s) "
                    "could not be restored. Please try again."
                )
        try:
            # For IOU: we need to send the licence everytime we start a node
            if self.node_type == "iou":
                license_check = self._project.controller.iou_license.get("license_check", True)
                iourc_content = self._project.controller.iou_license.get("iourc_content", None)
                await self.post("/start", timeout=240, data={"license_check": license_check, "iourc_content": iourc_content})
            else:
                await self.post("/start", data=data, timeout=240)
        except asyncio.TimeoutError:
            raise ControllerTimeoutError(f"Timeout when starting {self._name}")

    async def stop(self):
        """
        Stop a node
        """
        if self.missing_image:
            return
        try:
            await self.post("/stop", timeout=240, dont_connect=True)
        # We don't care if a node is down at this step
        except (ComputeError, ControllerError):
            pass
        except asyncio.TimeoutError:
            raise ControllerTimeoutError(f"Timeout when stopping {self._name}")

    async def suspend(self):
        """
        Suspend a node
        """
        try:
            await self.post("/suspend", timeout=240)
        except asyncio.TimeoutError:
            raise ControllerTimeoutError(f"Timeout when reloading {self._name}")

    async def reload(self):
        """
        Suspend a node
        """
        try:
            await self.post("/reload", timeout=240)
        except asyncio.TimeoutError:
            raise ControllerTimeoutError(f"Timeout when reloading {self._name}")

    async def reset_console(self):
        """
        Reset the console
        """

        if self._console and self._console_type in ("telnet", "ssh"):
            try:
                await self.post("/console/reset", timeout=240)
            except asyncio.TimeoutError:
                raise ControllerTimeoutError(f"Timeout when reset console {self._name}")

    async def get(self, path="", **kwargs):
        """
        HTTP get on the node
        """
        return await self._compute.get(
            f"/projects/{self._project.id}/{self._node_type}/nodes/{self._id}{path}", **kwargs
        )

    async def post(self, path, data=None, **kwargs):
        """
        HTTP post on the node
        """
        if data:
            return await self._compute.post(
                f"/projects/{self._project.id}/{self._node_type}/nodes/{self._id}{path}", data=data, **kwargs
            )
        else:
            return await self._compute.post(
                f"/projects/{self._project.id}/{self._node_type}/nodes/{self._id}{path}", **kwargs
            )

    async def put(self, path, data=None, **kwargs):
        """
        HTTP put on the node
        """
        if path is None:
            path = f"/projects/{self._project.id}/{self._node_type}/nodes/{self._id}"
        else:
            path = f"/projects/{self._project.id}/{self._node_type}/nodes/{self._id}{path}"
        if data:
            return await self._compute.put(path, data=data, **kwargs)
        else:
            return await self._compute.put(path, **kwargs)

    async def delete(self, path=None, **kwargs):
        """
        HTTP post on the node
        """
        if self.missing_image and path is None:
            # The node was never created on the compute (missing image). Any
            # partial object there is cleaned up when the project is closed.
            return None
        if path is None:
            return await self._compute.delete(
                f"/projects/{self._project.id}/{self._node_type}/nodes/{self._id}", **kwargs
            )
        else:
            return await self._compute.delete(
                f"/projects/{self._project.id}/{self._node_type}/nodes/{self._id}{path}", **kwargs
            )

    async def _upload_missing_image(self, type, img):
        """
        Search an image on local computer and upload it to remote compute
        if the image exists
        """

        if self._node_type == "docker":
            return await self._sync_missing_docker_image(img)

        for directory in images_directories(type):
            image = os.path.join(directory, img)
            if os.path.exists(image):
                self.project.emit_notification("log.info", {"message": f"Uploading missing image {img}"})
                try:
                    with open(image, "rb") as f:
                        await self._compute.post(
                            f"/{self._node_type}/images/{os.path.basename(img)}", data=f, timeout=None
                        )
                except OSError as e:
                    raise ControllerError(f"Can't upload {image}: {str(e)}")
                self.project.emit_notification("log.info", {"message": f"Upload finished for {img}"})
                return True
        return False

    async def _add_docker_image_digest(self, data):
        """
        Pin the Docker image of a node to the image id found on the Docker daemon
        of the controller host, so that a compute holding a different image under
        the same tag (e.g. a moved :latest) gets it re-synced instead of silently
        reusing the stale copy. Not set when the image is not on the controller host.
        """

        from gns3server.compute.docker import Docker
        from gns3server.compute.docker.docker_error import DockerError

        image = data.get("image")
        if not image:
            return
        try:
            image_info = await Docker.instance().query("GET", f"images/{image}/json")
        except DockerError:
            # not available on the controller host: nothing to pin against
            return
        image_id = image_info.get("Id")
        if image_id:
            data["image_digest"] = image_id

    async def _sync_missing_docker_image(self, image):
        """
        Export a Docker image from the Docker daemon on the controller host and
        stream it to the remote compute, or ask the compute to pull it when the
        image is not available locally
        """

        from gns3server.compute.docker import Docker
        from gns3server.compute.docker.docker_error import DockerError

        try:
            response = await Docker.instance().http_query("GET", f"images/{image}/get", timeout=None)
        except DockerError:
            # the image is not on the Docker daemon of the controller host: ask the
            # compute to pull it from the Docker repository as a fallback
            self.project.emit_notification(
                "log.info",
                {"message": f"Docker image '{image}' is not on the controller host, "
                            f"asking compute '{self._compute.name}' to pull it"}
            )
            await self._compute.post("/docker/images/pull", data={"image": image}, timeout=None)
            return True

        self.project.emit_notification(
            "log.info",
            {"message": f"Syncing Docker image '{image}' to compute '{self._compute.name}'"}
        )
        try:
            await self._compute.post("/docker/images/load", data=response.content, timeout=None)
        finally:
            response.close()
        self.project.emit_notification(
            "log.info",
            {"message": f"Docker image '{image}' has been synced to compute '{self._compute.name}'"}
        )
        return True

    async def dynamips_auto_idlepc(self):
        """
        Compute the idle PC for a dynamips node
        """
        return (
            await self._compute.get(
                f"/projects/{self._project.id}/{self._node_type}/nodes/{self._id}/auto_idlepc", timeout=240
            )
        ).json

    async def dynamips_idlepc_proposals(self):
        """
        Compute a list of potential idle PC
        """
        return (
            await self._compute.get(
                f"/projects/{self._project.id}/{self._node_type}/nodes/{self._id}/idlepc_proposals", timeout=240
            )
        ).json

    def get_port(self, adapter_number, port_number):
        """
        Return the port for this adapter_number and port_number
        or returns None if the port is not found
        """
        for port in self.ports:
            if port.adapter_number == adapter_number and port.port_number == port_number:
                return port
        return None

    def _list_ports(self):
        """
        Generate the list of port display in the client
        if the compute has sent a list we return it (use by
        node where you can not personalize the port naming).
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
                self._ports.append(PortFactory(f"{port}", 0, 0, port, "atm"))
            return

        elif self._node_type == "frame_relay_switch":
            frame_relay_port = set()
            # Mapping is like {"1:101": "10:202"}
            for source, dest in self._properties["mappings"].items():
                frame_relay_port.add(int(source.split(":")[0]))
                frame_relay_port.add(int(dest.split(":")[0]))
            frame_relay_port = sorted(frame_relay_port)
            for port in frame_relay_port:
                self._ports.append(PortFactory(f"{port}", 0, 0, port, "frame_relay"))
            return
        elif self._node_type == "dynamips":
            self._ports = DynamipsPortFactory(self._properties)
            return
        elif self._node_type == "docker":
            if is_iol_runner_environment(self._properties.get("environment")):
                # IOL adapters are 4-port units (the IOU model): ports are
                # Ethernet0/0-3, Ethernet1/0-3, … addressed as
                # (adapter_number, port_number 0-3).
                self._ports = StandardPortFactory(
                    self._properties,
                    4,
                    self._first_port_name,
                    "Ethernet{segment0}/{port0}",
                    4,
                    self.custom_adapters,
                )
            else:
                for adapter_number in range(0, self._properties["adapters"]):
                    custom_adapter_settings = {}
                    if self.custom_adapters:
                        for custom_adapter in self.custom_adapters:
                            if custom_adapter["adapter_number"] == adapter_number:
                                custom_adapter_settings = custom_adapter
                                break
                    port_name = f"eth{adapter_number}"
                    port_name = custom_adapter_settings.get("port_name", port_name)
                    mac_address = custom_adapter_settings.get("mac_address")
                    if not mac_address and "mac_address" in self._properties:
                        mac_address = int_to_macaddress(macaddress_to_int(self._properties["mac_address"]) + adapter_number)

                    port = PortFactory(port_name, 0, adapter_number, 0, "ethernet", short_name=port_name)
                    port.mac_address = mac_address
                    self._ports.append(port)
        elif self._node_type in ("ethernet_switch", "ethernet_hub"):
            # Basic node we don't want to have adapter number
            port_number = 0
            for port in self._properties.get("ports_mapping", []):
                self._ports.append(
                    PortFactory(port["name"], 0, 0, port_number, "ethernet", short_name=f"e{port_number}")
                )
                port_number += 1
        elif self._node_type in ("vpcs"):
            self._ports.append(PortFactory("Ethernet0", 0, 0, 0, "ethernet", short_name="e0"))
        elif self._node_type in ("cloud", "nat"):
            port_number = 0
            for port in self._properties.get("ports_mapping", []):
                self._ports.append(PortFactory(port["name"], 0, 0, port_number, "ethernet", short_name=port["name"]))
                port_number += 1
        else:
            self._ports = StandardPortFactory(
                self._properties,
                self._port_by_adapter,
                self._first_port_name,
                self._port_name_format,
                self._port_segment_size,
                self._custom_adapters,
            )

    def __repr__(self):
        return f"<gns3server.controller.Node {self._node_type} {self._name}>"

    def __eq__(self, other):
        if not isinstance(other, Node):
            return False
        return self.id == other.id and other.project.id == self.project.id

    def asdict(self, topology_dump=False):
        """
        :param topology_dump: Filter to keep only properties required for saving on disk
        """

        topology = {
                "compute_id": str(self._compute.id),
                "node_id": self._id,
                "node_type": self._node_type,
                "template_id": self._template_id,
                "name": self._name,
                "console": self._console,
                "console_type": self._console_type,
                "console_auto_start": self._console_auto_start,
                "netmiko_device_type": self._netmiko_device_type,
                "default_username": self._default_username,
                "default_password": self._default_password,
                "aux": self._aux,
                "aux_type": self._aux_type,
                "properties": self._properties,
                "label": self._label,
                "x": self._x,
                "y": self._y,
                "z": self._z,
                "locked": self._locked,
                "width": self._width,
                "height": self._height,
                "symbol": self._symbol,
                "port_name_format": self._port_name_format,
                "port_segment_size": self._port_segment_size,
                "first_port_name": self._first_port_name,
                "custom_adapters": self._custom_adapters,
                "tags": self._tags,
        }

        if topology_dump:
            return topology

        additional_data = {
            "project_id": self._project.id,
            "command_line": self._command_line,
            "status": self._status,
            "console_host": str(self._compute.console_host),
            "node_directory": self._node_directory,
            "ports": [port.asdict() for port in self.ports],
            "missing_image": self.missing_image,
            "missing_images": self._missing_images,
        }
        topology.update(additional_data)
        return topology
