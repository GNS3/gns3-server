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
import uuid
import json
import pytest
import aiohttp
from unittest.mock import MagicMock


from gns3server.controller import Controller
from gns3server.controller.compute import Compute
from gns3server.controller.project import Project
from gns3server.config import Config
from gns3server.version import __version__


def test_save(controller, controller_config_path):
    controller.save()
    assert os.path.exists(controller_config_path)
    with open(controller_config_path) as f:
        data = json.load(f)
        assert data["computes"] == []
        assert data["version"] == __version__


def test_load(controller, controller_config_path, async_run):
    controller.save()
    with open(controller_config_path) as f:
        data = json.load(f)
    data["computes"] = [
        {
            "host": "localhost",
            "port": 8000,
            "protocol": "http",
            "user": "admin",
            "password": "root",
            "compute_id": "test1"
        }
    ]
    with open(controller_config_path, "w+") as f:
        json.dump(data, f)
    async_run(controller.load())
    assert len(controller.computes) == 1
    assert controller.computes["test1"].__json__() == {
        "compute_id": "test1",
        "connected": False,
        "host": "localhost",
        "port": 8000,
        "protocol": "http",
        "user": "admin"
    }


def test_isEnabled(controller):
    Config.instance().set("Server", "controller", False)
    assert not controller.isEnabled()
    Config.instance().set("Server", "controller", True)
    assert controller.isEnabled()


def test_addCompute(controller, controller_config_path, async_run):
    async_run(controller.add_compute("test1"))
    assert len(controller.computes) == 1
    async_run(controller.add_compute("test1"))
    assert len(controller.computes) == 1
    async_run(controller.add_compute("test2"))
    assert len(controller.computes) == 2


def test_addComputeConfigFile(controller, controller_config_path, async_run):
    async_run(controller.add_compute("test1"))
    assert len(controller.computes) == 1
    with open(controller_config_path) as f:
        data = json.load(f)
        assert data["computes"] == [
            {
                'compute_id': 'test1',
                'host': 'localhost',
                'port': 8000,
                'protocol': 'http',
                'user': None,
                'password': None
            }
        ]


def test_getCompute(controller, async_run):
    compute = async_run(controller.add_compute("test1"))

    assert controller.get_compute("test1") == compute
    with pytest.raises(aiohttp.web.HTTPNotFound):
        assert controller.get_compute("dsdssd")


def test_addComputeLocal(controller, controller_config_path, async_run):
    """
    The local node is the controller itself you can not change the informations
    """
    Config.instance().set("Server", "local", True)
    async_run(controller.add_compute("local", host="example.org"))
    assert controller.get_compute("local").host == "localhost"


def test_addProject(controller, async_run):
    uuid1 = str(uuid.uuid4())
    uuid2 = str(uuid.uuid4())

    async_run(controller.addProject(project_id=uuid1))
    assert len(controller.projects) == 1
    async_run(controller.addProject(project_id=uuid1))
    assert len(controller.projects) == 1
    async_run(controller.addProject(project_id=uuid2))
    assert len(controller.projects) == 2


def test_remove_project(controller, async_run):
    uuid1 = str(uuid.uuid4())

    project1 = async_run(controller.addProject(project_id=uuid1))
    assert len(controller.projects) == 1

    controller.remove_project(project1)
    assert len(controller.projects) == 0


def test_addProject_with_compute(controller, async_run):
    uuid1 = str(uuid.uuid4())

    compute = Compute("test1", controller=MagicMock())
    compute.post = MagicMock()
    controller._computes = {"test1": compute}

    project1 = async_run(controller.addProject(project_id=uuid1))


def test_getProject(controller, async_run):
    uuid1 = str(uuid.uuid4())

    project = async_run(controller.addProject(project_id=uuid1))
    assert controller.get_project(uuid1) == project
    with pytest.raises(aiohttp.web.HTTPNotFound):
        assert controller.get_project("dsdssd")


def test_emit(controller, async_run):
    project1 = MagicMock()
    uuid1 = str(uuid.uuid4())
    controller._projects[uuid1] = project1

    project2 = MagicMock()
    uuid2 = str(uuid.uuid4())
    controller._projects[uuid2] = project2

    # Notif without project should be send to all projects
    controller.emit("test", {})
    assert project1.emit.called
    assert project2.emit.called


def test_emit_to_project(controller, async_run):
    project1 = MagicMock()
    uuid1 = str(uuid.uuid4())
    controller._projects[uuid1] = project1

    project2 = MagicMock()
    uuid2 = str(uuid.uuid4())
    controller._projects[uuid2] = project2

    # Notif with project should be send to this project
    controller.emit("test", {}, project_id=uuid1)
    project1.emit.assert_called_with('test', {})
    assert not project2.emit.called


def test_emit_to_project_not_exists(controller, async_run):
    project1 = MagicMock()
    uuid1 = str(uuid.uuid4())
    controller._projects[uuid1] = project1

    project2 = MagicMock()
    uuid2 = str(uuid.uuid4())
    controller._projects[uuid2] = project2

    # Notif with project should be send to this project
    controller.emit("test", {}, project_id="4444444")
    assert not project1.emit.called
    assert not project2.emit.called
