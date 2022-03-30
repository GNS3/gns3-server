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

import os
import pytest

from fastapi import HTTPException

from gns3server.utils.path import check_path_allowed, get_default_project_directory


def test_check_path_allowed():

    with pytest.raises(HTTPException):
        check_path_allowed("/private")


def test_get_default_project_directory(config):

    config.clear()
    path = os.path.normpath(os.path.expanduser("~/GNS3/projects"))
    assert get_default_project_directory() == path
    assert os.path.exists(path)
