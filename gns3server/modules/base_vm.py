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

from ..utils.asyncio import wait_run_in_executor

log = logging.getLogger(__name__)


class BaseVM:

    def __init__(self, name, vm_id, project, manager):

        self._name = name
        self._id = vm_id
        self._project = project
        self._manager = manager

        log.debug("{module}: {name} [{id}] initialized".format(module=self.manager.module_name,
                                                               name=self.name,
                                                               id=self.id))

    def __del__(self):

        self.close()

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
