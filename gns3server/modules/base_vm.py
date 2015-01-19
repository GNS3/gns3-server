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


import asyncio
from .vm_error import VMError
from ..config import Config

import logging
log = logging.getLogger(__name__)


class BaseVM:

    def __init__(self, name, identifier, manager):

        self._name = name
        self._id = identifier
        self._created = asyncio.Future()
        self._manager = manager
        self._config = Config.instance()
        asyncio.async(self._create())
        log.info("{type} device {name} [id={id}] has been created".format(type=self.__class__.__name__,
                                                                          name=self._name,
                                                                          id=self._id))

    #TODO: When delete release console ports


    @property
    def id(self):
        """
        Returns the unique ID for this VM.

        :returns: id (integer)
        """

        return self._id

    @property
    def name(self):
        """
        Returns the name for this VM.

        :returns: name (string)
        """

        return self._name

    @asyncio.coroutine
    def _execute(self, command):
        """
        Called when we receive an event.
        """

        raise NotImplementedError

    @asyncio.coroutine
    def _create(self):
        """
        Called when the run module is created and ready to receive
        commands. It's asynchronous.
        """
        self._created.set_result(True)
        log.info("{type} device {name} [id={id}] has been created".format(type=self.__class__.__name__,
                                                                          name=self._name,
                                                                          id=self._id))

    def wait_for_creation(self):
        return self._created

    @asyncio.coroutine
    def start(self):
        """
        Starts the VM process.
        """

        raise NotImplementedError


    @asyncio.coroutine
    def stop(self):
        """
        Starts the VM process.
        """

        raise NotImplementedError

