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
import aiohttp
import asyncio
import os
from tests.utils import asyncio_patch


from unittest.mock import patch, MagicMock
from gns3server.modules.vpcs.vpcs_vm import VPCSVM
from gns3server.modules.vpcs.vpcs_error import VPCSError
from gns3server.modules.vpcs import VPCS


@pytest.fixture(scope="module")
def manager(port_manager):
    m = VPCS.instance()
    m.port_manager = port_manager
    return m


@pytest.fixture(scope="function")
def vm(project, manager):
    return VPCSVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", project, manager)


def test_temporary_directory(project, manager):
    vm = VPCSVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", project, manager)
    assert isinstance(vm.temporary_directory, str)
