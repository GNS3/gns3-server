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
import pytest_asyncio
import os
import stat
import uuid

from fastapi import FastAPI, status
from httpx import AsyncClient
from tests.utils import asyncio_patch
from unittest.mock import patch

from gns3server.compute.project import Project

pytestmark = [pytest.mark.asyncio]


@pytest.fixture
def fake_iou_bin(images_dir) -> str:
    """Create a fake IOU image on disk"""

    path = os.path.join(images_dir, "IOU", "iou.bin")
    with open(path, "w+") as f:
        f.write('\x7fELF\x01\x01\x01')
    os.chmod(path, stat.S_IREAD | stat.S_IEXEC)
    return path


@pytest.fixture
def base_params(tmpdir, fake_iou_bin) -> dict:
    """Return standard parameters"""

    return {"application_id": 42, "name": "IOU-TEST-1", "path": "iou.bin"}


@pytest_asyncio.fixture
async def vm(app: FastAPI, compute_client: AsyncClient, compute_project: Project, base_params: dict) -> dict:

    response = await compute_client.post(app.url_path_for("compute:create_iou_node", project_id=compute_project.id), json=base_params)
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()


def startup_config_file(compute_project: Project, vm: dict) -> str:

    directory = os.path.join(compute_project.path, "project-files", "iou", vm["node_id"])
    os.makedirs(directory, exist_ok=True)
    return os.path.join(directory, "startup-config.cfg")


async def test_iou_create(app: FastAPI, compute_client: AsyncClient, compute_project: Project, base_params: dict) -> None:

    response = await compute_client.post(app.url_path_for("compute:create_iou_node", project_id=compute_project.id), json=base_params)
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["name"] == "IOU-TEST-1"
    assert response.json()["project_id"] == compute_project.id
    assert response.json()["serial_adapters"] == 2
    assert response.json()["ethernet_adapters"] == 2
    assert response.json()["ram"] == 256
    assert response.json()["nvram"] == 128
    assert response.json()["l1_keepalives"] is False


async def test_iou_create_with_params(app: FastAPI,
                                      compute_client: AsyncClient,
                                      compute_project: Project,
                                      base_params: dict) -> None:

    params = base_params
    params["ram"] = 1024
    params["nvram"] = 512
    params["serial_adapters"] = 4
    params["ethernet_adapters"] = 0
    params["l1_keepalives"] = True
    params["startup_config_content"] = "hostname test"
    params["use_default_iou_values"] = False

    response = await compute_client.post(app.url_path_for("compute:create_iou_node", project_id=compute_project.id), json=params)
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["name"] == "IOU-TEST-1"
    assert response.json()["project_id"] == compute_project.id
    assert response.json()["serial_adapters"] == 4
    assert response.json()["ethernet_adapters"] == 0
    assert response.json()["ram"] == 1024
    assert response.json()["nvram"] == 512
    assert response.json()["l1_keepalives"] is True
    assert response.json()["use_default_iou_values"] is False

    with open(startup_config_file(compute_project, response.json())) as f:
        assert f.read() == "hostname test"


@pytest.mark.parametrize(
    "name, status_code",
    (
        ("valid-name", status.HTTP_201_CREATED),
        ("42name", status.HTTP_409_CONFLICT),
        ("name42", status.HTTP_201_CREATED),
        ("-name", status.HTTP_409_CONFLICT),
        ("name%-test", status.HTTP_409_CONFLICT),
        ("x" * 63, status.HTTP_201_CREATED),
        ("x" * 64, status.HTTP_409_CONFLICT),
    ),
)
async def test_iou_create_with_invalid_name(
        app: FastAPI,
        compute_client: AsyncClient,
        compute_project: Project,
        base_params: dict,
        name: str,
        status_code: int
) -> None:

    base_params["name"] = name
    response = await compute_client.post(
        app.url_path_for("compute:create_iou_node", project_id=compute_project.id), json=base_params
    )
    assert response.status_code == status_code


async def test_iou_create_startup_config_already_exist(
        app: FastAPI,
        compute_client: AsyncClient,
        compute_project: Project,
        base_params: dict) -> None:
    """We don't erase a startup-config if already exist at project creation"""

    node_id = str(uuid.uuid4())
    startup_config_file_path = startup_config_file(compute_project, {'node_id': node_id})
    with open(startup_config_file_path, 'w+') as f:
        f.write("echo hello")

    params = base_params
    params["node_id"] = node_id
    params["startup_config_content"] = "hostname test"

    response = await compute_client.post(app.url_path_for("compute:create_iou_node", project_id=compute_project.id), json=params)
    assert response.status_code == status.HTTP_201_CREATED

    with open(startup_config_file(compute_project, response.json())) as f:
        assert f.read() == "echo hello"


async def test_iou_get(app: FastAPI, compute_client: AsyncClient, compute_project: Project, vm: dict) -> None:

    response = await compute_client.get(app.url_path_for("compute:get_iou_node", project_id=vm["project_id"], node_id=vm["node_id"]))
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["name"] == "IOU-TEST-1"
    assert response.json()["project_id"] == compute_project.id
    assert response.json()["serial_adapters"] == 2
    assert response.json()["ethernet_adapters"] == 2
    assert response.json()["ram"] == 256
    assert response.json()["nvram"] == 128
    assert response.json()["l1_keepalives"] is False


async def test_iou_start(app: FastAPI, compute_client: AsyncClient, vm: dict) -> None:

    with asyncio_patch("gns3server.compute.iou.iou_vm.IOUVM.start", return_value=True) as mock:
        response = await compute_client.post(app.url_path_for("compute:start_iou_node",
                                                      project_id=vm["project_id"],
                                                      node_id=vm["node_id"]), json={})
        assert mock.called
        assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_iou_start_with_iourc(app: FastAPI, compute_client: AsyncClient, vm: dict) -> None:

    params = {"iourc_content": "test"}
    with asyncio_patch("gns3server.compute.iou.iou_vm.IOUVM.start", return_value=True) as mock:
        response = await compute_client.post(app.url_path_for("compute:start_iou_node",
                                                      project_id=vm["project_id"],
                                                      node_id=vm["node_id"]), json=params)
        assert mock.called
        assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_iou_stop(app: FastAPI, compute_client: AsyncClient, vm: dict) -> None:

    with asyncio_patch("gns3server.compute.iou.iou_vm.IOUVM.stop", return_value=True) as mock:
        response = await compute_client.post(app.url_path_for("compute:stop_iou_node",
                                                      project_id=vm["project_id"],
                                                      node_id=vm["node_id"]))
        assert mock.called
        assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_iou_reload(app: FastAPI, compute_client: AsyncClient, vm: dict) -> None:

    with asyncio_patch("gns3server.compute.iou.iou_vm.IOUVM.reload", return_value=True) as mock:
        response = await compute_client.post(app.url_path_for("compute:reload_iou_node",
                                                      project_id=vm["project_id"],
                                                      node_id=vm["node_id"]))
        assert mock.called
        assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_iou_delete(app: FastAPI, compute_client: AsyncClient, vm: dict) -> None:

    with asyncio_patch("gns3server.compute.iou.IOU.delete_node", return_value=True) as mock:
        response = await compute_client.delete(app.url_path_for("compute:delete_iou_node",
                                                        project_id=vm["project_id"],
                                                        node_id=vm["node_id"]))
        assert mock.called
        assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_iou_update(app: FastAPI, compute_client: AsyncClient, vm: dict, free_console_port: int) -> None:

    params = {
        "name": "test",
        "console": free_console_port,
        "ram": 512,
        "nvram": 2048,
        "ethernet_adapters": 4,
        "serial_adapters": 0,
        "l1_keepalives": True,
        "use_default_iou_values": True,
    }

    response = await compute_client.put(app.url_path_for("compute:update_iou_node",
                                                 project_id=vm["project_id"],
                                                 node_id=vm["node_id"]), json=params)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["name"] == "test"
    assert response.json()["console"] == free_console_port
    assert response.json()["ethernet_adapters"] == 4
    assert response.json()["serial_adapters"] == 0
    assert response.json()["ram"] == 512
    assert response.json()["nvram"] == 2048
    assert response.json()["l1_keepalives"] is True
    assert response.json()["use_default_iou_values"] is True


async def test_iou_nio_create_udp(app: FastAPI, compute_client: AsyncClient, vm: dict) -> None:

    params = {"type": "nio_udp",
              "lport": 4242,
              "rport": 4343,
              "rhost": "127.0.0.1"}

    url = app.url_path_for("compute:create_iou_node_nio",
                           project_id=vm["project_id"],
                           node_id=vm["node_id"],
                           adapter_number="1",
                           port_number="0")
    response = await compute_client.post(url, json=params)
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["type"] == "nio_udp"


async def test_iou_nio_update_udp(app: FastAPI, compute_client: AsyncClient, vm: dict) -> None:

    params = {"type": "nio_udp",
              "lport": 4242,
              "rport": 4343,
              "rhost": "127.0.0.1"}

    url = app.url_path_for("compute:create_iou_node_nio",
                           project_id=vm["project_id"],
                           node_id=vm["node_id"],
                           adapter_number="1",
                           port_number="0")

    await compute_client.post(url, json=params)
    params["filters"] = {}

    url = app.url_path_for("compute:update_iou_node_nio",
                           project_id=vm["project_id"],
                           node_id=vm["node_id"],
                           adapter_number="1",
                           port_number="0")
    response = await compute_client.put(url, json=params)
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["type"] == "nio_udp"


async def test_iou_nio_create_ethernet(app: FastAPI, compute_client: AsyncClient, vm: dict, ethernet_device: str) -> None:

    params = {
        "type": "nio_ethernet",
        "ethernet_device": ethernet_device
    }

    url = app.url_path_for("compute:create_iou_node_nio",
                           project_id=vm["project_id"],
                           node_id=vm["node_id"],
                           adapter_number="1",
                           port_number="0")

    response = await compute_client.post(url, json=params)
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["type"] == "nio_ethernet"
    assert response.json()["ethernet_device"] == ethernet_device


async def test_iou_nio_create_ethernet_different_port(app: FastAPI,
                                                      compute_client: AsyncClient,
                                                      vm: dict,
                                                      ethernet_device: str) -> None:

    params = {
        "type": "nio_ethernet",
        "ethernet_device": ethernet_device
    }

    url = app.url_path_for("compute:create_iou_node_nio",
                           project_id=vm["project_id"],
                           node_id=vm["node_id"],
                           adapter_number="0",
                           port_number="3")
    response = await compute_client.post(url, json=params)
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["type"] == "nio_ethernet"
    assert response.json()["ethernet_device"] == ethernet_device


async def test_iou_nio_create_tap(app: FastAPI, compute_client: AsyncClient, vm: dict, ethernet_device: str) -> None:

    params = {
        "type": "nio_tap",
        "tap_device": ethernet_device
    }

    url = app.url_path_for("compute:create_iou_node_nio",
                           project_id=vm["project_id"],
                           node_id=vm["node_id"],
                           adapter_number="1",
                           port_number="0")
    with patch("gns3server.compute.base_manager.BaseManager.has_privileged_access", return_value=True):
        response = await compute_client.post(url, json=params)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["type"] == "nio_tap"


async def test_iou_delete_nio(app: FastAPI, compute_client: AsyncClient, vm: dict) -> None:

    params = {
        "type": "nio_udp",
        "lport": 4242,
        "rport": 4343,
        "rhost": "127.0.0.1"
    }

    url = app.url_path_for("compute:create_iou_node_nio",
                           project_id=vm["project_id"],
                           node_id=vm["node_id"],
                           adapter_number="1",
                           port_number="0")

    await compute_client.post(url, json=params)

    url = app.url_path_for("compute:delete_iou_node_nio",
                           project_id=vm["project_id"],
                           node_id=vm["node_id"],
                           adapter_number="1",
                           port_number="0")

    response = await compute_client.delete(url)
    assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_iou_start_capture(app: FastAPI, compute_client: AsyncClient, vm: dict) -> None:

    params = {
        "capture_file_name": "test.pcap",
        "data_link_type": "DLT_EN10MB"
    }

    url = app.url_path_for("compute:start_iou_node_capture",
                           project_id=vm["project_id"],
                           node_id=vm["node_id"],
                           adapter_number="0",
                           port_number="0")

    with patch("gns3server.compute.iou.iou_vm.IOUVM.is_running", return_value=True):
        with asyncio_patch("gns3server.compute.iou.iou_vm.IOUVM.start_capture") as mock:
            response = await compute_client.post(url, json=params)
            assert response.status_code == status.HTTP_200_OK
            assert mock.called
            assert "test.pcap" in response.json()["pcap_file_path"]


async def test_iou_stop_capture(app: FastAPI, compute_client: AsyncClient, vm: dict) -> None:

    url = app.url_path_for("compute:stop_iou_node_capture",
                           project_id=vm["project_id"],
                           node_id=vm["node_id"],
                           adapter_number="0",
                           port_number="0")

    with patch("gns3server.compute.iou.iou_vm.IOUVM.is_running", return_value=True):
        with asyncio_patch("gns3server.compute.iou.iou_vm.IOUVM.stop_capture") as mock:
            response = await compute_client.post(url)
            assert response.status_code == status.HTTP_204_NO_CONTENT
            assert mock.called


# @pytest.mark.asyncio
# async def test_iou_pcap(compute_api, vm, compute_project):
#
#     with asyncio_patch("gns3server.compute.iou.iou_vm.IOUVM.get_nio"):
#         with asyncio_patch("gns3server.compute.iou.IOU.stream_pcap_file"):
#             response = await compute_client.get("/projects/{project_id}/iou/nodes/{node_id}/adapters/0/ports/0/pcap".format(project_id=compute_project.id, node_id=vm["node_id"]), raw=True)
#             assert response.status_code == status.HTTP_200_OK


async def test_images(app: FastAPI, compute_client: AsyncClient, fake_iou_bin: str) -> None:

    response = await compute_client.get(app.url_path_for("compute:get_iou_images"))
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == [{"filename": "iou.bin", "path": "iou.bin", "filesize": 7, "md5sum": "e573e8f5c93c6c00783f20c7a170aa6c"}]


async def test_upload_image(app: FastAPI, compute_client: AsyncClient, tmpdir) -> None:

    with patch("gns3server.compute.IOU.get_images_directory", return_value=str(tmpdir)):
        response = await compute_client.post(app.url_path_for("compute:upload_iou_image", filename="test2"), content=b"TEST")
        assert response.status_code == status.HTTP_204_NO_CONTENT

    with open(str(tmpdir / "test2")) as f:
        assert f.read() == "TEST"

    with open(str(tmpdir / "test2.md5sum")) as f:
        checksum = f.read()
        assert checksum == "033bd94b1168d7e4f0d644c3c95e35bf"


async def test_upload_image_forbidden_location(app: FastAPI, compute_client: AsyncClient) -> None:

    file_path = "%2e%2e/hello"
    response = await compute_client.post(app.url_path_for("compute:upload_dynamips_image", filename=file_path), content=b"TEST")
    assert response.status_code == status.HTTP_403_FORBIDDEN


async def test_download_image(app: FastAPI, compute_client: AsyncClient, images_dir: str) -> None:

    response = await compute_client.post(app.url_path_for("compute:upload_dynamips_image", filename="test3"), content=b"TEST")
    assert response.status_code == status.HTTP_204_NO_CONTENT

    response = await compute_client.get(app.url_path_for("compute:download_dynamips_image", filename="test3"))
    assert response.status_code == status.HTTP_200_OK


async def test_download_image_forbidden(app: FastAPI, compute_client: AsyncClient, tmpdir) -> None:

    file_path = "foo/%2e%2e/%2e%2e/%2e%2e/%2e%2e/%2e%2e/%2e%2e/etc/passwd"
    response = await compute_client.get(app.url_path_for("compute:download_iou_image", filename=file_path))
    assert response.status_code == status.HTTP_403_FORBIDDEN


async def test_iou_duplicate(app: FastAPI, compute_client: AsyncClient, vm: dict, base_params: dict) -> None:

    # create destination node first
    response = await compute_client.post(app.url_path_for("compute:create_iou_node", project_id=vm["project_id"]), json=base_params)
    assert response.status_code == status.HTTP_201_CREATED

    params = {"destination_node_id": response.json()["node_id"]}

    response = await compute_client.post(app.url_path_for("compute:duplicate_iou_node",
                                                  project_id=vm["project_id"],
                                                  node_id=vm["node_id"]), json=params)
    assert response.status_code == status.HTTP_201_CREATED
