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
import socket
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
        assert data["gns3vm"] == controller.gns3vm.__json__()


def test_load_controller_settings(controller, controller_config_path, async_run):
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
    data["gns3vm"] = {"vmname": "Test VM"}
    with open(controller_config_path, "w+") as f:
        json.dump(data, f)
    assert len(async_run(controller._load_controller_settings())) == 1
    assert controller.settings["IOU"]
    assert controller.gns3vm.settings["vmname"] == "Test VM"


def test_load_controller_settings_with_no_computes_section(controller, controller_config_path, async_run):
    controller.save()
    with open(controller_config_path) as f:
        data = json.load(f)
    del data['computes']
    with open(controller_config_path, "w+") as f:
        json.dump(data, f)
    assert len(async_run(controller._load_controller_settings())) == 0


def test_import_computes_1_x(controller, controller_config_path, async_run):
    """
    At first start the server should import the
    computes from the gns3_gui 1.X
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

    async_run(controller._load_controller_settings())
    for compute in controller.computes.values():
        if compute.id != "local":
            assert len(compute.id) == 36
            assert compute.host == "127.0.0.1"
            assert compute.port == 3081
            assert compute.protocol == "http"
            assert compute.name == "http://127.0.0.1:3081"
            assert compute.user is None
            assert compute.password is None


def test_import_gns3vm_1_x(controller, controller_config_path, async_run):
    """
    At first start the server should import the
    gns3vm settings from the gns3_gui 1.X
    """
    gns3_gui_conf = {
        "Servers": {
            "vm": {
                "adjust_local_server_ip": True,
                "auto_start": True,
                "auto_stop": False,
                "headless": True,
                "remote_vm_host": "",
                "remote_vm_password": "",
                "remote_vm_port": 3080,
                "remote_vm_protocol": "http",
                "remote_vm_url": "",
                "remote_vm_user": "",
                "virtualization": "VMware",
                "vmname": "GNS3 VM",
                "vmx_path": "/Users/joe/Documents/Virtual Machines.localized/GNS3 VM.vmwarevm/GNS3 VM.vmx"
            }
        }
    }
    config_dir = os.path.dirname(controller_config_path)
    os.makedirs(config_dir, exist_ok=True)
    with open(os.path.join(config_dir, "gns3_gui.conf"), "w+") as f:
        json.dump(gns3_gui_conf, f)

    controller.gns3vm.settings["engine"] = None
    async_run(controller._load_controller_settings())
    assert controller.gns3vm.settings["engine"] == "vmware"
    assert controller.gns3vm.settings["enable"]
    assert controller.gns3vm.settings["headless"]
    assert controller.gns3vm.settings["when_exit"] == "keep"
    assert controller.gns3vm.settings["vmname"] == "GNS3 VM"


def test_import_remote_gns3vm_1_x(controller, controller_config_path, async_run):
    """
    At first start the server should import the
    computes and remote GNS3 VM from the gns3_gui 1.X
    """
    gns3_gui_conf = {
        "Servers": {
            "remote_servers": [
                {
                    "host": "127.0.0.1",
                    "password": "",
                    "port": 3080,
                    "protocol": "http",
                    "url": "http://127.0.0.1:3080",
                    "user": ""
                },
                {
                    "host": "127.0.0.1",
                    "password": "",
                    "port": 3081,
                    "protocol": "http",
                    "url": "http://127.0.0.1:3081",
                    "user": ""
                }
            ],
            "vm": {
                "adjust_local_server_ip": True,
                "auto_start": True,
                "auto_stop": False,
                "headless": True,
                "remote_vm_host": "127.0.0.1",
                "remote_vm_password": "",
                "remote_vm_port": 3081,
                "remote_vm_protocol": "http",
                "remote_vm_url": "http://127.0.0.1:3081",
                "remote_vm_user": "",
                "virtualization": "remote",
                "vmname": "GNS3 VM",
                "vmx_path": "/Users/joe/Documents/Virtual Machines.localized/GNS3 VM.vmwarevm/GNS3 VM.vmx"
            }
        }
    }
    config_dir = os.path.dirname(controller_config_path)
    os.makedirs(config_dir, exist_ok=True)
    with open(os.path.join(config_dir, "gns3_gui.conf"), "w+") as f:
        json.dump(gns3_gui_conf, f)

    with asyncio_patch("gns3server.controller.compute.Compute.connect"):
        async_run(controller._load_controller_settings())
    assert controller.gns3vm.settings["engine"] == "remote"
    assert controller.gns3vm.settings["vmname"] == "http://127.0.0.1:3081"


def test_settings(controller):
    controller._notification = MagicMock()
    controller.settings = {"a": 1}
    controller._notification.emit.assert_called_with("settings.updated", controller.settings)
    assert controller.settings["modification_uuid"] is not None


def test_load_projects(controller, projects_dir, async_run):
    controller.save()

    os.makedirs(os.path.join(projects_dir, "project1"))
    with open(os.path.join(projects_dir, "project1", "project1.gns3"), "w+") as f:
        f.write("")
    with asyncio_patch("gns3server.controller.Controller.load_project") as mock_load_project:
        async_run(controller.load_projects())
    mock_load_project.assert_called_with(os.path.join(projects_dir, "project1", "project1.gns3"), load=False)


def test_add_compute(controller, controller_config_path, async_run):
    controller._notification = MagicMock()
    c = async_run(controller.add_compute(compute_id="test1", connect=False))
    controller._notification.emit.assert_called_with("compute.created", c.__json__())
    assert len(controller.computes) == 1
    async_run(controller.add_compute(compute_id="test1", connect=False))
    controller._notification.emit.assert_called_with("compute.updated", c.__json__())
    assert len(controller.computes) == 1
    async_run(controller.add_compute(compute_id="test2", connect=False))
    assert len(controller.computes) == 2


def test_addDuplicateCompute(controller, controller_config_path, async_run):
    controller._notification = MagicMock()
    c = async_run(controller.add_compute(compute_id="test1", name="Test", connect=False))
    assert len(controller.computes) == 1
    with pytest.raises(aiohttp.web.HTTPConflict):
        async_run(controller.add_compute(compute_id="test2", name="Test", connect=False))


def test_deleteCompute(controller, controller_config_path, async_run):
    c = async_run(controller.add_compute(compute_id="test1", connect=False))
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


def test_deleteComputeProjectOpened(controller, controller_config_path, async_run):
    """
    When you delete a compute the project using it are close
    """
    c = async_run(controller.add_compute(compute_id="test1", connect=False))
    c.post = AsyncioMagicMock()
    assert len(controller.computes) == 1

    project1 = async_run(controller.add_project(name="Test1"))
    async_run(project1.open())
    # We simulate that the project use this compute
    project1._project_created_on_compute.add(c)

    project2 = async_run(controller.add_project(name="Test2"))
    async_run(project2.open())

    controller._notification = MagicMock()
    c._connected = True
    async_run(controller.delete_compute("test1"))
    assert len(controller.computes) == 0
    controller._notification.emit.assert_called_with("compute.deleted", c.__json__())
    with open(controller_config_path) as f:
        data = json.load(f)
        assert len(data["computes"]) == 0
    assert c.connected is False

    # Project 1 use this compute it should be close before deleting the compute
    assert project1.status == "closed"
    assert project2.status == "opened"


def test_addComputeConfigFile(controller, controller_config_path, async_run):
    async_run(controller.add_compute(compute_id="test1", name="Test", connect=False))
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
    compute = async_run(controller.add_compute(compute_id="test1", connect=False))

    assert controller.get_compute("test1") == compute
    with pytest.raises(aiohttp.web.HTTPNotFound):
        assert controller.get_compute("dsdssd")


def test_has_compute(controller, async_run):
    compute = async_run(controller.add_compute(compute_id="test1", connect=False))

    assert controller.has_compute("test1")
    assert not controller.has_compute("test2")


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


def test_start(controller, async_run):
    controller.gns3vm.settings = {
        "enable": False,
        "engine": "vmware",
        "vmname": "GNS3 VM"
    }
    with asyncio_patch("gns3server.controller.compute.Compute.connect") as mock:
        async_run(controller.start())
    assert len(controller.computes) == 1  # Local compute is created
    assert controller.computes["local"].name == socket.gethostname()


def test_start_vm(controller, async_run):
    """
    Start the controller with a GNS3 VM
    """
    controller.gns3vm.settings = {
        "enable": True,
        "engine": "vmware",
        "vmname": "GNS3 VM"
    }
    with asyncio_patch("gns3server.controller.gns3vm.vmware_gns3_vm.VMwareGNS3VM.start") as mock:
        with asyncio_patch("gns3server.controller.compute.Compute.connect") as mock_connect:
            async_run(controller.start())
            assert mock.called
    assert "local" in controller.computes
    assert "vm" in controller.computes
    assert len(controller.computes) == 2  # Local compute and vm are created


def test_stop(controller, async_run):
    c = async_run(controller.add_compute(compute_id="test1", connect=False))
    c._connected = True
    async_run(controller.stop())
    assert c.connected is False


def test_stop_vm(controller, async_run):
    """
    Stop GNS3 VM if configured
    """
    controller.gns3vm.settings = {
        "enable": True,
        "engine": "vmware",
        "when_exit": "stop",
        "vmname": "GNS3 VM"
    }
    controller.gns3vm.current_engine().running = True
    with asyncio_patch("gns3server.controller.gns3vm.vmware_gns3_vm.VMwareGNS3VM.stop") as mock:
        async_run(controller.stop())
        assert mock.called


def test_suspend_vm(controller, async_run):
    """
    Suspend GNS3 VM if configured
    """
    controller.gns3vm.settings = {
        "enable": True,
        "engine": "vmware",
        "when_exit": "suspend",
        "vmname": "GNS3 VM"
    }
    controller.gns3vm.current_engine().running = True
    with asyncio_patch("gns3server.controller.gns3vm.vmware_gns3_vm.VMwareGNS3VM.suspend") as mock:
        async_run(controller.stop())
        assert mock.called


def test_keep_vm(controller, async_run):
    """
    Keep GNS3 VM if configured
    """
    controller.gns3vm.settings = {
        "enable": True,
        "engine": "vmware",
        "when_exit": "keep",
        "vmname": "GNS3 VM"
    }
    controller.gns3vm.current_engine().running = True
    with asyncio_patch("gns3server.controller.gns3vm.vmware_gns3_vm.VMwareGNS3VM.suspend") as mock:
        async_run(controller.stop())
        assert not mock.called


def test_get_free_project_name(controller, async_run):

    async_run(controller.add_project(project_id=str(uuid.uuid4()), name="Test"))
    assert controller.get_free_project_name("Test") == "Test-1"
    async_run(controller.add_project(project_id=str(uuid.uuid4()), name="Test-1"))
    assert controller.get_free_project_name("Test") == "Test-2"
    assert controller.get_free_project_name("Hello") == "Hello"
