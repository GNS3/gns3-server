#!/usr/bin/env python
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
    """

    """
    :param uuid: Force project uuid (None by default auto generate an UUID)
    :param location: Parent path of the project. (None should create a tmp directory)
    """
    def __init__(self, uuid = None, location = None):
        if uuid is None:
            self.uuid = str(uuid4())
        else:
            self.uuid = uuid

        self.location = location
        if location is None:
            self.location = tempfile.mkdtemp()

        self.path = os.path.join(self.location, self.uuid)
        if os.path.exists(self.path) is False:
            os.mkdir(self.path)
            os.mkdir(os.path.join(self.path, 'files'))

    def __json__(self):
        return {
            "uuid": self.uuid,
            "location": self.location
        }
