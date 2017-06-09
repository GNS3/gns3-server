#!/usr/bin/env python
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

import os
import sys
import uuid
import json
import pytest
import aiohttp
import zipfile
import zipstream
from unittest.mock import MagicMock
from tests.utils import AsyncioMagicMock, asyncio_patch
from unittest.mock import patch
from uuid import uuid4

from gns3server.controller.project import Project
from gns3server.controller.ports.ethernet_port import EthernetPort
from gns3server.config import Config


@pytest.fixture
def project(controller):
    return Project(controller=controller, name="Test")


@pytest.fixture
def node(controller, project, async_run):
    compute = MagicMock()
    compute.id = "local"

    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    node = async_run(project.add_node(compute, "test", None, node_type="vpcs", properties={"startup_config": "test.cfg"}))
    return node


def test_affect_uuid():
    p = Project(name="Test")
    assert len(p.id) == 36

    p = Project(project_id='00010203-0405-0607-0809-0a0b0c0d0e0f', name="Test 2")
    assert p.id == '00010203-0405-0607-0809-0a0b0c0d0e0f'


def test_json(tmpdir):
    p = Project(name="Test")
    assert p.__json__() == {
        "name": "Test",
        "project_id": p.id,
        "path": p.path,
        "status": "opened",
        "filename": "Test.gns3",
        "auto_start": False,
        "auto_close": True,
        "auto_open": False,
        "scene_width": 2000,
        "scene_height": 1000
    }


def test_update(controller, async_run):
    project = Project(controller=controller, name="Hello")
    controller._notification = MagicMock()

    assert project.name == "Hello"
    async_run(project.update(name="World"))
    assert project.name == "World"
    controller.notification.emit.assert_any_call("project.updated", project.__json__())


def test_path(tmpdir):

    directory = Config.instance().get_section_config("Server").get("projects_path")

    with patch("gns3server.utils.path.get_default_project_directory", return_value=directory):
        p = Project(project_id=str(uuid4()), name="Test")
        assert p.path == os.path.join(directory, p.id)
        assert os.path.exists(os.path.join(directory, p.id))


def test_path_exist(tmpdir):
    """
    Should raise an error when you try to owerwrite
    an existing project
    """
    os.makedirs(str(tmpdir / "demo"))
    with pytest.raises(aiohttp.web.HTTPForbidden):
        p = Project(name="Test", path=str(tmpdir / "demo"))


def test_init_path(tmpdir):

    p = Project(path=str(tmpdir), project_id=str(uuid4()), name="Test")
    assert p.path == str(tmpdir)


@pytest.mark.skipif(sys.platform.startswith("win"), reason="Not supported on Windows")
def test_changing_path_with_quote_not_allowed(tmpdir):
    with pytest.raises(aiohttp.web.HTTPForbidden):
        p = Project(project_id=str(uuid4()), name="Test")
        p.path = str(tmpdir / "project\"53")


def test_captures_directory(tmpdir):
    p = Project(path=str(tmpdir / "capturestest"), name="Test")
    assert p.captures_directory == str(tmpdir / "capturestest" / "project-files" / "captures")
    assert os.path.exists(p.captures_directory)


def test_add_node_local(async_run, controller):
    """
    For a local server we send the project path
    """
    compute = MagicMock()
    compute.id = "local"
    project = Project(controller=controller, name="Test")
    controller._notification = MagicMock()

    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    node = async_run(project.add_node(compute, "test", None, node_type="vpcs", properties={"startup_config": "test.cfg"}))
    assert node.id in project._nodes

    compute.post.assert_any_call('/projects', data={
        "name": project._name,
        "project_id": project._id,
        "path": project._path
    })
    compute.post.assert_any_call('/projects/{}/vpcs/nodes'.format(project.id),
                                 data={'node_id': node.id,
                                       'startup_config': 'test.cfg',
                                       'name': 'test'},
                                 timeout=120)
    assert compute in project._project_created_on_compute
    controller.notification.emit.assert_any_call("node.created", node.__json__())


def test_add_node_non_local(async_run, controller):
    """
    For a non local server we do not send the project path
    """
    compute = MagicMock()
    compute.id = "remote"
    project = Project(controller=controller, name="Test")
    controller._notification = MagicMock()

    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    node = async_run(project.add_node(compute, "test", None, node_type="vpcs", properties={"startup_config": "test.cfg"}))

    compute.post.assert_any_call('/projects', data={
        "name": project._name,
        "project_id": project._id
    })
    compute.post.assert_any_call('/projects/{}/vpcs/nodes'.format(project.id),
                                 data={'node_id': node.id,
                                       'startup_config': 'test.cfg',
                                       'name': 'test'},
                                 timeout=120)
    assert compute in project._project_created_on_compute
    controller.notification.emit.assert_any_call("node.created", node.__json__())


def test_create_iou_on_multiple_node(async_run, controller):
    """
    Due to mac address collision you can't create an IOU node
    on two different server
    """
    compute = MagicMock()
    compute.id = "remote"

    compute2 = MagicMock()
    compute2.id = "remote2"

    project = Project(controller=controller, name="Test")

    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    node1 = async_run(project.add_node(compute, "test", None, node_type="iou"))
    with pytest.raises(aiohttp.web_exceptions.HTTPConflict):
        async_run(project.add_node(compute2, "test2", None, node_type="iou"))


def test_delete_node(async_run, controller):
    """
    For a local server we send the project path
    """
    compute = MagicMock()
    project = Project(controller=controller, name="Test")
    controller._notification = MagicMock()

    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    node = async_run(project.add_node(compute, "test", None, node_type="vpcs", properties={"startup_config": "test.cfg"}))
    assert node.id in project._nodes
    async_run(project.delete_node(node.id))
    assert node.id not in project._nodes

    compute.delete.assert_any_call('/projects/{}/vpcs/nodes/{}'.format(project.id, node.id))
    controller.notification.emit.assert_any_call("node.deleted", node.__json__())


def test_delete_node_delete_link(async_run, controller):
    """
    Delete a node delete all the node connected
    """
    compute = MagicMock()
    project = Project(controller=controller, name="Test")
    controller._notification = MagicMock()

    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    node = async_run(project.add_node(compute, "test", None, node_type="vpcs", properties={"startup_config": "test.cfg"}))

    link = async_run(project.add_link())
    async_run(link.add_node(node, 0, 0))

    async_run(project.delete_node(node.id))
    assert node.id not in project._nodes
    assert link.id not in project._links

    compute.delete.assert_any_call('/projects/{}/vpcs/nodes/{}'.format(project.id, node.id))
    controller.notification.emit.assert_any_call("node.deleted", node.__json__())
    controller.notification.emit.assert_any_call("link.deleted", link.__json__())


def test_get_node(async_run, controller):
    compute = MagicMock()
    project = Project(controller=controller, name="Test")

    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    vm = async_run(project.add_node(compute, "test", None, node_type="vpcs", properties={"startup_config": "test.cfg"}))
    assert project.get_node(vm.id) == vm

    with pytest.raises(aiohttp.web_exceptions.HTTPNotFound):
        project.get_node("test")

    # Raise an error if the project is not opened
    async_run(project.close())
    with pytest.raises(aiohttp.web.HTTPForbidden):
        project.get_node(vm.id)


def test_addLink(async_run, project, controller):
    compute = MagicMock()

    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    vm1 = async_run(project.add_node(compute, "test1", None, node_type="vpcs", properties={"startup_config": "test.cfg"}))
    vm1._ports = [EthernetPort("E0", 0, 3, 1)]
    vm2 = async_run(project.add_node(compute, "test2", None, node_type="vpcs", properties={"startup_config": "test.cfg"}))
    vm2._ports = [EthernetPort("E0", 0, 4, 2)]
    controller._notification = MagicMock()
    link = async_run(project.add_link())
    async_run(link.add_node(vm1, 3, 1))
    with asyncio_patch("gns3server.controller.udp_link.UDPLink.create") as mock_udp_create:
        async_run(link.add_node(vm2, 4, 2))
    assert mock_udp_create.called
    assert len(link._nodes) == 2
    controller.notification.emit.assert_any_call("link.created", link.__json__())


def test_getLink(async_run, project):
    compute = MagicMock()

    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    link = async_run(project.add_link())
    assert project.get_link(link.id) == link

    with pytest.raises(aiohttp.web_exceptions.HTTPNotFound):
        project.get_link("test")


def test_deleteLink(async_run, project, controller):
    compute = MagicMock()

    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    assert len(project._links) == 0
    link = async_run(project.add_link())
    assert len(project._links) == 1
    controller._notification = MagicMock()
    async_run(project.delete_link(link.id))
    controller.notification.emit.assert_any_call("link.deleted", link.__json__())
    assert len(project._links) == 0


def test_addDrawing(async_run, project, controller):
    controller.notification.emit = MagicMock()

    drawing = async_run(project.add_drawing(None, svg="<svg></svg>"))
    assert len(project._drawings) == 1
    controller.notification.emit.assert_any_call("drawing.created", drawing.__json__())


def test_getDrawing(async_run, project):
    drawing = async_run(project.add_drawing(None))
    assert project.get_drawing(drawing.id) == drawing

    with pytest.raises(aiohttp.web_exceptions.HTTPNotFound):
        project.get_drawing("test")


def test_deleteDrawing(async_run, project, controller):
    assert len(project._drawings) == 0
    drawing = async_run(project.add_drawing())
    assert len(project._drawings) == 1
    controller._notification = MagicMock()
    async_run(project.delete_drawing(drawing.id))
    controller.notification.emit.assert_any_call("drawing.deleted", drawing.__json__())
    assert len(project._drawings) == 0


def test_cleanPictures(async_run, project, controller):
    """
    When a project is close old pictures should be removed
    """

    drawing = async_run(project.add_drawing())
    drawing._svg = "test.png"
    open(os.path.join(project.pictures_directory, "test.png"), "w+").close()
    open(os.path.join(project.pictures_directory, "test2.png"), "w+").close()
    async_run(project.close())
    assert os.path.exists(os.path.join(project.pictures_directory, "test.png"))
    assert not os.path.exists(os.path.join(project.pictures_directory, "test2.png"))


def test_delete(async_run, project, controller):
    assert os.path.exists(project.path)
    async_run(project.delete())
    assert not os.path.exists(project.path)


def test_dump():
    directory = Config.instance().get_section_config("Server").get("projects_path")

    with patch("gns3server.utils.path.get_default_project_directory", return_value=directory):
        p = Project(project_id='00010203-0405-0607-0809-0a0b0c0d0e0f', name="Test")
        p.dump()
        with open(os.path.join(directory, p.id, "Test.gns3")) as f:
            content = f.read()
            assert "00010203-0405-0607-0809-0a0b0c0d0e0f" in content


def test_open_close(async_run, controller):
    project = Project(controller=controller, status="closed", name="Test")
    assert project.status == "closed"
    project.start_all = AsyncioMagicMock()
    async_run(project.open())
    assert not project.start_all.called
    assert project.status == "opened"
    controller._notification = MagicMock()
    async_run(project.close())
    assert project.status == "closed"
    controller.notification.emit.assert_any_call("project.closed", project.__json__())


def test_open_auto_start(async_run, controller):
    project = Project(controller=controller, status="closed", name="Test")
    project.auto_start = True
    project.start_all = AsyncioMagicMock()
    async_run(project.open())
    assert project.start_all.called


def test_is_running(project, async_run, node):
    """
    If a node is started or paused return True
    """

    assert project.is_running() is False
    node._status = "started"
    assert project.is_running() is True


def test_duplicate(project, async_run, controller):
    """
    Duplicate a project, the node should remain on the remote server
    if they were on remote server
    """
    compute = MagicMock()
    compute.id = "remote"
    compute.list_files = AsyncioMagicMock(return_value=[])
    controller._computes["remote"] = compute

    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    remote_vpcs = async_run(project.add_node(compute, "test", None, node_type="vpcs", properties={"startup_config": "test.cfg"}))

    # We allow node not allowed for standard import / export
    remote_virtualbox = async_run(project.add_node(compute, "test", None, node_type="vmware", properties={"startup_config": "test.cfg"}))

    new_project = async_run(project.duplicate(name="Hello"))
    assert new_project.id != project.id
    assert new_project.name == "Hello"

    async_run(new_project.open())

    assert list(new_project.nodes.values())[0].compute.id == "remote"
    assert list(new_project.nodes.values())[1].compute.id == "remote"


def test_duplicate_with_zipfile_encoding_issues(project, async_run, controller):
    zf = zipstream.ZipFile()
    zf.writestr('test\udcc3', "data")

    with asyncio_patch('gns3server.controller.project.export_project', return_value=zf):
        with pytest.raises(aiohttp.web.HTTPConflict):
            async_run(project.duplicate(name="Hello"))


def test_snapshots(project):
    """
    List the snapshots
    """
    os.makedirs(os.path.join(project.path, "snapshots"))
    open(os.path.join(project.path, "snapshots", "test1_260716_103713.gns3project"), "w+").close()
    project.reset()

    assert len(project.snapshots) == 1
    assert list(project.snapshots.values())[0].name == "test1"


def test_get_snapshot(project):
    os.makedirs(os.path.join(project.path, "snapshots"))
    open(os.path.join(project.path, "snapshots", "test1.gns3project"), "w+").close()
    project.reset()

    snapshot = list(project.snapshots.values())[0]
    assert project.get_snapshot(snapshot.id) == snapshot

    with pytest.raises(aiohttp.web_exceptions.HTTPNotFound):
        project.get_snapshot("BLU")


def test_delete_snapshot(project, async_run):
    os.makedirs(os.path.join(project.path, "snapshots"))
    open(os.path.join(project.path, "snapshots", "test1_260716_103713.gns3project"), "w+").close()
    project.reset()

    snapshot = list(project.snapshots.values())[0]
    assert project.get_snapshot(snapshot.id) == snapshot

    async_run(project.delete_snapshot(snapshot.id))

    with pytest.raises(aiohttp.web_exceptions.HTTPNotFound):
        project.get_snapshot(snapshot.id)

    assert not os.path.exists(os.path.join(project.path, "snapshots", "test1.gns3project"))


def test_snapshot(project, async_run):
    """
    Create a snapshot
    """
    assert len(project.snapshots) == 0

    snapshot = async_run(project.snapshot("test1"))
    assert snapshot.name == "test1"

    assert len(project.snapshots) == 1
    assert list(project.snapshots.values())[0].name == "test1"

    # Raise a conflict if name is already use
    with pytest.raises(aiohttp.web_exceptions.HTTPConflict):
        snapshot = async_run(project.snapshot("test1"))


def test_start_all(project, async_run):
    compute = MagicMock()
    compute.id = "local"
    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    for node_i in range(0, 10):
        async_run(project.add_node(compute, "test", None, node_type="vpcs", properties={"startup_config": "test.cfg"}))

    compute.post = AsyncioMagicMock()
    async_run(project.start_all())
    assert len(compute.post.call_args_list) == 10


def test_stop_all(project, async_run):
    compute = MagicMock()
    compute.id = "local"
    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    for node_i in range(0, 10):
        async_run(project.add_node(compute, "test", None, node_type="vpcs", properties={"startup_config": "test.cfg"}))

    compute.post = AsyncioMagicMock()
    async_run(project.stop_all())
    assert len(compute.post.call_args_list) == 10


def test_suspend_all(project, async_run):
    compute = MagicMock()
    compute.id = "local"
    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    for node_i in range(0, 10):
        async_run(project.add_node(compute, "test", None, node_type="vpcs", properties={"startup_config": "test.cfg"}))

    compute.post = AsyncioMagicMock()
    async_run(project.suspend_all())
    assert len(compute.post.call_args_list) == 10


def test_node_name(project, async_run):
    compute = MagicMock()
    compute.id = "local"
    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    node = async_run(project.add_node(compute, "test-{0}", None, node_type="vpcs", properties={"startup_config": "test.cfg"}))
    assert node.name == "test-1"
    node = async_run(project.add_node(compute, "test-{0}", None, node_type="vpcs", properties={"startup_config": "test.cfg"}))
    assert node.name == "test-2"
    node = async_run(project.add_node(compute, "hello world-{0}", None, node_type="vpcs", properties={"startup_config": "test.cfg"}))
    assert node.name == "helloworld-1"
    node = async_run(project.add_node(compute, "hello world-{0}", None, node_type="vpcs", properties={"startup_config": "test.cfg"}))
    assert node.name == "helloworld-2"
