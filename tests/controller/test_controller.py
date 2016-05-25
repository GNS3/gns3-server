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
        "user": "admin",
        "name": "http://localhost:8000"
    }


def test_isEnabled(controller):
    Config.instance().set("Server", "controller", False)
    assert not controller.is_enabled()
    Config.instance().set("Server", "controller", True)
    assert controller.is_enabled()


def test_addCompute(controller, controller_config_path, async_run):
    controller._notification = MagicMock()
    c = async_run(controller.add_compute("test1"))
    controller._notification.emit.assert_called_with("compute.created", c.__json__())
    assert len(controller.computes) == 1
    async_run(controller.add_compute("test1"))
    controller._notification.emit.assert_called_with("compute.updated", c.__json__())
    assert len(controller.computes) == 1
    async_run(controller.add_compute("test2"))
    assert len(controller.computes) == 2


def test_deleteCompute(controller, controller_config_path, async_run):
    c = async_run(controller.add_compute("test1"))
    assert len(controller.computes) == 1
    controller._notification = MagicMock()
    async_run(controller.delete_compute("test1"))
    assert len(controller.computes) == 0
    controller._notification.emit.assert_called_with("compute.deleted", c.__json__())


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


def test_initControllerLocal(controller, controller_config_path, async_run):
    """
    The local node is the controller itself you can not change the informations
    """
    # The default test controller is not local
    assert len(controller._computes) == 0
    Config.instance().set("Server", "local", True)
    c = Controller()
    assert len(c._computes) == 1


def test_addProject(controller, async_run):
    uuid1 = str(uuid.uuid4())
    uuid2 = str(uuid.uuid4())

    async_run(controller.add_project(project_id=uuid1))
    assert len(controller.projects) == 1
    async_run(controller.add_project(project_id=uuid1))
    assert len(controller.projects) == 1
    async_run(controller.add_project(project_id=uuid2))
    assert len(controller.projects) == 2


def test_remove_project(controller, async_run):
    uuid1 = str(uuid.uuid4())

    project1 = async_run(controller.add_project(project_id=uuid1))
    assert len(controller.projects) == 1

    controller.remove_project(project1)
    assert len(controller.projects) == 0


def test_addProject_with_compute(controller, async_run):
    uuid1 = str(uuid.uuid4())

    compute = Compute("test1", controller=MagicMock())
    compute.post = MagicMock()
    controller._computes = {"test1": compute}

    project1 = async_run(controller.add_project(project_id=uuid1))


def test_getProject(controller, async_run):
    uuid1 = str(uuid.uuid4())

    project = async_run(controller.add_project(project_id=uuid1))
    assert controller.get_project(uuid1) == project
    with pytest.raises(aiohttp.web.HTTPNotFound):
        assert controller.get_project("dsdssd")
