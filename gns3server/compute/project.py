# -*- coding: utf-8 -*-
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

import os
import aiohttp
import shutil
import asyncio
import hashlib

from uuid import UUID, uuid4

from .port_manager import PortManager
from .notification_manager import NotificationManager
from ..config import Config
from ..utils.asyncio import wait_run_in_executor
from ..utils.path import check_path_allowed, get_default_project_directory

import logging
log = logging.getLogger(__name__)


class Project:

    """
    A project contains a list of nodes.
    In theory nodes are isolated project/project.

    :param project_id: force project identifier (None by default auto generate an UUID)
    :param path: path of the project. (None use the standard directory)
    """

    def __init__(self, name=None, project_id=None, path=None, variables=None):

        self._name = name
        if project_id:
            try:
                UUID(project_id, version=4)
            except ValueError:
                raise aiohttp.web.HTTPBadRequest(text="{} is not a valid UUID".format(project_id))
        else:
            project_id = str(uuid4())
        self._id = project_id
        self._deleted = False
        self._nodes = set()
        self._used_tcp_ports = set()
        self._used_udp_ports = set()
        self._variables = variables

        if path is None:
            location = get_default_project_directory()
            path = os.path.join(location, self._id)
        try:
            os.makedirs(path, exist_ok=True)
        except OSError as e:
            raise aiohttp.web.HTTPInternalServerError(text="Could not create project directory: {}".format(e))
        self.path = path

        try:
            if os.path.exists(self.tmp_working_directory()):
                shutil.rmtree(self.tmp_working_directory())
        except OSError as e:
            raise aiohttp.web.HTTPInternalServerError(text="Could not clean project directory: {}".format(e))

        log.info("Project {id} with path '{path}' created".format(path=self._path, id=self._id))

    def __json__(self):

        return {
            "name": self._name,
            "project_id": self._id,
            "variables": self._variables
        }

    def _config(self):

        return Config.instance().get_section_config("Server")

    def is_local(self):

        return self._config().getboolean("local", False)

    @property
    def id(self):

        return self._id

    @property
    def path(self):

        return self._path

    @path.setter
    def path(self, path):
        check_path_allowed(path)

        if hasattr(self, "_path"):
            if path != self._path and self.is_local() is False:
                raise aiohttp.web.HTTPForbidden(text="Changing the project directory path is not allowed")

        self._path = path

    @property
    def name(self):

        return self._name

    @name.setter
    def name(self, name):

        if "/" in name or "\\" in name:
            raise aiohttp.web.HTTPForbidden(text="Project names cannot contain path separators")
        self._name = name

    @property
    def nodes(self):

        return self._nodes

    @property
    def variables(self):
        return self._variables

    @variables.setter
    def variables(self, variables):
        self._variables = variables

    def record_tcp_port(self, port):
        """
        Associate a reserved TCP port number with this project.

        :param port: TCP port number
        """

        if port not in self._used_tcp_ports:
            self._used_tcp_ports.add(port)

    def record_udp_port(self, port):
        """
        Associate a reserved UDP port number with this project.

        :param port: UDP port number
        """

        if port not in self._used_udp_ports:
            self._used_udp_ports.add(port)

    def remove_tcp_port(self, port):
        """
        Removes an associated TCP port number from this project.

        :param port: TCP port number
        """

        if port in self._used_tcp_ports:
            self._used_tcp_ports.remove(port)

    def remove_udp_port(self, port):
        """
        Removes an associated UDP port number from this project.

        :param port: UDP port number
        """

        if port in self._used_udp_ports:
            self._used_udp_ports.remove(port)

    def module_working_directory(self, module_name):
        """
        Returns a working directory for the module
        The directory is created if the directory doesn't exist.

        :param module_name: name for the module
        :returns: working directory
        """

        workdir = self.module_working_path(module_name)
        if not self._deleted:
            try:
                os.makedirs(workdir, exist_ok=True)
            except OSError as e:
                raise aiohttp.web.HTTPInternalServerError(text="Could not create module working directory: {}".format(e))
        return workdir

    def module_working_path(self, module_name):
        """
        Returns the working directory for the module. If you want
        to be sure to have the directory on disk take a look on:
            module_working_directory
        """

        return os.path.join(self._path, "project-files", module_name)

    def node_working_directory(self, node):
        """
        Returns a working directory for a specific node.
        If the directory doesn't exist, the directory is created.

        :param node: Node instance

        :returns: Node working directory
        """

        workdir = self.node_working_path(node)
        if not self._deleted:
            try:
                os.makedirs(workdir, exist_ok=True)
            except OSError as e:
                raise aiohttp.web.HTTPInternalServerError(text="Could not create the node working directory: {}".format(e))
        return workdir

    def node_working_path(self, node):
        """
        Returns a node working path for node. It doesn't create structure if not present on system.
        :param node: Node instance
        :return: Node working path
        """
        return os.path.join(self._path, "project-files", node.manager.module_name.lower(), node.id)


    def tmp_working_directory(self):
        """
        A temporary directory. Will be clean at project open and close
        """
        return os.path.join(self._path, "tmp")

    def capture_working_directory(self):
        """
        Returns a working directory where to store packet capture files.

        :returns: path to the directory
        """

        workdir = os.path.join(self._path, "project-files", "captures")
        if not self._deleted:
            try:
                os.makedirs(workdir, exist_ok=True)
            except OSError as e:
                raise aiohttp.web.HTTPInternalServerError(text="Could not create the capture working directory: {}".format(e))
        return workdir

    def add_node(self, node):
        """
        Adds a node to the project.
        In theory this should be called by the node manager.

        :param node: Node instance
        """

        self._nodes.add(node)

    def get_node(self, node_id):
        """
        Returns a Node instance.

        :param node_id: Node identifier

        :returns: Node instance
        """

        try:
            UUID(node_id, version=4)
        except ValueError:
            raise aiohttp.web.HTTPBadRequest(text="Node ID {} is not a valid UUID".format(node_id))

        for node in self._nodes:
            if node.id == node_id:
                return node

        raise aiohttp.web.HTTPNotFound(text="Node ID {} doesn't exist".format(node_id))

    async def remove_node(self, node):
        """
        Removes a node from the project.
        In theory this should be called by the node manager.

        :param node: Node instance
        """

        if node in self._nodes:
            await node.delete()
            self._nodes.remove(node)

    async def update(self, variables=None, **kwargs):
        original_variables = self.variables
        self.variables = variables

        # we need to update docker nodes when variables changes
        if original_variables != variables:
            for node in self.nodes:
                if hasattr(node, 'update'):
                    await node.update()

    async def close(self):
        """
        Closes the project, but keep project data on disk
        """

        project_nodes_id = set([n.id for n in self.nodes])

        for module in self.compute():
            module_nodes_id = set([n.id for n in module.instance().nodes])
            # We close the project only for the modules using it
            if len(module_nodes_id & project_nodes_id):
                await module.instance().project_closing(self)

        await self._close_and_clean(False)

        for module in self.compute():
            module_nodes_id = set([n.id for n in module.instance().nodes])
            # We close the project only for the modules using it
            if len(module_nodes_id & project_nodes_id):
                await module.instance().project_closed(self)

        try:
            if os.path.exists(self.tmp_working_directory()):
                shutil.rmtree(self.tmp_working_directory())
        except OSError:
            pass

    async def _close_and_clean(self, cleanup):
        """
        Closes the project, and cleanup the disk if cleanup is True

        :param cleanup: Whether to delete the project directory
        """

        tasks = []
        for node in self._nodes:
            tasks.append(asyncio.ensure_future(node.manager.close_node(node.id)))

        if tasks:
            done, _ = await asyncio.wait(tasks)
            for future in done:
                try:
                    future.result()
                except (Exception, GeneratorExit) as e:
                    log.error("Could not close node {}".format(e), exc_info=1)

        if cleanup and os.path.exists(self.path):
            self._deleted = True
            try:
                await wait_run_in_executor(shutil.rmtree, self.path)
                log.info("Project {id} with path '{path}' deleted".format(path=self._path, id=self._id))
            except OSError as e:
                raise aiohttp.web.HTTPInternalServerError(text="Could not delete the project directory: {}".format(e))
        else:
            log.info("Project {id} with path '{path}' closed".format(path=self._path, id=self._id))

        if self._used_tcp_ports:
            log.warning("Project {} has TCP ports still in use: {}".format(self.id, self._used_tcp_ports))
        if self._used_udp_ports:
            log.warning("Project {} has UDP ports still in use: {}".format(self.id, self._used_udp_ports))

        # clean the remaining ports that have not been cleaned by their respective node.
        port_manager = PortManager.instance()
        for port in self._used_tcp_ports.copy():
            port_manager.release_tcp_port(port, self)
        for port in self._used_udp_ports.copy():
            port_manager.release_udp_port(port, self)

    async def delete(self):
        """
        Removes project from disk
        """

        for module in self.compute():
            await module.instance().project_closing(self)
        await self._close_and_clean(True)
        for module in self.compute():
            await module.instance().project_closed(self)

    def compute(self):
        """
        Returns all loaded modules from compute.
        """

        # We import it at the last time to avoid circular dependencies
        from ..compute import MODULES
        return MODULES

    def emit(self, action, event):
        """
        Send an event to all the client listening for notifications

        :param action: Action name
        :param event: Event to send
        """
        NotificationManager.instance().emit(action, event, project_id=self.id)

    async def list_files(self):
        """
        :returns: Array of files in project without temporary files. The files are dictionary {"path": "test.bin", "md5sum": "aaaaa"}
        """

        files = []
        for dirpath, dirnames, filenames in os.walk(self.path, followlinks=False):
            for filename in filenames:
                if not filename.endswith(".ghost"):
                    path = os.path.relpath(dirpath, self.path)
                    path = os.path.join(path, filename)
                    path = os.path.normpath(path)
                    file_info = {"path": path}

                    try:
                        file_info["md5sum"] = await wait_run_in_executor(self._hash_file, os.path.join(dirpath, filename))
                    except OSError:
                        continue
                    files.append(file_info)

        return files

    def _hash_file(self, path):
        """
        Compute and md5 hash for file

        :returns: hexadecimal md5
        """

        m = hashlib.md5()
        with open(path, "rb") as f:
            while True:
                buf = f.read(128)
                if not buf:
                    break
                m.update(buf)
        return m.hexdigest()
