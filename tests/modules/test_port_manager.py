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

import aiohttp
import pytest
import sys
from unittest.mock import patch
from gns3server.modules.port_manager import PortManager
from gns3server.modules.project import Project


def test_reserve_tcp_port():
    pm = PortManager()
    project = Project()
    pm.reserve_tcp_port(2001, project)
    with pytest.raises(aiohttp.web.HTTPConflict):
        pm.reserve_tcp_port(2001, project)


def test_reserve_tcp_port_outside_range():
    pm = PortManager()
    project = Project()
    with pytest.raises(aiohttp.web.HTTPConflict):
        pm.reserve_tcp_port(80, project)


def test_reserve_udp_port():
    pm = PortManager()
    project = Project()
    pm.reserve_udp_port(10000, project)
    with pytest.raises(aiohttp.web.HTTPConflict):
        pm.reserve_udp_port(10000, project)


def test_reserve_udp_port_outside_range():
    pm = PortManager()
    project = Project()
    with pytest.raises(aiohttp.web.HTTPConflict):
        pm.reserve_udp_port(80, project)


def test_release_udp_port():
    pm = PortManager()
    project = Project()
    pm.reserve_udp_port(10000, project)
    pm.release_udp_port(10000, project)
    pm.reserve_udp_port(10000, project)


def test_find_unused_port():
    p = PortManager().find_unused_port(1000, 10000)
    assert p is not None


def test_find_unused_port_invalid_range():
    with pytest.raises(aiohttp.web.HTTPConflict):
        p = PortManager().find_unused_port(10000, 1000)
