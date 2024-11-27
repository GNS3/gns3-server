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
import uuid
import os
import sys
import stat
from tests.utils import asyncio_patch
from unittest.mock import patch


@pytest.fixture
def fake_qemu_bin(monkeypatch, tmpdir):

    monkeypatch.setenv("PATH", str(tmpdir))
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
        f.write("1234567")
    os.chmod(bin_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    return bin_path


@pytest.fixture
def base_params(tmpdir, fake_qemu_bin):
    """Return standard parameters"""

    return {"name": "PC TEST 1", "qemu_path": fake_qemu_bin}


@pytest.fixture
async def vm(compute_api, compute_project, base_params):

    response = await compute_api.post("/projects/{project_id}/qemu/nodes".format(project_id=compute_project.id), base_params)
    assert response.status == 201
    return response.json


async def test_qemu_create(compute_api, compute_project, base_params, fake_qemu_bin):

    response = await compute_api.post("/projects/{project_id}/qemu/nodes".format(project_id=compute_project.id), base_params)
    assert response.status == 201
    assert response.route == "/projects/{project_id}/qemu/nodes"
    assert response.json["name"] == "PC TEST 1"
    assert response.json["project_id"] == compute_project.id
    assert response.json["qemu_path"] == fake_qemu_bin
    assert response.json["platform"] == "x86_64"


async def test_qemu_create_platform(compute_api, compute_project, base_params, fake_qemu_bin):

    base_params["qemu_path"] = None
    base_params["platform"] = "x86_64"
    response = await compute_api.post("/projects/{project_id}/qemu/nodes".format(project_id=compute_project.id), base_params)
    assert response.status == 201
    assert response.route == "/projects/{project_id}/qemu/nodes"
    assert response.json["name"] == "PC TEST 1"
    assert response.json["project_id"] == compute_project.id
    assert response.json["qemu_path"] == fake_qemu_bin
    assert response.json["platform"] == "x86_64"


async def test_qemu_create_with_params(compute_api, compute_project, base_params, fake_qemu_vm):

    params = base_params
    params["ram"] = 1024
    params["hda_disk_image"] = "linux载.img"
    response = await compute_api.post("/projects/{project_id}/qemu/nodes".format(project_id=compute_project.id), params)
    assert response.status == 201
    assert response.route == "/projects/{project_id}/qemu/nodes"
    assert response.json["name"] == "PC TEST 1"
    assert response.json["project_id"] == compute_project.id
    assert response.json["ram"] == 1024
    assert response.json["hda_disk_image"] == "linux载.img"
    assert response.json["hda_disk_image_md5sum"] == "fcea920f7412b5da7be0cf42b8c93759"


@pytest.mark.skipif(sys.platform.startswith("win"), reason="Not supported on Windows")
async def test_qemu_create_with_project_file(compute_api, compute_project, base_params, fake_qemu_vm):

    response = await compute_api.post("/projects/{project_id}/files/hello.img".format(project_id=compute_project.id), body="world", raw=True)
    assert response.status == 201
    params = base_params
    params["hda_disk_image"] = "hello.img"
    response = await compute_api.post("/projects/{project_id}/qemu/nodes".format(project_id=compute_project.id), params)
    assert response.status == 201
    assert response.json["hda_disk_image"] == "hello.img"
    assert response.json["hda_disk_image_md5sum"] == "7d793037a0760186574b0282f2f435e7"


async def test_qemu_get(compute_api, compute_project, vm):

    response = await compute_api.get("/projects/{project_id}/qemu/nodes/{node_id}".format(project_id=vm["project_id"], node_id=vm["node_id"]))
    assert response.status == 200
    assert response.route == "/projects/{project_id}/qemu/nodes/{node_id}"
    assert response.json["name"] == "PC TEST 1"
    assert response.json["project_id"] == compute_project.id
    assert response.json["node_directory"] == os.path.join(compute_project.path, "project-files", "qemu", vm["node_id"])


async def test_qemu_start(compute_api, vm):

    with asyncio_patch("gns3server.compute.qemu.qemu_vm.QemuVM.start", return_value=True) as mock:
        response = await compute_api.post("/projects/{project_id}/qemu/nodes/{node_id}/start".format(project_id=vm["project_id"], node_id=vm["node_id"]))
        assert mock.called
        assert response.status == 200
        assert response.json["name"] == "PC TEST 1"


async def test_qemu_stop(compute_api, vm):

    with asyncio_patch("gns3server.compute.qemu.qemu_vm.QemuVM.stop", return_value=True) as mock:
        response = await compute_api.post("/projects/{project_id}/qemu/nodes/{node_id}/stop".format(project_id=vm["project_id"], node_id=vm["node_id"]))
        assert mock.called
        assert response.status == 204


async def test_qemu_reload(compute_api, vm):

    with asyncio_patch("gns3server.compute.qemu.qemu_vm.QemuVM.reload", return_value=True) as mock:
        response = await compute_api.post("/projects/{project_id}/qemu/nodes/{node_id}/reload".format(project_id=vm["project_id"], node_id=vm["node_id"]))
        assert mock.called
        assert response.status == 204


async def test_qemu_suspend(compute_api, vm):

    with asyncio_patch("gns3server.compute.qemu.qemu_vm.QemuVM.suspend", return_value=True) as mock:
        response = await compute_api.post("/projects/{project_id}/qemu/nodes/{node_id}/suspend".format(project_id=vm["project_id"], node_id=vm["node_id"]))
        assert mock.called
        assert response.status == 204


async def test_qemu_resume(compute_api, vm):

    with asyncio_patch("gns3server.compute.qemu.qemu_vm.QemuVM.resume", return_value=True) as mock:
        response = await compute_api.post("/projects/{project_id}/qemu/nodes/{node_id}/resume".format(project_id=vm["project_id"], node_id=vm["node_id"]))
        assert mock.called
        assert response.status == 204


async def test_qemu_delete(compute_api, vm):

    with asyncio_patch("gns3server.compute.qemu.Qemu.delete_node", return_value=True) as mock:
        response = await compute_api.delete("/projects/{project_id}/qemu/nodes/{node_id}".format(project_id=vm["project_id"], node_id=vm["node_id"]))
        assert mock.called
        assert response.status == 204


async def test_qemu_update(compute_api, vm, free_console_port, fake_qemu_vm):

    params = {
        "name": "test",
        "console": free_console_port,
        "ram": 1024,
        "hdb_disk_image": "linux载.img"
    }

    with patch("gns3server.compute.qemu.qemu_vm.QemuVM.updated") as mock:
        response = await compute_api.put("/projects/{project_id}/qemu/nodes/{node_id}".format(project_id=vm["project_id"], node_id=vm["node_id"]), params)
        assert response.status == 200
        assert response.json["name"] == "test"
        assert response.json["console"] == free_console_port
        assert response.json["hdb_disk_image"] == "linux载.img"
        assert response.json["ram"] == 1024
        assert mock.called


async def test_qemu_nio_create_udp(compute_api, vm):

    params = {
        "type": "nio_udp",
        "lport": 4242,
        "rport": 4343,
        "rhost": "127.0.0.1"
    }

    with asyncio_patch("gns3server.compute.qemu.qemu_vm.QemuVM.add_ubridge_udp_connection"):
        await compute_api.put("/projects/{project_id}/qemu/nodes/{node_id}".format(project_id=vm["project_id"], node_id=vm["node_id"]), {"adapters": 2})
        response = await compute_api.post("/projects/{project_id}/qemu/nodes/{node_id}/adapters/1/ports/0/nio".format(project_id=vm["project_id"], node_id=vm["node_id"]), params)
    assert response.status == 201
    assert response.route == r"/projects/{project_id}/qemu/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio"
    assert response.json["type"] == "nio_udp"


async def test_qemu_nio_update_udp(compute_api, vm):

    params = {
        "type": "nio_udp",
        "lport": 4242,
        "rport": 4343,
        "rhost": "127.0.0.1"
    }

    await compute_api.put("/projects/{project_id}/qemu/nodes/{node_id}".format(project_id=vm["project_id"], node_id=vm["node_id"]), {"adapters": 2})
    await compute_api.post("/projects/{project_id}/qemu/nodes/{node_id}/adapters/1/ports/0/nio".format(project_id=vm["project_id"], node_id=vm["node_id"]), params)

    params["filters"] = {}
    response = await compute_api.put("/projects/{project_id}/qemu/nodes/{node_id}/adapters/1/ports/0/nio".format(project_id=vm["project_id"], node_id=vm["node_id"]), params)
    assert response.status == 201, response.body.decode()
    assert response.route == r"/projects/{project_id}/qemu/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio"
    assert response.json["type"] == "nio_udp"


async def test_qemu_delete_nio(compute_api, vm):

    params = {
        "type": "nio_udp",
        "lport": 4242,
        "rport": 4343,
        "rhost": "127.0.0.1"
    }

    with asyncio_patch("gns3server.compute.qemu.qemu_vm.QemuVM._ubridge_send"):
        await compute_api.put("/projects/{project_id}/qemu/nodes/{node_id}".format(project_id=vm["project_id"], node_id=vm["node_id"]), {"adapters": 2})
        await compute_api.post("/projects/{project_id}/qemu/nodes/{node_id}/adapters/1/ports/0/nio".format(project_id=vm["project_id"], node_id=vm["node_id"]), params)
        response = await compute_api.delete("/projects/{project_id}/qemu/nodes/{node_id}/adapters/1/ports/0/nio".format(project_id=vm["project_id"], node_id=vm["node_id"]))
    assert response.status == 204
    assert response.route == r"/projects/{project_id}/qemu/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio"


async def test_qemu_list_binaries(compute_api, vm):

    ret = [{"path": "/tmp/1", "version": "2.2.0"},
           {"path": "/tmp/2", "version": "2.1.0"}]

    with asyncio_patch("gns3server.compute.qemu.Qemu.binary_list", return_value=ret) as mock:
        response = await compute_api.get("/qemu/binaries".format(project_id=vm["project_id"]))
        mock.assert_called_with(None)
        assert response.status == 200
        assert response.json == ret


async def test_qemu_list_binaries_filter(compute_api, vm):

    ret = [
        {"path": "/tmp/x86_64", "version": "2.2.0"},
        {"path": "/tmp/alpha", "version": "2.1.0"},
        {"path": "/tmp/i386", "version": "2.1.0"}
    ]

    with asyncio_patch("gns3server.compute.qemu.Qemu.binary_list", return_value=ret) as mock:
        response = await compute_api.get("/qemu/binaries".format(project_id=vm["project_id"]), body={"archs": ["i386"]})
        assert response.status == 200
        mock.assert_called_with(["i386"])
        assert response.json == ret


async def test_images(compute_api, fake_qemu_vm):

    response = await compute_api.get("/qemu/images")
    assert response.status == 200
    assert {"filename": "linux载.img", "path": "linux载.img", "md5sum": "fcea920f7412b5da7be0cf42b8c93759", "filesize": 7} in response.json


@pytest.mark.skipif(sys.platform.startswith("win"), reason="Does not work on Windows")
async def test_upload_image(compute_api, tmpdir):

    with patch("gns3server.compute.Qemu.get_images_directory", return_value=str(tmpdir)):
        response = await compute_api.post("/qemu/images/test2使", body="TEST", raw=True)
        assert response.status == 204

    with open(str(tmpdir / "test2使")) as f:
        assert f.read() == "TEST"

    with open(str(tmpdir / "test2使.md5sum")) as f:
        checksum = f.read()
        assert checksum == "033bd94b1168d7e4f0d644c3c95e35bf"


async def test_upload_image_ova(compute_api, tmpdir):

    with patch("gns3server.compute.Qemu.get_images_directory", return_value=str(tmpdir)):
        response = await compute_api.post("/qemu/images/test2.ova/test2.vmdk", body="TEST", raw=True)
        assert response.status == 204

    with open(str(tmpdir / "test2.ova" / "test2.vmdk")) as f:
        assert f.read() == "TEST"

    with open(str(tmpdir / "test2.ova" / "test2.vmdk.md5sum")) as f:
        checksum = f.read()
        assert checksum == "033bd94b1168d7e4f0d644c3c95e35bf"


async def test_upload_image_forbiden_location(compute_api, tmpdir):

    with patch("gns3server.compute.Qemu.get_images_directory", return_value=str(tmpdir)):
        response = await compute_api.post("/qemu/images/../../test2", body="TEST", raw=True)
        assert response.status == 404


@pytest.mark.skipif(not sys.platform.startswith("win") and os.getuid() == 0, reason="Root can delete any image")
async def test_upload_image_permission_denied(compute_api, images_dir):

    with open(os.path.join(images_dir, "QEMU", "test2.tmp"), "w+") as f:
        f.write("")
    os.chmod(os.path.join(images_dir, "QEMU", "test2.tmp"), 0)

    response = await compute_api.post("/qemu/images/test2", body="TEST", raw=True)
    assert response.status == 409


async def test_create_img_relative(compute_api):

    params = {
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
        response = await compute_api.post("/qemu/img", params)
    assert response.status == 201


async def test_create_img_absolute_non_local(compute_api, config):

    config.set("Server", "local", "false")
    params = {
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
        response = await compute_api.post("/qemu/img", params)
    assert response.status == 403


async def test_create_img_absolute_local(compute_api, config):

    config.set("Server", "local", "true")
    params = {
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
        response = await compute_api.post("/qemu/img", params)
    assert response.status == 201


async def test_capabilities(compute_api):

    with asyncio_patch("gns3server.compute.Qemu.get_kvm_archs", return_value=["x86_64"]):
        response = await compute_api.get("/qemu/capabilities")
        assert response.json["kvm"] == ["x86_64"]


async def test_qemu_duplicate(compute_api, vm):

    params = {"destination_node_id": str(uuid.uuid4())}
    with asyncio_patch("gns3server.compute.qemu.Qemu.duplicate_node", return_value=True) as mock:
        response = await compute_api.post("/projects/{project_id}/qemu/nodes/{node_id}/duplicate".format(project_id=vm["project_id"], node_id=vm["node_id"]), params)
        assert mock.called
        assert response.status == 201


async def test_qemu_start_capture(compute_api, vm):

    params = {
        "capture_file_name": "test.pcap",
        "data_link_type": "DLT_EN10MB"
    }

    with patch("gns3server.compute.qemu.qemu_vm.QemuVM.is_running", return_value=True):
        with asyncio_patch("gns3server.compute.qemu.qemu_vm.QemuVM.start_capture") as mock:
            response = await compute_api.post("/projects/{project_id}/qemu/nodes/{node_id}/adapters/0/ports/0/start_capture".format(project_id=vm["project_id"], node_id=vm["node_id"]), params)
            assert response.status == 200
            assert mock.called
            assert "test.pcap" in response.json["pcap_file_path"]


async def test_qemu_stop_capture(compute_api, vm):

    with patch("gns3server.compute.qemu.qemu_vm.QemuVM.is_running", return_value=True):
        with asyncio_patch("gns3server.compute.qemu.qemu_vm.QemuVM.stop_capture") as mock:
            response = await compute_api.post("/projects/{project_id}/qemu/nodes/{node_id}/adapters/0/ports/0/stop_capture".format(project_id=vm["project_id"], node_id=vm["node_id"]))
            assert response.status == 204
            assert mock.called


async def test_qemu_pcap(compute_api, vm, compute_project):

    with asyncio_patch("gns3server.compute.qemu.qemu_vm.QemuVM.get_nio"):
        with asyncio_patch("gns3server.compute.qemu.Qemu.stream_pcap_file"):
            response = await compute_api.get("/projects/{project_id}/qemu/nodes/{node_id}/adapters/0/ports/0/pcap".format(project_id=compute_project.id, node_id=vm["node_id"]), raw=True)
            assert response.status == 200
