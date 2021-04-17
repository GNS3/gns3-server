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

import shutil
import pytest
import uuid
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


def test_vmname(compute, project):
    """
    Additionnal properties should be add to the properties
    field
    """

    node = Node(project, compute, "PC",
                node_id=str(uuid.uuid4()),
                node_type="virtualbox",
                vmname="test")
    assert node.properties["vmname"] == "test"


def test_empty_properties(compute, project):
    """
    Empty properties need to be ignored
    """
    node = Node(project, compute, "PC",
                node_id=str(uuid.uuid4()),
                node_type="virtualbox",
                aa="",
                bb=None,
                category=2,
                cc="xx")
    assert "aa" not in node.properties
    assert "bb" not in node.properties
    assert "cc" in node.properties
    assert "category" not in node.properties  # Controller only


@pytest.mark.asyncio
async def test_eq(compute, project, node, controller):

    assert node == Node(project, compute, "demo1", node_id=node.id, node_type="qemu")
    assert node != "a"
    assert node != Node(project, compute, "demo2", node_id=str(uuid.uuid4()), node_type="qemu")
    assert node != Node(Project(str(uuid.uuid4()), controller=controller), compute, "demo3", node_id=node.id, node_type="qemu")


def test_json(node, compute):

    assert node.asdict() == {
        "compute_id": str(compute.id),
        "project_id": node.project.id,
        "node_id": node.id,
        "template_id": None,
        "node_type": node.node_type,
        "name": "demo",
        "console": node.console,
        "console_type": node.console_type,
        "console_host": str(compute.console_host),
        "aux": node.aux,
        "aux_type": node.aux_type,
        "command_line": None,
        "node_directory": None,
        "properties": node.properties,
        "status": node.status,
        "x": node.x,
        "y": node.y,
        "z": node.z,
        "locked": node.locked,
        "width": node.width,
        "height": node.height,
        "symbol": node.symbol,
        "label": node.label,
        "port_name_format": "Ethernet{0}",
        "port_segment_size": 0,
        "first_port_name": None,
        "custom_adapters": [],
        "console_auto_start": False,
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

    assert node.asdict(topology_dump=True) == {
        "compute_id": str(compute.id),
        "node_id": node.id,
        "template_id": None,
        "node_type": node.node_type,
        "name": "demo",
        "console": node.console,
        "console_type": node.console_type,
        "aux": node.aux,
        "aux_type": node.aux_type,
        "properties": node.properties,
        "x": node.x,
        "y": node.y,
        "z": node.z,
        "locked": node.locked,
        "width": node.width,
        "height": node.height,
        "symbol": node.symbol,
        "label": node.label,
        "port_name_format": "Ethernet{0}",
        "port_segment_size": 0,
        "first_port_name": None,
        "custom_adapters": [],
        "console_auto_start": False,
    }


def test_init_without_uuid(project, compute):
    node = Node(project, compute, "demo",
                node_type="vpcs",
                console_type="vnc")
    assert node.id is not None


@pytest.mark.asyncio
async def test_create(node, compute):

    node._console = 2048
    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    assert await node.create() is True
    data = {
        "console": 2048,
        "console_type": "vnc",
        "node_id": node.id,
        "startup_script": "echo test",
        "name": "demo"
    }
    compute.post.assert_called_with("/projects/{}/vpcs/nodes".format(node.project.id), data=data, timeout=1200)
    assert node._console == 2048
    assert node._properties == {"startup_script": "echo test"}


@pytest.mark.asyncio
async def test_create_image_missing(node, compute):

    node._console = 2048
    node.__calls = 0

    async def resp(*args, **kwargs):
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

    assert await node.create() is True
    #assert node._upload_missing_image.called is True


@pytest.mark.asyncio
async def test_create_base_script(node, config, compute, tmpdir):

    config.settings.Server.configs_path = str(tmpdir)
    with open(str(tmpdir / 'test.txt'), 'w+') as f:
        f.write('hostname test')

    node._properties = {"base_script_file": "test.txt"}
    node._console = 2048

    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    assert await node.create() is True
    data = {
        "console": 2048,
        "console_type": "vnc",
        "node_id": node.id,
        "startup_script": "hostname test",
        "name": "demo"
    }

    compute.post.assert_called_with("/projects/{}/vpcs/nodes".format(node.project.id), data=data, timeout=1200)


def test_symbol(node, symbols_dir):
    """
    Change symbol should change the node size
    """

    node.symbol = ":/symbols/classic/dslam.svg"
    assert node.symbol == ":/symbols/classic/dslam.svg"
    assert node.width == 50
    assert node.height == 53
    assert node.label["x"] is None
    assert node.label["y"] == -40

    node.symbol = ":/symbols/classic/cloud.svg"
    assert node.symbol == ":/symbols/classic/cloud.svg"
    assert node.width == 159
    assert node.height == 71
    assert node.label["x"] is None
    assert node.label["y"] == -40
    assert node.label["style"] == None#"font-family: TypeWriter;font-size: 10.0;font-weight: bold;fill: #000000;fill-opacity: 1.0;"

    shutil.copy(os.path.join("gns3server", "symbols", "classic", "cloud.svg"), os.path.join(symbols_dir, "cloud2.svg"))
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
    assert node.label["style"] == None #"font-family: TypeWriter;font-size: 10;font-weight: bold;fill: #ff0000;fill-opacity: 1.0;"


@pytest.mark.asyncio
async def test_update(node, compute, project, controller):

    response = MagicMock()
    response.json = {"console": 2048}
    compute.put = AsyncioMagicMock(return_value=response)
    controller._notification = AsyncioMagicMock()
    project.dump = MagicMock()

    await node.update(x=42, console=2048, console_type="vnc", properties={"startup_script": "echo test"}, name="demo")
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
    #controller._notification.emit.assert_called_with("node.updated", node.asdict())
    assert project.dump.called


@pytest.mark.asyncio
async def test_update_properties(node, compute, controller):
    """
    properties will be updated by the answer from compute
    """
    response = MagicMock()
    response.json = {"console": 2048}
    compute.put = AsyncioMagicMock(return_value=response)
    controller._notification = AsyncioMagicMock()

    await node.update(x=42, console=2048, console_type="vnc", properties={"startup_script": "hello world"}, name="demo")
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
    #node_notif = copy.deepcopy(node.asdict())
    #node_notif["properties"]["startup_script"] = "echo test"
    #controller._notification.emit.assert_called_with("node.updated", node_notif)


@pytest.mark.asyncio
async def test_update_only_controller(node, compute):
    """
    When updating property used only on controller we don't need to
    call the compute
    """

    compute.put = AsyncioMagicMock()
    node._project.emit_notification = AsyncioMagicMock()

    await node.update(x=42)
    assert not compute.put.called
    assert node.x == 42
    node._project.emit_notification.assert_called_with("node.updated", node.asdict())

    # If nothing change a second notif should not be sent
    node._project.emit_notification = AsyncioMagicMock()
    await node.update(x=42)
    assert not node._project.emit_notification.called


@pytest.mark.asyncio
async def test_update_no_changes(node, compute):
    """
    We don't call the compute node if all compute properties has not changed
    """
    response = MagicMock()
    response.json = {"console": 2048}
    compute.put = AsyncioMagicMock(return_value=response)

    await node.update(console=2048, x=42)
    assert compute.put.called

    compute.put = AsyncioMagicMock()
    await node.update(console=2048, x=43)
    assert not compute.put.called
    assert node.x == 43


@pytest.mark.asyncio
async def test_start(node, compute):

    compute.post = AsyncioMagicMock()

    await node.start()
    compute.post.assert_called_with("/projects/{}/vpcs/nodes/{}/start".format(node.project.id, node.id), timeout=240)


@pytest.mark.asyncio
async def test_start_iou(compute, project, controller):

    node = Node(project, compute, "demo",
                node_id=str(uuid.uuid4()),
                node_type="iou")
    compute.post = AsyncioMagicMock()

    # Without licence configured it should raise an error
    #with pytest.raises(aiohttp.web.HTTPConflict):
    #    async_run(node.start())

    controller._iou_license_settings = {"license_check": True, "iourc_content": "aa"}
    await node.start()
    compute.post.assert_called_with("/projects/{}/iou/nodes/{}/start".format(node.project.id, node.id), timeout=240, data={"license_check": True, "iourc_content": "aa"})


@pytest.mark.asyncio
async def test_stop(node, compute):

    compute.post = AsyncioMagicMock()

    await node.stop()
    compute.post.assert_called_with("/projects/{}/vpcs/nodes/{}/stop".format(node.project.id, node.id), timeout=240, dont_connect=True)


@pytest.mark.asyncio
async def test_suspend(node, compute):

    compute.post = AsyncioMagicMock()
    await node.suspend()
    compute.post.assert_called_with("/projects/{}/vpcs/nodes/{}/suspend".format(node.project.id, node.id), timeout=240)


@pytest.mark.asyncio
async def test_reload(node, compute):

    compute.post = AsyncioMagicMock()
    await node.reload()
    compute.post.assert_called_with("/projects/{}/vpcs/nodes/{}/reload".format(node.project.id, node.id), timeout=240)


@pytest.mark.asyncio
async def test_create_without_console(node, compute):
    """
    None properties should be send. Because it can mean the emulator doesn't support it
    """

    response = MagicMock()
    response.json = {"console": 2048, "test_value": "success"}
    compute.post = AsyncioMagicMock(return_value=response)

    await node.create()
    data = {
        "console_type": "vnc",
        "node_id": node.id,
        "startup_script": "echo test",
        "name": "demo"
    }
    compute.post.assert_called_with("/projects/{}/vpcs/nodes".format(node.project.id), data=data, timeout=1200)
    assert node._console == 2048
    assert node._properties == {"test_value": "success", "startup_script": "echo test"}


@pytest.mark.asyncio
async def test_delete(node, compute):

    await node.destroy()
    compute.delete.assert_called_with("/projects/{}/vpcs/nodes/{}".format(node.project.id, node.id))


@pytest.mark.asyncio
async def test_post(node, compute):

    await node.post("/test", {"a": "b"})
    compute.post.assert_called_with("/projects/{}/vpcs/nodes/{}/test".format(node.project.id, node.id), data={"a": "b"})


@pytest.mark.asyncio
async def test_delete(node, compute):

    await node.delete("/test")
    compute.delete.assert_called_with("/projects/{}/vpcs/nodes/{}/test".format(node.project.id, node.id))


@pytest.mark.asyncio
async def test_dynamips_idle_pc(node, compute):

    node._node_type = "dynamips"
    response = MagicMock()
    response.json = {"idlepc": "0x60606f54"}
    compute.get = AsyncioMagicMock(return_value=response)
    await node.dynamips_auto_idlepc()
    compute.get.assert_called_with("/projects/{}/dynamips/nodes/{}/auto_idlepc".format(node.project.id, node.id), timeout=240)


@pytest.mark.asyncio
async def test_dynamips_idlepc_proposals(node, compute):

    node._node_type = "dynamips"
    response = MagicMock()
    response.json = ["0x60606f54", "0x30ff6f37"]
    compute.get = AsyncioMagicMock(return_value=response)
    await node.dynamips_idlepc_proposals()
    compute.get.assert_called_with("/projects/{}/dynamips/nodes/{}/idlepc_proposals".format(node.project.id, node.id), timeout=240)


@pytest.mark.asyncio
async def test_upload_missing_image(compute, controller, images_dir):

    project = Project(str(uuid.uuid4()), controller=controller)
    node = Node(project, compute, "demo",
                node_id=str(uuid.uuid4()),
                node_type="qemu",
                properties={"hda_disk_image": "linux.img"})
    open(os.path.join(images_dir, "linux.img"), 'w+').close()
    assert await node._upload_missing_image("qemu", "linux.img") is True
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
    port = node.get_port(42, 0)
    assert port is None


@pytest.mark.asyncio
async def test_parse_node_response(node):
    """
    When a node is updated we notify the links connected to it
    """

    link = MagicMock()
    link.node_updated = AsyncioMagicMock()
    node.add_link(link)
    await node.parse_node_response({"status": "started"})
    assert link.node_updated.called
