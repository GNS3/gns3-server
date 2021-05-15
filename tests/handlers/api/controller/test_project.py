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

import uuid
import os
import pytest
import zipfile
import json

from unittest.mock import patch, MagicMock
from tests.utils import asyncio_patch


@pytest.fixture
async def project(controller_api, controller):

    u = str(uuid.uuid4())
    params = {"name": "test", "project_id": u}
    await controller_api.post("/projects", params)
    return controller.get_project(u)


async def test_create_project_with_path(controller_api, tmpdir):

    response = await controller_api.post("/projects", {"name": "test", "path": str(tmpdir), "project_id": "00010203-0405-0607-0809-0a0b0c0d0e0f"})
    assert response.status == 201
    assert response.json["name"] == "test"
    assert response.json["project_id"] == "00010203-0405-0607-0809-0a0b0c0d0e0f"
    assert response.json["status"] == "opened"


async def test_create_project_without_dir(controller_api):

    params = {"name": "test", "project_id": "10010203-0405-0607-0809-0a0b0c0d0e0f"}
    response = await controller_api.post("/projects", params)
    assert response.status == 201
    assert response.json["project_id"] == "10010203-0405-0607-0809-0a0b0c0d0e0f"
    assert response.json["name"] == "test"


async def test_create_project_with_uuid(controller_api):

    params = {"name": "test", "project_id": "30010203-0405-0607-0809-0a0b0c0d0e0f"}
    response = await controller_api.post("/projects", params)
    assert response.status == 201
    assert response.json["project_id"] == "30010203-0405-0607-0809-0a0b0c0d0e0f"
    assert response.json["name"] == "test"


async def test_create_project_with_variables(controller_api):

    variables = [
        {"name": "TEST1"},
        {"name": "TEST2", "value": "value1"}
    ]
    params = {"name": "test", "project_id": "30010203-0405-0607-0809-0a0b0c0d0e0f", "variables": variables}
    response = await controller_api.post("/projects", params)
    assert response.status == 201
    assert response.json["variables"] == [
        {"name": "TEST1"},
        {"name": "TEST2", "value": "value1"}
    ]


async def test_create_project_with_supplier(controller_api):

    supplier = {
        'logo': 'logo.png',
        'url': 'http://example.com'
    }
    params = {"name": "test", "project_id": "30010203-0405-0607-0809-0a0b0c0d0e0f", "supplier": supplier}
    response = await controller_api.post("/projects", params)
    assert response.status == 201
    assert response.json["supplier"] == supplier


async def test_update_project(controller_api):

    params = {"name": "test", "project_id": "10010203-0405-0607-0809-0a0b0c0d0e0f"}
    response = await controller_api.post("/projects", params)
    assert response.status == 201
    assert response.json["project_id"] == "10010203-0405-0607-0809-0a0b0c0d0e0f"
    assert response.json["name"] == "test"

    params = {"name": "test2"}
    response = await controller_api.put("/projects/10010203-0405-0607-0809-0a0b0c0d0e0f", params)
    assert response.status == 200
    assert response.json["name"] == "test2"


async def test_update_project_with_variables(controller_api):

    variables = [
        {"name": "TEST1"},
        {"name": "TEST2", "value": "value1"}
    ]
    params = {"name": "test", "project_id": "10010203-0405-0607-0809-0a0b0c0d0e0f", "variables": variables}
    response = await controller_api.post("/projects", params)
    assert response.status == 201

    params = {"name": "test2"}
    response = await controller_api.put("/projects/10010203-0405-0607-0809-0a0b0c0d0e0f", params)
    assert response.status == 200
    assert response.json["variables"] == variables


async def test_list_projects(controller_api, tmpdir):

    await controller_api.post("/projects", {"name": "test", "path": str(tmpdir), "project_id": "00010203-0405-0607-0809-0a0b0c0d0e0f"})
    response = await controller_api.get("/projects")
    assert response.status == 200
    projects = response.json
    assert projects[0]["name"] == "test"


async def test_get_project(controller_api, project):

    response = await controller_api.get("/projects/{project_id}".format(project_id=project.id))
    assert response.status == 200
    assert response.json["name"] == "test"


async def test_delete_project(controller_api, project, controller):

    with asyncio_patch("gns3server.controller.project.Project.delete", return_value=True) as mock:
        response = await controller_api.delete("/projects/{project_id}".format(project_id=project.id))
        assert response.status == 204
        assert mock.called
        assert project not in controller.projects


async def test_delete_project_invalid_uuid(controller_api):

    response = await controller_api.delete("/projects/{project_id}".format(project_id=uuid.uuid4()))
    assert response.status == 404


async def test_close_project(controller_api, project):

    with asyncio_patch("gns3server.controller.project.Project.close", return_value=True) as mock:
        response = await controller_api.post("/projects/{project_id}/close".format(project_id=project.id))
        assert response.status == 204
        assert mock.called


async def test_open_project(controller_api, project):

    with asyncio_patch("gns3server.controller.project.Project.open", return_value=True) as mock:
        response = await controller_api.post("/projects/{project_id}/open".format(project_id=project.id))
        assert response.status == 201
        assert mock.called


async def test_load_project(controller_api, project, config):

    config.set("Server", "local", "true")
    with asyncio_patch("gns3server.controller.Controller.load_project", return_value=project) as mock:
        response = await controller_api.post("/projects/load".format(project_id=project.id), {"path": "/tmp/test.gns3"})
        assert response.status == 201
        mock.assert_called_with("/tmp/test.gns3")
        assert response.json["project_id"] == project.id


async def test_notification(controller_api, http_client, project, controller):

    async with http_client.get(controller_api.get_url("/projects/{project_id}/notifications".format(project_id=project.id))) as response:
        response.body = await response.content.read(200)
        controller.notification.project_emit("node.created", {"a": "b"})
        response.body += await response.content.readany()
        assert response.status == 200
        assert b'"action": "ping"' in response.body
        assert b'"cpu_usage_percent"' in response.body
        assert b'{"action": "node.created", "event": {"a": "b"}}\n' in response.body
        assert project.status == "opened"


async def test_notification_invalid_id(controller_api):

    response = await controller_api.get("/projects/{project_id}/notifications".format(project_id=uuid.uuid4()))
    assert response.status == 404


async def test_notification_ws(controller_api, http_client, controller, project):

    ws = await http_client.ws_connect(controller_api.get_url("/projects/{project_id}/notifications/ws".format(project_id=project.id)))
    answer = await ws.receive()
    answer = json.loads(answer.data)
    assert answer["action"] == "ping"

    controller.notification.project_emit("test", {})
    answer = await ws.receive()
    answer = json.loads(answer.data)
    assert answer["action"] == "test"

    if not ws.closed:
        await ws.close()

    assert project.status == "opened"


async def test_export_with_images(controller_api, tmpdir, project):

    project.dump = MagicMock()
    os.makedirs(project.path, exist_ok=True)
    with open(os.path.join(project.path, 'a'), 'w+') as f:
        f.write('hello')

    os.makedirs(str(tmpdir / "IOS"))
    with open(str(tmpdir / "IOS" / "test.image"), "w+") as f:
        f.write("AAA")

    topology = {
        "topology": {
            "nodes": [
                {
                    "properties": {
                        "image": "test.image"
                    },
                    "node_type": "dynamips"
                }
            ]
        }
    }
    with open(os.path.join(project.path, "test.gns3"), 'w+') as f:
        json.dump(topology, f)

    with patch("gns3server.compute.Dynamips.get_images_directory", return_value=str(tmpdir / "IOS")):
        response = await controller_api.get("/projects/{project_id}/export?include_images=yes".format(project_id=project.id))
    assert response.status == 200
    assert response.headers['CONTENT-TYPE'] == 'application/gns3project'
    assert response.headers['CONTENT-DISPOSITION'] == 'attachment; filename="{}.gns3project"'.format(project.name)

    with open(str(tmpdir / 'project.zip'), 'wb+') as f:
        f.write(response.body)

    with zipfile.ZipFile(str(tmpdir / 'project.zip')) as myzip:
        with myzip.open("a") as myfile:
            content = myfile.read()
            assert content == b"hello"
        myzip.getinfo("images/IOS/test.image")


async def test_export_without_images(controller_api, tmpdir, project):

    project.dump = MagicMock()
    os.makedirs(project.path, exist_ok=True)
    with open(os.path.join(project.path, 'a'), 'w+') as f:
        f.write('hello')

    os.makedirs(str(tmpdir / "IOS"))
    with open(str(tmpdir / "IOS" / "test.image"), "w+") as f:
        f.write("AAA")

    topology = {
        "topology": {
            "nodes": [
                {
                    "properties": {
                        "image": "test.image"
                    },
                    "node_type": "dynamips"
                }
            ]
        }
    }
    with open(os.path.join(project.path, "test.gns3"), 'w+') as f:
        json.dump(topology, f)

    with patch("gns3server.compute.Dynamips.get_images_directory", return_value=str(tmpdir / "IOS"),):
        response = await controller_api.get("/projects/{project_id}/export?include_images=0".format(project_id=project.id))
    assert response.status == 200
    assert response.headers['CONTENT-TYPE'] == 'application/gns3project'
    assert response.headers['CONTENT-DISPOSITION'] == 'attachment; filename="{}.gns3project"'.format(project.name)

    with open(str(tmpdir / 'project.zip'), 'wb+') as f:
        f.write(response.body)

    with zipfile.ZipFile(str(tmpdir / 'project.zip')) as myzip:
        with myzip.open("a") as myfile:
            content = myfile.read()
            assert content == b"hello"
        # Image should not exported
        with pytest.raises(KeyError):
            myzip.getinfo("images/IOS/test.image")


async def test_get_file(controller_api, project):

    os.makedirs(project.path, exist_ok=True)
    with open(os.path.join(project.path, 'hello'), 'w+') as f:
        f.write('world')

    response = await controller_api.get("/projects/{project_id}/files/hello".format(project_id=project.id))
    assert response.status == 200
    assert response.body == b"world"

    response = await controller_api.get("/projects/{project_id}/files/false".format(project_id=project.id))
    assert response.status == 404

    response = await controller_api.get("/projects/{project_id}/files/../hello".format(project_id=project.id))
    assert response.status == 404


async def test_write_file(controller_api, project):

    response = await controller_api.post("/projects/{project_id}/files/hello".format(project_id=project.id), body="world", raw=True)
    assert response.status == 201

    with open(os.path.join(project.path, "hello")) as f:
        assert f.read() == "world"

    response = await controller_api.post("/projects/{project_id}/files/../hello".format(project_id=project.id), raw=True)
    assert response.status == 404


# async def test_write_and_get_file_with_leading_slashes_in_filename(controller_api, project):
#
#     response = await controller_api.post("/projects/{project_id}/files//hello".format(project_id=project.id), body="world", raw=True)
#     assert response.status == 200
#
#     response = await controller_api.get("/projects/{project_id}/files//hello".format(project_id=project.id), raw=True)
#     assert response.status == 200
#     assert response.body == b"world"


async def test_import(controller_api, tmpdir, controller):

    with zipfile.ZipFile(str(tmpdir / "test.zip"), 'w') as myzip:
        myzip.writestr("project.gns3", b'{"project_id": "c6992992-ac72-47dc-833b-54aa334bcd05", "version": "2.0.0", "name": "test"}')
        myzip.writestr("demo", b"hello")

    project_id = str(uuid.uuid4())
    with open(str(tmpdir / "test.zip"), "rb") as f:
        response = await controller_api.post("/projects/{project_id}/import".format(project_id=project_id), body=f.read(), raw=True)
    assert response.status == 201

    project = controller.get_project(project_id)
    with open(os.path.join(project.path, "demo")) as f:
        content = f.read()
    assert content == "hello"


async def test_duplicate(controller_api, project):

    response = await controller_api.post("/projects/{project_id}/duplicate".format(project_id=project.id), {"name": "hello"})
    assert response.status == 201
    assert response.json["name"] == "hello"
