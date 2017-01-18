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

import shutil
import aiohttp
import pytest
import uuid
import asyncio
import copy
import os
from unittest.mock import MagicMock, ANY


from tests.utils import AsyncioMagicMock

from gns3server.controller.node import Node
from gns3server.controller.project import Project


@pytest.fixture
def compute():
    s = AsyncioMagicMock()
    s.id = "http://test.com:42"
    return s


@pytest.fixture
def project(controller):
    return Project(str(uuid.uuid4()), controller=controller)


@pytest.fixture
def node(compute, project):
    node = Node(project, compute, "demo",
                node_id=str(uuid.uuid4()),
                node_type="vpcs",
                console_type="vnc",
                properties={"startup_script": "echo test"})
    return node


def test_name(compute, project):
    """
    If node use a name template generate names
    """
    node = Node(project, compute, "PC",
                node_id=str(uuid.uuid4()),
                node_type="vpcs",
                console_type="vnc",
                properties={"startup_script": "echo test"})
    assert node.name == "PC"
    node = Node(project, compute, "PC{0}",
                node_id=str(uuid.uuid4()),
                node_type="vpcs",
                console_type="vnc",
                properties={"startup_script": "echo test"})
    assert node.name == "PC1"
    node = Node(project, compute, "PC{0}",
                node_id=str(uuid.uuid4()),
                node_type="vpcs",
                console_type="vnc",
                properties={"startup_script": "echo test"})
    assert node.name == "PC2"

    # If we change the name to a name already used we patch the name to a free
    node.name == "PC1"
    assert node.name == "PC2"


def test_eq(compute, project, node, controller):
    assert node == Node(project, compute, "demo1", node_id=node.id, node_type="qemu")
    assert node != "a"
    assert node != Node(project, compute, "demo2", node_id=str(uuid.uuid4()), node_type="qemu")
    assert node != Node(Project(str(uuid.uuid4()), controller=controller), compute, "demo3", node_id=node.id, node_type="qemu")


def test_properties_filter(project, compute):
    """
    Some properties are private and should not be exposed
    """
    node = Node(project, compute, "demo",
                node_id=str(uuid.uuid4()),
                node_type="vpcs",
                console_type="vnc",
                properties={"startup_script": "echo test", "iourc_content": "test"})
    assert node._properties == {"startup_script": "echo test", "iourc_content": "test"}
    assert node._filter_properties() == {"startup_script": "echo test"}


def test_json(node, compute):
    assert node.__json__() == {
        "compute_id": str(compute.id),
        "project_id": node.project.id,
        "node_id": node.id,
        "node_type": node.node_type,
        "name": "demo",
        "console": node.console,
        "console_type": node.console_type,
        "console_host": str(compute.console_host),
        "command_line": None,
        "node_directory": None,
        "properties": node.properties,
        "status": node.status,
        "x": node.x,
        "y": node.y,
        "z": node.z,
        "width": node.width,
        "height": node.height,
        "symbol": node.symbol,
        "label": node.label,
        "port_name_format": "Ethernet{0}",
        "port_segment_size": 0,
        "first_port_name": None,
        "ports": [
            {
                "adapter_number": 0,
                "data_link_types": {"Ethernet": "DLT_EN10MB"},
                "link_type": "ethernet",
                "name": "Ethernet0",
                "port_number": 0,
                "short_name": "e0"
            }
        ]
    }
    assert node.__json__(topology_dump=True) == {
        "compute_id": str(compute.id),
        "node_id": node.id,
        "node_type": node.node_type,
        "name": "demo",
        "console": node.console,
        "console_type": node.console_type,
        "properties": node.properties,
        "x": node.x,
        "y": node.y,
        "z": node.z,
        "width": node.width,
        "height": node.height,
        "symbol": node.symbol,
        "label": node.label,
        "port_name_format": "Ethernet{0}",
        "port_segment_size": 0,
        "first_port_name": None
    }


def test_init_without_uuid(project, compute):
    node = Node(project, compute, "demo",
                node_type="vpcs",
                console_type="vnc")
    assert node.id is not None


def test_create(node, compute, project, async_run):
    node._console = 2048

    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    assert async_run(node.create()) is True
    data = {
        "console": 2048,
        "console_type": "vnc",
        "node_id": node.id,
        "startup_script": "echo test",
        "name": "demo"
    }
    compute.post.assert_called_with("/projects/{}/vpcs/nodes".format(node.project.id), data=data, timeout=120)
    assert node._console == 2048
    assert node._properties == {"startup_script": "echo test"}


def test_create_image_missing(node, compute, project, async_run):
    node._console = 2048

    node.__calls = 0

    @asyncio.coroutine
    def resp(*args, **kwargs):
        node.__calls += 1
        response = MagicMock()
        if node.__calls == 1:
            response.status = 409
            response.json = {"image": "linux.img", "exception": "ImageMissingError"}
        else:
            response.status = 200
        return response

    compute.post = AsyncioMagicMock(side_effect=resp)
    node._upload_missing_image = AsyncioMagicMock(return_value=True)

    assert async_run(node.create()) is True
    node._upload_missing_image.called is True


def test_symbol(node, symbols_dir):
    """
    Change symbol should change the node size
    """
    node.symbol = ":/symbols/dslam.svg"
    assert node.symbol == ":/symbols/dslam.svg"
    assert node.width == 50
    assert node.height == 53
    assert node.label["x"] is None
    assert node.label["y"] == -40

    node.symbol = ":/symbols/cloud.svg"
    assert node.symbol == ":/symbols/cloud.svg"
    assert node.width == 159
    assert node.height == 71
    assert node.label["x"] is None
    assert node.label["y"] == -40
    assert node.label["style"] == "font-size: 10;font-familly: Verdana"

    shutil.copy(os.path.join("gns3server", "symbols", "cloud.svg"), os.path.join(symbols_dir, "cloud2.svg"))
    node.symbol = "cloud2.svg"
    assert node.symbol == "cloud2.svg"
    assert node.width == 159
    assert node.height == 71

    # No abs path, fix them (bug of 1.5)
    node.symbol = "/tmp/cloud2.svg"
    assert node.symbol == "cloud2.svg"
    assert node.width == 159
    assert node.height == 71


def test_label_with_default_label_font(node):
    """
    If user has changed the font we need to have the node label using
    the correct color
    """
    node.project.controller.settings = {
        "GraphicsView": {
            "default_label_color": "#ff0000",
            "default_label_font": "TypeWriter,10,-1,5,75,0,0,0,0,0"
        }
    }

    node._label = None
    node.symbol = ":/symbols/dslam.svg"
    assert node.label["style"] == "font-family: TypeWriter;font-size: 10;font-weight: bold;fill: #ff0000;fill-opacity: 1.0;"


def test_update(node, compute, project, async_run, controller):
    response = MagicMock()
    response.json = {"console": 2048}
    compute.put = AsyncioMagicMock(return_value=response)
    controller._notification = AsyncioMagicMock()
    project.dump = MagicMock()

    async_run(node.update(x=42, console=2048, console_type="vnc", properties={"startup_script": "echo test"}, name="demo"))
    data = {
        "console": 2048,
        "console_type": "vnc",
        "startup_script": "echo test",
        "name": "demo"
    }
    compute.put.assert_called_with("/projects/{}/vpcs/nodes/{}".format(node.project.id, node.id), data=data)
    assert node._console == 2048
    assert node.x == 42
    assert node._properties == {"startup_script": "echo test"}
    controller._notification.emit.assert_called_with("node.updated", node.__json__())
    assert project.dump.called


def test_update_properties(node, compute, project, async_run, controller):
    """
    properties will be updated by the answer from compute
    """
    response = MagicMock()
    response.json = {"console": 2048}
    compute.put = AsyncioMagicMock(return_value=response)
    controller._notification = AsyncioMagicMock()

    async_run(node.update(x=42, console=2048, console_type="vnc", properties={"startup_script": "hello world"}, name="demo"))
    data = {
        "console": 2048,
        "console_type": "vnc",
        "startup_script": "hello world",
        "name": "demo"
    }
    compute.put.assert_called_with("/projects/{}/vpcs/nodes/{}".format(node.project.id, node.id), data=data)
    assert node._console == 2048
    assert node.x == 42
    assert node._properties == {"startup_script": "echo test"}

    # The notif should contain the old properties because it's the compute that will emit
    # the correct info
    node_notif = copy.deepcopy(node.__json__())
    node_notif["properties"]["startup_script"] = "echo test"
    controller._notification.emit.assert_called_with("node.updated", node_notif)


def test_update_only_controller(node, controller, compute, project, async_run):
    """
    When updating property used only on controller we don't need to
    call the compute
    """
    compute.put = AsyncioMagicMock()
    controller._notification = AsyncioMagicMock()

    async_run(node.update(x=42))
    assert not compute.put.called
    assert node.x == 42
    controller._notification.emit.assert_called_with("node.updated", node.__json__())

    # If nothing change a second notif should not be send
    controller._notification = AsyncioMagicMock()
    async_run(node.update(x=42))
    assert not controller._notification.emit.called


def test_update_no_changes(node, compute, project, async_run):
    """
    We don't call the compute node if all compute properties has not changed
    """
    response = MagicMock()
    response.json = {"console": 2048}
    compute.put = AsyncioMagicMock(return_value=response)

    async_run(node.update(console=2048, x=42))
    assert compute.put.called

    compute.put = AsyncioMagicMock()
    async_run(node.update(console=2048, x=43))
    assert not compute.put.called
    assert node.x == 43


def test_start(node, compute, project, async_run):

    compute.post = AsyncioMagicMock()

    async_run(node.start())
    compute.post.assert_called_with("/projects/{}/vpcs/nodes/{}/start".format(node.project.id, node.id), timeout=240)


def test_start_iou(compute, project, async_run, controller):
    node = Node(project, compute, "demo",
                node_id=str(uuid.uuid4()),
                node_type="iou")
    compute.post = AsyncioMagicMock()

    # Without licence configured it should raise an error
    with pytest.raises(aiohttp.web.HTTPConflict):
        async_run(node.start())

    controller.settings["IOU"] = {"iourc_content": "aa"}
    async_run(node.start())
    compute.post.assert_called_with("/projects/{}/iou/nodes/{}/start".format(node.project.id, node.id), timeout=240, data={"iourc_content": "aa"})


def test_stop(node, compute, project, async_run):

    compute.post = AsyncioMagicMock()

    async_run(node.stop())
    compute.post.assert_called_with("/projects/{}/vpcs/nodes/{}/stop".format(node.project.id, node.id), timeout=240, dont_connect=True)


def test_suspend(node, compute, project, async_run):

    compute.post = AsyncioMagicMock()

    async_run(node.suspend())
    compute.post.assert_called_with("/projects/{}/vpcs/nodes/{}/suspend".format(node.project.id, node.id), timeout=240)


def test_reload(node, compute, project, async_run):

    compute.post = AsyncioMagicMock()

    async_run(node.reload())
    compute.post.assert_called_with("/projects/{}/vpcs/nodes/{}/reload".format(node.project.id, node.id), timeout=240)


def test_create_without_console(node, compute, project, async_run):
    """
    None properties should be send. Because it can mean the emulator doesn"t support it
    """

    response = MagicMock()
    response.json = {"console": 2048, "test_value": "success"}
    compute.post = AsyncioMagicMock(return_value=response)

    async_run(node.create())
    data = {
        "console_type": "vnc",
        "node_id": node.id,
        "startup_script": "echo test",
        "name": "demo"
    }
    compute.post.assert_called_with("/projects/{}/vpcs/nodes".format(node.project.id), data=data, timeout=120)
    assert node._console == 2048
    assert node._properties == {"test_value": "success", "startup_script": "echo test"}


def test_delete(node, compute, async_run):
    async_run(node.destroy())
    compute.delete.assert_called_with("/projects/{}/vpcs/nodes/{}".format(node.project.id, node.id))


def test_post(node, compute, async_run):
    async_run(node.post("/test", {"a": "b"}))
    compute.post.assert_called_with("/projects/{}/vpcs/nodes/{}/test".format(node.project.id, node.id), data={"a": "b"})


def test_delete(node, compute, async_run):
    async_run(node.delete("/test"))
    compute.delete.assert_called_with("/projects/{}/vpcs/nodes/{}/test".format(node.project.id, node.id))


def test_dynamips_idle_pc(node, async_run, compute):
    node._node_type = "dynamips"
    response = MagicMock()
    response.json = {"idlepc": "0x60606f54"}
    compute.get = AsyncioMagicMock(return_value=response)

    async_run(node.dynamips_auto_idlepc())
    compute.get.assert_called_with("/projects/{}/dynamips/nodes/{}/auto_idlepc".format(node.project.id, node.id), timeout=240)


def test_dynamips_idlepc_proposals(node, async_run, compute):
    node._node_type = "dynamips"
    response = MagicMock()
    response.json = ["0x60606f54", "0x30ff6f37"]
    compute.get = AsyncioMagicMock(return_value=response)

    async_run(node.dynamips_idlepc_proposals())
    compute.get.assert_called_with("/projects/{}/dynamips/nodes/{}/idlepc_proposals".format(node.project.id, node.id), timeout=240)


def test_upload_missing_image(compute, controller, async_run, images_dir):
    project = Project(str(uuid.uuid4()), controller=controller)
    node = Node(project, compute, "demo",
                node_id=str(uuid.uuid4()),
                node_type="qemu",
                properties={"hda_disk_image": "linux.img"})
    open(os.path.join(images_dir, "linux.img"), 'w+').close()
    assert async_run(node._upload_missing_image("qemu", "linux.img")) is True
    compute.post.assert_called_with("/qemu/images/linux.img", data=ANY, timeout=None)


def test_update_label(node):
    """
    The text in label need to be always the
    node name
    """
    node.name = "Test"
    assert node.label["text"] == "Test"
    node.label = {"text": "Wrong", "x": 12}
    assert node.label["text"] == "Test"
    assert node.label["x"] == 12


def test_get_port(node):
    node._node_type = "qemu"
    node._properties["adapters"] = 2
    node._list_ports()
    port = node.get_port(0, 0)
    assert port.adapter_number == 0
    assert port.port_number == 0
    port = node.get_port(1, 0)
    assert port.adapter_number == 1
    with pytest.raises(aiohttp.web.HTTPNotFound):
        port = node.get_port(42, 0)


def test_parse_node_response(node, async_run):
    """
    When a node is updated we notify the links connected to it
    """
    link = MagicMock()
    link.node_updated = AsyncioMagicMock()
    node.add_link(link)
    async_run(node.parse_node_response({"status": "started"}))
    assert link.node_updated.called
