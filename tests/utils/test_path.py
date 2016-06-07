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
import aiohttp


from gns3server.utils.path import check_path_allowed, get_default_project_directory
from gns3server.utils import force_unix_path


def test_check_path_allowed(config, tmpdir):
    config.set("Server", "local", False)
    config.set("Server", "projects_path", str(tmpdir))
    with pytest.raises(aiohttp.web.HTTPForbidden):
        check_path_allowed("/private")

    config.set("Server", "local", True)
    check_path_allowed(str(tmpdir / "hello" / "world"))
    check_path_allowed("/private")


def test_get_default_project_directory(config):

    config.clear()

    path = os.path.normpath(os.path.expanduser("~/GNS3/projects"))
    assert get_default_project_directory() == path
    assert os.path.exists(path)
