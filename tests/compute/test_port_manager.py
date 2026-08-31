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
import threading
import uuid

from fastapi import HTTPException
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
    with pytest.raises(HTTPException):
        pm.reserve_udp_port(20000, project)


def test_reserve_udp_port_outside_range():

    pm = PortManager()
    project = Project(project_id=str(uuid.uuid4()))
    with pytest.raises(HTTPException):
        pm.reserve_udp_port(80, project)


def test_release_udp_port():

    pm = PortManager()
    project = Project(project_id=str(uuid.uuid4()))
    pm.reserve_udp_port(20000, project)
    pm.release_udp_port(20000, project)
    pm.reserve_udp_port(20000, project)


def test_concurrent_udp_port_allocation_no_duplicates():
    """
    Regression test for the link UDP self-loop bug (docs/bugs/link-udp-self-loop.md):
    both ends of a link are allocated concurrently on the controller
    (asyncio.gather -> two POST /ports/udp), and FastAPI runs the sync route
    handler in a threadpool. The find-then-add allocation must be atomic,
    otherwise both threads can probe and return the same "free" port —
    handing lport == rport to both ends, which makes every packet loop back
    to its sender (one-way link).
    """

    pm = PortManager()
    pm.udp_port_range = (50000, 50100)
    project = Project(project_id=str(uuid.uuid4()))

    workers = 8
    rounds = 10
    barrier = threading.Barrier(workers)
    results = []
    results_lock = threading.Lock()

    def worker():
        allocated = []
        for _ in range(rounds):
            # start each round together to maximize the collision window
            barrier.wait()
            allocated.append(pm.get_free_udp_port(project))
        with results_lock:
            results.extend(allocated)

    threads = [threading.Thread(target=worker) for _ in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(results) == workers * rounds
    assert len(set(results)) == len(results), "the same UDP port was handed to two callers"
    assert pm.udp_ports == set(results)


def test_concurrent_tcp_port_allocation_no_duplicates():
    """
    Same race class as the UDP self-loop bug, on the console/TCP side:
    concurrent get_free_tcp_port calls must never return the same port.
    """

    pm = PortManager()
    pm.console_port_range = (51000, 51100)
    project = Project(project_id=str(uuid.uuid4()))

    workers = 8
    rounds = 10
    barrier = threading.Barrier(workers)
    results = []
    results_lock = threading.Lock()

    def worker():
        allocated = []
        for _ in range(rounds):
            barrier.wait()
            allocated.append(pm.get_free_tcp_port(project))
        with results_lock:
            results.extend(allocated)

    threads = [threading.Thread(target=worker) for _ in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(results) == workers * rounds
    assert len(set(results)) == len(results), "the same TCP port was handed to two callers"
    assert pm.tcp_ports == set(results)


def test_find_unused_port():

    p = PortManager().find_unused_port(1000, 10000)
    assert p is not None


def test_find_unused_port_invalid_range():

    with pytest.raises(HTTPException):
        p = PortManager().find_unused_port(10000, 1000)


def test_set_console_host(config):
    """
    If allow remote connection we need to bind console host
    to 0.0.0.0
    """

    p = PortManager()
    config.settings.Server.allow_remote_console = False
    p.console_host = "10.42.1.42"
    assert p.console_host == "10.42.1.42"
    p = PortManager()
    config.settings.Server.allow_remote_console = True
    p.console_host = "10.42.1.42"
    assert p.console_host == "0.0.0.0"
