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
from tests.utils import AsyncioMagicMock, asyncio_patch

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
        assert data["settings"] == {}


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
    data["settings"] = {"IOU": True}
    with open(controller_config_path, "w+") as f:
        json.dump(data, f)
    async_run(controller.load())
    assert len(controller.computes) == 1
    assert controller.settings["IOU"]
    assert controller.computes["test1"].__json__() == {
        "compute_id": "test1",
        "connected": False,
        "host": "localhost",
        "port": 8000,
        "protocol": "http",
        "user": "admin",
        "name": "http://admin@localhost:8000",
        "cpu_usage_percent": None,
        "memory_usage_percent": None
    }


def test_import_computes(controller, controller_config_path, async_run):
    """
    At first start the server should import the
    computes from the gns3_gui
    """
    gns3_gui_conf = {
        "Servers": {
            "remote_servers": [
                {
                    "host": "127.0.0.1",
                    "password": "",
                    "port": 3081,
                    "protocol": "http",
                    "url": "http://127.0.0.1:3081",
                    "user": ""
                }
            ]
        }
    }
    config_dir = os.path.dirname(controller_config_path)
    os.makedirs(config_dir, exist_ok=True)
    with open(os.path.join(config_dir, "gns3_gui.conf"), "w+") as f:
        json.dump(gns3_gui_conf, f)

    async_run(controller.load())
    assert len(controller.computes) == 1
    compute = list(controller.computes.values())[0]
    assert compute.host == "127.0.0.1"
    assert compute.port == 3081
    assert compute.protocol == "http"
    assert compute.name == "http://127.0.0.1:3081"
    assert compute.user is None
    assert compute.password is None


def test_settings(controller):
    controller._notification = MagicMock()
    controller.settings = {"a": 1}
    controller._notification.emit.assert_called_with("settings.updated", {"a": 1})


def test_load_projects(controller, projects_dir, async_run):
    controller.save()

    os.makedirs(os.path.join(projects_dir, "project1"))
    with open(os.path.join(projects_dir, "project1", "project1.gns3"), "w+") as f:
        f.write("")
    with asyncio_patch("gns3server.controller.Controller.load_project") as mock_load_project:
        async_run(controller.load())
    mock_load_project.assert_called_with(os.path.join(projects_dir, "project1", "project1.gns3"), load=False)


def test_isEnabled(controller):
    Config.instance().set("Server", "controller", False)
    assert not controller.is_enabled()
    Config.instance().set("Server", "controller", True)
    assert controller.is_enabled()


def test_addCompute(controller, controller_config_path, async_run):
    controller._notification = MagicMock()
    c = async_run(controller.add_compute(compute_id="test1"))
    controller._notification.emit.assert_called_with("compute.created", c.__json__())
    assert len(controller.computes) == 1
    async_run(controller.add_compute(compute_id="test1"))
    controller._notification.emit.assert_called_with("compute.updated", c.__json__())
    assert len(controller.computes) == 1
    async_run(controller.add_compute(compute_id="test2"))
    assert len(controller.computes) == 2


def test_addDuplicateCompute(controller, controller_config_path, async_run):
    controller._notification = MagicMock()
    c = async_run(controller.add_compute(compute_id="test1", name="Test"))
    assert len(controller.computes) == 1
    with pytest.raises(aiohttp.web.HTTPConflict):
        async_run(controller.add_compute(compute_id="test2", name="Test"))


def test_deleteCompute(controller, controller_config_path, async_run):
    c = async_run(controller.add_compute(compute_id="test1"))
    assert len(controller.computes) == 1
    controller._notification = MagicMock()
    c._connected = True
    async_run(controller.delete_compute("test1"))
    assert len(controller.computes) == 0
    controller._notification.emit.assert_called_with("compute.deleted", c.__json__())
    with open(controller_config_path) as f:
        data = json.load(f)
        assert len(data["computes"]) == 0
    assert c.connected is False


def test_addComputeConfigFile(controller, controller_config_path, async_run):
    async_run(controller.add_compute(compute_id="test1", name="Test"))
    assert len(controller.computes) == 1
    with open(controller_config_path) as f:
        data = json.load(f)
        assert data["computes"] == [
            {
                'compute_id': 'test1',
                'name': 'Test',
                'host': 'localhost',
                'port': 3080,
                'protocol': 'http',
                'user': None,
                'password': None
            }
        ]


def test_getCompute(controller, async_run):
    compute = async_run(controller.add_compute(compute_id="test1"))

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


def test_add_project(controller, async_run):
    uuid1 = str(uuid.uuid4())
    uuid2 = str(uuid.uuid4())

    async_run(controller.add_project(project_id=uuid1, name="Test"))
    assert len(controller.projects) == 1
    async_run(controller.add_project(project_id=uuid1, name="Test"))
    assert len(controller.projects) == 1
    async_run(controller.add_project(project_id=uuid2, name="Test 2"))
    assert len(controller.projects) == 2


def test_addDuplicateProject(controller, async_run):
    uuid1 = str(uuid.uuid4())
    uuid2 = str(uuid.uuid4())

    async_run(controller.add_project(project_id=uuid1, name="Test"))
    assert len(controller.projects) == 1
    with pytest.raises(aiohttp.web.HTTPConflict):
        async_run(controller.add_project(project_id=uuid2, name="Test"))


def test_remove_project(controller, async_run):
    uuid1 = str(uuid.uuid4())

    project1 = async_run(controller.add_project(project_id=uuid1, name="Test"))
    assert len(controller.projects) == 1

    controller.remove_project(project1)
    assert len(controller.projects) == 0


def test_addProject_with_compute(controller, async_run):
    uuid1 = str(uuid.uuid4())

    compute = Compute("test1", controller=MagicMock())
    compute.post = MagicMock()
    controller._computes = {"test1": compute}

    project1 = async_run(controller.add_project(project_id=uuid1, name="Test"))


def test_getProject(controller, async_run):
    uuid1 = str(uuid.uuid4())

    project = async_run(controller.add_project(project_id=uuid1, name="Test"))
    assert controller.get_project(uuid1) == project
    with pytest.raises(aiohttp.web.HTTPNotFound):
        assert controller.get_project("dsdssd")


def test_close(controller, async_run):
    c = async_run(controller.add_compute(compute_id="test1"))
    c._connected = True
    async_run(controller.close())
    assert c.connected is False


def test_load_project(controller, async_run, tmpdir):
    data = {
        "name": "Experience",
        "project_id": "c8d07a5a-134f-4c3f-8599-e35eac85eb17",
        "revision": 5,
        "type": "topology",
        "version": "2.0.0dev1",
        "topology": {
            "drawings": [],
            "computes": [
                {
                    "compute_id": "my_remote",
                    "host": "127.0.0.1",
                    "name": "My remote",
                    "port": 3080,
                    "protocol": "http",
                }
            ],
            "links": [
                {
                    "link_id": "c44331d2-2da4-490d-9aad-7f5c126ae271",
                    "nodes": [
                        {"node_id": "c067b922-7f77-4680-ac00-0226c6583598", "adapter_number": 0, "port_number": 0},
                        {"node_id": "50d66d7b-0dd7-4e9f-b720-6eb621ae6543", "adapter_number": 0, "port_number": 0},
                    ],
                }
            ],
            "nodes": [
                {
                    "compute_id": "my_remote",
                    "name": "PC2",
                    "node_id": "c067b922-7f77-4680-ac00-0226c6583598",
                    "node_type": "vpcs",
                    "properties": {
                        "startup_script": "set pcname PC2\n",
                        "startup_script_path": "startup.vpc"
                    },
                },
                {
                    "compute_id": "my_remote",
                    "name": "PC1",
                    "node_id": "50d66d7b-0dd7-4e9f-b720-6eb621ae6543",
                    "node_type": "vpcs",
                    "properties": {
                        "startup_script": "set pcname PC1\n",
                        "startup_script_path": "startup.vpc"
                    },
                }
            ]
        }
    }
    with open(str(tmpdir / "test.gns3"), "w+") as f:
        json.dump(data, f)
    controller.add_compute = AsyncioMagicMock()
    controller._computes["my_remote"] = MagicMock()

    with asyncio_patch("gns3server.controller.node.Node.create") as mock_node_create:
        project = async_run(controller.load_project(str(tmpdir / "test.gns3")))

    assert project._topology_file() == str(tmpdir / "test.gns3")
    controller.add_compute.assert_called_with(compute_id='my_remote', host='127.0.0.1', name='My remote', port=3080, protocol='http')
    project = controller.get_project('c8d07a5a-134f-4c3f-8599-e35eac85eb17')
    assert project.name == "Experience"
    assert project.path == str(tmpdir)
    link = project.get_link("c44331d2-2da4-490d-9aad-7f5c126ae271")
    assert len(link.nodes) == 2

    node1 = project.get_node("50d66d7b-0dd7-4e9f-b720-6eb621ae6543")
    assert node1.name == "PC1"

    # Reload the same project should do nothing
    with asyncio_patch("gns3server.controller.Controller.add_project") as mock_add_project:
        project = async_run(controller.load_project(str(tmpdir / "test.gns3")))
    assert not mock_add_project.called


def test_get_free_project_name(controller, async_run):

    async_run(controller.add_project(project_id=str(uuid.uuid4()), name="Test"))
    assert controller.get_free_project_name("Test") == "Test-1"
    async_run(controller.add_project(project_id=str(uuid.uuid4()), name="Test-1"))
    assert controller.get_free_project_name("Test") == "Test-2"
    assert controller.get_free_project_name("Hello") == "Hello"

