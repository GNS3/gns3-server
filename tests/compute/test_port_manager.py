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

import aiohttp
import pytest
import uuid
from unittest.mock import patch

from gns3server.compute.port_manager import PortManager
from gns3server.compute.project import Project


def test_reserve_tcp_port():

    pm = PortManager()
    project = Project(project_id=str(uuid.uuid4()))
    pm.reserve_tcp_port(2001, project)
    with patch("gns3server.compute.project.Project.emit") as mock_emit:
        port = pm.reserve_tcp_port(2001, project)
        assert port != 2001


def test_reserve_tcp_port_outside_range():

    pm = PortManager()
    project = Project(project_id=str(uuid.uuid4()))
    with patch("gns3server.compute.project.Project.emit") as mock_emit:
        port = pm.reserve_tcp_port(80, project)
        assert port != 80


def test_reserve_tcp_port_already_used_by_another_program():
    """
    This test simulate a scenario where the port is already taken
    by another programm on the server
    """

    pm = PortManager()
    project = Project(project_id=str(uuid.uuid4()))
    with patch("gns3server.compute.port_manager.PortManager._check_port") as mock_check:

        def execute_mock(host, port, *args):
            if port == 2001:
                raise OSError("Port is already used")
            else:
                return True

        mock_check.side_effect = execute_mock

        with patch("gns3server.compute.project.Project.emit"):
            port = pm.reserve_tcp_port(2001, project)
            assert port != 2001


def test_reserve_tcp_port_already_used():
    """
    This test simulate a scenario where the port is already taken
    by another program on the server
    """

    pm = PortManager()
    project = Project(project_id=str(uuid.uuid4()))
    with patch("gns3server.compute.port_manager.PortManager._check_port") as mock_check:

        def execute_mock(host, port, *args):
            if port == 2001:
                raise OSError("Port is already used")
            else:
                return True

        mock_check.side_effect = execute_mock

        with patch("gns3server.compute.project.Project.emit"):
            port = pm.reserve_tcp_port(2001, project)
            assert port != 2001


def test_reserve_udp_port():

    pm = PortManager()
    project = Project(project_id=str(uuid.uuid4()))
    pm.reserve_udp_port(20000, project)
    with pytest.raises(aiohttp.web.HTTPConflict):
        pm.reserve_udp_port(20000, project)


def test_reserve_udp_port_outside_range():

    pm = PortManager()
    project = Project(project_id=str(uuid.uuid4()))
    with pytest.raises(aiohttp.web.HTTPConflict):
        pm.reserve_udp_port(80, project)


def test_release_udp_port():

    pm = PortManager()
    project = Project(project_id=str(uuid.uuid4()))
    pm.reserve_udp_port(20000, project)
    pm.release_udp_port(20000, project)
    pm.reserve_udp_port(20000, project)


def test_find_unused_port():

    p = PortManager().find_unused_port(1000, 10000)
    assert p is not None


def test_find_unused_port_invalid_range():

    with pytest.raises(aiohttp.web.HTTPConflict):
        p = PortManager().find_unused_port(10000, 1000)


def test_set_console_host(config):
    """
    If allow remote connection we need to bind console host
    to 0.0.0.0
    """

    p = PortManager()
    config.set_section_config("Server", {"allow_remote_console": False})
    p.console_host = "10.42.1.42"
    assert p.console_host == "10.42.1.42"
    p = PortManager()
    config.set_section_config("Server", {"allow_remote_console": True})
    p.console_host = "10.42.1.42"
    assert p.console_host == "0.0.0.0"
