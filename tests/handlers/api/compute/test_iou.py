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
import stat
import sys
import uuid

from tests.utils import asyncio_patch
from unittest.mock import patch

pytestmark = pytest.mark.skipif(sys.platform.startswith("win"), reason="Not supported on Windows")


@pytest.fixture
def fake_iou_bin(images_dir):
    """Create a fake IOU image on disk"""

    path = os.path.join(images_dir, "IOU", "iou.bin")
    with open(path, "w+") as f:
        f.write('\x7fELF\x01\x01\x01')
    os.chmod(path, stat.S_IREAD | stat.S_IEXEC)
    return path


@pytest.fixture
def base_params(tmpdir, fake_iou_bin):
    """Return standard parameters"""

    return {"application_id": 42, "name": "PC TEST 1", "path": "iou.bin"}


@pytest.fixture
async def vm(compute_api, compute_project, base_params):

    response = await compute_api.post("/projects/{project_id}/iou/nodes".format(project_id=compute_project.id), base_params)
    assert response.status == 201
    return response.json


def startup_config_file(compute_project, vm):

    directory = os.path.join(compute_project.path, "project-files", "iou", vm["node_id"])
    os.makedirs(directory, exist_ok=True)
    return os.path.join(directory, "startup-config.cfg")


async def test_iou_create(compute_api, compute_project, base_params):

    response = await compute_api.post("/projects/{project_id}/iou/nodes".format(project_id=compute_project.id), base_params)
    assert response.status == 201
    assert response.route == "/projects/{project_id}/iou/nodes"
    assert response.json["name"] == "PC TEST 1"
    assert response.json["project_id"] == compute_project.id
    assert response.json["serial_adapters"] == 2
    assert response.json["ethernet_adapters"] == 2
    assert response.json["ram"] == 256
    assert response.json["nvram"] == 128
    assert response.json["l1_keepalives"] is False


async def test_iou_create_with_params(compute_api, compute_project, base_params):

    params = base_params
    params["ram"] = 1024
    params["nvram"] = 512
    params["serial_adapters"] = 4
    params["ethernet_adapters"] = 0
    params["l1_keepalives"] = True
    params["startup_config_content"] = "hostname test"
    params["use_default_iou_values"] = False

    response = await compute_api.post("/projects/{project_id}/iou/nodes".format(project_id=compute_project.id), params)
    assert response.status == 201
    assert response.route == "/projects/{project_id}/iou/nodes"
    assert response.json["name"] == "PC TEST 1"
    assert response.json["project_id"] == compute_project.id
    assert response.json["serial_adapters"] == 4
    assert response.json["ethernet_adapters"] == 0
    assert response.json["ram"] == 1024
    assert response.json["nvram"] == 512
    assert response.json["l1_keepalives"] is True
    assert response.json["use_default_iou_values"] is False

    with open(startup_config_file(compute_project, response.json)) as f:
        assert f.read() == "hostname test"


async def test_iou_create_startup_config_already_exist(compute_api, compute_project, base_params):
    """We don't erase a startup-config if already exist at project creation"""

    node_id = str(uuid.uuid4())
    startup_config_file_path = startup_config_file(compute_project, {'node_id': node_id})
    with open(startup_config_file_path, 'w+') as f:
        f.write("echo hello")

    params = base_params
    params["node_id"] = node_id
    params["startup_config_content"] = "hostname test"

    response = await compute_api.post("/projects/{project_id}/iou/nodes".format(project_id=compute_project.id), params)
    assert response.status == 201
    assert response.route == "/projects/{project_id}/iou/nodes"

    with open(startup_config_file(compute_project, response.json)) as f:
        assert f.read() == "echo hello"


async def test_iou_get(compute_api, compute_project, vm):

    response = await compute_api.get("/projects/{project_id}/iou/nodes/{node_id}".format(project_id=vm["project_id"], node_id=vm["node_id"]))
    assert response.status == 200
    assert response.route == "/projects/{project_id}/iou/nodes/{node_id}"
    assert response.json["name"] == "PC TEST 1"
    assert response.json["project_id"] == compute_project.id
    assert response.json["serial_adapters"] == 2
    assert response.json["ethernet_adapters"] == 2
    assert response.json["ram"] == 256
    assert response.json["nvram"] == 128
    assert response.json["l1_keepalives"] is False


async def test_iou_start(compute_api, vm):

    with asyncio_patch("gns3server.compute.iou.iou_vm.IOUVM.start", return_value=True) as mock:
        response = await compute_api.post("/projects/{project_id}/iou/nodes/{node_id}/start".format(project_id=vm["project_id"], node_id=vm["node_id"]))
        assert mock.called
        assert response.status == 200
        assert response.json["name"] == "PC TEST 1"


async def test_iou_start_with_iourc(compute_api, vm):

    params = {"iourc_content": "test"}
    with asyncio_patch("gns3server.compute.iou.iou_vm.IOUVM.start", return_value=True) as mock:
        response = await compute_api.post("/projects/{project_id}/iou/nodes/{node_id}/start".format(project_id=vm["project_id"], node_id=vm["node_id"]), params)
        assert mock.called
        assert response.status == 200

    response = await compute_api.get("/projects/{project_id}/iou/nodes/{node_id}".format(project_id=vm["project_id"], node_id=vm["node_id"]))
    assert response.status == 200


async def test_iou_stop(compute_api, vm):

    with asyncio_patch("gns3server.compute.iou.iou_vm.IOUVM.stop", return_value=True) as mock:
        response = await compute_api.post("/projects/{project_id}/iou/nodes/{node_id}/stop".format(project_id=vm["project_id"], node_id=vm["node_id"]))
        assert mock.called
        assert response.status == 204


async def test_iou_reload(compute_api, vm):

    with asyncio_patch("gns3server.compute.iou.iou_vm.IOUVM.reload", return_value=True) as mock:
        response = await compute_api.post("/projects/{project_id}/iou/nodes/{node_id}/reload".format(project_id=vm["project_id"], node_id=vm["node_id"]))
        assert mock.called
        assert response.status == 204


async def test_iou_delete(compute_api, vm):

    with asyncio_patch("gns3server.compute.iou.IOU.delete_node", return_value=True) as mock:
        response = await compute_api.delete("/projects/{project_id}/iou/nodes/{node_id}".format(project_id=vm["project_id"], node_id=vm["node_id"]))
        assert mock.called
        assert response.status == 204


async def test_iou_update(compute_api, vm, free_console_port):

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

    response = await compute_api.put("/projects/{project_id}/iou/nodes/{node_id}".format(project_id=vm["project_id"], node_id=vm["node_id"]), params)
    assert response.status == 200
    assert response.json["name"] == "test"
    assert response.json["console"] == free_console_port
    assert response.json["ethernet_adapters"] == 4
    assert response.json["serial_adapters"] == 0
    assert response.json["ram"] == 512
    assert response.json["nvram"] == 2048
    assert response.json["l1_keepalives"] is True
    assert response.json["use_default_iou_values"] is True


async def test_iou_nio_create_udp(compute_api, vm):

    params = {"type": "nio_udp",
              "lport": 4242,
              "rport": 4343,
              "rhost": "127.0.0.1"}

    response = await compute_api.post("/projects/{project_id}/iou/nodes/{node_id}/adapters/1/ports/0/nio".format(project_id=vm["project_id"], node_id=vm["node_id"]), params)
    assert response.status == 201
    assert response.route == r"/projects/{project_id}/iou/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio"
    assert response.json["type"] == "nio_udp"


async def test_iou_nio_update_udp(compute_api, vm):

    params = {"type": "nio_udp",
              "lport": 4242,
              "rport": 4343,
              "rhost": "127.0.0.1"}

    await compute_api.post("/projects/{project_id}/iou/nodes/{node_id}/adapters/1/ports/0/nio".format(project_id=vm["project_id"], node_id=vm["node_id"]), params)

    params["filters"] = {}
    response = await compute_api.put("/projects/{project_id}/iou/nodes/{node_id}/adapters/1/ports/0/nio".format(project_id=vm["project_id"], node_id=vm["node_id"]), params)
    assert response.status == 201, response.body.decode()
    assert response.route == r"/projects/{project_id}/iou/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio"
    assert response.json["type"] == "nio_udp"


async def test_iou_nio_create_ethernet(compute_api, vm, ethernet_device):

    params = {
        "type": "nio_ethernet",
        "ethernet_device": ethernet_device
    }

    response = await compute_api.post("/projects/{project_id}/iou/nodes/{node_id}/adapters/1/ports/0/nio".format(project_id=vm["project_id"], node_id=vm["node_id"]), params)
    assert response.status == 201
    assert response.route == r"/projects/{project_id}/iou/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio"
    assert response.json["type"] == "nio_ethernet"
    assert response.json["ethernet_device"] == ethernet_device


async def test_iou_nio_create_ethernet_different_port(compute_api, vm, ethernet_device):

    params = {
        "type": "nio_ethernet",
        "ethernet_device": ethernet_device
    }

    response = await compute_api.post("/projects/{project_id}/iou/nodes/{node_id}/adapters/0/ports/3/nio".format(project_id=vm["project_id"], node_id=vm["node_id"]), params)
    assert response.status == 201
    assert response.route == r"/projects/{project_id}/iou/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio"
    assert response.json["type"] == "nio_ethernet"
    assert response.json["ethernet_device"] == ethernet_device


async def test_iou_nio_create_tap(compute_api, vm, ethernet_device):

    params = {
        "type": "nio_tap",
        "tap_device": ethernet_device
    }

    with patch("gns3server.compute.base_manager.BaseManager.has_privileged_access", return_value=True):
        response = await compute_api.post("/projects/{project_id}/iou/nodes/{node_id}/adapters/1/ports/0/nio".format(project_id=vm["project_id"], node_id=vm["node_id"]), params)
        assert response.status == 201
        assert response.route == r"/projects/{project_id}/iou/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio"
        assert response.json["type"] == "nio_tap"


async def test_iou_delete_nio(compute_api, vm):

    params = {
        "type": "nio_udp",
        "lport": 4242,
        "rport": 4343,
        "rhost": "127.0.0.1"
    }

    await compute_api.post("/projects/{project_id}/iou/nodes/{node_id}/adapters/1/ports/0/nio".format(project_id=vm["project_id"], node_id=vm["node_id"]), params)
    response = await compute_api.delete("/projects/{project_id}/iou/nodes/{node_id}/adapters/1/ports/0/nio".format(project_id=vm["project_id"], node_id=vm["node_id"]))
    assert response.status == 204
    assert response.route == r"/projects/{project_id}/iou/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio"


async def test_iou_start_capture(compute_api, vm):

    params = {
        "capture_file_name": "test.pcap",
        "data_link_type": "DLT_EN10MB"
    }
    with patch("gns3server.compute.iou.iou_vm.IOUVM.is_running", return_value=True):
        with asyncio_patch("gns3server.compute.iou.iou_vm.IOUVM.start_capture") as mock:
            response = await compute_api.post("/projects/{project_id}/iou/nodes/{node_id}/adapters/0/ports/0/start_capture".format(project_id=vm["project_id"], node_id=vm["node_id"]), params)
            assert response.status == 200
            assert mock.called
            assert "test.pcap" in response.json["pcap_file_path"]


async def test_iou_stop_capture(compute_api, vm):

    with patch("gns3server.compute.iou.iou_vm.IOUVM.is_running", return_value=True):
        with asyncio_patch("gns3server.compute.iou.iou_vm.IOUVM.stop_capture") as mock:
            response = await compute_api.post("/projects/{project_id}/iou/nodes/{node_id}/adapters/0/ports/0/stop_capture".format(project_id=vm["project_id"], node_id=vm["node_id"]))
            assert response.status == 204
            assert mock.called


async def test_iou_pcap(compute_api, vm, compute_project):

    with asyncio_patch("gns3server.compute.iou.iou_vm.IOUVM.get_nio"):
        with asyncio_patch("gns3server.compute.iou.IOU.stream_pcap_file"):
            response = await compute_api.get("/projects/{project_id}/iou/nodes/{node_id}/adapters/0/ports/0/pcap".format(project_id=compute_project.id, node_id=vm["node_id"]), raw=True)
            assert response.status == 200


async def test_images(compute_api, fake_iou_bin):

    response = await compute_api.get("/iou/images")
    assert response.status == 200
    assert response.json == [{"filename": "iou.bin", "path": "iou.bin", "filesize": 7, "md5sum": "e573e8f5c93c6c00783f20c7a170aa6c"}]


async def test_image_vm(compute_api, tmpdir):

    with patch("gns3server.compute.IOU.get_images_directory", return_value=str(tmpdir)):
        response = await compute_api.post("/iou/images/test2", body="TEST", raw=True)
        assert response.status == 204

    with open(str(tmpdir / "test2")) as f:
        assert f.read() == "TEST"

    with open(str(tmpdir / "test2.md5sum")) as f:
        checksum = f.read()
        assert checksum == "033bd94b1168d7e4f0d644c3c95e35bf"


async def test_iou_duplicate(compute_api, vm):

    params = {"destination_node_id": str(uuid.uuid4())}
    with asyncio_patch("gns3server.compute.iou.IOU.duplicate_node", return_value=True) as mock:
        response = await compute_api.post("/projects/{project_id}/iou/nodes/{node_id}/duplicate".format(project_id=vm["project_id"], node_id=vm["node_id"]), params)
        assert mock.called
        assert response.status == 201
