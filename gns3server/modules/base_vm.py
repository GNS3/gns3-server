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


import logging
log = logging.getLogger(__name__)


class BaseVM:

    def __init__(self, name, uuid, project, manager):

        self._name = name
        self._uuid = uuid
        self._project = project
        self._manager = manager

        log.info("{module}: {name} [{uuid}] has been created".format(module=self.manager.module_name,
                                                                     name=self.name,
                                                                     uuid=self.uuid))

    # TODO: When delete release console ports

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

        log.info("{module}: {name} [{uuid}]: renamed to {new_name}".format(module=self.manager.module_name,
                                                                           name=self.name,
                                                                           uuid=self.uuid,
                                                                           new_name=new_name))
        self._name = new_name

    @property
    def uuid(self):
        """
        Returns the UUID for this VM.

        :returns: uuid (string)
        """

        return self._uuid

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

        return self._project.vm_working_directory(self.manager.module_name.lower(), self._uuid)

    def create(self):
        """
        Creates the VM.
        """

        return

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
