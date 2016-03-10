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
from uuid import UUID, uuid4


class Project:
    """
    A project inside controller

    :param project_id: force project identifier (None by default auto generate an UUID)
    :param path: path of the project. (None use the standard directory)
    :param temporary: boolean to tell if the project is a temporary project (destroy when closed)
    """

    def __init__(self, name=None, project_id=None, path=None, temporary=False):

        self._name = name
        if project_id is None:
            self._id = str(uuid4())
        else:
            try:
                UUID(project_id, version=4)
            except ValueError:
                raise aiohttp.web.HTTPBadRequest(text="{} is not a valid UUID".format(project_id))
            self._id = project_id
        self._path = path
        self._temporary = temporary
        self._hypervisors = set()

    @property
    def name(self):
        return self._name

    @property
    def id(self):
        return self._id

    @property
    def temporary(self):
        return self._temporary

    @property
    def path(self):
        return self._path

    @asyncio.coroutine
    def addHypervisor(self, hypervisor):
        self._hypervisors.add(hypervisor)
        yield from hypervisor.post("/projects", self)

    @asyncio.coroutine
    def close(self):
        for hypervisor in self._hypervisors:
            yield from hypervisor.post("/projects/{}/close".format(self._id))

    @asyncio.coroutine
    def commit(self):
        for hypervisor in self._hypervisors:
            yield from hypervisor.post("/projects/{}/commit".format(self._id))

    @asyncio.coroutine
    def delete(self):
        for hypervisor in self._hypervisors:
            yield from hypervisor.delete("/projects/{}".format(self._id))

    def __json__(self):

        return {
            "name": self._name,
            "project_id": self._id,
            "temporary": self._temporary,
            "path": self._path
        }
