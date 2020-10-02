# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 GNS3 Technologies Inc.
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

import pytest

from gns3server.compute.compute_error import ComputeNotFoundError
from gns3server.compute.project_manager import ProjectManager


def test_create_project():

    pm = ProjectManager.instance()
    project = pm.create_project(project_id='00010203-0405-0607-0809-0a0b0c0d0e0f')
    assert project == pm.get_project('00010203-0405-0607-0809-0a0b0c0d0e0f')


def test_project_not_found():

    pm = ProjectManager.instance()
    with pytest.raises(ComputeNotFoundError):
        pm.get_project('00010203-0405-0607-0809-000000000000')
