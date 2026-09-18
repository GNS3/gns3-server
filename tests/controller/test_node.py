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
from tests.utils import AsyncioMagicMock, asyncio_patch
from gns3server.compute.docker.docker_error import DockerError

from gns3server.controller.node import Node
from gns3server.controller.project import Project
from gns3server.controller.controller_error import ComputeConflictError, ControllerError


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


def test_docker_iol_ports_grouped_in_four_port_units(compute, project):
    """
    IOL docker nodes (GNS3_IOL_RUNNER) model adapters as 4-port units: ports
    are Ethernet0/0-3, Ethernet1/0-3, … addressed (adapter, port 0-3), like
    the native IOU node type. Plain docker nodes keep the flat eth naming.
    """

    node = Node(project, compute, "iol",
                node_id=str(uuid.uuid4()),
                node_type="docker",
                properties={"adapters": 2, "environment": "GNS3_IOL_RUNNER=1"})
    ports = node.ports
    assert [p.asdict()["name"] for p in ports] == [
        "Ethernet0/0", "Ethernet0/1", "Ethernet0/2", "Ethernet0/3",
        "Ethernet1/0", "Ethernet1/1", "Ethernet1/2", "Ethernet1/3",
    ]
    assert (ports[5].adapter_number, ports[5].port_number) == (1, 1)
    assert ports[5].short_name == "e1/1"

    node = Node(project, compute, "web",
                node_id=str(uuid.uuid4()),
                node_type="docker",
                properties={"adapters": 2})
    assert [p.asdict()["name"] for p in node.ports] == ["eth0", "eth1"]


def test_docker_iol_startup_config_materialized_once(compute, project, monkeypatch):
    """
    The GNS3_IOL_STARTUP_CONFIG environment knob references a config file in
    the controller's configs directory: like the IOU startup_config mapping,
    its content is sent to the compute exactly once (the knob is consumed) —
    afterwards the node's configuration lives in its NVRAM on the compute.
    """

    node = Node(project, compute, "iol",
                node_id=str(uuid.uuid4()),
                node_type="docker",
                properties={"environment": "GNS3_IOL_RUNNER=1\nGNS3_IOL_STARTUP_CONFIG=my-iol-config.txt"})
    monkeypatch.setattr(node, "_base_config_file_content", lambda path: "hostname %h\n")

    data = node._node_data()
    assert data["startup_config_content"] == "hostname %h\n"
    assert data["environment"] == "GNS3_IOL_RUNNER=1"
    assert "GNS3_IOL_STARTUP_CONFIG" not in node.properties["environment"]

    # sent only once: a later sync (e.g. project reload) carries neither
    data = node._node_data()
    assert "startup_config_content" not in data


def test_docker_iol_startup_config_missing_file_keeps_knob(compute, project, monkeypatch):

    node = Node(project, compute, "iol",
                node_id=str(uuid.uuid4()),
                node_type="docker",
                properties={"environment": "GNS3_IOL_RUNNER=1\nGNS3_IOL_STARTUP_CONFIG=gone.txt"})
    monkeypatch.setattr(node, "_base_config_file_content", lambda path: None)

    data = node._node_data()
    assert "startup_config_content" not in data
    # the knob is kept so the config still applies once the file shows up
    assert "GNS3_IOL_STARTUP_CONFIG" in node.properties["environment"]


def test_extract_iol_startup_config_knob_variants():

    from gns3server.controller.node import _extract_iol_startup_config_knob

    assert _extract_iol_startup_config_knob(None) == (None, None)
    assert _extract_iol_startup_config_knob("GNS3_IOL_RUNNER=1") == (None, "GNS3_IOL_RUNNER=1")
    # whitespace and trailing commas are tolerated, like the compute env parsing
    filename, environment = _extract_iol_startup_config_knob("GNS3_IOL_RUNNER=1,\n GNS3_IOL_STARTUP_CONFIG=cfg.txt ,")
    assert filename == "cfg.txt"
    assert environment == "GNS3_IOL_RUNNER=1,"
    # an empty value is treated as absent
    filename, environment = _extract_iol_startup_config_knob("GNS3_IOL_STARTUP_CONFIG=")
    assert filename is None


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
        "tags": [],
        "custom_adapters": [],
        "console_auto_start": False,
        "netmiko_device_type": None,
        "default_username": None,
        "default_password": None,
        "ports": [
            {
                "adapter_number": 0,
                "data_link_types": {"Ethernet": "DLT_EN10MB"},
                "link_type": "ethernet",
                "name": "Ethernet0",
                "port_number": 0,
                "short_name": "e0"
            }
        ],
        "missing_image": False,
        "missing_images": []
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
        "tags": [],
        "console_auto_start": False,
        "netmiko_device_type": None,
        "default_username": None,
        "default_password": None,
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
async def test_create_image_missing_kept_in_degraded_state(project, compute, tmpdir, config):
    """
    With allow_missing_image=True a node whose image cannot be provided is kept
    on the controller and flagged instead of aborting the whole project open.
    """

    config.settings.Server.images_path = str(tmpdir)
    node = Node(project, compute, "r1",
                node_id=str(uuid.uuid4()),
                node_type="qemu",
                properties={"hda_disk_image": "missing.qcow2", "ram": 256})

    async def resp(*args, **kwargs):
        raise ComputeConflictError(
            "/projects/{}/qemu/nodes".format(project.id),
            {"message": "The image is missing", "image": "missing.qcow2", "exception": "ImageMissingError"}
        )

    compute.post = AsyncioMagicMock(side_effect=resp)
    node._upload_missing_image = AsyncioMagicMock(return_value=False)

    assert await node.create(allow_missing_image=True) is False
    assert node.missing_image is True
    assert node.missing_images == [
        {"property": "hda_disk_image", "image": "missing.qcow2", "image_type": "qemu"}
    ]


@pytest.mark.asyncio
async def test_create_image_missing_raises_by_default(project, compute, tmpdir, config):
    """
    Without allow_missing_image the historical behaviour is preserved: the
    ImageMissingError is re-raised.
    """

    config.settings.Server.images_path = str(tmpdir)
    node = Node(project, compute, "r1",
                node_id=str(uuid.uuid4()),
                node_type="qemu",
                properties={"hda_disk_image": "missing.qcow2", "ram": 256})

    async def resp(*args, **kwargs):
        raise ComputeConflictError(
            "/projects/{}/qemu/nodes".format(project.id),
            {"message": "The image is missing", "image": "missing.qcow2", "exception": "ImageMissingError"}
        )

    compute.post = AsyncioMagicMock(side_effect=resp)
    node._upload_missing_image = AsyncioMagicMock(return_value=False)

    with pytest.raises(ComputeConflictError):
        await node.create()
    assert node.missing_image is False


@pytest.mark.asyncio
async def test_create_image_missing_raises_after_upload_retries(project, compute):
    node = Node(
        project,
        compute,
        "r1",
        node_id=str(uuid.uuid4()),
        node_type="qemu",
        properties={"hda_disk_image": "missing.qcow2", "ram": 256},
    )

    async def resp(*args, **kwargs):
        raise ComputeConflictError(
            f"/projects/{project.id}/qemu/nodes",
            {"message": "missing", "image": "missing.qcow2", "exception": "ImageMissingError"},
        )

    compute.post = AsyncioMagicMock(side_effect=resp)
    node._upload_missing_image = AsyncioMagicMock(return_value=True)

    with pytest.raises(ComputeConflictError):
        await node.create()
    assert compute.post.call_count == 6
    assert node.missing_image is False


@pytest.mark.asyncio
async def test_create_image_missing_without_image_name_is_not_degraded(project, compute):
    """A malformed conflict must not leave a controller-only node marked healthy."""

    node = Node(
        project,
        compute,
        "r1",
        node_id=str(uuid.uuid4()),
        node_type="qemu",
        properties={"hda_disk_image": "present.qcow2", "ram": 256},
    )

    async def resp(*args, **kwargs):
        raise ComputeConflictError(
            f"/projects/{project.id}/qemu/nodes",
            {"message": "The image is missing", "exception": "ImageMissingError"},
        )

    compute.post = AsyncioMagicMock(side_effect=resp)
    node._image_available = MagicMock(return_value=True)

    with pytest.raises(ComputeConflictError):
        await node.create(allow_missing_image=True)
    assert node.missing_image is False


def test_compute_missing_images_matches_reported_basename_to_property(project, compute):
    node = Node(
        project,
        compute,
        "r1",
        node_id=str(uuid.uuid4()),
        node_type="qemu",
        properties={
            "hda_disk_image": "/images/qemu/disk.qcow2",
            "cdrom_image": "/images/qemu/installer.iso",
            "ram": 256,
        },
    )
    node._image_available = MagicMock(return_value=True)

    assert node._compute_missing_images("installer.iso") == [
        {"property": "cdrom_image", "image": "installer.iso", "image_type": "qemu"}
    ]


def test_compute_missing_images_deduplicates_path_and_reported_basename(project, compute):
    node = Node(
        project,
        compute,
        "r1",
        node_id=str(uuid.uuid4()),
        node_type="qemu",
        properties={"cdrom_image": "/images/qemu/installer.iso", "ram": 256},
    )
    node._image_available = MagicMock(return_value=False)

    assert node._compute_missing_images("installer.iso") == [
        {
            "property": "cdrom_image",
            "image": "/images/qemu/installer.iso",
            "image_type": "qemu",
        }
    ]


@pytest.mark.asyncio
async def test_create_docker_image_missing_after_failed_pull(project, compute):
    """
    A Docker image that cannot be pulled from the registry keeps the node in a
    degraded state instead of aborting the project open.
    """

    node = Node(project, compute, "web",
                node_id=str(uuid.uuid4()),
                node_type="docker",
                properties={"image": "ghost:latest", "adapters": 1})

    async def resp(*args, **kwargs):
        raise ComputeConflictError(
            "/projects/{}/docker/nodes".format(project.id),
            {"message": "The image is missing", "image": "ghost:latest", "exception": "ImageMissingError"}
        )

    compute.post = AsyncioMagicMock(side_effect=resp)
    node._upload_missing_image = AsyncioMagicMock(
        side_effect=ControllerError("Failed to pull Docker image 'ghost:latest'")
    )

    assert await node.create(allow_missing_image=True) is False
    assert node.missing_image is True
    assert node.missing_images == [
        {"property": "image", "image": "ghost:latest", "image_type": "docker"}
    ]


@pytest.mark.asyncio
async def test_create_docker_image_missing_pull_error_raises_by_default(project, compute):
    """
    Without allow_missing_image a failed Docker pull is still surfaced.
    """

    node = Node(project, compute, "web",
                node_id=str(uuid.uuid4()),
                node_type="docker",
                properties={"image": "ghost:latest", "adapters": 1})

    async def resp(*args, **kwargs):
        raise ComputeConflictError(
            "/projects/{}/docker/nodes".format(project.id),
            {"message": "The image is missing", "image": "ghost:latest", "exception": "ImageMissingError"}
        )

    compute.post = AsyncioMagicMock(side_effect=resp)
    node._upload_missing_image = AsyncioMagicMock(
        side_effect=ControllerError("Failed to pull Docker image 'ghost:latest'")
    )

    with pytest.raises(ControllerError):
        await node.create()


def test_compute_missing_images_lists_all_unavailable_slots(project, compute, tmpdir, config):
    """
    All the image slots of a multi-image node are reported, not only the first
    one the compute complained about.
    """

    config.settings.Server.images_path = str(tmpdir)
    node = Node(project, compute, "r1",
                node_id=str(uuid.uuid4()),
                node_type="qemu",
                properties={
                    "hda_disk_image": "present.qcow2",
                    "hdc_disk_image": "missing.qcow2",
                    "initrd": "missing.initrd",
                    "ram": 256,
                })
    # make one image available on the controller
    os.makedirs(os.path.join(str(tmpdir), "QEMU"), exist_ok=True)
    with open(os.path.join(str(tmpdir), "QEMU", "present.qcow2"), "w") as f:
        f.write("x")

    missing = node._compute_missing_images()
    assert {m["property"] for m in missing} == {"hdc_disk_image", "initrd"}
    assert all(m["image_type"] == "qemu" for m in missing)


@pytest.mark.asyncio
async def test_start_missing_image(node):

    node._missing_images = [
        {"property": "hda_disk_image", "image": "missing.qcow2", "image_type": "qemu"}
    ]
    with pytest.raises(ControllerError):
        await node.start()


@pytest.mark.asyncio
async def test_update_recreates_missing_image_node(project, compute, node):
    """
    Updating the image of a degraded node creates it on the compute and clears
    the missing image state.
    """

    node._missing_images = [
        {"property": "image", "image": "missing.image", "image_type": "ios"}
    ]
    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)
    project.restore_deferred_links = AsyncioMagicMock()

    await node.update(properties={"image": "available.image"})
    assert node.missing_image is False
    assert node.missing_images == []
    assert project.restore_deferred_links.called is True


@pytest.mark.asyncio
async def test_update_replaces_qemu_linked_clone_backing_image(project, compute):
    """Stale linked-clone metadata must not override a replacement image."""

    qemu_node = Node(
        project,
        compute,
        "old-qemu",
        node_id=str(uuid.uuid4()),
        node_type="qemu",
        properties={
            "hda_disk_image": "hda_disk.qcow2",
            "hda_disk_image_backing_file": "missing.qcow2",
            "hda_disk_image_md5sum": "old-checksum",
        },
    )
    qemu_node._missing_images = [
        {"property": "hda_disk_image", "image": "missing.qcow2", "image_type": "qemu"}
    ]
    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)
    project.restore_deferred_links = AsyncioMagicMock()

    await qemu_node.update(
        properties={
            **qemu_node.properties,
            "hda_disk_image": "replacement.qcow2",
        }
    )

    request_data = compute.post.call_args.kwargs["data"]
    assert request_data["hda_disk_image"] == "replacement.qcow2"
    assert request_data["disk_images_to_reset"] == ["hda_disk_image"]
    assert "hda_disk_image_backing_file" not in request_data
    assert "hda_disk_image_md5sum" not in request_data
    assert qemu_node.missing_image is False


@pytest.mark.asyncio
async def test_update_missing_image_node_rolls_back_after_create_error(project, compute, node):
    original_properties = {"image": "missing.image"}
    node._properties = original_properties.copy()
    node._missing_images = [
        {"property": "image", "image": "missing.image", "image_type": "ios"}
    ]
    compute.post = AsyncioMagicMock(side_effect=ControllerError("create failed"))

    with pytest.raises(ControllerError):
        await node.update(properties={"image": "invalid.image"})

    assert node.properties == original_properties
    assert node.missing_images == [
        {"property": "image", "image": "missing.image", "image_type": "ios"}
    ]


@pytest.mark.asyncio
async def test_start_retries_ready_deferred_links(node, project):
    peer = MagicMock()
    peer.missing_image = False
    link = MagicMock()
    link.deferred = True
    link._nodes = [{"node": node}, {"node": peer}]
    node._links.add(link)
    project.restore_deferred_links = AsyncioMagicMock()

    with pytest.raises(ControllerError, match="deferred link"):
        await node.start()

    project.restore_deferred_links.assert_called_once_with(node)


@pytest.mark.asyncio
async def test_stop_missing_image_node_does_not_contact_compute(node, compute):
    node._missing_images = [
        {"property": "image", "image": "missing.image", "image_type": "ios"}
    ]
    compute.post = AsyncioMagicMock()

    await node.stop()

    compute.post.assert_not_called()


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
async def test_update_netmiko_device_type(node, compute):
    """
    netmiko_device_type is a controller-only property: updating it must not
    call the compute and must be visible in the node json.
    """

    compute.put = AsyncioMagicMock()
    node._project.emit_notification = AsyncioMagicMock()
    node._project.dump = MagicMock()

    await node.update(netmiko_device_type="cisco_ios_telnet")
    assert not compute.put.called
    assert node.netmiko_device_type == "cisco_ios_telnet"
    assert node.asdict()["netmiko_device_type"] == "cisco_ios_telnet"

    # the field can also be cleared with an empty string
    await node.update(netmiko_device_type="")
    assert node.netmiko_device_type == ""
    assert node.asdict()["netmiko_device_type"] == ""


def test_netmiko_device_type_from_template_kwargs(compute, project):
    """
    A node created with the template properties as kwargs inherits
    netmiko_device_type without sending it to the compute.
    """

    node = Node(project, compute, "test", node_type="vpcs", netmiko_device_type="nokia_srl")
    assert node.netmiko_device_type == "nokia_srl"
    # controller-only: must not leak into the compute properties
    assert "netmiko_device_type" not in node.properties
    assert node.asdict(topology_dump=True)["netmiko_device_type"] == "nokia_srl"


@pytest.mark.asyncio
async def test_update_default_credentials(node, compute):
    """
    default_username/default_password are controller-only properties: updating
    them must not call the compute and must be persisted in the node json.
    """

    compute.put = AsyncioMagicMock()
    node._project.emit_notification = AsyncioMagicMock()
    node._project.dump = MagicMock()

    await node.update(default_username="admin", default_password="secret")
    assert not compute.put.called
    assert node.default_username == "admin"
    assert node.default_password == "secret"
    assert node.asdict()["default_username"] == "admin"
    assert node.asdict(topology_dump=True)["default_password"] == "secret"

    # credentials never leak into the compute properties
    assert "default_username" not in node.properties
    assert "default_password" not in node.properties

    # both fields can be cleared with an empty string
    await node.update(default_username="", default_password="")
    assert node.default_username == ""
    assert node.default_password == ""


def test_default_credentials_from_template_kwargs(compute, project):
    """
    A node created from a template with appliance metadata inherits the
    default credentials without sending them to the compute.
    """

    node = Node(project, compute, "test", node_type="vpcs",
                default_username="root", default_password="cisco123")
    assert node.default_username == "root"
    assert node.default_password == "cisco123"
    assert "default_username" not in node.properties
    assert "default_password" not in node.properties
    assert node.asdict(topology_dump=True)["default_username"] == "root"


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


@pytest.mark.asyncio
async def test_upload_missing_image_from_nested_directory(compute, controller, images_dir):

    project = Project(str(uuid.uuid4()), controller=controller)
    node = Node(project, compute, "demo",
                node_id=str(uuid.uuid4()),
                node_type="qemu",
                properties={"hda_disk_image": "nested.img"})
    nested_dir = os.path.join(images_dir, "vendor")
    os.makedirs(nested_dir)
    open(os.path.join(nested_dir, "nested.img"), "w+").close()

    assert await node._upload_missing_image("qemu", "nested.img") is True
    compute.post.assert_called_with("/qemu/images/nested.img", data=ANY, timeout=None)


@pytest.mark.asyncio
async def test_sync_missing_docker_image_from_controller_daemon(compute, controller):

    project = Project(str(uuid.uuid4()), controller=controller)
    node = Node(project, compute, "demo",
                node_id=str(uuid.uuid4()),
                node_type="docker",
                properties={"image": "gns3/frr:latest"})

    response = MagicMock()
    response.content = MagicMock()
    with asyncio_patch("gns3server.compute.docker.Docker.http_query", return_value=response) as save_mock:
        assert await node._upload_missing_image("docker", "gns3/frr:latest") is True
        save_mock.assert_called_with("GET", "images/gns3/frr:latest/get", timeout=None)
    compute.post.assert_called_with("/docker/images/load", data=response.content, timeout=None)
    response.close.assert_called_once_with()


@pytest.mark.asyncio
async def test_sync_missing_docker_image_pull_fallback(compute, controller):

    project = Project(str(uuid.uuid4()), controller=controller)
    node = Node(project, compute, "demo",
                node_id=str(uuid.uuid4()),
                node_type="docker",
                properties={"image": "nginx:latest"})

    with asyncio_patch("gns3server.compute.docker.Docker.http_query", side_effect=DockerError("404")):
        assert await node._upload_missing_image("docker", "nginx:latest") is True
    compute.post.assert_called_with("/docker/images/pull", data={"image": "nginx:latest"}, timeout=None)


@pytest.mark.asyncio
async def test_create_docker_node_pins_image_digest(compute, controller):

    project = Project(str(uuid.uuid4()), controller=controller)
    node = Node(project, compute, "demo",
                node_id=str(uuid.uuid4()),
                node_type="docker",
                properties={"image": "gns3/frr:latest", "adapters": 1})

    response = MagicMock()
    response.status = 200
    response.json = {}
    compute.post = AsyncioMagicMock(return_value=response)

    image_id = "sha256:" + "a" * 64
    with asyncio_patch("gns3server.compute.docker.Docker.query", return_value={"Id": image_id}):
        assert await node.create() is True
    # the image id from the controller host daemon is pinned into the create payload
    data = compute.post.call_args[1]["data"]
    assert data["image_digest"] == image_id


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
