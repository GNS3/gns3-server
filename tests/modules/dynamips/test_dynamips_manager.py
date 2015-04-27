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


import pytest
import tempfile
import sys

from gns3server.modules.dynamips import Dynamips
from gns3server.modules.dynamips.dynamips_error import DynamipsError
from unittest.mock import patch


@pytest.fixture(scope="module")
def manager(port_manager):
    m = Dynamips.instance()
    m.port_manager = port_manager
    return m


def test_vm_invalid_dynamips_path(manager):
    with patch("gns3server.config.Config.get_section_config", return_value={"dynamips_path": "/bin/test_fake"}):
        with pytest.raises(DynamipsError):
            manager.find_dynamips()

@pytest.mark.skipif(sys.platform.startswith("win"), reason="Not supported by Windows")
def test_vm_non_executable_dynamips_path(manager):
    tmpfile = tempfile.NamedTemporaryFile()
    with patch("gns3server.config.Config.get_section_config", return_value={"dynamips_path": tmpfile.name}):
        with pytest.raises(DynamipsError):
            manager.find_dynamips()
