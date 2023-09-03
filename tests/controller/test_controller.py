#!/usr/bin/env python
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

import os
import uuid
import json
import pytest
import socket
from unittest.mock import MagicMock, patch
from tests.utils import AsyncioMagicMock, asyncio_patch

from gns3server.controller.compute import Compute
from gns3server.controller.controller_error import ControllerError, ControllerNotFoundError
from gns3server.version import __version__


# def test_save(controller, controller_config_path):
#
#     controller.save()
#     assert os.path.exists(controller_config_path)
#     with open(controller_config_path) as f:
#         data = json.load(f)
#         assert data["version"] == __version__
#         assert data["iou_license"] == controller.iou_license
#         assert data["gns3vm"] == controller.gns3vm.asdict()
#
#
# def test_load_controller_settings(controller, controller_config_path):
#
#     controller.save()
#     with open(controller_config_path) as f:
#         data = json.load(f)
#     data["gns3vm"] = {"vmname": "Test VM"}
#     with open(controller_config_path, "w+") as f:
#         json.dump(data, f)
#     controller._load_controller_settings()
#     assert controller.gns3vm.settings["vmname"] == "Test VM"
#
#
# def test_load_controller_settings_with_no_computes_section(controller, controller_config_path):
#
#     controller.save()
#     with open(controller_config_path) as f:
#         data = json.load(f)
#     with open(controller_config_path, "w+") as f:
#         json.dump(data, f)
#     assert len(controller._load_controller_settings()) == 0
#
#
# def test_import_computes_1_x(controller, controller_config_path):
#     """
#     At first start the server should import the
#     computes from the gns3_gui 1.X
#     """
#
#     gns3_gui_conf = {
#         "Servers": {
#             "remote_servers": [
#                 {
#                     "host": "127.0.0.1",
#                     "password": "",
#                     "port": 3081,
#                     "protocol": "http",
#                     "url": "http://127.0.0.1:3081",
#                     "user": ""
#                 }
#             ]
#         }
#     }
#     config_dir = os.path.dirname(controller_config_path)
#     os.makedirs(config_dir, exist_ok=True)
#     with open(os.path.join(config_dir, "gns3_gui.conf"), "w+") as f:
#         json.dump(gns3_gui_conf, f)
#
#     controller._load_controller_settings()
#     for compute in controller.computes.values():
#         if compute.id != "local":
#             assert len(compute.id) == 36
#             assert compute.host == "127.0.0.1"
#             assert compute.port == 3081
#             assert compute.protocol == "http"
#             assert compute.name == "http://127.0.0.1:3081"
#             assert compute.user is None
#             assert compute.password is None


@pytest.mark.asyncio
async def test_load_projects(controller, projects_dir):

    controller.save()
    os.makedirs(os.path.join(projects_dir, "project1"))
    with open(os.path.join(projects_dir, "project1", "project1.gns3"), "w+") as f:
        f.write("")
    with asyncio_patch("gns3server.controller.Controller.load_project") as mock_load_project:
        await controller.load_projects()
    mock_load_project.assert_called_with(os.path.join(projects_dir, "project1", "project1.gns3"), load=False)


@pytest.mark.asyncio
async def test_add_compute(controller):

    controller._notification = MagicMock()
    c = await controller.add_compute(compute_id="test1", connect=False)
    controller._notification.controller_emit.assert_called_with("compute.created", c.asdict())
    assert len(controller.computes) == 1
    await controller.add_compute(compute_id="test1", connect=False)
    controller._notification.controller_emit.assert_called_with("compute.updated", c.asdict())
    assert len(controller.computes) == 1
    await controller.add_compute(compute_id="test2", connect=False)
    assert len(controller.computes) == 2


@pytest.mark.asyncio
async def test_addDuplicateCompute(controller):

    controller._notification = MagicMock()
    c = await controller.add_compute(compute_id="test1", name="Test", connect=False)
    assert len(controller.computes) == 1
    with pytest.raises(ControllerError):
        await controller.add_compute(compute_id="test2", name="Test", connect=False)


@pytest.mark.asyncio
async def test_deleteComputeProjectOpened(controller, controller_config_path):
    """
    When you delete a compute the project using it are close
    """

    c = await controller.add_compute(compute_id="test1", connect=False)
    c.post = AsyncioMagicMock()
    assert len(controller.computes) == 1

    project1 = await controller.add_project(name="Test1")
    await project1.open()
    # We simulate that the project use this compute
    project1._project_created_on_compute.add(c)

    project2 = await controller.add_project(name="Test2")
    await project2.open()

    controller._notification = MagicMock()
    c._connected = True
    await controller.delete_compute("test1")
    assert len(controller.computes) == 0
    controller._notification.controller_emit.assert_called_with("compute.deleted", c.asdict())
    assert c.connected is False

    # Project 1 use this compute it should be close before deleting the compute
    assert project1.status == "closed"
    assert project2.status == "opened"


@pytest.mark.asyncio
async def test_getCompute(controller):

    compute = await controller.add_compute(compute_id="test1", connect=False)
    assert controller.get_compute("test1") == compute
    with pytest.raises(ControllerNotFoundError):
        assert controller.get_compute("dsdssd")


@pytest.mark.asyncio
async def test_has_compute(controller):

    await controller.add_compute(compute_id="test1", connect=False)
    assert controller.has_compute("test1")
    assert not controller.has_compute("test2")


@pytest.mark.asyncio
async def test_add_project(controller):

    uuid1 = str(uuid.uuid4())
    uuid2 = str(uuid.uuid4())
    await controller.add_project(project_id=uuid1, name="Test")
    assert len(controller.projects) == 1
    await controller.add_project(project_id=uuid1, name="Test")
    assert len(controller.projects) == 1
    await controller.add_project(project_id=uuid2, name="Test 2")
    assert len(controller.projects) == 2


@pytest.mark.asyncio
async def test_addDuplicateProject(controller):

    uuid1 = str(uuid.uuid4())
    uuid2 = str(uuid.uuid4())
    await controller.add_project(project_id=uuid1, name="Test")
    assert len(controller.projects) == 1
    with pytest.raises(ControllerError):
        await controller.add_project(project_id=uuid2, name="Test")


@pytest.mark.asyncio
async def test_remove_project(controller):

    uuid1 = str(uuid.uuid4())
    project1 = await controller.add_project(project_id=uuid1, name="Test")
    assert len(controller.projects) == 1
    controller.remove_project(project1)
    assert len(controller.projects) == 0


@pytest.mark.asyncio
async def test_addProject_with_compute(controller):

    uuid1 = str(uuid.uuid4())
    compute = Compute("test1", controller=MagicMock())
    compute.post = MagicMock()
    controller._computes = {"test1": compute}
    await controller.add_project(project_id=uuid1, name="Test")


@pytest.mark.asyncio
async def test_getProject(controller):

    uuid1 = str(uuid.uuid4())
    project = await controller.add_project(project_id=uuid1, name="Test")
    assert controller.get_project(uuid1) == project
    with pytest.raises(ControllerNotFoundError):
        assert controller.get_project("dsdssd")


@pytest.mark.asyncio
async def test_start(controller):

    controller.gns3vm.settings = {
        "enable": False,
        "engine": "vmware",
        "vmname": "GNS3 VM"
    }

    #with asyncio_patch("gns3server.controller.compute.Compute.connect") as mock:
    await controller.start()
    #assert mock.called
    assert len(controller.computes) == 1  # Local compute is created
    assert controller.computes["local"].name == f"{socket.gethostname()} (controller)"


@pytest.mark.asyncio
async def test_start_vm(controller):
    """
    Start the controller with a GNS3 VM
    """

    controller.gns3vm.settings = {
        "enable": True,
        "engine": "vmware",
        "vmname": "GNS3 VM"
    }

    with asyncio_patch("gns3server.controller.gns3vm.vmware_gns3_vm.VMwareGNS3VM.start") as mock:
        with asyncio_patch("gns3server.controller.gns3vm.GNS3VM._check_network"):
            with asyncio_patch("gns3server.controller.compute.Compute.connect"):
                await controller.start()
                assert mock.called
    assert "local" in controller.computes
    assert "vm" in controller.computes
    assert len(controller.computes) == 2  # Local compute and vm are created


@pytest.mark.asyncio
async def test_stop(controller):

    c = await controller.add_compute(compute_id="test1", connect=False)
    c._connected = True
    await controller.stop()
    assert c.connected is False


@pytest.mark.asyncio
async def test_stop_vm(controller):
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
        await controller.stop()
        assert mock.called


@pytest.mark.asyncio
async def test_suspend_vm(controller):
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
        await controller.stop()
        assert mock.called


@pytest.mark.asyncio
async def test_keep_vm(controller):
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
        await controller.stop()
        assert not mock.called


@pytest.mark.asyncio
async def test_get_free_project_name(controller):

    await controller.add_project(project_id=str(uuid.uuid4()), name="Test")
    assert controller.get_free_project_name("Test") == "Test-1"
    await controller.add_project(project_id=str(uuid.uuid4()), name="Test-1")
    assert controller.get_free_project_name("Test") == "Test-2"
    assert controller.get_free_project_name("Hello") == "Hello"


@pytest.mark.asyncio
async def test_install_base_configs(controller, config, tmpdir):

    config.settings.Server.configs_path = str(tmpdir)
    with open(str(tmpdir / 'iou_l2_base_startup-config.txt'), 'w+') as f:
        f.write('test')

    controller._install_base_configs()
    assert os.path.exists(str(tmpdir / 'iou_l3_base_startup-config.txt'))

    # Check is the file has not been overwritten
    with open(str(tmpdir / 'iou_l2_base_startup-config.txt')) as f:
        assert f.read() == 'test'


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "builtin_disk",
    [
        "empty8G.qcow2",
        "empty10G.qcow2",
        "empty20G.qcow2",
        "empty30G.qcow2",
        "empty40G.qcow2",
        "empty50G.qcow2",
        "empty100G.qcow2",
        "empty150G.qcow2",
        "empty200G.qcow2",
        "empty250G.qcow2",
        "empty500G.qcow2",
        "empty1T.qcow2"
    ]
)
async def test_install_builtin_disks(controller, config, tmpdir, builtin_disk):

    config.settings.Server.images_path = str(tmpdir)
    controller._install_builtin_disks()
    # we only install Qemu empty disks at this time
    assert os.path.exists(str(tmpdir / "QEMU" / builtin_disk))


def test_appliances(controller, config, tmpdir):

    my_appliance = {
        "name": "My Appliance",
        "status": "stable"
    }
    with open(str(tmpdir / "my_appliance.gns3a"), 'w+') as f:
        json.dump(my_appliance, f)
    # A broken appliance
    my_appliance = {
        "name": "Broken"
    }
    with open(str(tmpdir / "my_appliance2.gns3a"), 'w+') as f:
        json.dump(my_appliance, f)

    config.settings.Server.appliances_path = str(tmpdir)
    controller.appliance_manager.install_builtin_appliances()
    controller.appliance_manager.load_appliances()
    assert len(controller.appliance_manager.appliances) > 0
    for appliance in controller.appliance_manager.appliances.values():
        assert appliance.asdict()["status"] != "broken"
    assert "Alpine Linux" in [c.asdict()["name"] for c in controller.appliance_manager.appliances.values()]
    assert "My Appliance" not in [c.asdict()["name"] for c in controller.appliance_manager.appliances.values()]

    for c in controller.appliance_manager.appliances.values():
        j = c.asdict()
        if j["name"] == "Alpine Linux":
            assert j["builtin"]


@pytest.mark.asyncio
async def test_autoidlepc(controller):

    controller._computes["local"] = AsyncioMagicMock()
    node_mock = AsyncioMagicMock()
    with asyncio_patch("gns3server.controller.Project.add_node", return_value=node_mock):
        await controller.autoidlepc("local", "c7200", "test.bin", 512)
    assert node_mock.dynamips_auto_idlepc.called
    assert len(controller.projects) == 0
