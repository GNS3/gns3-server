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
import tempfile
from uuid import uuid4


class Project:

    """
    A project contains a list of VM.
    In theory VM are isolated project/project.

    :param uuid: Force project uuid (None by default auto generate an UUID)
    :param location: Parent path of the project. (None should create a tmp directory)
    """

    def __init__(self, uuid=None, location=None):

        if uuid is None:
            self._uuid = str(uuid4())
        else:
            assert len(uuid) == 36
            self._uuid = uuid

        self._location = location
        if location is None:
            self._location = tempfile.mkdtemp()

        self._path = os.path.join(self._location, self._uuid)
        if os.path.exists(self._path) is False:
            os.mkdir(self._path)
            os.mkdir(os.path.join(self._path, "files"))

    @property
    def uuid(self):

        return self._uuid

    @property
    def location(self):

        return self._location

    @property
    def path(self):

        return self._path

    def __json__(self):

        return {
            "uuid": self._uuid,
            "location": self._location
        }
