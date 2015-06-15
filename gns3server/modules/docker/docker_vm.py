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

"""
Docker container instance.
"""

import sys
import shlex
import re
import os
import tempfile
import json
import socket
import asyncio
import docker

from pkg_resources import parse_version
from .docker_error import DockerError
from ..base_vm import BaseVM

import logging
log = logging.getLogger(__name__)


class Container(BaseVM):
    """Docker container implementation.

    :param name: Docker container name
    :param project: Project instance
    :param manager: Manager instance
    :param image: Docker image
    """
    def __init__(self, name, image, project, manager):
        self._name = name
        self._project = project
        self._manager = manager
        self._image = image

        log.debug(
            "{module}: {name} [{image}] initialized.".format(
                module=self.manager.module_name,
                name=self.name,
                image=self._image))

    def __json__(self):
        return {
            "name": self._name,
            "id": self._id,
            "project_id": self._project.id,
            "image": self._image,
        }

    @asyncio.coroutine
    def _get_container_state(self):
        """Returns the container state (e.g. running, paused etc.)

        :returns: state
        :rtype: str
        """
        try:
            result = yield from self.manager.execute(
                "inspect_container", {"container": self._id})
            for state, value in result["State"].items():
                if value is True:
                    return state.lower()
            return 'exited'
        except Exception as err:
            raise DockerError("Could not get container state for {0}: ".format(
                self._name), str(err))

    @asyncio.coroutine
    def create(self):
        """Creates the Docker container."""
        result = yield from self.manager.execute(
            "create_container", {"name": self._name, "image": self._image})
        self._id = result['Id']
        log.info("Docker container '{name}' [{id}] created".format(
            name=self._name, id=self._id))
        return True

    @asyncio.coroutine
    def start(self):
        """Starts this Docker container."""
        state = yield from self._get_container_state()
        if state == "paused":
            self.unpause()
        else:
            result = yield from self.manager.execute(
                "start", {"container": self._id})
        log.info("Docker container '{name}' [{image}] started".format(
            name=self._name, image=self._image))

    def is_running(self):
        """Checks if the container is running.

        :returns: True or False
        :rtype: bool
        """
        state = self._get_container_state()
        if state == "running":
            return True
        return False

    @asyncio.coroutine
    def restart(self):
        """Restarts this Docker container."""
        result = yield from self.manager.execute(
            "restart", {"container": self._id})
        log.info("Docker container '{name}' [{image}] restarted".format(
            name=self._name, image=self._image))

    @asyncio.coroutine
    def stop(self):
        """Stops this Docker container."""
        result = yield from self.manager.execute(
            "kill", {"container": self._id})
        log.info("Docker container '{name}' [{image}] stopped".format(
            name=self._name, image=self._image))

    @asyncio.coroutine
    def pause(self):
        """Pauses this Docker container."""
        result = yield from self.manager.execute(
            "pause", {"container": self._id})
        log.info("Docker container '{name}' [{image}] paused".format(
            name=self._name, image=self._image))

    @asyncio.coroutine
    def unpause(self):
        """Unpauses this Docker container."""
        result = yield from self.manager.execute(
            "unpause", {"container": self._id})
        log.info("Docker container '{name}' [{image}] unpaused".format(
            name=self._name, image=self._image))

    @asyncio.coroutine
    def remove(self):
        """Removes this Docker container."""
        state = yield from self._get_container_state()
        if state == "paused":
            self.unpause()
        result = yield from self.manager.execute(
            "remove_container", {"container": self._id, "force": True})
        log.info("Docker container '{name}' [{image}] removed".format(
            name=self._name, image=self._image))
