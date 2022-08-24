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

import uuid
import os
import pytest
import pytest_asyncio
from unittest.mock import patch, MagicMock
from tests.utils import asyncio_patch

from gns3server.compute.vpcs import VPCS
from gns3server.compute.dynamips import Dynamips
from gns3server.compute.qemu import Qemu
from gns3server.compute.error import NodeError, ImageMissingError
from gns3server.utils import force_unix_path


@pytest_asyncio.fixture(scope="function")
async def vpcs(port_manager):

    VPCS._instance = None
    vpcs = VPCS.instance()
    vpcs.port_manager = port_manager
    return vpcs


@pytest_asyncio.fixture(scope="function")
async def qemu(port_manager):

    Qemu._instance = None
    Qemu._init_config_disk = MagicMock()  # do not create the config.img image
    qemu = Qemu.instance()
    qemu.port_manager = port_manager
    return qemu


@pytest.mark.asyncio
async def test_create_node_new_topology(compute_project, vpcs):

    node_id = str(uuid.uuid4())
    node = await vpcs.create_node("PC 1", compute_project.id, node_id)
    assert node in compute_project.nodes


@pytest.mark.asyncio
async def test_create_twice_same_node_new_topology(compute_project, vpcs):

    compute_project._nodes = set()
    node_id = str(uuid.uuid4())
    node = await vpcs.create_node("PC 1", compute_project.id, node_id, console=2222)
    assert node in compute_project.nodes
    assert len(compute_project.nodes) == 1
    await vpcs.create_node("PC 2", compute_project.id, node_id, console=2222)
    assert len(compute_project.nodes) == 1


@pytest.mark.asyncio
async def test_create_node_new_topology_without_uuid(compute_project, vpcs):

    node = await vpcs.create_node("PC 1", compute_project.id, None)
    assert node in compute_project.nodes
    assert len(node.id) == 36


def test_get_abs_image_path(qemu, tmpdir, config):

    os.makedirs(str(tmpdir / "QEMU"))
    path1 = force_unix_path(str(tmpdir / "test1.bin"))
    open(path1, 'w+').close()

    path2 = force_unix_path(str(tmpdir / "QEMU" / "test2.bin"))
    open(path2, 'w+').close()

    config.settings.Server.images_path = str(tmpdir)
    assert qemu.get_abs_image_path(path1) == path1
    assert qemu.get_abs_image_path("test1.bin") == path1
    assert qemu.get_abs_image_path(path2) == path2
    assert qemu.get_abs_image_path("test2.bin") == path2
    assert qemu.get_abs_image_path("../test1.bin") == path1


def test_get_abs_image_path_non_local(qemu, tmpdir, config):

    path1 = tmpdir / "images" / "QEMU" / "test1.bin"
    path1.write("1", ensure=True)
    path1 = force_unix_path(str(path1))

    path2 = tmpdir / "private" / "QEMU" / "test2.bin"
    path2.write("1", ensure=True)
    path2 = force_unix_path(str(path2))

    # If non local we can't use path outside images directory
    config.settings.Server.images_path = str(tmpdir / "images")
    assert qemu.get_abs_image_path(path1) == path1
    with pytest.raises(NodeError):
        qemu.get_abs_image_path(path2)
    with pytest.raises(NodeError):
        qemu.get_abs_image_path("C:\\test2.bin")

    # config.settings.Server.images_path = str(tmpdir / "images")
    # config.settings.Server.local = True
    # assert qemu.get_abs_image_path(path2) == path2


def test_get_abs_image_additional_image_paths(qemu, tmpdir, config):

    path1 = tmpdir / "images1" / "QEMU" / "test1.bin"
    path1.write("1", ensure=True)
    path1 = force_unix_path(str(path1))

    path2 = tmpdir / "images2" / "test2.bin"
    path2.write("1", ensure=True)
    path2 = force_unix_path(str(path2))

    config.settings.Server.images_path = str(tmpdir / "images1")
    config.settings.Server.additional_images_paths = "/tmp/null24564;" + str(tmpdir / "images2")

    assert qemu.get_abs_image_path("test1.bin") == path1
    assert qemu.get_abs_image_path("test2.bin") == path2
    # Absolute path
    assert qemu.get_abs_image_path(str(path2)) == path2

    with pytest.raises(ImageMissingError):
        qemu.get_abs_image_path("test4.bin")


def test_get_abs_image_recursive(qemu, tmpdir, config):

    path1 = tmpdir / "images1" / "QEMU" / "demo" / "test1.bin"
    path1.write("1", ensure=True)
    path1 = force_unix_path(str(path1))

    path2 = tmpdir / "images1" / "QEMU" / "test2.bin"
    path2.write("1", ensure=True)
    path2 = force_unix_path(str(path2))

    config.settings.Server.images_path = str(tmpdir / "images1")

    assert qemu.get_abs_image_path("test1.bin") == path1
    assert qemu.get_abs_image_path("test2.bin") == path2
    # Absolute path
    assert qemu.get_abs_image_path(str(path1)) == path1


def test_get_abs_image_recursive_ova(qemu, tmpdir, config):

    path1 = tmpdir / "images1" / "QEMU" / "demo" / "test.ova" / "test1.bin"
    path1.write("1", ensure=True)
    path1 = force_unix_path(str(path1))

    path2 = tmpdir / "images1" / "QEMU" / "test.ova" / "test2.bin"
    path2.write("1", ensure=True)
    path2 = force_unix_path(str(path2))

    config.settings.Server.images_path = str(tmpdir / "images1")

    assert qemu.get_abs_image_path("demo/test.ova/test1.bin") == path1
    assert qemu.get_abs_image_path("test.ova/test2.bin") == path2
    # Absolute path
    assert qemu.get_abs_image_path(str(path1)) == path1


def test_get_relative_image_path(qemu, tmpdir, config):

    os.makedirs(str(tmpdir / "images1" / "QEMU"))
    os.makedirs(str(tmpdir / "images1" / "VBOX"))
    path1 = force_unix_path(str(tmpdir / "images1" / "test1.bin"))
    open(path1, 'w+').close()

    path2 = force_unix_path(str(tmpdir / "images1" / "QEMU" / "test2.bin"))
    open(path2, 'w+').close()

    os.makedirs(str(tmpdir / "images2"))
    path3 = force_unix_path(str(tmpdir / "images2" / "test3.bin"))
    open(path3, 'w+').close()

    path4 = force_unix_path(str(tmpdir / "test4.bin"))
    open(path4, 'w+').close()

    # The user use an image of another emulator we return the full path
    path5 = force_unix_path(str(tmpdir / "images1" / "VBOX" / "test5.bin"))
    open(path5, 'w+').close()

    config.settings.Server.images_path = str(tmpdir / "images1")
    config.settings.Server.additional_images_paths = str(tmpdir / "images2")

    assert qemu.get_relative_image_path(path1) == "test1.bin"
    assert qemu.get_relative_image_path("test1.bin") == "test1.bin"
    assert qemu.get_relative_image_path(path2) == "test2.bin"
    assert qemu.get_relative_image_path("test2.bin") == "test2.bin"
    assert qemu.get_relative_image_path("../test1.bin") == "test1.bin"
    assert qemu.get_relative_image_path("test3.bin") == "test3.bin"
    with pytest.raises(NodeError):
        assert qemu.get_relative_image_path(path4) == path4
    assert qemu.get_relative_image_path(path5) == path5


@pytest.mark.asyncio
async def test_list_images(qemu, tmpdir):

    fake_images = ["a.qcow2", "b.qcow2", ".blu.qcow2", "a.qcow2.md5sum"]
    tmp_images_dir = os.path.join(tmpdir, "images")
    os.makedirs(tmp_images_dir, exist_ok=True)
    for image in fake_images:
        with open(os.path.join(tmp_images_dir, image), "w+") as f:
            f.write("1")

    with patch("gns3server.utils.images.default_images_directory", return_value=str(tmp_images_dir)):
        assert sorted(await qemu.list_images(), key=lambda k: k['filename']) == [
            {"filename": "a.qcow2", "path": "a.qcow2", "md5sum": "c4ca4238a0b923820dcc509a6f75849b", "filesize": 1},
            {"filename": "b.qcow2", "path": "b.qcow2", "md5sum": "c4ca4238a0b923820dcc509a6f75849b", "filesize": 1}
        ]


@pytest.mark.asyncio
async def test_list_images_recursives(qemu, tmpdir):

    tmp_images_dir = os.path.join(tmpdir, "images")
    os.makedirs(tmp_images_dir, exist_ok=True)
    fake_images = ["a.qcow2", "b.qcow2", ".blu.qcow2", "a.qcow2.md5sum"]
    for image in fake_images:
        with open(os.path.join(tmp_images_dir, image), "w+") as f:
            f.write("1")
    os.makedirs(os.path.join(tmp_images_dir, "c"))
    fake_images = ["c.qcow2", "c.qcow2.md5sum"]
    for image in fake_images:
        with open(os.path.join(tmp_images_dir, "c", image), "w+") as f:
            f.write("1")

    with patch("gns3server.utils.images.default_images_directory", return_value=str(tmp_images_dir)):

        assert sorted(await qemu.list_images(), key=lambda k: k['filename']) == [
            {"filename": "a.qcow2", "path": "a.qcow2", "md5sum": "c4ca4238a0b923820dcc509a6f75849b", "filesize": 1},
            {"filename": "b.qcow2", "path": "b.qcow2", "md5sum": "c4ca4238a0b923820dcc509a6f75849b", "filesize": 1},
            {"filename": "c.qcow2", "path": force_unix_path(os.path.sep.join(["c", "c.qcow2"])), "md5sum": "c4ca4238a0b923820dcc509a6f75849b", "filesize": 1}
        ]


@pytest.mark.asyncio
async def test_list_images_empty(qemu, tmpdir):

    with patch("gns3server.compute.Qemu.get_images_directory", return_value=str(tmpdir)):
        assert await qemu.list_images() == []


@pytest.mark.asyncio
async def test_list_images_directory_not_exist(qemu):

    with patch("gns3server.compute.Qemu.get_images_directory", return_value="/bla"):
        assert await qemu.list_images() == []


@pytest.mark.asyncio
async def test_delete_node(vpcs, compute_project):

    compute_project._nodes = set()
    node_id = str(uuid.uuid4())
    node = await vpcs.create_node("PC 1", compute_project.id, node_id, console=2222)
    assert node in compute_project.nodes
    with patch("gns3server.compute.project.Project.emit") as mock_emit:
        await vpcs.delete_node(node_id)
        mock_emit.assert_called_with("node.deleted", node)
    assert node not in compute_project.nodes


@pytest.mark.asyncio
async def test_duplicate_vpcs(vpcs, compute_project):

    source_node_id = str(uuid.uuid4())
    source_node = await vpcs.create_node("PC-1", compute_project.id, source_node_id, console=2222)
    with open(os.path.join(source_node.working_dir, "startup.vpc"), "w+") as f:
        f.write("set pcname PC-1\nip dhcp\n")
    destination_node_id = str(uuid.uuid4())
    destination_node = await vpcs.create_node("PC-2", compute_project.id, destination_node_id, console=2223)
    await vpcs.duplicate_node(source_node_id, destination_node_id)
    with open(os.path.join(destination_node.working_dir, "startup.vpc")) as f:
        startup = f.read().strip()
        assert startup == "set pcname PC-2\nip dhcp\n".strip()


@pytest.mark.asyncio
async def test_duplicate_ethernet_switch(compute_project):

    with asyncio_patch('gns3server.compute.dynamips.nodes.ethernet_switch.EthernetSwitch.create'):
        dynamips_manager = Dynamips.instance()
        source_node_id = str(uuid.uuid4())
        await dynamips_manager.create_node("SW-1", compute_project.id, source_node_id, node_type='ethernet_switch')
        destination_node_id = str(uuid.uuid4())
        await dynamips_manager.create_node("SW-2", compute_project.id, destination_node_id, node_type='ethernet_switch')
        await dynamips_manager.duplicate_node(source_node_id, destination_node_id)
