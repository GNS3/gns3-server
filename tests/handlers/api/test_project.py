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

"""
This test suite check /project endpoint
"""

import uuid
import os
import asyncio
import aiohttp
import zipfile

from unittest.mock import patch
from tests.utils import asyncio_patch

from gns3server.handlers.api.project_handler import ProjectHandler
from gns3server.modules.project_manager import ProjectManager


def test_create_project_with_path(server, tmpdir):
    with patch("gns3server.modules.project.Project.is_local", return_value=True):
        response = server.post("/projects", {"name": "test", "path": str(tmpdir)})
        assert response.status == 201
        assert response.json["path"] == str(tmpdir)
        assert response.json["name"] == "test"


def test_create_project_without_dir(server):
    query = {"name": "test"}
    response = server.post("/projects", query, example=True)
    assert response.status == 201
    assert response.json["project_id"] is not None
    assert response.json["temporary"] is False
    assert response.json["name"] == "test"


def test_create_temporary_project(server):
    query = {"name": "test", "temporary": True}
    response = server.post("/projects", query)
    assert response.status == 201
    assert response.json["project_id"] is not None
    assert response.json["temporary"] is True
    assert response.json["name"] == "test"


def test_create_project_with_uuid(server):
    query = {"name": "test", "project_id": "00010203-0405-0607-0809-0a0b0c0d0e0f"}
    response = server.post("/projects", query)
    assert response.status == 201
    assert response.json["project_id"] == "00010203-0405-0607-0809-0a0b0c0d0e0f"
    assert response.json["name"] == "test"


def test_show_project(server):
    query = {"name": "test", "project_id": "00010203-0405-0607-0809-0a0b0c0d0e02", "temporary": False}
    response = server.post("/projects", query)
    assert response.status == 201
    response = server.get("/projects/00010203-0405-0607-0809-0a0b0c0d0e02", example=True)
    assert len(response.json.keys()) == 5
    assert len(response.json["location"]) > 0
    assert response.json["project_id"] == "00010203-0405-0607-0809-0a0b0c0d0e02"
    assert response.json["temporary"] is False
    assert response.json["name"] == "test"


def test_show_project_invalid_uuid(server):
    response = server.get("/projects/00010203-0405-0607-0809-0a0b0c0d0e42")
    assert response.status == 404


def test_list_projects(server):
    ProjectManager.instance()._projects = {}

    query = {"name": "test", "project_id": "00010203-0405-0607-0809-0a0b0c0d0e0f"}
    response = server.post("/projects", query)
    assert response.status == 201
    query = {"name": "test", "project_id": "00010203-0405-0607-0809-0a0b0c0d0e0b"}
    response = server.post("/projects", query)
    assert response.status == 201

    response = server.get("/projects", example=True)
    assert response.status == 200
    print(response.json)
    assert len(response.json) == 2
    assert response.json[0]["project_id"] == "00010203-0405-0607-0809-0a0b0c0d0e0b" or response.json[1]["project_id"] == "00010203-0405-0607-0809-0a0b0c0d0e0b"


def test_update_temporary_project(server):
    query = {"name": "test", "temporary": True}
    response = server.post("/projects", query)
    assert response.status == 201
    query = {"name": "test", "temporary": False}
    response = server.put("/projects/{project_id}".format(project_id=response.json["project_id"]), query, example=True)
    assert response.status == 200
    assert response.json["temporary"] is False


def test_update_path_project_temporary(server, tmpdir):

    os.makedirs(str(tmpdir / "a"))
    os.makedirs(str(tmpdir / "b"))

    with patch("gns3server.modules.project.Project.is_local", return_value=True):
        response = server.post("/projects", {"name": "first_name", "path": str(tmpdir / "a"), "temporary": True})
        assert response.status == 201
        assert response.json["name"] == "first_name"
        query = {"name": "second_name", "path": str(tmpdir / "b")}
        response = server.put("/projects/{project_id}".format(project_id=response.json["project_id"]), query, example=True)
        assert response.status == 200
        assert response.json["path"] == str(tmpdir / "b")
        assert response.json["name"] == "second_name"

        assert not os.path.exists(str(tmpdir / "a"))
        assert os.path.exists(str(tmpdir / "b"))


def test_update_path_project_non_temporary(server, tmpdir):

    os.makedirs(str(tmpdir / "a"))
    os.makedirs(str(tmpdir / "b"))

    with patch("gns3server.modules.project.Project.is_local", return_value=True):
        response = server.post("/projects", {"name": "first_name", "path": str(tmpdir / "a")})
        assert response.status == 201
        assert response.json["name"] == "first_name"
        query = {"name": "second_name", "path": str(tmpdir / "b")}
        response = server.put("/projects/{project_id}".format(project_id=response.json["project_id"]), query, example=True)
        assert response.status == 200
        assert response.json["path"] == str(tmpdir / "b")
        assert response.json["name"] == "second_name"

        assert os.path.exists(str(tmpdir / "a"))
        assert os.path.exists(str(tmpdir / "b"))


def test_update_path_project_non_local(server, tmpdir):

    with patch("gns3server.modules.project.Project.is_local", return_value=False):
        response = server.post("/projects", {"name": "first_name"})
        assert response.status == 201
        query = {"name": "second_name", "path": str(tmpdir)}
        response = server.put("/projects/{project_id}".format(project_id=response.json["project_id"]), query, example=True)
        assert response.status == 403


def test_commit_project(server, project):
    with asyncio_patch("gns3server.modules.project.Project.commit", return_value=True) as mock:
        response = server.post("/projects/{project_id}/commit".format(project_id=project.id), example=True)
    assert response.status == 204
    assert mock.called


def test_commit_project_invalid_uuid(server):
    response = server.post("/projects/{project_id}/commit".format(project_id=uuid.uuid4()))
    assert response.status == 404


def test_delete_project(server, project):
    with asyncio_patch("gns3server.modules.project.Project.delete", return_value=True) as mock:
        response = server.delete("/projects/{project_id}".format(project_id=project.id), example=True)
        assert response.status == 204
        assert mock.called


def test_delete_project_invalid_uuid(server):
    response = server.delete("/projects/{project_id}".format(project_id=uuid.uuid4()))
    assert response.status == 404


def test_close_project(server, project):
    with asyncio_patch("gns3server.modules.project.Project.close", return_value=True) as mock:
        response = server.post("/projects/{project_id}/close".format(project_id=project.id), example=True)
        assert response.status == 204
        assert mock.called


def test_close_project_two_client_connected(server, project):

    ProjectHandler._notifications_listening = {project.id: 2}

    with asyncio_patch("gns3server.modules.project.Project.close", return_value=True) as mock:
        response = server.post("/projects/{project_id}/close".format(project_id=project.id), example=True)
        assert response.status == 204
        assert not mock.called


def test_close_project_invalid_uuid(server):
    response = server.post("/projects/{project_id}/close".format(project_id=uuid.uuid4()))
    assert response.status == 404


def test_notification(server, project, loop):
    @asyncio.coroutine
    def go(future):
        response = yield from aiohttp.request("GET", server.get_url("/projects/{project_id}/notifications".format(project_id=project.id), 1))
        response.body = yield from response.content.read(200)
        project.emit("vm.created", {"a": "b"})
        response.body += yield from response.content.read(50)
        response.close()
        future.set_result(response)

    future = asyncio.Future()
    asyncio.async(go(future))
    response = loop.run_until_complete(future)
    assert response.status == 200
    assert b'"action": "ping"' in response.body
    assert b'"cpu_usage_percent"' in response.body
    assert b'{"action": "vm.created", "event": {"a": "b"}}\n' in response.body


def test_notification_invalid_id(server):
    response = server.get("/projects/{project_id}/notifications".format(project_id=uuid.uuid4()))
    assert response.status == 404


def test_list_files(server, project):
    files = [
        {
            "path": "test.txt",
            "md5sum": "ad0234829205b9033196ba818f7a872b"
        },
        {
            "path": "vm-1/dynamips/test.bin",
            "md5sum": "098f6bcd4621d373cade4e832627b4f6"
        }
    ]
    with asyncio_patch("gns3server.modules.project.Project.list_files", return_value=files) as mock:
        response = server.get("/projects/{project_id}/files".format(project_id=project.id), example=True)
        assert response.status == 200
        assert response.json == files


def test_get_file(server, tmpdir):

    with patch("gns3server.config.Config.get_section_config", return_value={"project_directory": str(tmpdir)}):
        project = ProjectManager.instance().create_project()

    with open(os.path.join(project.path, "hello"), "w+") as f:
        f.write("world")

    response = server.get("/projects/{project_id}/files/hello".format(project_id=project.id), raw=True)
    assert response.status == 200
    assert response.body == b"world"

    response = server.get("/projects/{project_id}/files/false".format(project_id=project.id), raw=True)
    assert response.status == 404

    response = server.get("/projects/{project_id}/files/../hello".format(project_id=project.id), raw=True)
    assert response.status == 403


def test_write_file(server, tmpdir):

    with patch("gns3server.config.Config.get_section_config", return_value={"project_directory": str(tmpdir)}):
        project = ProjectManager.instance().create_project()

    with open(os.path.join(project.path, "hello"), "w+") as f:
        f.write("world")

    response = server.post("/projects/{project_id}/files/hello".format(project_id=project.id), body="universe", raw=True)
    assert response.status == 200

    with open(os.path.join(project.path, "hello")) as f:
        content = f.read()
        assert content == "universe"

    response = server.post("/projects/{project_id}/files/test/false".format(project_id=project.id), body="universe", raw=True)
    assert response.status == 404

    response = server.post("/projects/{project_id}/files/../hello".format(project_id=project.id), body="universe", raw=True)
    assert response.status == 403


def test_export(server, tmpdir, loop, project):

    os.makedirs(project.path, exist_ok=True)
    with open(os.path.join(project.path, 'a'), 'w+') as f:
        f.write('hello')

    response = server.get("/projects/{project_id}/export".format(project_id=project.id), raw=True)
    assert response.status == 200
    assert response.headers['CONTENT-TYPE'] == 'application/gns3project'
    assert response.headers['CONTENT-DISPOSITION'] == 'attachment; filename="{}.gns3project"'.format(project.name)

    with open(str(tmpdir / 'project.zip'), 'wb+') as f:
        f.write(response.body)

    with zipfile.ZipFile(str(tmpdir / 'project.zip')) as myzip:
        with myzip.open("a") as myfile:
            content = myfile.read()
            assert content == b"hello"


def test_import(server, tmpdir, loop, project):

    with zipfile.ZipFile(str(tmpdir / "test.zip"), 'w') as myzip:
        myzip.writestr("demo", b"hello")

    project_id = project.id

    with open(str(tmpdir / "test.zip"), "rb") as f:
        response = server.post("/projects/{project_id}/import".format(project_id=project_id), body=f.read(), raw=True)
    assert response.status == 201

    project = ProjectManager.instance().get_project(project_id=project_id)
    with open(os.path.join(project.path, "demo")) as f:
        content = f.read()
    assert content == "hello"
