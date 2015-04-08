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
import logging
import aiohttp
import shutil
import asyncio
import tempfile

from ..utils.asyncio import wait_run_in_executor
from .vm_error import VMError

log = logging.getLogger(__name__)


class BaseVM:

    """
    Base vm implementation.

    :param name: name of this IOU vm
    :param vm_id: IOU instance identifier
    :param project: Project instance
    :param manager: parent VM Manager
    :param console: TCP console port
    """

    def __init__(self, name, vm_id, project, manager, console=None):

        self._name = name
        self._id = vm_id
        self._project = project
        self._manager = manager
        self._console = console
        self._temporary_directory = None

        if self._console is not None:
            self._console = self._manager.port_manager.reserve_tcp_port(self._console, self._project)
        else:
            self._console = self._manager.port_manager.get_free_tcp_port(self._project)

        log.debug("{module}: {name} [{id}] initialized. Console port {console}".format(module=self.manager.module_name,
                                                                                       name=self.name,
                                                                                       id=self.id,
                                                                                       console=self._console))

    def __del__(self):

        self.close()
        if self._temporary_directory is not None:
            if os.path.exists(self._temporary_directory):
                shutil.rmtree(self._temporary_directory, ignore_errors=True)

    @property
    def project(self):
        """
        Returns the VM current project.

        :returns: Project instance.
        """

        return self._project

    @property
    def name(self):
        """
        Returns the name for this VM.

        :returns: name
        """

        return self._name

    @name.setter
    def name(self, new_name):
        """
        Sets the name of this VM.

        :param new_name: name
        """

        log.info("{module}: {name} [{id}] renamed to {new_name}".format(module=self.manager.module_name,
                                                                        name=self.name,
                                                                        id=self.id,
                                                                        new_name=new_name))
        self._name = new_name

    @property
    def id(self):
        """
        Returns the ID for this VM.

        :returns: VM identifier (string)
        """

        return self._id

    @property
    def manager(self):
        """
        Returns the manager for this VM.

        :returns: instance of manager
        """

        return self._manager

    @property
    def working_dir(self):
        """
        Return VM working directory
        """

        return self._project.vm_working_directory(self)

    @property
    def temporary_directory(self):
        if self._temporary_directory is None:
            try:
                self._temporary_directory = tempfile.mkdtemp()
            except OSError as e:
                raise VMError("Can't create temporary directory: {}".format(e))
        return self._temporary_directory

    def create(self):
        """
        Creates the VM.
        """

        log.info("{module}: {name} [{id}] created".format(module=self.manager.module_name,
                                                          name=self.name,
                                                          id=self.id))

    @asyncio.coroutine
    def delete(self):
        """
        Delete the VM (including all its files).
        """

        directory = self.project.vm_working_directory(self)
        if os.path.exists(directory):
            try:
                yield from wait_run_in_executor(shutil.rmtree, directory)
            except OSError as e:
                raise aiohttp.web.HTTPInternalServerError(text="Could not delete the VM working directory: {}".format(e))

    def start(self):
        """
        Starts the VM process.
        """

        raise NotImplementedError

    def stop(self):
        """
        Starts the VM process.
        """

        raise NotImplementedError

    def close(self):
        """
        Close the VM process.
        """

        raise NotImplementedError

    @property
    def console(self):
        """
        Returns the console port of this VPCS vm.

        :returns: console port
        """

        return self._console

    @console.setter
    def console(self, console):
        """
        Changes the console port

        :params console: Console port (integer)
        """

        if console == self._console:
            return
        if self._console:
            self._manager.port_manager.release_tcp_port(self._console, self._project)
        self._console = self._manager.port_manager.reserve_tcp_port(console, self._project)
        log.info("{module}: '{name}' [{id}]: console port set to {port}".format(module=self.manager.module_name,
                                                                                name=self.name,
                                                                                id=self.id,
                                                                                port=console))
