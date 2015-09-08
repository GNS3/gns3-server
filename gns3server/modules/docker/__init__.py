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
Docker server module.
"""

import os
import sys
import shutil
import asyncio
import subprocess
import logging
import docker

log = logging.getLogger(__name__)

from ..base_manager import BaseManager
from ..project_manager import ProjectManager
from .docker_vm import Container
from .docker_error import DockerError


class Docker(BaseManager):

    _VM_CLASS = Container

    def __init__(self):
        super().__init__()
        # FIXME: make configurable and start docker before trying
        self._server_url = 'unix://var/run/docker.sock'
        # FIXME: handle client failure
        self._client = docker.Client(base_url=self._server_url)
        self._execute_lock = asyncio.Lock()

    @property
    def server_url(self):
        """Returns the Docker server url.

        :returns: url
        :rtype: string
        """
        return self._server_url

    @server_url.setter
    def server_url(self, value):
        self._server_url = value
        # FIXME: handle client failure
        self._client = docker.Client(base_url=value)

    @asyncio.coroutine
    def execute(self, command, kwargs, timeout=60):
        command = getattr(self._client, command)
        log.debug("Executing Docker with command: {}".format(command))
        try:
            # FIXME: async wait
            result = command(**kwargs)
        except Exception as error:
            raise DockerError("Docker has returned an error: {}".format(error))
        return result

    # FIXME: do this in docker
    @asyncio.coroutine
    def project_closed(self, project):
        """Called when a project is closed.

        :param project: Project instance
        """
        yield from super().project_closed(project)
        hdd_files_to_close = yield from self._find_inaccessible_hdd_files()
        for hdd_file in hdd_files_to_close:
            log.info("Closing VirtualBox VM disk file {}".format(os.path.basename(hdd_file)))
            try:
                yield from self.execute("closemedium", ["disk", hdd_file])
            except VirtualBoxError as e:
                log.warning("Could not close VirtualBox VM disk file {}: {}".format(os.path.basename(hdd_file), e))
                continue

    @asyncio.coroutine
    def list_images(self):
        """Gets Docker image list.

        :returns: list of dicts
        :rtype: list
        """
        images = []
        for image in self._client.images():
            for tag in image['RepoTags']:
                images.append({'imagename': tag})
        return images

    @asyncio.coroutine
    def list_containers(self):
        """Gets Docker container list.

        :returns: list of dicts
        :rtype: list
        """
        return self._client.containers()

    def get_container(self, cid, project_id=None):
        """Returns a Docker container.

        :param id: Docker container identifier
        :param project_id: Project identifier

        :returns: Docker container
        """
        if project_id:
            # check if the project_id exists
            project = ProjectManager.instance().get_project(project_id)

        if cid not in self._vms:
            raise aiohttp.web.HTTPNotFound(
                text="Docker container with ID {} doesn't exist".format(vm_id))

        container = self._vms[cid]
        if project_id:
            if container.project.id != project.id:
                raise aiohttp.web.HTTPNotFound(
                    text="Project ID {} doesn't belong to container {}".format(
                        project_id, container.name))
        return container
