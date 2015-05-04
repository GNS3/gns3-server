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

import uuid
import os
import pytest
from unittest.mock import patch


from gns3server.modules.vpcs import VPCS
from gns3server.modules.qemu import Qemu


@pytest.fixture(scope="function")
def qemu(port_manager):
    Qemu._instance = None
    qemu = Qemu.instance()
    qemu.port_manager = port_manager
    return qemu


def test_create_vm_new_topology(loop, project, port_manager):

    VPCS._instance = None
    vpcs = VPCS.instance()
    vpcs.port_manager = port_manager
    vm_id = str(uuid.uuid4())
    vm = loop.run_until_complete(vpcs.create_vm("PC 1", project.id, vm_id))
    assert vm in project.vms


def test_create_twice_same_vm_new_topology(loop, project, port_manager):

    project._vms = set()
    VPCS._instance = None
    vpcs = VPCS.instance()
    vpcs.port_manager = port_manager
    vm_id = str(uuid.uuid4())
    vm = loop.run_until_complete(vpcs.create_vm("PC 1", project.id, vm_id, console=2222))
    assert vm in project.vms
    assert len(project.vms) == 1
    vm = loop.run_until_complete(vpcs.create_vm("PC 2", project.id, vm_id, console=2222))
    assert len(project.vms) == 1


def test_create_vm_new_topology_without_uuid(loop, project, port_manager):

    VPCS._instance = None
    vpcs = VPCS.instance()
    vpcs.port_manager = port_manager
    vm = loop.run_until_complete(vpcs.create_vm("PC 1", project.id, None))
    assert vm in project.vms
    assert len(vm.id) == 36


def test_create_vm_old_topology(loop, project, tmpdir, port_manager):

    with patch("gns3server.modules.project.Project.is_local", return_value=True):
        # Create an old topology directory
        project_dir = str(tmpdir / "testold")
        vm_dir = os.path.join(project_dir, "testold-files", "vpcs", "pc-1")
        project.path = project_dir
        project.name = "testold"
        os.makedirs(vm_dir, exist_ok=True)
        with open(os.path.join(vm_dir, "startup.vpc"), "w+") as f:
            f.write("1")

        VPCS._instance = None
        vpcs = VPCS.instance()
        vpcs.port_manager = port_manager
        vm_id = 1
        vm = loop.run_until_complete(vpcs.create_vm("PC 1", project.id, vm_id))
        assert len(vm.id) == 36

        assert os.path.exists(os.path.join(project_dir, "testold-files")) is False

        vm_dir = os.path.join(project_dir, "project-files", "vpcs", vm.id)
        with open(os.path.join(vm_dir, "startup.vpc")) as f:
            assert f.read() == "1"


def test_get_abs_image_path(qemu, tmpdir):
    os.makedirs(str(tmpdir / "QEMU"))
    path1 = str(tmpdir / "test1.bin")
    open(path1, 'w+').close()

    path2 = str(tmpdir / "QEMU" / "test2.bin")
    open(path2, 'w+').close()

    with patch("gns3server.config.Config.get_section_config", return_value={"images_path": str(tmpdir)}):
        assert qemu.get_abs_image_path(path1) == path1
        assert qemu.get_abs_image_path("test1.bin") == path1
        assert qemu.get_abs_image_path(path2) == path2
        assert qemu.get_abs_image_path("test2.bin") == path2
        assert qemu.get_abs_image_path("../test1.bin") == path1

        # We look at first in new location
        path2 = str(tmpdir / "QEMU" / "test1.bin")
        open(path2, 'w+').close()
        assert qemu.get_abs_image_path("test1.bin") == path2


def test_get_relative_image_path(qemu, tmpdir):
    os.makedirs(str(tmpdir / "QEMU"))
    path1 = str(tmpdir / "test1.bin")
    open(path1, 'w+').close()

    path2 = str(tmpdir / "QEMU" / "test2.bin")
    open(path2, 'w+').close()

    with patch("gns3server.config.Config.get_section_config", return_value={"images_path": str(tmpdir)}):
        assert qemu.get_relative_image_path(path1) == path1
        assert qemu.get_relative_image_path("test1.bin") == path1
        assert qemu.get_relative_image_path(path2) == "test2.bin"
        assert qemu.get_relative_image_path("test2.bin") == "test2.bin"
        assert qemu.get_relative_image_path("../test1.bin") == path1
