#!/usr/bin/env python
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

import os
import sys
import uuid
import pytest
import aiohttp
from unittest.mock import MagicMock
from tests.utils import AsyncioMagicMock, asyncio_patch
from unittest.mock import patch
from uuid import uuid4

from gns3server.controller.project import Project
from gns3server.controller.template import Template
from gns3server.controller.node import Node
from gns3server.controller.ports.ethernet_port import EthernetPort
from gns3server.config import Config


@pytest.fixture
async def node(controller, project):

    compute = MagicMock()
    compute.id = "local"
    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)
    node = await project.add_node(compute, "test", None, node_type="vpcs", properties={"startup_config": "test.cfg"})
    return node


async def test_affect_uuid():

    with patch('gns3server.controller.project.Project.emit_controller_notification') as mock_notification:
        p = Project(name="Test")
        mock_notification.assert_called()
        assert len(p.id) == 36
        p = Project(project_id='00010203-0405-0607-0809-0a0b0c0d0e0f', name="Test 2")
        assert p.id == '00010203-0405-0607-0809-0a0b0c0d0e0f'


async def test_json():

    with patch('gns3server.controller.project.Project.emit_controller_notification') as mock_notification:
        p = Project(name="Test")
        mock_notification.assert_called()

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
        "scene_height": 1000,
        "zoom": 100,
        "show_grid": False,
        "show_interface_labels": False,
        "show_layers": False,
        "snap_to_grid": False,
        "grid_size": 75,
        "drawing_grid_size": 25,
        "supplier": None,
        "variables": None
    }


async def test_update(controller):

    project = Project(controller=controller, name="Hello")
    project.emit_controller_notification = MagicMock()
    assert project.name == "Hello"
    await project.update(name="World")
    assert project.name == "World"
    project.emit_controller_notification.assert_any_call("project.updated", project.__json__())


async def test_update_on_compute(controller):

    variables = [{"name": "TEST", "value": "VAL1"}]
    compute = MagicMock()
    compute.id = "local"
    project = Project(controller=controller, name="Test")
    project._project_created_on_compute = [compute]
    project.emit_notification = MagicMock()
    await project.update(variables=variables)
    compute.put.assert_any_call('/projects/{}'.format(project.id), {"variables": variables})


async def test_path(projects_dir):

    directory = projects_dir
    with patch("gns3server.utils.path.get_default_project_directory", return_value=directory):
        with patch('gns3server.controller.project.Project.emit_controller_notification') as mock_notification:
            p = Project(project_id=str(uuid4()), name="Test")
            mock_notification.assert_called()
        assert p.path == os.path.join(directory, p.id)
        assert os.path.exists(os.path.join(directory, p.id))


def test_path_exist(tmpdir):
    """
    Should raise an error when you try to overwrite
    an existing project
    """

    os.makedirs(str(tmpdir / "demo"))
    with pytest.raises(aiohttp.web.HTTPForbidden):
        Project(name="Test", path=str(tmpdir / "demo"))


async def test_init_path(tmpdir):

    with patch('gns3server.controller.project.Project.emit_controller_notification') as mock_notification:
        p = Project(path=str(tmpdir), project_id=str(uuid4()), name="Test")
        mock_notification.assert_called()
        assert p.path == str(tmpdir)


@pytest.mark.skipif(sys.platform.startswith("win"), reason="Not supported on Windows")
async def test_changing_path_with_quote_not_allowed(tmpdir):

    with pytest.raises(aiohttp.web.HTTPForbidden):
        with patch('gns3server.controller.project.Project.emit_controller_notification'):
            p = Project(project_id=str(uuid4()), name="Test")
            p.path = str(tmpdir / "project\"53")


async def test_captures_directory(tmpdir):

    with patch('gns3server.controller.project.Project.emit_controller_notification'):
        p = Project(path=str(tmpdir / "capturestest"), name="Test")
        assert p.captures_directory == str(tmpdir / "capturestest" / "project-files" / "captures")
        assert os.path.exists(p.captures_directory)


async def test_add_node_local(controller):
    """
    For a local server we send the project path
    """

    compute = MagicMock()
    compute.id = "local"
    project = Project(controller=controller, name="Test")
    project.emit_notification = MagicMock()

    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    node = await project.add_node(compute, "test", None, node_type="vpcs", properties={"startup_script": "test.cfg"})
    assert node.id in project._nodes

    compute.post.assert_any_call('/projects', data={
        "name": project._name,
        "project_id": project._id,
        "path": project._path,
    })
    compute.post.assert_any_call('/projects/{}/vpcs/nodes'.format(project.id),
                                 data={'node_id': node.id,
                                       'startup_script': 'test.cfg',
                                       'name': 'test'},
                                 timeout=1200)
    assert compute in project._project_created_on_compute
    project.emit_notification.assert_any_call("node.created", node.__json__())


async def test_add_node_non_local(controller):
    """
    For a non local server we do not send the project path
    """

    compute = MagicMock()
    compute.id = "remote"
    project = Project(controller=controller, name="Test")
    project.emit_notification = MagicMock()

    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    node = await project.add_node(compute, "test", None, node_type="vpcs", properties={"startup_script": "test.cfg"})

    compute.post.assert_any_call('/projects', data={
        "name": project._name,
        "project_id": project._id
    })
    compute.post.assert_any_call('/projects/{}/vpcs/nodes'.format(project.id), data={'node_id': node.id,
                                                                                     'startup_script': 'test.cfg',
                                                                                     'name': 'test'}, timeout=1200)
    assert compute in project._project_created_on_compute
    project.emit_notification.assert_any_call("node.created", node.__json__())


async def test_add_node_iou(controller):
    """
    Test if an application ID is allocated for IOU nodes
    """

    compute = MagicMock()
    compute.id = "local"
    project = await controller.add_project(project_id=str(uuid.uuid4()), name="test1")
    project.emit_notification = MagicMock()

    response = MagicMock()
    compute.post = AsyncioMagicMock(return_value=response)

    node1 = await project.add_node(compute, "test1", None, node_type="iou")
    node2 = await project.add_node(compute, "test2", None, node_type="iou")
    node3 = await project.add_node(compute, "test3", None, node_type="iou")
    assert node1.properties["application_id"] == 1
    assert node2.properties["application_id"] == 2
    assert node3.properties["application_id"] == 3


async def test_add_node_iou_with_multiple_projects(controller):
    """
    Test if an application ID is allocated for IOU nodes with different projects already opened
    """
    compute = MagicMock()
    compute.id = "local"
    project1 = await controller.add_project(project_id=str(uuid.uuid4()), name="test1")
    project1.emit_notification = MagicMock()
    project2 = await controller.add_project(project_id=str(uuid.uuid4()), name="test2")
    project2.emit_notification = MagicMock()
    project3 = await controller.add_project(project_id=str(uuid.uuid4()), name="test3")
    project3.emit_notification = MagicMock()
    response = MagicMock()
    compute.post = AsyncioMagicMock(return_value=response)

    node1 = await project1.add_node(compute, "test1", None, node_type="iou")
    node2 = await project1.add_node(compute, "test2", None, node_type="iou")
    node3 = await project1.add_node(compute, "test3", None, node_type="iou")

    node4 = await project2.add_node(compute, "test4", None, node_type="iou")
    node5 = await project2.add_node(compute, "test5", None, node_type="iou")
    node6 = await project2.add_node(compute, "test6", None, node_type="iou")

    node7 = await project3.add_node(compute, "test7", None, node_type="iou")
    node8 = await project3.add_node(compute, "test8", None, node_type="iou")
    node9 = await project3.add_node(compute, "test9", None, node_type="iou")

    assert node1.properties["application_id"] == 1
    assert node2.properties["application_id"] == 2
    assert node3.properties["application_id"] == 3

    assert node4.properties["application_id"] == 4
    assert node5.properties["application_id"] == 5
    assert node6.properties["application_id"] == 6

    assert node7.properties["application_id"] == 7
    assert node8.properties["application_id"] == 8
    assert node9.properties["application_id"] == 9

    controller.remove_project(project1)
    project4 = await controller.add_project(project_id=str(uuid.uuid4()), name="test4")
    project4.emit_notification = MagicMock()

    node10 = await project3.add_node(compute, "test10", None, node_type="iou")
    node11 = await project3.add_node(compute, "test11", None, node_type="iou")
    node12 = await project3.add_node(compute, "test12", None, node_type="iou")

    assert node10.properties["application_id"] == 1
    assert node11.properties["application_id"] == 2
    assert node12.properties["application_id"] == 3


async def test_add_node_iou_with_multiple_projects_different_computes(controller):
    """
    Test if an application ID is allocated for IOU nodes with different projects already opened
    """
    compute1 = MagicMock()
    compute1.id = "remote1"
    compute2 = MagicMock()
    compute2.id = "remote2"
    project1 = await controller.add_project(project_id=str(uuid.uuid4()), name="test1")
    project1.emit_notification = MagicMock()
    project2 = await controller.add_project(project_id=str(uuid.uuid4()), name="test2")
    project2.emit_notification = MagicMock()
    response = MagicMock()
    compute1.post = AsyncioMagicMock(return_value=response)
    compute2.post = AsyncioMagicMock(return_value=response)

    node1 = await project1.add_node(compute1, "test1", None, node_type="iou")
    node2 = await project1.add_node(compute1, "test2", None, node_type="iou")

    node3 = await project2.add_node(compute2, "test3", None, node_type="iou")
    node4 = await project2.add_node(compute2, "test4", None, node_type="iou")

    assert node1.properties["application_id"] == 1
    assert node2.properties["application_id"] == 2

    assert node3.properties["application_id"] == 1
    assert node4.properties["application_id"] == 2

    node5 = await project1.add_node(compute2, "test5", None, node_type="iou")
    node6 = await project2.add_node(compute1, "test6", None, node_type="iou")

    assert node5.properties["application_id"] == 3
    assert node6.properties["application_id"] == 4


async def test_add_node_iou_no_id_available(controller):
    """
    Test if an application ID is allocated for IOU nodes
    """

    compute = MagicMock()
    compute.id = "local"
    project = await controller.add_project(project_id=str(uuid.uuid4()), name="test")
    project.emit_notification = MagicMock()
    response = MagicMock()
    compute.post = AsyncioMagicMock(return_value=response)

    with pytest.raises(aiohttp.web.HTTPConflict):
        for i in range(1, 513):
            prop = {"properties": {"application_id": i}}
            project._nodes[i] = Node(project, compute, "Node{}".format(i), node_id=i, node_type="iou", **prop)
        await project.add_node(compute, "test1", None, node_type="iou")


async def test_add_node_from_template(controller):
    """
    For a local server we send the project path
    """

    compute = MagicMock()
    compute.id = "local"
    project = Project(controller=controller, name="Test")
    project.emit_notification = MagicMock()
    template = Template(str(uuid.uuid4()), {
        "compute_id": "local",
        "name": "Test",
        "template_type": "vpcs",
        "builtin": False,
    })
    controller.template_manager.templates[template.id] = template
    controller._computes["local"] = compute

    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    node = await project.add_node_from_template(template.id, x=23, y=12)
    compute.post.assert_any_call('/projects', data={
        "name": project._name,
        "project_id": project._id,
        "path": project._path
    })

    assert compute in project._project_created_on_compute
    project.emit_notification.assert_any_call("node.created", node.__json__())


async def test_add_builtin_node_from_template(controller):
    """
    For a local server we send the project path
    """

    compute = MagicMock()
    compute.id = "local"
    project = Project(controller=controller, name="Test")
    project.emit_notification = MagicMock()
    template = Template(str(uuid.uuid4()), {
        "name": "Builtin-switch",
        "template_type": "ethernet_switch",
    }, builtin=True)

    controller.template_manager.templates[template.id] = template
    template.__json__()
    controller._computes["local"] = compute

    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    node = await project.add_node_from_template(template.id, x=23, y=12, compute_id="local")
    compute.post.assert_any_call('/projects', data={
        "name": project._name,
        "project_id": project._id,
        "path": project._path
    })

    assert compute in project._project_created_on_compute
    project.emit_notification.assert_any_call("node.created", node.__json__())


async def test_delete_node(controller):
    """
    For a local server we send the project path
    """
    compute = MagicMock()
    project = Project(controller=controller, name="Test")
    project.emit_notification = MagicMock()

    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    node = await project.add_node(compute, "test", None, node_type="vpcs", properties={"startup_config": "test.cfg"})
    assert node.id in project._nodes
    await project.delete_node(node.id)
    assert node.id not in project._nodes

    compute.delete.assert_any_call('/projects/{}/vpcs/nodes/{}'.format(project.id, node.id))
    project.emit_notification.assert_any_call("node.deleted", node.__json__())


async def test_delete_locked_node(controller):
    """
    For a local server we send the project path
    """

    compute = MagicMock()
    project = Project(controller=controller, name="Test")
    project.emit_notification = MagicMock()

    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    node = await project.add_node(compute, "test", None, node_type="vpcs", properties={"startup_config": "test.cfg"})
    assert node.id in project._nodes
    node.locked = True
    with pytest.raises(aiohttp.web_exceptions.HTTPConflict):
        await project.delete_node(node.id)


async def test_delete_node_delete_link(controller):
    """
    Delete a node delete all the node connected
    """
    compute = MagicMock()
    project = Project(controller=controller, name="Test")
    project.emit_notification = MagicMock()

    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    node = await project.add_node(compute, "test", None, node_type="vpcs", properties={"startup_config": "test.cfg"})

    link = await project.add_link()
    await link.add_node(node, 0, 0)

    await project.delete_node(node.id)
    assert node.id not in project._nodes
    assert link.id not in project._links

    compute.delete.assert_any_call('/projects/{}/vpcs/nodes/{}'.format(project.id, node.id))
    project.emit_notification.assert_any_call("node.deleted", node.__json__())
    project.emit_notification.assert_any_call("link.deleted", link.__json__())


async def test_get_node(controller):

    compute = MagicMock()
    project = Project(controller=controller, name="Test")

    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    vm = await project.add_node(compute, "test", None, node_type="vpcs", properties={"startup_config": "test.cfg"})
    assert project.get_node(vm.id) == vm

    with pytest.raises(aiohttp.web_exceptions.HTTPNotFound):
        project.get_node("test")

    # Raise an error if the project is not opened
    await project.close()
    with pytest.raises(aiohttp.web.HTTPForbidden):
        project.get_node(vm.id)


async def test_list_nodes(controller):

    compute = MagicMock()
    project = Project(controller=controller, name="Test")

    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    vm = await project.add_node(compute, "test", None, node_type="vpcs", properties={"startup_config": "test.cfg"})
    assert len(project.nodes) == 1
    assert isinstance(project.nodes, dict)

    await project.close()
    assert len(project.nodes) == 1
    assert isinstance(project.nodes, dict)


async def test_add_link(project):

    compute = MagicMock()

    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    vm1 = await project.add_node(compute, "test1", None, node_type="vpcs", properties={"startup_config": "test.cfg"})
    vm1._ports = [EthernetPort("E0", 0, 3, 1)]
    vm2 = await project.add_node(compute, "test2", None, node_type="vpcs", properties={"startup_config": "test.cfg"})
    vm2._ports = [EthernetPort("E0", 0, 4, 2)]
    project.emit_notification = MagicMock()
    link = await project.add_link()
    await link.add_node(vm1, 3, 1)
    with asyncio_patch("gns3server.controller.udp_link.UDPLink.create") as mock_udp_create:
        await link.add_node(vm2, 4, 2)
    assert mock_udp_create.called
    assert len(link._nodes) == 2
    project.emit_notification.assert_any_call("link.created", link.__json__())


async def test_list_links(project):

    compute = MagicMock()
    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    await project.add_link()
    assert len(project.links) == 1

    await project.close()
    assert len(project.links) == 1


async def test_get_link(project):

    compute = MagicMock()
    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    link = await project.add_link()
    assert project.get_link(link.id) == link

    with pytest.raises(aiohttp.web_exceptions.HTTPNotFound):
        project.get_link("test")


async def test_delete_link(project):

    compute = MagicMock()
    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    assert len(project._links) == 0
    link = await project.add_link()
    assert len(project._links) == 1
    project.emit_notification = MagicMock()
    await project.delete_link(link.id)
    project.emit_notification.assert_any_call("link.deleted", link.__json__())
    assert len(project._links) == 0


async def test_add_drawing(project):

    project.emit_notification = MagicMock()
    drawing = await project.add_drawing(None, svg="<svg></svg>")
    assert len(project._drawings) == 1
    project.emit_notification.assert_any_call("drawing.created", drawing.__json__())


async def test_get_drawing(project):

    drawing = await project.add_drawing(None)
    assert project.get_drawing(drawing.id) == drawing

    with pytest.raises(aiohttp.web_exceptions.HTTPNotFound):
        project.get_drawing("test")


async def test_list_drawing(project):

    await project.add_drawing(None)
    assert len(project.drawings) == 1

    await project.close()
    assert len(project.drawings) == 1


async def test_delete_drawing(project):

    assert len(project._drawings) == 0
    drawing = await project.add_drawing()
    assert len(project._drawings) == 1
    project.emit_notification = MagicMock()
    await project.delete_drawing(drawing.id)
    project.emit_notification.assert_any_call("drawing.deleted", drawing.__json__())
    assert len(project._drawings) == 0


async def test_clean_pictures(project):
    """
    When a project is close old pictures should be removed
    """

    drawing = await project.add_drawing()
    drawing._svg = "test.png"
    open(os.path.join(project.pictures_directory, "test.png"), "w+").close()
    open(os.path.join(project.pictures_directory, "test2.png"), "w+").close()
    await project.close()
    assert os.path.exists(os.path.join(project.pictures_directory, "test.png"))
    assert not os.path.exists(os.path.join(project.pictures_directory, "test2.png"))


async def test_clean_pictures_and_keep_supplier_logo(project):
    """
    When a project is close old pictures should be removed
    """

    project.supplier = {
        'logo': 'logo.png'
    }

    drawing = await project.add_drawing()
    drawing._svg = "test.png"
    open(os.path.join(project.pictures_directory, "test.png"), "w+").close()
    open(os.path.join(project.pictures_directory, "test2.png"), "w+").close()
    open(os.path.join(project.pictures_directory, "logo.png"), "w+").close()

    await project.close()
    assert os.path.exists(os.path.join(project.pictures_directory, "test.png"))
    assert not os.path.exists(os.path.join(project.pictures_directory, "test2.png"))
    assert os.path.exists(os.path.join(project.pictures_directory, "logo.png"))


async def test_delete(project):

    assert os.path.exists(project.path)
    await project.delete()
    assert not os.path.exists(project.path)


async def test_dump(projects_dir):

    directory = projects_dir
    with patch("gns3server.utils.path.get_default_project_directory", return_value=directory):
        with patch('gns3server.controller.project.Project.emit_controller_notification'):
            p = Project(project_id='00010203-0405-0607-0809-0a0b0c0d0e0f', name="Test")
            p.dump()
            with open(os.path.join(directory, p.id, "Test.gns3")) as f:
                content = f.read()
                assert "00010203-0405-0607-0809-0a0b0c0d0e0f" in content


# async def test_open_close(controller):
#
#     with patch('gns3server.controller.project.Project.emit_controller_notification'):
#         project = Project(controller=controller, name="Test")
#         assert project.status == "opened"
#         await project.close()
#         project.start_all = AsyncioMagicMock()
#         await project.open()
#         assert not project.start_all.called
#         assert project.status == "opened"
#         project.emit_controller_notification = MagicMock()
#         await project.close()
#         assert project.status == "closed"
#         project.emit_controller_notification.assert_any_call("project.closed", project.__json__())
#
#
# async def test_open_auto_start(controller):
#
#     with patch('gns3server.controller.project.Project.emit_controller_notification'):
#         project = Project(controller=controller, name="Test", auto_start=True)
#         assert project.status == "opened"
#         await project.close()
#         project.start_all = AsyncioMagicMock()
#         await project.open()
#         assert project.start_all.called


def test_is_running(project, node):
    """
    If a node is started or paused return True
    """

    assert project.is_running() is False
    node._status = "started"
    assert project.is_running() is True


async def test_duplicate(project, controller):
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

    remote_vpcs = await project.add_node(compute, "test", None, node_type="vpcs", properties={"startup_config": "test.cfg"})

    # We allow node not allowed for standard import / export
    remote_virtualbox = await project.add_node(compute, "test", None, node_type="vmware", properties={"startup_config": "test.cfg"})

    new_project = await project.duplicate(name="Hello")
    assert new_project.id != project.id
    assert new_project.name == "Hello"

    await new_project.open()

    assert list(new_project.nodes.values())[0].compute.id == "remote"
    assert list(new_project.nodes.values())[1].compute.id == "remote"


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
    open(os.path.join(project.path, "snapshots", "test1_260716_103713.gns3project"), "w+").close()
    project.reset()

    snapshot = list(project.snapshots.values())[0]
    assert project.get_snapshot(snapshot.id) == snapshot

    with pytest.raises(aiohttp.web_exceptions.HTTPNotFound):
        project.get_snapshot("BLU")


async def test_delete_snapshot(project):

    os.makedirs(os.path.join(project.path, "snapshots"))
    open(os.path.join(project.path, "snapshots", "test1_260716_103713.gns3project"), "w+").close()
    project.reset()

    snapshot = list(project.snapshots.values())[0]
    assert project.get_snapshot(snapshot.id) == snapshot

    await project.delete_snapshot(snapshot.id)

    with pytest.raises(aiohttp.web_exceptions.HTTPNotFound):
        project.get_snapshot(snapshot.id)

    assert not os.path.exists(os.path.join(project.path, "snapshots", "test1.gns3project"))


async def test_snapshot(project):
    """
    Create a snapshot
    """

    assert len(project.snapshots) == 0
    snapshot = await project.snapshot("test1")
    assert snapshot.name == "test1"

    assert len(project.snapshots) == 1
    assert list(project.snapshots.values())[0].name == "test1"

    # Raise a conflict if name is already use
    with pytest.raises(aiohttp.web_exceptions.HTTPConflict):
        snapshot = await project.snapshot("test1")


async def test_start_all(project):

    compute = MagicMock()
    compute.id = "local"
    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    for node_i in range(0, 10):
        await project.add_node(compute, "test", None, node_type="vpcs", properties={"startup_config": "test.cfg"})

    compute.post = AsyncioMagicMock()
    await project.start_all()
    assert len(compute.post.call_args_list) == 10


async def test_stop_all(project):

    compute = MagicMock()
    compute.id = "local"
    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    for node_i in range(0, 10):
        await project.add_node(compute, "test", None, node_type="vpcs", properties={"startup_config": "test.cfg"})

    compute.post = AsyncioMagicMock()
    await project.stop_all()
    assert len(compute.post.call_args_list) == 10


async def test_suspend_all(project):

    compute = MagicMock()
    compute.id = "local"
    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    for node_i in range(0, 10):
        await project.add_node(compute, "test", None, node_type="vpcs", properties={"startup_config": "test.cfg"})

    compute.post = AsyncioMagicMock()
    await project.suspend_all()
    assert len(compute.post.call_args_list) == 10


async def test_console_reset_all(project):

    compute = MagicMock()
    compute.id = "local"
    response = MagicMock()
    response.json = {"console": 2048, "console_type": "telnet"}
    compute.post = AsyncioMagicMock(return_value=response)

    for node_i in range(0, 10):
        await project.add_node(compute, "test", None, node_type="vpcs", properties={"startup_config": "test.cfg"})

    compute.post = AsyncioMagicMock()
    await project.reset_console_all()
    assert len(compute.post.call_args_list) == 10


async def test_node_name(project):

    compute = MagicMock()
    compute.id = "local"
    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    node = await project.add_node(compute, "test-{0}", None, node_type="vpcs", properties={"startup_config": "test.cfg"})
    assert node.name == "test-1"
    node = await project.add_node(compute, "test-{0}", None, node_type="vpcs", properties={"startup_config": "test.cfg"})
    assert node.name == "test-2"
    node = await project.add_node(compute, "hello world-{0}", None, node_type="vpcs", properties={"startup_config": "test.cfg"})
    assert node.name == "helloworld-1"
    node = await project.add_node(compute, "hello world-{0}", None, node_type="vpcs", properties={"startup_config": "test.cfg"})
    assert node.name == "helloworld-2"
    node = await project.add_node(compute, "VPCS-1", None, node_type="vpcs", properties={"startup_config": "test.cfg"})
    assert node.name == "VPCS-1"
    node = await project.add_node(compute, "VPCS-1", None, node_type="vpcs", properties={"startup_config": "test.cfg"})
    assert node.name == "VPCS-2"

    node = await project.add_node(compute, "R3", None, node_type="vpcs", properties={"startup_config": "test.cfg"})
    assert node.name == "R3"


async def test_duplicate_node(project):

    compute = MagicMock()
    compute.id = "local"
    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    original = await project.add_node(
        compute,
        "test",
        None,
        node_type="vpcs",
        properties={
            "startup_config": "test.cfg"
        })
    new_node = await project.duplicate_node(original, 42, 10, 11)
    assert new_node.x == 42
