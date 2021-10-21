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
import os
import sys
import stat

from fastapi import FastAPI, status
from httpx import AsyncClient
from tests.utils import asyncio_patch
from unittest.mock import patch

from gns3server.compute.project import Project

pytestmark = pytest.mark.asyncio


@pytest.fixture
def fake_qemu_bin(monkeypatch, tmpdir) -> str:

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
def fake_qemu_vm(images_dir) -> str:

    img_dir = os.path.join(images_dir, "QEMU")
    bin_path = os.path.join(img_dir, "linux载.img")
    with open(bin_path, "w+") as f:
        f.write("1")
    os.chmod(bin_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    return bin_path


@pytest.fixture
def base_params(tmpdir, fake_qemu_bin) -> dict:
    """Return standard parameters"""

    return {"name": "PC TEST 1", "qemu_path": fake_qemu_bin}


@pytest.fixture
async def vm(app: FastAPI, client: AsyncClient, compute_project: Project, base_params: dict) -> None:

    response = await client.post(app.url_path_for("compute:create_qemu_node", project_id=compute_project.id), json=base_params)
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()


async def test_qemu_create(app: FastAPI,
                           client: AsyncClient,
                           compute_project: Project,
                           base_params: dict,
                           fake_qemu_bin: str) -> None:

    response = await client.post(app.url_path_for("compute:create_qemu_node", project_id=compute_project.id), json=base_params)
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["name"] == "PC TEST 1"
    assert response.json()["project_id"] == compute_project.id
    assert response.json()["qemu_path"] == fake_qemu_bin
    assert response.json()["platform"] == "x86_64"


async def test_qemu_create_platform(app: FastAPI,
                                    client: AsyncClient,
                                    compute_project: Project,
                                    base_params: dict,
                                    fake_qemu_bin: str):

    base_params["qemu_path"] = None
    base_params["platform"] = "x86_64"
    response = await client.post(app.url_path_for("compute:create_qemu_node", project_id=compute_project.id), json=base_params)
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["name"] == "PC TEST 1"
    assert response.json()["project_id"] == compute_project.id
    assert response.json()["qemu_path"] == fake_qemu_bin
    assert response.json()["platform"] == "x86_64"


@pytest.mark.asyncio
async def test_qemu_create_with_params(app: FastAPI,
                                       client: AsyncClient,
                                       compute_project: Project,
                                       base_params: dict,
                                       fake_qemu_vm: str):

    params = base_params
    params["ram"] = 1024
    params["hda_disk_image"] = "linux载.img"
    response = await client.post(app.url_path_for("compute:create_qemu_node", project_id=compute_project.id), json=params)
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["name"] == "PC TEST 1"
    assert response.json()["project_id"] == compute_project.id
    assert response.json()["ram"] == 1024
    assert response.json()["hda_disk_image"] == "linux载.img"
    assert response.json()["hda_disk_image_md5sum"] == "c4ca4238a0b923820dcc509a6f75849b"


@pytest.mark.skipif(sys.platform.startswith("win"), reason="Not supported on Windows")
async def test_qemu_create_with_project_file(app: FastAPI,
                                             client: AsyncClient,
                                             compute_project: Project,
                                             base_params: dict,
                                             fake_qemu_vm: str) -> None:

    response = await client.post(app.url_path_for("compute:write_compute_project_file",
                                                  project_id=compute_project.id,
                                                  file_path="hello.img"), content=b"world")
    assert response.status_code == status.HTTP_204_NO_CONTENT
    params = base_params
    params["hda_disk_image"] = "hello.img"
    response = await client.post(app.url_path_for("compute:create_qemu_node", project_id=compute_project.id), json=params)
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["hda_disk_image"] == "hello.img"
    assert response.json()["hda_disk_image_md5sum"] == "7d793037a0760186574b0282f2f435e7"


async def test_qemu_get(app: FastAPI, client: AsyncClient, compute_project: Project, vm: dict):

    response = await client.get(app.url_path_for("compute:get_qemu_node", project_id=vm["project_id"], node_id=vm["node_id"]))
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["name"] == "PC TEST 1"
    assert response.json()["project_id"] == compute_project.id
    assert response.json()["node_directory"] == os.path.join(compute_project.path,
                                                             "project-files",
                                                             "qemu",
                                                             vm["node_id"])


async def test_qemu_start(app: FastAPI, client: AsyncClient, vm: dict) -> None:

    with asyncio_patch("gns3server.compute.qemu.qemu_vm.QemuVM.start", return_value=True) as mock:
        response = await client.post(app.url_path_for("compute:start_qemu_node",
                                                      project_id=vm["project_id"],
                                                      node_id=vm["node_id"]))
        assert mock.called
        assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_qemu_stop(app: FastAPI, client: AsyncClient, vm: dict) -> None:

    with asyncio_patch("gns3server.compute.qemu.qemu_vm.QemuVM.stop", return_value=True) as mock:
        response = await client.post(app.url_path_for("compute:stop_qemu_node",
                                                      project_id=vm["project_id"],
                                                      node_id=vm["node_id"]))
        assert mock.called
        assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_qemu_reload(app: FastAPI, client: AsyncClient, vm) -> None:

    with asyncio_patch("gns3server.compute.qemu.qemu_vm.QemuVM.reload", return_value=True) as mock:
        response = await client.post(app.url_path_for("compute:reload_qemu_node",
                                                      project_id=vm["project_id"],
                                                      node_id=vm["node_id"]))
        assert mock.called
        assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_qemu_suspend(app: FastAPI, client: AsyncClient, vm: dict) -> None:

    with asyncio_patch("gns3server.compute.qemu.qemu_vm.QemuVM.suspend", return_value=True) as mock:
        response = await client.post(app.url_path_for("compute:suspend_qemu_node",
                                                      project_id=vm["project_id"],
                                                      node_id=vm["node_id"]))
        assert mock.called
        assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_qemu_resume(app: FastAPI, client: AsyncClient, vm: dict) -> None:

    with asyncio_patch("gns3server.compute.qemu.qemu_vm.QemuVM.resume", return_value=True) as mock:
        response = await client.post(app.url_path_for("compute:resume_qemu_node",
                                                      project_id=vm["project_id"],
                                                      node_id=vm["node_id"]))
        assert mock.called
        assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_qemu_delete(app: FastAPI, client: AsyncClient, vm: dict) -> None:

    with asyncio_patch("gns3server.compute.qemu.Qemu.delete_node", return_value=True) as mock:
        response = await client.delete(app.url_path_for("compute:delete_qemu_node",
                                                        project_id=vm["project_id"],
                                                        node_id=vm["node_id"]))
        assert mock.called
        assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_qemu_update(app: FastAPI,
                           client: AsyncClient,
                           vm: dict,
                           free_console_port: int,
                           fake_qemu_vm: str) -> None:

    params = {
        "name": "test",
        "console": free_console_port,
        "ram": 1024,
        "hdb_disk_image": "linux载.img"
    }

    response = await client.put(app.url_path_for("compute:update_qemu_node",
                                                 project_id=vm["project_id"],
                                                 node_id=vm["node_id"]), json=params)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["name"] == "test"
    assert response.json()["console"] == free_console_port
    assert response.json()["hdb_disk_image"] == "linux载.img"
    assert response.json()["ram"] == 1024


async def test_qemu_nio_create_udp(app: FastAPI, client: AsyncClient, vm: dict) -> None:

    params = {
        "type": "nio_udp",
        "lport": 4242,
        "rport": 4343,
        "rhost": "127.0.0.1"
    }

    with asyncio_patch("gns3server.compute.qemu.qemu_vm.QemuVM.add_ubridge_udp_connection"):
        await client.put(app.url_path_for("compute:update_qemu_node",
                                                 project_id=vm["project_id"],
                                                 node_id=vm["node_id"]), json={"adapters": 2})

        url = app.url_path_for("compute:create_qemu_node_nio",
                               project_id=vm["project_id"],
                               node_id=vm["node_id"],
                               adapter_number="1",
                               port_number="0")
        response = await client.post(url, json=params)
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["type"] == "nio_udp"


async def test_qemu_nio_update_udp(app: FastAPI, client: AsyncClient, vm: dict) -> None:

    params = {
        "type": "nio_udp",
        "lport": 4242,
        "rport": 4343,
        "rhost": "127.0.0.1"
    }

    await client.put(app.url_path_for("compute:update_qemu_node",
                                      project_id=vm["project_id"],
                                      node_id=vm["node_id"]), json={"adapters": 2})

    url = app.url_path_for("compute:create_qemu_node_nio",
                           project_id=vm["project_id"],
                           node_id=vm["node_id"],
                           adapter_number="1",
                           port_number="0")

    await client.post(url, json=params)

    params["filters"] = {}

    url = app.url_path_for("compute:update_qemu_node_nio",
                           project_id=vm["project_id"],
                           node_id=vm["node_id"],
                           adapter_number="1",
                           port_number="0")
    response = await client.put(url, json=params)
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["type"] == "nio_udp"


async def test_qemu_delete_nio(app: FastAPI, client: AsyncClient, vm: dict) -> None:

    params = {
        "type": "nio_udp",
        "lport": 4242,
        "rport": 4343,
        "rhost": "127.0.0.1"
    }

    with asyncio_patch("gns3server.compute.qemu.qemu_vm.QemuVM._ubridge_send"):
        await client.put(app.url_path_for("compute:update_qemu_node",
                                                 project_id=vm["project_id"],
                                                 node_id=vm["node_id"]), json={"adapters": 2})

        url = app.url_path_for("compute:create_qemu_node_nio",
                               project_id=vm["project_id"],
                               node_id=vm["node_id"],
                               adapter_number="1",
                               port_number="0")
        await client.post(url, json=params)

        url = app.url_path_for("compute:delete_qemu_node_nio",
                               project_id=vm["project_id"],
                               node_id=vm["node_id"],
                               adapter_number="1",
                               port_number="0")
        response = await client.delete(url)
    assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_qemu_list_binaries(app: FastAPI, client: AsyncClient, vm: dict) -> None:

    ret = [{"path": "/tmp/1", "version": "2.2.0"},
           {"path": "/tmp/2", "version": "2.1.0"}]

    with asyncio_patch("gns3server.compute.qemu.Qemu.binary_list", return_value=ret) as mock:
        response = await client.get(app.url_path_for("compute:get_qemu_binaries"))
        assert mock.called_with(None)
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == ret


# async def test_qemu_list_binaries_filter(app: FastAPI, client: AsyncClient, vm: dict) -> None:
#
#     ret = [
#         {"path": "/tmp/x86_64", "version": "2.2.0"},
#         {"path": "/tmp/alpha", "version": "2.1.0"},
#         {"path": "/tmp/i386", "version": "2.1.0"}
#     ]
#
#     with asyncio_patch("gns3server.compute.qemu.Qemu.binary_list", return_value=ret) as mock:
#         response = await client.get(app.url_path_for("compute:get_qemu_binaries"),
#                                     json={"archs": ["i386"]})
#         assert response.status_code == status.HTTP_200_OK
#         assert mock.called_with(["i386"])
#         assert response.json() == ret


async def test_images(app: FastAPI, client: AsyncClient, fake_qemu_vm) -> None:

    response = await client.get(app.url_path_for("compute:get_qemu_images"))
    assert response.status_code == status.HTTP_200_OK
    assert {"filename": "linux载.img", "path": "linux载.img", "md5sum": "c4ca4238a0b923820dcc509a6f75849b", "filesize": 1} in response.json()


async def test_upload_image(app: FastAPI, client: AsyncClient, tmpdir: str) -> None:

    with patch("gns3server.compute.Qemu.get_images_directory", return_value=str(tmpdir)):

        response = await client.post(app.url_path_for("compute:upload_qemu_image",
                                                      filename="test2使"), content=b"TEST")
        assert response.status_code == status.HTTP_204_NO_CONTENT

    with open(str(tmpdir / "test2使")) as f:
        assert f.read() == "TEST"

    with open(str(tmpdir / "test2使.md5sum")) as f:
        checksum = f.read()
        assert checksum == "033bd94b1168d7e4f0d644c3c95e35bf"


async def test_upload_image_ova(app: FastAPI, client: AsyncClient, tmpdir:str) -> None:

    with patch("gns3server.compute.Qemu.get_images_directory", return_value=str(tmpdir)):

        response = await client.post(app.url_path_for("compute:upload_qemu_image",
                                                      filename="test2.ova/test2.vmdk"), content=b"TEST")
        assert response.status_code == status.HTTP_204_NO_CONTENT

    with open(str(tmpdir / "test2.ova" / "test2.vmdk")) as f:
        assert f.read() == "TEST"

    with open(str(tmpdir / "test2.ova" / "test2.vmdk.md5sum")) as f:
        checksum = f.read()
        assert checksum == "033bd94b1168d7e4f0d644c3c95e35bf"


async def test_upload_image_forbidden_location(app: FastAPI, client: AsyncClient, tmpdir: str) -> None:

    response = await client.post(app.url_path_for("compute:upload_qemu_image",
                                                  filename="/qemu/images/../../test2"), content=b"TEST")
    assert response.status_code == status.HTTP_403_FORBIDDEN


async def test_download_image(app: FastAPI, client: AsyncClient, images_dir: str) -> None:

    response = await client.post(app.url_path_for("compute:upload_qemu_image", filename="test3"), content=b"TEST")
    assert response.status_code == status.HTTP_204_NO_CONTENT

    response = await client.get(app.url_path_for("compute:download_qemu_image", filename="test3"))
    assert response.status_code == status.HTTP_200_OK


async def test_download_image_forbidden_location(app: FastAPI, client: AsyncClient, tmpdir) -> None:

    file_path = "foo/%2e%2e/%2e%2e/%2e%2e/%2e%2e/%2e%2e/%2e%2e/etc/passwd"
    response = await client.get(app.url_path_for("compute:download_qemu_image", filename=file_path))
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.skipif(not sys.platform.startswith("win") and os.getuid() == 0, reason="Root can delete any image")
async def test_upload_image_permission_denied(app: FastAPI, client: AsyncClient, images_dir: str) -> None:

    with open(os.path.join(images_dir, "QEMU", "test2.tmp"), "w+") as f:
        f.write("")
    os.chmod(os.path.join(images_dir, "QEMU", "test2.tmp"), 0)

    response = await client.post(app.url_path_for("compute:upload_qemu_image", filename="test2"), content=b"TEST")
    assert response.status_code == status.HTTP_409_CONFLICT


@pytest.mark.asyncio
async def test_create_img_relative(app: FastAPI, client: AsyncClient):

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
        response = await client.post(app.url_path_for("compute:create_qemu_image"), json=params)
    assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_create_img_absolute_non_local(app: FastAPI, client: AsyncClient, config) -> None:

    config.settings.Server.local = False
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
        response = await client.post(app.url_path_for("compute:create_qemu_image"), json=params)
    assert response.status_code == 403


async def test_create_img_absolute_local(app: FastAPI, client: AsyncClient, config) -> None:

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
        response = await client.post(app.url_path_for("compute:create_qemu_image"), json=params)
    assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_capabilities(app: FastAPI, client: AsyncClient) -> None:

    with asyncio_patch("gns3server.compute.Qemu.get_kvm_archs", return_value=["x86_64"]):
        response = await client.get(app.url_path_for("compute:get_qemu_capabilities"))
        assert response.json()["kvm"] == ["x86_64"]


async def test_qemu_duplicate(app: FastAPI,
                              client: AsyncClient,
                              compute_project: Project,
                              vm: dict,
                              base_params: dict) -> None:

    # create destination node first
    response = await client.post(app.url_path_for("compute:create_qemu_node",
                                                  project_id=vm["project_id"]), json=base_params)

    assert response.status_code == status.HTTP_201_CREATED
    params = {"destination_node_id": response.json()["node_id"]}
    response = await client.post(app.url_path_for("compute:duplicate_qemu_node",
                                                  project_id=vm["project_id"], node_id=vm["node_id"]), json=params)
    assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.asyncio
async def test_qemu_start_capture(app: FastAPI, client: AsyncClient, vm):

    params = {
        "capture_file_name": "test.pcap",
        "data_link_type": "DLT_EN10MB"
    }

    url = app.url_path_for("compute:start_qemu_node_capture",
                           project_id=vm["project_id"],
                           node_id=vm["node_id"],
                           adapter_number="0",
                           port_number="0")

    with patch("gns3server.compute.qemu.qemu_vm.QemuVM.is_running", return_value=True):
        with asyncio_patch("gns3server.compute.qemu.qemu_vm.QemuVM.start_capture") as mock:
            response = await client.post(url, json=params)
            assert response.status_code == status.HTTP_200_OK
            assert mock.called
            assert "test.pcap" in response.json()["pcap_file_path"]


@pytest.mark.asyncio
async def test_qemu_stop_capture(app: FastAPI, client: AsyncClient, vm):

    url = app.url_path_for("compute:stop_qemu_node_capture",
                           project_id=vm["project_id"],
                           node_id=vm["node_id"],
                           adapter_number="0",
                           port_number="0")

    with patch("gns3server.compute.qemu.qemu_vm.QemuVM.is_running", return_value=True):
        with asyncio_patch("gns3server.compute.qemu.qemu_vm.QemuVM.stop_capture") as mock:
            response = await client.post(url)
            assert response.status_code == status.HTTP_204_NO_CONTENT
            assert mock.called


# @pytest.mark.asyncio
# async def test_qemu_pcap(app: FastAPI, client: AsyncClient, vm, compute_project):
#
#     with asyncio_patch("gns3server.compute.qemu.qemu_vm.QemuVM.get_nio"):
#         with asyncio_patch("gns3server.compute.qemu.Qemu.stream_pcap_file"):
#             response = await client.get("/projects/{project_id}/qemu/nodes/{node_id}/adapters/0/ports/0/pcap".format(project_id=compute_project.id, node_id=vm["node_id"]), raw=True)
#             assert response.status_code == status.HTTP_200_OK
