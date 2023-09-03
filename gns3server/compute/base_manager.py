#
# Copyright (C) 2015 GNS3 Technologies Inc.
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

import sys
import os
import struct
import stat
import asyncio
import aiofiles
import socket
import shutil
import re
import logging

log = logging.getLogger(__name__)

from gns3server.utils.asyncio import cancellable_wait_run_in_executor
from gns3server.compute.compute_error import ComputeError, ComputeForbiddenError, ComputeNotFoundError
from gns3server.utils.interfaces import is_interface_up

from uuid import UUID, uuid4
from typing import Type
from ..config import Config
from ..utils.asyncio import wait_run_in_executor
from ..utils import force_unix_path
from .project_manager import ProjectManager
from .port_manager import PortManager
from .base_node import BaseNode

from .nios.nio_udp import NIOUDP
from .nios.nio_tap import NIOTAP
from .nios.nio_ethernet import NIOEthernet
from ..utils.images import md5sum, remove_checksum, images_directories, default_images_directory, list_images
from .error import NodeError, ImageMissingError

CHUNK_SIZE = 1024 * 8  # 8KB


class BaseManager:

    """
    Base class for all Manager classes.
    Responsible of management of a node pool of the same type.
    """

    _convert_lock = None

    def __init__(self):

        BaseManager._convert_lock = asyncio.Lock()
        self._nodes = {}
        self._port_manager = None
        self._config = Config.instance()

    @classmethod
    def node_types(cls):
        """
        :returns: Array of supported node type on this computer
        """

        # By default we transform DockerVM => docker but you can override this (see builtins)
        return [cls._NODE_CLASS.__name__.rstrip("VM").lower()]

    @property
    def nodes(self):
        """
        List of nodes manage by the module
        """

        return self._nodes.values()

    @classmethod
    def instance(cls):
        """
        Singleton to return only one instance of BaseManager.

        :returns: instance of BaseManager
        """

        if not hasattr(cls, "_instance") or cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def module_name(self):
        """
        Returns the module name.

        :returns: module name
        """

        return self.__class__.__name__

    @property
    def port_manager(self):
        """
        Returns the port manager.

        :returns: Port manager
        """

        if self._port_manager is None:
            self._port_manager = PortManager.instance()
        return self._port_manager

    @port_manager.setter
    def port_manager(self, new_port_manager):

        self._port_manager = new_port_manager

    @property
    def config(self):
        """
        Returns the server config.

        :returns: Config
        """

        return self._config

    async def unload(self):

        tasks = []
        for node_id in self._nodes.keys():
            tasks.append(asyncio.ensure_future(self.close_node(node_id)))

        if tasks:
            done, _ = await asyncio.wait(tasks)
            for future in done:
                try:
                    future.result()
                except (Exception, GeneratorExit) as e:
                    log.error(f"Could not close node: {e}", exc_info=1)
                    continue

        if hasattr(BaseManager, "_instance"):
            BaseManager._instance = None
        log.debug(f"Module {self.module_name} unloaded")

    def get_node(self, node_id, project_id=None) -> Type[BaseNode]:
        """
        Returns a Node instance.

        :param node_id: Node identifier
        :param project_id: Project identifier

        :returns: Node instance
        """

        if project_id:
            # check the project_id exists
            project = ProjectManager.instance().get_project(project_id)

        try:
            UUID(node_id, version=4)
        except ValueError:
            raise ComputeError(f"Node ID {node_id} is not a valid UUID")

        if node_id not in self._nodes:
            raise ComputeNotFoundError(f"Node ID {node_id} doesn't exist")

        node = self._nodes[node_id]
        if project_id:
            if node.project.id != project.id:
                raise ComputeNotFoundError("Project ID {project_id} doesn't belong to node {node.name}")

        return node

    async def create_node(self, name, project_id, node_id, *args, **kwargs):
        """
        Create a new node

        :param name: Node name
        :param project_id: Project identifier
        :param node_id: restore a node identifier
        """

        if node_id in self._nodes:
            return self._nodes[node_id]

        project = ProjectManager.instance().get_project(project_id)
        if not node_id:
            node_id = str(uuid4())

        node = self._NODE_CLASS(name, node_id, project, self, *args, **kwargs)
        if asyncio.iscoroutinefunction(node.create):
            await node.create()
        else:
            node.create()
        self._nodes[node.id] = node
        project.add_node(node)
        return node

    async def duplicate_node(self, source_node_id, destination_node_id):
        """
        Duplicate a node

        :param source_node_id: Source node identifier
        :param destination_node_id: Destination node identifier
        :returns: New node instance
        """

        source_node = self.get_node(source_node_id)
        destination_node = self.get_node(destination_node_id)

        # Some node don't have working dir like switch
        if not hasattr(destination_node, "working_dir"):
            return destination_node

        destination_dir = destination_node.working_dir
        try:
            shutil.rmtree(destination_dir)
            shutil.copytree(source_node.working_dir, destination_dir, symlinks=True, ignore_dangling_symlinks=True)
        except OSError as e:
            raise ComputeError(f"Cannot duplicate node data: {e}")

        # We force a refresh of the name. This forces the rewrite
        # of some configuration files
        node_name = destination_node.name
        destination_node.name = node_name + str(uuid4())
        destination_node.name = node_name

        return destination_node

    async def close_node(self, node_id):
        """
        Close a node

        :param node_id: Node identifier

        :returns: Node instance
        """

        node = self.get_node(node_id)
        if asyncio.iscoroutinefunction(node.close):
            await node.close()
        else:
            node.close()
        return node

    async def project_closing(self, project):
        """
        Called when a project is about to be closed.

        :param project: Project instance
        """

        pass

    async def project_closed(self, project):
        """
        Called when a project is closed.

        :param project: Project instance
        """

        for node in project.nodes:
            if node.id in self._nodes:
                del self._nodes[node.id]

    async def delete_node(self, node_id):
        """
        Delete a node. The node working directory will be destroyed when a commit is received.

        :param node_id: Node identifier
        :returns: Node instance
        """

        node = None
        try:
            node = self.get_node(node_id)
            await self.close_node(node_id)
        finally:
            if node:
                node.project.emit("node.deleted", node)
                await node.project.remove_node(node)
        if node.id in self._nodes:
            del self._nodes[node.id]
        return node

    @staticmethod
    def has_privileged_access(executable):
        """
        Check if an executable have the right to attach to Ethernet and TAP adapters.

        :param executable: executable path

        :returns: True or False
        """

        if sys.platform.startswith("darwin"):
            if os.stat(executable).st_uid == 0:
                return True

        if os.geteuid() == 0:
            # we are root, so we should have privileged access.
            return True

        if os.stat(executable).st_uid == 0 and (
            os.stat(executable).st_mode & stat.S_ISUID or os.stat(executable).st_mode & stat.S_ISGID
        ):
            # the executable has set UID bit.
            return True

        # test if the executable has the CAP_NET_RAW capability (Linux only)
        try:
            if sys.platform.startswith("linux") and "security.capability" in os.listxattr(executable):
                caps = os.getxattr(executable, "security.capability")
                # test the 2nd byte and check if the 13th bit (CAP_NET_RAW) is set
                if struct.unpack("<IIIII", caps)[1] & 1 << 13:
                    return True
        except (AttributeError, OSError) as e:
            log.error(f"Could not determine if CAP_NET_RAW capability is set for {executable}: {e}")

        return False

    def create_nio(self, nio_settings):
        """
        Creates a new NIO.

        :param nio_settings: information to create the NIO

        :returns: a NIO object
        """

        nio = None
        if nio_settings["type"] == "nio_udp":
            lport = nio_settings["lport"]
            rhost = nio_settings["rhost"]
            rport = nio_settings["rport"]
            try:
                info = socket.getaddrinfo(rhost, rport, socket.AF_UNSPEC, socket.SOCK_DGRAM, 0, socket.AI_PASSIVE)
                if not info:
                    raise ComputeError(f"getaddrinfo returned an empty list on {rhost}:{rport}")
                for res in info:
                    af, socktype, proto, _, sa = res
                    with socket.socket(af, socktype, proto) as sock:
                        sock.connect(sa)
            except OSError as e:
                raise ComputeError(f"Could not create an UDP connection to {rhost}:{rport}: {e}")
            nio = NIOUDP(lport, rhost, rport)
            nio.filters = nio_settings.get("filters", {})
            nio.suspend = nio_settings.get("suspend", False)
        elif nio_settings["type"] == "nio_tap":
            tap_device = nio_settings["tap_device"]
            # if not is_interface_up(tap_device):
            #    raise aiohttp.web.HTTPConflict(text="TAP interface {} does not exist or is down".format(tap_device))
            # FIXME: check for permissions on tap device
            # if not self.has_privileged_access(executable):
            #    raise aiohttp.web.HTTPForbidden(text="{} has no privileged access to {}.".format(executable, tap_device))
            nio = NIOTAP(tap_device)
        elif nio_settings["type"] in ("nio_generic_ethernet", "nio_ethernet"):
            ethernet_device = nio_settings["ethernet_device"]
            if not is_interface_up(ethernet_device):
                raise ComputeError(f"Ethernet interface {ethernet_device} does not exist or is down")
            nio = NIOEthernet(ethernet_device)
        assert nio is not None
        return nio

    async def stream_pcap_file(self, nio, project_id):
        """
        Streams a PCAP file.

        :param nio: NIO object
        :param project_id: Project identifier
        """

        if not nio.capturing:
            raise ComputeError("Nothing to stream because there is no packet capture active")

        project = ProjectManager.instance().get_project(project_id)
        path = os.path.normpath(os.path.join(project.capture_working_directory(), nio.pcap_output_file))

        # Raise an error if user try to escape
        if path[0] == ".":
            raise ComputeForbiddenError("Cannot stream PCAP file outside the capture working directory")

        try:
            with open(path, "rb") as f:
                while nio.capturing:
                    data = f.read(CHUNK_SIZE)
                    if not data:
                        await asyncio.sleep(0.1)
                        continue
                    yield data
        except FileNotFoundError:
            raise ComputeNotFoundError(f"File '{path}' not found")
        except PermissionError:
            raise ComputeForbiddenError(f"File '{path}' cannot be accessed")

    def get_abs_image_path(self, path, extra_dir=None):
        """
        Get the absolute path of an image

        :param path: file path
        :param extra_dir: an additional directory to be added to the search path

        :returns: file path
        """

        if not path or path == ".":
            return ""
        orig_path = os.path.normpath(path)

        img_directory = self.get_images_directory()
        valid_directory_prefices = images_directories(self._NODE_TYPE)
        if extra_dir:
            valid_directory_prefices.append(extra_dir)

        # Windows path should not be send to a unix server
        if re.match(r"^[A-Z]:", path) is not None:
            raise NodeError(
                f"'{path}' is not allowed on this remote server (Windows path). Please only use a file from '{img_directory}'"
            )

        if not os.path.isabs(orig_path):

            for directory in valid_directory_prefices:
                log.debug(f"Searching for image '{orig_path}' in '{directory}'")
                path = self._recursive_search_file_in_directory(directory, orig_path)
                if path:
                    return force_unix_path(path)

            # Not found we try the default directory
            log.debug(f"Searching for image '{orig_path}' in default directory")
            s = os.path.split(orig_path)
            path = force_unix_path(os.path.join(img_directory, *s))
            if os.path.exists(path):
                return path
            raise ImageMissingError(orig_path)

        # Check to see if path is an absolute path to a valid directory
        path = force_unix_path(path)
        for directory in valid_directory_prefices:
            log.debug(f"Searching for image '{orig_path}' in '{directory}'")
            if os.path.commonprefix([directory, path]) == directory:
                if os.path.exists(path):
                    return path
                raise ImageMissingError(orig_path)
        raise NodeError(f"'{path}' is not allowed on this remote server. Please only use a file from '{img_directory}'")

    def _recursive_search_file_in_directory(self, directory, searched_file):
        """
        Search for a file in directory and is subdirectories

        :returns: Path or None if not found
        """
        s = os.path.split(searched_file)

        for root, dirs, files in os.walk(directory):
            for file in files:
                if s[1] == file and (s[0] == '' or root == os.path.join(directory, s[0])):
                    path = os.path.normpath(os.path.join(root, s[1]))
                    if os.path.exists(path):
                        return path
        return None

    def get_relative_image_path(self, path, extra_dir=None):
        """
        Get a path relative to images directory path
        or an abspath if the path is not located inside
        image directory

        :param path: file path
        :param extra_dir: an additional directory to be added to the search path

        :returns: file path
        """

        if not path:
            return ""

        path = force_unix_path(self.get_abs_image_path(path, extra_dir))
        img_directory = self.get_images_directory()

        valid_directory_prefices = images_directories(self._NODE_TYPE)
        if extra_dir:
            valid_directory_prefices.append(extra_dir)

        for directory in valid_directory_prefices:
            if os.path.commonprefix([directory, path]) == directory:
                relpath = os.path.relpath(path, directory)
                # We don't allow to recurse search from the top image directory just for image type directory (compatibility with old releases)
                if os.sep not in relpath or directory == img_directory:
                    return relpath
        return path

    async def list_images(self):
        """
        Return the list of available images for this node type

        :returns: Array of hash
        """

        try:
            return await list_images(self._NODE_TYPE)
        except OSError as e:
            raise ComputeError(f"Can not list images {e}")

    def get_images_directory(self):
        """
        Get the image directory on disk
        """

        if hasattr(self, "_NODE_TYPE"):
            return default_images_directory(self._NODE_TYPE)
        raise NotImplementedError

    async def write_image(self, filename, stream):

        directory = self.get_images_directory()
        path = os.path.abspath(os.path.join(directory, *os.path.split(filename)))
        if os.path.commonprefix([directory, path]) != directory:
            raise ComputeForbiddenError(f"Could not write image: {filename}, '{path}' is forbidden")
        log.info(f"Writing image file to '{path}'")
        try:
            remove_checksum(path)
            # We store the file under his final name only when the upload is finished
            tmp_path = path + ".tmp"
            os.makedirs(os.path.dirname(path), exist_ok=True)
            async with aiofiles.open(tmp_path, "wb") as f:
                async for chunk in stream:
                    await f.write(chunk)
            os.chmod(tmp_path, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
            shutil.move(tmp_path, path)
            await cancellable_wait_run_in_executor(md5sum, path)
        except OSError as e:
            raise ComputeError(f"Could not write image '{filename}': {e}")

    def reset(self):
        """
        Reset module for tests
        """
        self._nodes = {}
