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

from unittest.mock import patch
from tests.utils import asyncio_patch

from gns3server.handlers.api.hypervisor.project_handler import ProjectHandler
from gns3server.hypervisor.project_manager import ProjectManager


def test_create_project_with_path(http_hypervisor, tmpdir):
    with patch("gns3server.hypervisor.project.Project.is_local", return_value=True):
        response = http_hypervisor.post("/projects", {"name": "test", "path": str(tmpdir), "project_id": "00010203-0405-0607-0809-0a0b0c0d0e0f"})
        assert response.status == 201
        assert response.json["name"] == "test"
        assert response.json["project_id"] == "00010203-0405-0607-0809-0a0b0c0d0e0f"


def test_create_project_without_dir(http_hypervisor):
    query = {"name": "test", "project_id": "10010203-0405-0607-0809-0a0b0c0d0e0f"}
    response = http_hypervisor.post("/projects", query, example=True)
    assert response.status == 201
    assert response.json["project_id"] == "10010203-0405-0607-0809-0a0b0c0d0e0f"
    assert response.json["temporary"] is False
    assert response.json["name"] == "test"


def test_create_temporary_project(http_hypervisor):
    query = {"name": "test", "temporary": True, "project_id": "20010203-0405-0607-0809-0a0b0c0d0e0f"}
    response = http_hypervisor.post("/projects", query)
    assert response.status == 201
    assert response.json["project_id"] == "20010203-0405-0607-0809-0a0b0c0d0e0f"
    assert response.json["temporary"] is True
    assert response.json["name"] == "test"


def test_create_project_with_uuid(http_hypervisor):
    query = {"name": "test", "project_id": "30010203-0405-0607-0809-0a0b0c0d0e0f"}
    response = http_hypervisor.post("/projects", query)
    assert response.status == 201
    assert response.json["project_id"] == "30010203-0405-0607-0809-0a0b0c0d0e0f"
    assert response.json["name"] == "test"


def test_show_project(http_hypervisor):
    query = {"name": "test", "project_id": "40010203-0405-0607-0809-0a0b0c0d0e02", "temporary": False}
    response = http_hypervisor.post("/projects", query)
    assert response.status == 201
    response = http_hypervisor.get("/projects/40010203-0405-0607-0809-0a0b0c0d0e02", example=True)
    assert len(response.json.keys()) == 3
    assert response.json["project_id"] == "40010203-0405-0607-0809-0a0b0c0d0e02"
    assert response.json["temporary"] is False
    assert response.json["name"] == "test"


def test_show_project_invalid_uuid(http_hypervisor):
    response = http_hypervisor.get("/projects/50010203-0405-0607-0809-0a0b0c0d0e42")
    assert response.status == 404


def test_list_projects(http_hypervisor):
    ProjectManager.instance()._projects = {}

    query = {"name": "test", "project_id": "51010203-0405-0607-0809-0a0b0c0d0e0f"}
    response = http_hypervisor.post("/projects", query)
    assert response.status == 201
    query = {"name": "test", "project_id": "52010203-0405-0607-0809-0a0b0c0d0e0b"}
    response = http_hypervisor.post("/projects", query)
    assert response.status == 201

    response = http_hypervisor.get("/projects", example=True)
    assert response.status == 200
    assert len(response.json) == 2
    assert "51010203-0405-0607-0809-0a0b0c0d0e0f" in [p["project_id"] for p in response.json]


def test_update_temporary_project(http_hypervisor):
    query = {"name": "test", "temporary": True, "project_id": "60010203-0405-0607-0809-0a0b0c0d0e0b"}
    response = http_hypervisor.post("/projects", query)
    assert response.status == 201
    query = {"name": "test", "temporary": False}
    response = http_hypervisor.put("/projects/{project_id}".format(project_id=response.json["project_id"]), query, example=True)
    assert response.status == 200
    assert response.json["temporary"] is False


def test_update_path_project_temporary(http_hypervisor, tmpdir):

    os.makedirs(str(tmpdir / "a"))
    os.makedirs(str(tmpdir / "b"))

    with patch("gns3server.hypervisor.project.Project.is_local", return_value=True):
        response = http_hypervisor.post("/projects", {"name": "first_name", "path": str(tmpdir / "a"), "temporary": True, "project_id": "70010203-0405-0607-0809-0a0b0c0d0e0b"})
        assert response.status == 201
        assert response.json["name"] == "first_name"
        query = {"name": "second_name", "path": str(tmpdir / "b")}
        response = http_hypervisor.put("/projects/{project_id}".format(project_id=response.json["project_id"]), query, example=True)
        assert response.status == 200
        assert response.json["name"] == "second_name"

        assert not os.path.exists(str(tmpdir / "a"))
        assert os.path.exists(str(tmpdir / "b"))


def test_update_path_project_non_temporary(http_hypervisor, tmpdir):

    os.makedirs(str(tmpdir / "a"))
    os.makedirs(str(tmpdir / "b"))

    with patch("gns3server.hypervisor.project.Project.is_local", return_value=True):
        response = http_hypervisor.post("/projects", {"name": "first_name", "path": str(tmpdir / "a"), "project_id": "80010203-0405-0607-0809-0a0b0c0d0e0b"})
        assert response.status == 201
        assert response.json["name"] == "first_name"
        query = {"name": "second_name", "path": str(tmpdir / "b")}
        response = http_hypervisor.put("/projects/{project_id}".format(project_id=response.json["project_id"]), query, example=True)
        assert response.status == 200
        assert response.json["name"] == "second_name"

        assert os.path.exists(str(tmpdir / "a"))
        assert os.path.exists(str(tmpdir / "b"))


def test_update_path_project_non_local(http_hypervisor, tmpdir):

    with patch("gns3server.hypervisor.project.Project.is_local", return_value=False):
        response = http_hypervisor.post("/projects", {"name": "first_name", "project_id": "90010203-0405-0607-0809-0a0b0c0d0e0b"})
        assert response.status == 201
        query = {"name": "second_name", "path": str(tmpdir)}
        response = http_hypervisor.put("/projects/{project_id}".format(project_id=response.json["project_id"]), query, example=True)
        assert response.status == 403


def test_commit_project(http_hypervisor, project):
    with asyncio_patch("gns3server.hypervisor.project.Project.commit", return_value=True) as mock:
        response = http_hypervisor.post("/projects/{project_id}/commit".format(project_id=project.id), example=True)
    assert response.status == 204
    assert mock.called


def test_commit_project_invalid_uuid(http_hypervisor):
    response = http_hypervisor.post("/projects/{project_id}/commit".format(project_id=uuid.uuid4()))
    assert response.status == 404


def test_delete_project(http_hypervisor, project):
    with asyncio_patch("gns3server.hypervisor.project.Project.delete", return_value=True) as mock:
        response = http_hypervisor.delete("/projects/{project_id}".format(project_id=project.id), example=True)
        assert response.status == 204
        assert mock.called


def test_delete_project_invalid_uuid(http_hypervisor):
    response = http_hypervisor.delete("/projects/{project_id}".format(project_id=uuid.uuid4()))
    assert response.status == 404


def test_close_project(http_hypervisor, project):
    with asyncio_patch("gns3server.hypervisor.project.Project.close", return_value=True) as mock:
        response = http_hypervisor.post("/projects/{project_id}/close".format(project_id=project.id), example=True)
        assert response.status == 204
        assert mock.called


def test_close_project_two_client_connected(http_hypervisor, project):

    ProjectHandler._notifications_listening = {project.id: 2}

    with asyncio_patch("gns3server.hypervisor.project.Project.close", return_value=True) as mock:
        response = http_hypervisor.post("/projects/{project_id}/close".format(project_id=project.id), example=True)
        assert response.status == 204
        assert not mock.called


def test_close_project_invalid_uuid(http_hypervisor):
    response = http_hypervisor.post("/projects/{project_id}/close".format(project_id=uuid.uuid4()))
    assert response.status == 404


def test_notification(http_hypervisor, project, loop):
    @asyncio.coroutine
    def go(future):
        response = yield from aiohttp.request("GET", http_hypervisor.get_url("/projects/{project_id}/notifications".format(project_id=project.id)))
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


def test_notification_invalid_id(http_hypervisor):
    response = http_hypervisor.get("/projects/{project_id}/notifications".format(project_id=uuid.uuid4()))
    assert response.status == 404


def test_list_files(http_hypervisor, project):
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
    with asyncio_patch("gns3server.hypervisor.project.Project.list_files", return_value=files) as mock:
        response = http_hypervisor.get("/projects/{project_id}/files".format(project_id=project.id), example=True)
        assert response.status == 200
        assert response.json == files


def test_get_file(http_hypervisor, tmpdir):

    with patch("gns3server.config.Config.get_section_config", return_value={"project_directory": str(tmpdir)}):
        project = ProjectManager.instance().create_project(project_id="01010203-0405-0607-0809-0a0b0c0d0e0b")

    with open(os.path.join(project.path, "hello"), "w+") as f:
        f.write("world")

    response = http_hypervisor.get("/projects/{project_id}/files/hello".format(project_id=project.id), raw=True)
    assert response.status == 200
    assert response.body == b"world"

    response = http_hypervisor.get("/projects/{project_id}/files/false".format(project_id=project.id), raw=True)
    assert response.status == 404

    response = http_hypervisor.get("/projects/{project_id}/files/../hello".format(project_id=project.id), raw=True)
    assert response.status == 403
