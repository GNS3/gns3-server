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
from gns3server.modules.vm_error import VMError
from gns3server.utils import force_unix_path


@pytest.fixture(scope="function")
def vpcs(port_manager):
    VPCS._instance = None
    vpcs = VPCS.instance()
    vpcs.port_manager = port_manager
    return vpcs


@pytest.fixture(scope="function")
def qemu(port_manager):
    Qemu._instance = None
    qemu = Qemu.instance()
    qemu.port_manager = port_manager
    return qemu


def test_create_vm_new_topology(loop, project, vpcs):
    vm_id = str(uuid.uuid4())
    vm = loop.run_until_complete(vpcs.create_vm("PC 1", project.id, vm_id))
    assert vm in project.vms


def test_create_twice_same_vm_new_topology(loop, project, vpcs):
    project._vms = set()
    vm_id = str(uuid.uuid4())
    vm = loop.run_until_complete(vpcs.create_vm("PC 1", project.id, vm_id, console=2222))
    assert vm in project.vms
    assert len(project.vms) == 1
    vm = loop.run_until_complete(vpcs.create_vm("PC 2", project.id, vm_id, console=2222))
    assert len(project.vms) == 1


def test_create_vm_new_topology_without_uuid(loop, project, vpcs):
    vm = loop.run_until_complete(vpcs.create_vm("PC 1", project.id, None))
    assert vm in project.vms
    assert len(vm.id) == 36


def test_create_vm_old_topology(loop, project, tmpdir, vpcs):

    with patch("gns3server.modules.project.Project.is_local", return_value=True):
        # Create an old topology directory
        project_dir = str(tmpdir / "testold")
        vm_dir = os.path.join(project_dir, "testold-files", "vpcs", "pc-1")
        project.path = project_dir
        project.name = "testold"
        os.makedirs(vm_dir, exist_ok=True)
        with open(os.path.join(vm_dir, "startup.vpc"), "w+") as f:
            f.write("1")

        vm_id = 1
        vm = loop.run_until_complete(vpcs.create_vm("PC 1", project.id, vm_id))
        assert len(vm.id) == 36

        assert os.path.exists(os.path.join(project_dir, "testold-files")) is False

        vm_dir = os.path.join(project_dir, "project-files", "vpcs", vm.id)
        with open(os.path.join(vm_dir, "startup.vpc")) as f:
            assert f.read() == "1"


def test_get_abs_image_path(qemu, tmpdir):
    os.makedirs(str(tmpdir / "QEMU"))
    path1 = force_unix_path(str(tmpdir / "test1.bin"))
    open(path1, 'w+').close()

    path2 = force_unix_path(str(tmpdir / "QEMU" / "test2.bin"))
    open(path2, 'w+').close()

    with patch("gns3server.config.Config.get_section_config", return_value={"images_path": str(tmpdir)}):
        assert qemu.get_abs_image_path(path1) == path1
        assert qemu.get_abs_image_path("test1.bin") == path1
        assert qemu.get_abs_image_path(path2) == path2
        assert qemu.get_abs_image_path("test2.bin") == path2
        assert qemu.get_abs_image_path("../test1.bin") == path1


def test_get_abs_image_path_non_local(qemu, tmpdir):
    path1 = tmpdir / "images" / "QEMU" / "test1.bin"
    path1.write("1", ensure=True)
    path1 = force_unix_path(str(path1))

    path2 = tmpdir / "private" / "QEMU" / "test2.bin"
    path2.write("1", ensure=True)
    path2 = force_unix_path(str(path2))

    # If non local we can't use path outside images directory
    with patch("gns3server.config.Config.get_section_config", return_value={"images_path": str(tmpdir / "images"), "local": False}):
        assert qemu.get_abs_image_path(path1) == path1
        with pytest.raises(VMError):
            qemu.get_abs_image_path(path2)
        with pytest.raises(VMError):
            qemu.get_abs_image_path("C:\\test2.bin")

    with patch("gns3server.config.Config.get_section_config", return_value={"images_path": str(tmpdir / "images"), "local": True}):
        assert qemu.get_abs_image_path(path2) == path2


def test_get_relative_image_path(qemu, tmpdir):
    os.makedirs(str(tmpdir / "QEMU"))
    path1 = force_unix_path(str(tmpdir / "test1.bin"))
    open(path1, 'w+').close()

    path2 = force_unix_path(str(tmpdir / "QEMU" / "test2.bin"))
    open(path2, 'w+').close()

    with patch("gns3server.config.Config.get_section_config", return_value={"images_path": str(tmpdir)}):
        assert qemu.get_relative_image_path(path1) == path1
        assert qemu.get_relative_image_path("test1.bin") == path1
        assert qemu.get_relative_image_path(path2) == "test2.bin"
        assert qemu.get_relative_image_path("test2.bin") == "test2.bin"
        assert qemu.get_relative_image_path("../test1.bin") == path1


def test_get_relative_image_path_ova(qemu, tmpdir):
    os.makedirs(str(tmpdir / "QEMU" / "test.ovf"))
    path = str(tmpdir / "QEMU" / "test.ovf" / "test.bin")
    open(path, 'w+').close()

    with patch("gns3server.config.Config.get_section_config", return_value={"images_path": str(tmpdir)}):
        assert qemu.get_relative_image_path(path) == os.path.join("test.ovf", "test.bin")
        assert qemu.get_relative_image_path(os.path.join("test.ovf", "test.bin")) == os.path.join("test.ovf", "test.bin")


def test_list_images(loop, qemu, tmpdir):

    fake_images = ["a.bin", "b.bin", ".blu.bin", "a.bin.md5sum"]
    for image in fake_images:
        with open(str(tmpdir / image), "w+") as f:
            f.write("1")

    with patch("gns3server.modules.Qemu.get_images_directory", return_value=str(tmpdir)):
        assert loop.run_until_complete(qemu.list_images()) == [
            {"filename": "a.bin", "path": "a.bin"},
            {"filename": "b.bin", "path": "b.bin"}
        ]


def test_list_images_recursives(loop, qemu, tmpdir):

    fake_images = ["a.bin", "b.bin", ".blu.bin", "a.bin.md5sum"]
    for image in fake_images:
        with open(str(tmpdir / image), "w+") as f:
            f.write("1")
    os.makedirs(str(tmpdir / "c"))
    fake_images = ["c.bin", "c.bin.md5sum"]
    for image in fake_images:
        with open(str(tmpdir / "c" / image), "w+") as f:
            f.write("1")

    with patch("gns3server.modules.Qemu.get_images_directory", return_value=str(tmpdir)):
        assert loop.run_until_complete(qemu.list_images()) == [
            {"filename": "a.bin", "path": "a.bin"},
            {"filename": "b.bin", "path": "b.bin"},
            {"filename": "c.bin", "path": os.path.sep.join(["c", "c.bin"])}
        ]


def test_list_images_empty(loop, qemu, tmpdir):
    with patch("gns3server.modules.Qemu.get_images_directory", return_value=str(tmpdir)):
        assert loop.run_until_complete(qemu.list_images()) == []


def test_list_images_directory_not_exist(loop, qemu):
    with patch("gns3server.modules.Qemu.get_images_directory", return_value="/bla"):
        assert loop.run_until_complete(qemu.list_images()) == []
