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

import pytest
import os
import sys
import stat
from tests.utils import asyncio_patch
from unittest.mock import patch
from gns3server.config import Config


@pytest.fixture
def fake_qemu_bin():

    if sys.platform.startswith("win"):
        bin_path = os.path.join(os.environ["PATH"], "qemu-system-x86_64w.exe")
    else:
        bin_path = os.path.join(os.environ["PATH"], "qemu-system-x86_64")
    with open(bin_path, "w+") as f:
        f.write("1")
    os.chmod(bin_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    return bin_path


@pytest.fixture
def fake_qemu_vm(images_dir):

    img_dir = os.path.join(images_dir, "QEMU")
    bin_path = os.path.join(img_dir, "linux载.img")
    with open(bin_path, "w+") as f:
        f.write("1")
    os.chmod(bin_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    return bin_path


@pytest.fixture
def base_params(tmpdir, fake_qemu_bin):
    """Return standard parameters"""
    return {"name": "PC TEST 1", "qemu_path": fake_qemu_bin}


@pytest.fixture
def vm(http_compute, project, base_params):
    response = http_compute.post("/projects/{project_id}/qemu/nodes".format(project_id=project.id), base_params)
    assert response.status == 201
    return response.json


def test_qemu_create(http_compute, project, base_params, fake_qemu_bin):
    response = http_compute.post("/projects/{project_id}/qemu/nodes".format(project_id=project.id), base_params)
    assert response.status == 201
    assert response.route == "/projects/{project_id}/qemu/nodes"
    assert response.json["name"] == "PC TEST 1"
    assert response.json["project_id"] == project.id
    assert response.json["qemu_path"] == fake_qemu_bin
    assert response.json["platform"] == "x86_64"


def test_qemu_create_platform(http_compute, project, base_params, fake_qemu_bin):
    base_params["qemu_path"] = None
    base_params["platform"] = "x86_64"

    response = http_compute.post("/projects/{project_id}/qemu/nodes".format(project_id=project.id), base_params)
    assert response.status == 201
    assert response.route == "/projects/{project_id}/qemu/nodes"
    assert response.json["name"] == "PC TEST 1"
    assert response.json["project_id"] == project.id
    assert response.json["qemu_path"] == fake_qemu_bin
    assert response.json["platform"] == "x86_64"


def test_qemu_create_with_params(http_compute, project, base_params, fake_qemu_vm):
    params = base_params
    params["ram"] = 1024
    params["hda_disk_image"] = "linux载.img"

    response = http_compute.post("/projects/{project_id}/qemu/nodes".format(project_id=project.id), params, example=True)

    assert response.status == 201
    assert response.route == "/projects/{project_id}/qemu/nodes"
    assert response.json["name"] == "PC TEST 1"
    assert response.json["project_id"] == project.id
    assert response.json["ram"] == 1024
    assert response.json["hda_disk_image"] == "linux载.img"
    assert response.json["hda_disk_image_md5sum"] == "c4ca4238a0b923820dcc509a6f75849b"


def test_qemu_get(http_compute, project, vm):
    response = http_compute.get("/projects/{project_id}/qemu/nodes/{node_id}".format(project_id=vm["project_id"], node_id=vm["node_id"]), example=True)
    assert response.status == 200
    assert response.route == "/projects/{project_id}/qemu/nodes/{node_id}"
    assert response.json["name"] == "PC TEST 1"
    assert response.json["project_id"] == project.id
    assert response.json["node_directory"] == os.path.join(project.path, "project-files", "qemu", vm["node_id"])


def test_qemu_start(http_compute, vm):
    with asyncio_patch("gns3server.compute.qemu.qemu_vm.QemuVM.start", return_value=True) as mock:
        response = http_compute.post("/projects/{project_id}/qemu/nodes/{node_id}/start".format(project_id=vm["project_id"], node_id=vm["node_id"]), example=True)
        assert mock.called
        assert response.status == 200
        assert response.json["name"] == "PC TEST 1"


def test_qemu_stop(http_compute, vm):
    with asyncio_patch("gns3server.compute.qemu.qemu_vm.QemuVM.stop", return_value=True) as mock:
        response = http_compute.post("/projects/{project_id}/qemu/nodes/{node_id}/stop".format(project_id=vm["project_id"], node_id=vm["node_id"]), example=True)
        assert mock.called
        assert response.status == 204


def test_qemu_reload(http_compute, vm):
    with asyncio_patch("gns3server.compute.qemu.qemu_vm.QemuVM.reload", return_value=True) as mock:
        response = http_compute.post("/projects/{project_id}/qemu/nodes/{node_id}/reload".format(project_id=vm["project_id"], node_id=vm["node_id"]), example=True)
        assert mock.called
        assert response.status == 204


def test_qemu_suspend(http_compute, vm):
    with asyncio_patch("gns3server.compute.qemu.qemu_vm.QemuVM.suspend", return_value=True) as mock:
        response = http_compute.post("/projects/{project_id}/qemu/nodes/{node_id}/suspend".format(project_id=vm["project_id"], node_id=vm["node_id"]), example=True)
        assert mock.called
        assert response.status == 204


def test_qemu_resume(http_compute, vm):
    with asyncio_patch("gns3server.compute.qemu.qemu_vm.QemuVM.resume", return_value=True) as mock:
        response = http_compute.post("/projects/{project_id}/qemu/nodes/{node_id}/resume".format(project_id=vm["project_id"], node_id=vm["node_id"]), example=True)
        assert mock.called
        assert response.status == 204


def test_qemu_delete(http_compute, vm):
    with asyncio_patch("gns3server.compute.qemu.Qemu.delete_node", return_value=True) as mock:
        response = http_compute.delete("/projects/{project_id}/qemu/nodes/{node_id}".format(project_id=vm["project_id"], node_id=vm["node_id"]), example=True)
        assert mock.called
        assert response.status == 204


def test_qemu_update(http_compute, vm, free_console_port, project, fake_qemu_vm):
    params = {
        "name": "test",
        "console": free_console_port,
        "ram": 1024,
        "hdb_disk_image": "linux载.img"
    }
    response = http_compute.put("/projects/{project_id}/qemu/nodes/{node_id}".format(project_id=vm["project_id"], node_id=vm["node_id"]), params, example=True)
    assert response.status == 200
    assert response.json["name"] == "test"
    assert response.json["console"] == free_console_port
    assert response.json["hdb_disk_image"] == "linux载.img"
    assert response.json["ram"] == 1024


def test_qemu_nio_create_udp(http_compute, vm):
    http_compute.put("/projects/{project_id}/qemu/nodes/{node_id}".format(project_id=vm["project_id"], node_id=vm["node_id"]), {"adapters": 2})
    response = http_compute.post("/projects/{project_id}/qemu/nodes/{node_id}/adapters/1/ports/0/nio".format(project_id=vm["project_id"], node_id=vm["node_id"]), {"type": "nio_udp",
                                                                                                                                                                   "lport": 4242,
                                                                                                                                                                   "rport": 4343,
                                                                                                                                                                   "rhost": "127.0.0.1"},
                                 example=True)
    assert response.status == 201
    assert response.route == "/projects/{project_id}/qemu/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio"
    assert response.json["type"] == "nio_udp"


def test_qemu_nio_create_ethernet(http_compute, vm):
    http_compute.put("/projects/{project_id}/qemu/nodes/{node_id}".format(project_id=vm["project_id"], node_id=vm["node_id"]), {"adapters": 2})
    response = http_compute.post("/projects/{project_id}/qemu/nodes/{node_id}/adapters/1/ports/0/nio".format(project_id=vm["project_id"], node_id=vm["node_id"]), {"type": "nio_ethernet",
                                                                                                                                                                   "ethernet_device": "eth0",
                                                                                                                                                                   },
                                 example=True)
    assert response.status == 409


def test_qemu_delete_nio(http_compute, vm):
    http_compute.put("/projects/{project_id}/qemu/nodes/{node_id}".format(project_id=vm["project_id"], node_id=vm["node_id"]), {"adapters": 2})
    http_compute.post("/projects/{project_id}/qemu/nodes/{node_id}/adapters/1/ports/0/nio".format(project_id=vm["project_id"], node_id=vm["node_id"]), {"type": "nio_udp",
                                                                                                                                                        "lport": 4242,
                                                                                                                                                        "rport": 4343,
                                                                                                                                                        "rhost": "127.0.0.1"})
    response = http_compute.delete("/projects/{project_id}/qemu/nodes/{node_id}/adapters/1/ports/0/nio".format(project_id=vm["project_id"], node_id=vm["node_id"]), example=True)
    assert response.status == 204
    assert response.route == "/projects/{project_id}/qemu/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio"


def test_qemu_list_binaries(http_compute, vm):
    ret = [{"path": "/tmp/1", "version": "2.2.0"},
           {"path": "/tmp/2", "version": "2.1.0"}]
    with asyncio_patch("gns3server.compute.qemu.Qemu.binary_list", return_value=ret) as mock:
        response = http_compute.get("/qemu/binaries".format(project_id=vm["project_id"]), example=True)
        assert mock.called_with(None)
        assert response.status == 200
        assert response.json == ret


def test_qemu_list_binaries_filter(http_compute, vm):
    ret = [
        {"path": "/tmp/x86_64", "version": "2.2.0"},
        {"path": "/tmp/alpha", "version": "2.1.0"},
        {"path": "/tmp/i386", "version": "2.1.0"}
    ]
    with asyncio_patch("gns3server.compute.qemu.Qemu.binary_list", return_value=ret) as mock:
        response = http_compute.get("/qemu/binaries".format(project_id=vm["project_id"]), body={"archs": ["i386"]}, example=True)
        assert response.status == 200
        assert mock.called_with(["i386"])
        assert response.json == ret


def test_images(http_compute, tmpdir, fake_qemu_vm):

    response = http_compute.get("/qemu/images")
    assert response.status == 200
    assert response.json == [{"filename": "linux载.img", "path": "linux载.img", "md5sum": "c4ca4238a0b923820dcc509a6f75849b", "filesize": 1}]


def test_upload_image(http_compute, tmpdir):
    with patch("gns3server.compute.Qemu.get_images_directory", return_value=str(tmpdir),):
        response = http_compute.post("/qemu/images/test2使", body="TEST", raw=True)
        assert response.status == 204

    with open(str(tmpdir / "test2使")) as f:
        assert f.read() == "TEST"

    with open(str(tmpdir / "test2使.md5sum")) as f:
        checksum = f.read()
        assert checksum == "033bd94b1168d7e4f0d644c3c95e35bf"


def test_upload_image_ova(http_compute, tmpdir):
    with patch("gns3server.compute.Qemu.get_images_directory", return_value=str(tmpdir),):
        response = http_compute.post("/qemu/images/test2.ova/test2.vmdk", body="TEST", raw=True)
        assert response.status == 204

    with open(str(tmpdir / "test2.ova" / "test2.vmdk")) as f:
        assert f.read() == "TEST"

    with open(str(tmpdir / "test2.ova" / "test2.vmdk.md5sum")) as f:
        checksum = f.read()
        assert checksum == "033bd94b1168d7e4f0d644c3c95e35bf"


def test_upload_image_forbiden_location(http_compute, tmpdir):
    with patch("gns3server.compute.Qemu.get_images_directory", return_value=str(tmpdir),):
        response = http_compute.post("/qemu/images/../../test2", body="TEST", raw=True)
        assert response.status == 403


def test_upload_image_permission_denied(http_compute, tmpdir):
    with open(str(tmpdir / "test2.tmp"), "w+") as f:
        f.write("")
    os.chmod(str(tmpdir / "test2.tmp"), 0)

    with patch("gns3server.compute.Qemu.get_images_directory", return_value=str(tmpdir),):
        response = http_compute.post("/qemu/images/test2", body="TEST", raw=True)
        assert response.status == 409


def test_create_img_relative(http_compute):
    body = {
        "qemu_img": "/tmp/qemu-img",
        "path": "hda.qcow2",
        "format": "qcow2",
        "preallocation": "metadata",
        "cluster_size": 64,
        "refcount_bits": 12,
        "lazy_refcounts": "off",
        "size": 100
    }
    with asyncio_patch("gns3server.compute.Qemu.create_disk"):
        response = http_compute.post("/qemu/img", body=body, example=True)

    assert response.status == 201


def test_create_img_absolute_non_local(http_compute):

    config = Config.instance()
    config.set("Server", "local", "false")

    body = {
        "qemu_img": "/tmp/qemu-img",
        "path": "/tmp/hda.qcow2",
        "format": "qcow2",
        "preallocation": "metadata",
        "cluster_size": 64,
        "refcount_bits": 12,
        "lazy_refcounts": "off",
        "size": 100
    }
    with asyncio_patch("gns3server.compute.Qemu.create_disk"):
        response = http_compute.post("/qemu/img", body=body, example=True)

    assert response.status == 403


def test_create_img_absolute_local(http_compute):

    config = Config.instance()
    config.set("Server", "local", "true")

    body = {
        "qemu_img": "/tmp/qemu-img",
        "path": "/tmp/hda.qcow2",
        "format": "qcow2",
        "preallocation": "metadata",
        "cluster_size": 64,
        "refcount_bits": 12,
        "lazy_refcounts": "off",
        "size": 100
    }
    with asyncio_patch("gns3server.compute.Qemu.create_disk"):
        response = http_compute.post("/qemu/img", body=body, example=True)

    assert response.status == 201


def test_capabilities(http_compute):
    with asyncio_patch("gns3server.compute.Qemu.get_kvm_archs", return_value=["x86_64"]):
        response = http_compute.get("/qemu/capabilities", example=True)
        assert response.json["kvm"] == ["x86_64"]
